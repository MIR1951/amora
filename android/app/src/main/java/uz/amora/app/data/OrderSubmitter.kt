package uz.amora.app.data

import java.util.UUID
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class SubmitState(
    val submitting: Boolean = false,
    val error: ApiException? = null,
    val createdOrderId: Int? = null,
)

/**
 * Buyurtmani serverga yuboradi. Yuborish ekranga emas, ilovaga bog'langan: mijoz savatdan chiqib
 * ketsa ham so'rov oxirigacha boradi, savat tozalanadi va buyurtma faol buyurtmalar qatoriga tushadi.
 *
 * Har bir buyurtma bitta kalit (`client_order_id`) bilan ketadi va u telefonda saqlanadi: javob
 * yo'qolsa (internet uzildi, ilova yopildi), qayta yuborishda o'sha kalit ishlatiladi va server
 * buyurtmani ikkinchi marta yaratmaydi.
 */
class OrderSubmitter(
    private val api: ApiClient,
    private val account: Account,
    private val cart: CartStore,
    private val activeOrders: ActiveOrders,
    private val live: LiveUpdates,
    private val scope: CoroutineScope,
) {
    private val _state = MutableStateFlow(SubmitState())
    val state: StateFlow<SubmitState> = _state.asStateFlow()

    /**
     * [draft]: kalitsiz buyurtma. [fingerprint]: uning tarkibi izi (savat, manzil, izoh, promokod):
     * o'zgarmagan bo'lsa, avvalgi urinishning kaliti qayta ishlatiladi.
     */
    fun submit(draft: OrderIn, fingerprint: String) {
        if (_state.value.submitting) return
        val pending = orderKeyFor(cart.pendingOrder, fingerprint) { UUID.randomUUID().toString() }
        // So'rov ketishidan OLDIN saqlanadi: javobi kelmay qolsa ham kalit yo'qolmaydi
        cart.pendingOrder = pending
        val order = draft.copy(clientOrderId = pending.clientOrderId)
        _state.value = SubmitState(submitting = true)
        scope.launch {
            try {
                val created = account.withAuth { api.createOrder(order) }
                finish(created.id)
            } catch (e: ApiException) {
                if (isDefinitiveRejection(e.status)) {
                    // Server aniq rad etdi: buyurtma yaratilmagan, kalit endi kerak emas
                    if (cart.pendingOrder == pending) cart.pendingOrder = null
                    _state.value = SubmitState(error = e)
                    return@launch
                }
                // Javob kelmadi yoki tushunarsiz: buyurtma serverga yetib borgan bo'lishi mumkin.
                // Qayta urinishga ruxsat berishdan oldin faol buyurtmalar tekshiriladi
                activeOrders.refresh()
                val existing = activeOrders.orders.value.firstOrNull { it.clientOrderId == pending.clientOrderId }
                if (existing != null) finish(existing.id) else _state.value = SubmitState(error = e)
            }
        }
    }

    private fun finish(orderId: Int) {
        // Savat bo'shaganda izoh, promokod va kalit ham birga o'chadi
        cart.clear()
        // Yangi buyurtma darhol "faol buyurtmalar"ga qo'shiladi: bosh sahifadagi belgi va
        // bildirishnomalar shunga tayanadi
        live.orderPlaced()
        _state.value = SubmitState(createdOrderId = orderId)
    }

    fun clearError() {
        _state.update { it.copy(error = null) }
    }

    /** Savat ekrani yangi buyurtma ekraniga o'tdi (yoki natija endi kerak emas). */
    fun consumeCreatedOrder() {
        _state.update { it.copy(createdOrderId = null) }
    }
}
