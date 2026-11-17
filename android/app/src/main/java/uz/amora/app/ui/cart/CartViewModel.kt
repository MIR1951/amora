package uz.amora.app.ui.cart

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import java.util.UUID
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import uz.amora.app.AppContainer
import uz.amora.app.data.Address
import uz.amora.app.data.ApiException
import uz.amora.app.data.LiveEvent
import uz.amora.app.data.OrderIn
import uz.amora.app.data.Quote
import uz.amora.app.data.toCartItems

data class CartUiState(
    // Server hisoblagan summa. Savat o'zgarganda qayta so'raladi.
    val quote: Quote? = null,
    val quoteLoading: Boolean = false,
    val quoteError: String? = null,
    val comment: String = "",
    // Mijoz yozayotgan promokod va "Qo'llash" bosilgandan keyin serverga yuborilgani
    val promoInput: String = "",
    val appliedPromo: String? = null,
    val submitting: Boolean = false,
    val submitError: String? = null,
    val createdOrderId: Int? = null,
)

private data class QuoteRequest(
    val items: Map<Int, Int>,
    val address: Address?,
    val promo: String?,
    val tick: Int,
)

class CartViewModel(private val container: AppContainer) : ViewModel() {
    private val _state = MutableStateFlow(CartUiState())
    val state: StateFlow<CartUiState> = _state.asStateFlow()

    // Qiymati o'zgarsa, summa serverdan qayta so'raladi
    private val refreshTick = MutableStateFlow(0)
    private val appliedPromo = MutableStateFlow<String?>(null)

    // Bitta buyurtma uchun bitta kalit: internet uzilib qayta yuborilsa, buyurtma ikkilanmaydi.
    // Savat, manzil yoki izoh o'zgarsa, bu endi boshqa buyurtma: kalit ham yangilanadi.
    private var clientOrderId = UUID.randomUUID().toString()
    private var orderFingerprint = ""

    init {
        viewModelScope.launch {
            combine(
                container.cart.items,
                container.session.address,
                appliedPromo,
                refreshTick,
            ) { items, address, promo, tick ->
                QuoteRequest(items, address, promo, tick)
            }.collectLatest { request ->
                if (request.items.isEmpty()) {
                    _state.update { it.copy(quote = null, quoteLoading = false, quoteError = null) }
                    return@collectLatest
                }
                _state.update { it.copy(quoteLoading = true) }
                delay(QUOTE_DEBOUNCE_MS) // tugma ketma-ket bosilganda faqat oxirgi holat so'raladi
                loadQuote(request)
            }
        }
        // Savat ochiq turganda menyu yoki kafe sozlamalari o'zgarsa (taom tugadi, narx o'zgardi,
        // kafe yopildi, aksiya o'zgardi), summa va ogohlantirishlar serverdan qayta so'raladi
        viewModelScope.launch {
            container.realtime.events.collect { event ->
                if (event !is LiveEvent.OrderChanged) refreshQuote()
            }
        }
        // Ro'yxatdan o'tgach (yoki raqam o'zgargach) birinchi buyurtma chegirmasi qayta tekshiriladi
        viewModelScope.launch {
            container.session.profile.collect { refreshQuote() }
        }
    }

    private suspend fun loadQuote(request: QuoteRequest) {
        try {
            val quote = container.api.quote(
                request.items.toCartItems(),
                request.address?.latitude,
                request.address?.longitude,
                request.promo,
            )
            _state.update { it.copy(quote = quote, quoteLoading = false, quoteError = null) }
        } catch (e: ApiException) {
            _state.update { it.copy(quoteLoading = false, quoteError = e.message) }
        }
    }

    fun refreshQuote() {
        refreshTick.update { it + 1 }
    }

    fun setPromoInput(value: String) {
        val cleaned = value.filter { it.isLetterOrDigit() || it == '-' || it == '_' }
            .uppercase()
            .take(MAX_PROMO_LENGTH)
        _state.update { it.copy(promoInput = cleaned) }
    }

    fun applyPromo() {
        val code = _state.value.promoInput.trim()
        if (code.isEmpty()) return
        _state.update { it.copy(appliedPromo = code) }
        appliedPromo.value = code
    }

    fun removePromo() {
        _state.update { it.copy(appliedPromo = null, promoInput = "") }
        appliedPromo.value = null
    }

    fun setComment(comment: String) {
        _state.update { it.copy(comment = comment.take(MAX_COMMENT_LENGTH)) }
    }

    fun clearSubmitError() {
        _state.update { it.copy(submitError = null) }
    }

    fun consumeCreatedOrder() {
        _state.update { it.copy(createdOrderId = null) }
    }

    fun submit() {
        val current = _state.value
        if (current.submitting) return
        val items = container.cart.items.value
        val address = container.session.address.value
        val profile = container.session.profile.value
        val quote = current.quote
        if (items.isEmpty() || address == null || profile == null || quote == null) return

        val comment = current.comment.trim()
        // Ishlamagan kod buyurtmaga yuborilmaydi: mijoz sababini ko'rgan, summa usiz hisoblangan
        val promo = current.appliedPromo?.takeIf { quote.promoError == null }
        val fingerprint = "$items|$address|$comment|${profile.phone}|$promo"
        if (fingerprint != orderFingerprint) {
            orderFingerprint = fingerprint
            clientOrderId = UUID.randomUUID().toString()
        }
        val order = OrderIn(
            items = items.toCartItems(),
            latitude = address.latitude,
            longitude = address.longitude,
            addressNote = address.note,
            comment = comment,
            name = profile.name,
            phone = profile.phone,
            clientOrderId = clientOrderId,
            expectedTotal = quote.total,
            promoCode = promo,
        )

        _state.update { it.copy(submitting = true, submitError = null) }
        viewModelScope.launch {
            try {
                val created = container.account.withAuth { container.api.createOrder(order) }
                orderFingerprint = ""
                container.cart.clear()
                // Yangi buyurtma darhol "faol buyurtmalar"ga qo'shiladi: bosh sahifadagi belgi va
                // bildirishnomalar shunga tayanadi
                container.live.orderPlaced()
                appliedPromo.value = null
                _state.update {
                    it.copy(
                        submitting = false,
                        comment = "",
                        promoInput = "",
                        appliedPromo = null,
                        createdOrderId = created.id,
                    )
                }
            } catch (e: ApiException) {
                _state.update { it.copy(submitting = false, submitError = e.message) }
                // Narx yoki taom holati o'zgargan bo'lishi mumkin: summani qayta so'raymiz
                if (!e.isNetwork) refreshQuote()
            }
        }
    }

    private companion object {
        const val QUOTE_DEBOUNCE_MS = 300L
        const val MAX_COMMENT_LENGTH = 500
        const val MAX_PROMO_LENGTH = 20
    }
}
