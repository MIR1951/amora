package uz.amora.app.ui.cart

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
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
import uz.amora.app.data.orderFingerprint
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
    // Ko'rsatilayotgan summa qaysi kod bilan hisoblangan: yangi kod tekshirilguncha eski
    // natija uning ostida ko'rinmasin
    val quotePromo: String? = null,
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
    // Izoh va promokod savat bilan birga telefonda saqlanadi: tizim ilovani yopib qo'ysa ham yo'qolmaydi
    private val _state = MutableStateFlow(
        CartUiState(
            comment = container.cart.comment,
            promoInput = container.cart.promo ?: "",
            appliedPromo = container.cart.promo,
        ),
    )
    val state: StateFlow<CartUiState> = _state.asStateFlow()

    // Qiymati o'zgarsa, summa serverdan qayta so'raladi
    private val refreshTick = MutableStateFlow(0)
    private val appliedPromo = MutableStateFlow(container.cart.promo)

    init {
        // Avvalgi buyurtma mijoz savatdan chiqib ketgandan keyin yaratilgan: u bosh sahifada
        // ko'rinib turibdi, savat qayta ochilganda o'sha buyurtmaga o'tib ketilmaydi
        if (!container.orders.state.value.submitting) container.orders.consumeCreatedOrder()
        // Buyurtma ilova darajasida yuboriladi (ekran yopilsa ham tugaydi): natijasi shu yerda ko'rsatiladi
        viewModelScope.launch {
            container.orders.state.collect { submit ->
                _state.update {
                    it.copy(
                        submitting = submit.submitting,
                        submitError = submit.error?.message,
                        createdOrderId = submit.createdOrderId,
                    )
                }
                // Narx yoki taom holati o'zgargan bo'lishi mumkin: summani qayta so'raymiz
                if (submit.error?.isNetwork == false) refreshQuote()
            }
        }
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
                    // Savat bo'shadi (buyurtma berildi yoki tozalandi): izoh va promokod ham o'chadi
                    appliedPromo.value = null
                    _state.update {
                        it.copy(
                            quote = null,
                            quoteLoading = false,
                            quoteError = null,
                            comment = "",
                            promoInput = "",
                            appliedPromo = null,
                        )
                    }
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
                container.session.profile.value?.phone,
            )
            _state.update {
                it.copy(quote = quote, quotePromo = request.promo, quoteLoading = false, quoteError = null)
            }
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
        container.cart.promo = code
        _state.update { it.copy(appliedPromo = code) }
        appliedPromo.value = code
    }

    fun removePromo() {
        container.cart.promo = null
        _state.update { it.copy(appliedPromo = null, promoInput = "") }
        appliedPromo.value = null
    }

    fun setComment(comment: String) {
        val text = comment.take(MAX_COMMENT_LENGTH)
        container.cart.comment = text
        _state.update { it.copy(comment = text) }
    }

    fun clearSubmitError() {
        container.orders.clearError()
    }

    fun consumeCreatedOrder() {
        container.orders.consumeCreatedOrder()
    }

    fun submit() {
        val current = _state.value
        if (current.submitting) return
        val items = container.cart.items.value
        val address = container.session.address.value
        val profile = container.session.profile.value
        val quote = current.quote
        if (items.isEmpty() || address == null || profile == null || !profile.verified || quote == null) return
        // Yangi kiritilgan kod hali tekshirilmagan: summa boshqacha bo'lishi mumkin
        if (current.quotePromo != current.appliedPromo) return

        val comment = current.comment.trim()
        // Ishlamagan kod buyurtmaga yuborilmaydi: mijoz sababini ko'rgan, summa usiz hisoblangan
        val promo = current.appliedPromo?.takeIf { quote.promoError == null }
        // Bitta buyurtma uchun bitta kalit: internet uzilib qayta yuborilsa, buyurtma ikkilanmaydi.
        // Savat, manzil, izoh yoki promokod o'zgarsa, bu endi boshqa buyurtma: kalit ham yangilanadi.
        val fingerprint = orderFingerprint(items, address, comment, profile.phone, promo)
        val order = OrderIn(
            items = items.toCartItems(),
            latitude = address.latitude,
            longitude = address.longitude,
            addressNote = address.note,
            comment = comment,
            name = profile.name,
            phone = profile.phone,
            expectedTotal = quote.total,
            promoCode = promo,
        )
        container.orders.submit(order, fingerprint)
    }

    private companion object {
        const val QUOTE_DEBOUNCE_MS = 300L
        const val MAX_COMMENT_LENGTH = 500
        const val MAX_PROMO_LENGTH = 20
    }
}
