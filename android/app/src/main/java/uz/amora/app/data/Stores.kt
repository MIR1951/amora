package uz.amora.app.data

import android.content.Context
import android.content.SharedPreferences
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/**
 * Mijozning ismi va telefoni. Telefon har doim `+998XXXXXXXXX` ko'rinishida.
 * `verified`: raqam Telegram orqali tasdiqlangan. Ilovaning eski versiyasida qo'lda yozilgan
 * raqam tasdiqlanmagan bo'ladi: buyurtma berishdan oldin tasdiqlash kerak.
 */
data class Profile(val name: String, val phone: String, val verified: Boolean = false)

/** Yetkazish manzili: xaritadagi nuqta va mo'ljal. */
data class Address(val latitude: Double, val longitude: Double, val note: String)

/** Telefonda saqlanadigan ma'lumotlar: kirish kaliti (token), profil va oxirgi manzil. */
class SessionStore(context: Context) {
    private val prefs: SharedPreferences =
        context.applicationContext.getSharedPreferences("amora_session", Context.MODE_PRIVATE)

    private val _profile = MutableStateFlow(readProfile())
    val profile: StateFlow<Profile?> = _profile.asStateFlow()

    private val _address = MutableStateFlow(readAddress())
    val address: StateFlow<Address?> = _address.asStateFlow()

    private val _tokenFlow = MutableStateFlow(prefs.getString(KEY_TOKEN, null))

    /** Kirish kaliti o'zgarganda jonli ulanish yangi kalit bilan qayta o'rnatiladi. */
    val tokenFlow: StateFlow<String?> = _tokenFlow.asStateFlow()

    val token: String?
        get() = _tokenFlow.value

    fun saveToken(token: String?) {
        val editor = prefs.edit()
        if (token == null) editor.remove(KEY_TOKEN) else editor.putString(KEY_TOKEN, token)
        editor.apply()
        _tokenFlow.value = token
    }

    /** Bildirishnomaga ruxsat bir marta so'ralgan: mijoz rad etsa, qayta-qayta bezovta qilinmaydi. */
    var notificationsAsked: Boolean
        get() = prefs.getBoolean(KEY_NOTIFICATIONS_ASKED, false)
        set(value) = prefs.edit().putBoolean(KEY_NOTIFICATIONS_ASKED, value).apply()

    /** Firebase bergan qurilma manzili va u qaysi kirish kaliti bilan serverga yuborilgani. */
    var pushToken: String?
        get() = prefs.getString(KEY_PUSH_TOKEN, null)
        set(value) = prefs.edit().putString(KEY_PUSH_TOKEN, value).apply()

    var pushTokenSentWith: String?
        get() = prefs.getString(KEY_PUSH_SENT_WITH, null)
        set(value) = prefs.edit().putString(KEY_PUSH_SENT_WITH, value).apply()

    fun saveProfile(profile: Profile) {
        prefs.edit()
            .putString(KEY_NAME, profile.name)
            .putString(KEY_PHONE, profile.phone)
            .putBoolean(KEY_PHONE_VERIFIED, profile.verified)
            .apply()
        _profile.value = profile
    }

    /** Server kirish kalitini tanimadi: telefon hisobdan chiqdi, raqamni qayta tasdiqlash kerak. */
    fun signOut() {
        saveToken(null)
        _profile.value?.let { saveProfile(it.copy(verified = false)) }
    }

    fun saveAddress(address: Address) {
        prefs.edit()
            .putString(KEY_LATITUDE, address.latitude.toString())
            .putString(KEY_LONGITUDE, address.longitude.toString())
            .putString(KEY_NOTE, address.note)
            .apply()
        _address.value = address
    }

    private fun readProfile(): Profile? {
        val name = prefs.getString(KEY_NAME, null)
        val phone = prefs.getString(KEY_PHONE, null)
        if (name.isNullOrBlank() || phone.isNullOrBlank()) return null
        val verified = prefs.getBoolean(KEY_PHONE_VERIFIED, false) && prefs.getString(KEY_TOKEN, null) != null
        return Profile(name, phone, verified)
    }

    private fun readAddress(): Address? {
        val latitude = prefs.getString(KEY_LATITUDE, null)?.toDoubleOrNull()
        val longitude = prefs.getString(KEY_LONGITUDE, null)?.toDoubleOrNull()
        if (latitude == null || longitude == null) return null
        return Address(latitude, longitude, prefs.getString(KEY_NOTE, null) ?: "")
    }

    private companion object {
        const val KEY_TOKEN = "token"
        const val KEY_NAME = "name"
        const val KEY_PHONE = "phone"
        const val KEY_PHONE_VERIFIED = "phone_verified"
        const val KEY_LATITUDE = "latitude"
        const val KEY_LONGITUDE = "longitude"
        const val KEY_NOTE = "address_note"
        const val KEY_NOTIFICATIONS_ASKED = "notifications_asked"
        const val KEY_PUSH_TOKEN = "push_token"
        const val KEY_PUSH_SENT_WITH = "push_token_sent_with"
    }
}

/** Savat: taom raqami -> soni. Ilova yopilsa ham saqlanib qoladi. */
class CartStore(context: Context) {
    private val prefs: SharedPreferences =
        context.applicationContext.getSharedPreferences("amora_cart", Context.MODE_PRIVATE)

    private val _items = MutableStateFlow(decodeCart(prefs.getString(KEY_ITEMS, null)))
    val items: StateFlow<Map<Int, Int>> = _items.asStateFlow()

    fun quantity(productId: Int): Int = _items.value[productId] ?: 0

    fun add(productId: Int) = set(productId, quantity(productId) + 1)

    fun remove(productId: Int) = set(productId, quantity(productId) - 1)

    fun set(productId: Int, quantity: Int) {
        val next = LinkedHashMap(_items.value)
        if (quantity <= 0) next.remove(productId) else next[productId] = quantity.coerceAtMost(MAX_QUANTITY)
        publish(next)
    }

    fun replace(items: Map<Int, Int>) {
        val next = LinkedHashMap<Int, Int>()
        for ((productId, quantity) in items) {
            if (quantity > 0) next[productId] = quantity.coerceAtMost(MAX_QUANTITY)
        }
        publish(next)
    }

    /** Menyudan olib tashlangan taomlarni savatdan ham chiqaradi. */
    fun retain(productIds: Set<Int>) {
        val current = _items.value
        if (current.keys.all { it in productIds }) return
        publish(LinkedHashMap(current.filterKeys { it in productIds }))
    }

    fun clear() = publish(LinkedHashMap())

    private fun publish(next: Map<Int, Int>) {
        _items.value = next
        prefs.edit().putString(KEY_ITEMS, encodeCart(next)).apply()
    }

    companion object {
        const val MAX_QUANTITY = 50
        private const val KEY_ITEMS = "items"
    }
}

fun encodeCart(items: Map<Int, Int>): String =
    items.entries.joinToString(";") { "${it.key}:${it.value}" }

fun decodeCart(text: String?): Map<Int, Int> {
    val result = LinkedHashMap<Int, Int>()
    if (text.isNullOrBlank()) return result
    for (part in text.split(";")) {
        val pieces = part.split(":")
        if (pieces.size != 2) continue
        val productId = pieces[0].toIntOrNull() ?: continue
        val quantity = pieces[1].toIntOrNull() ?: continue
        if (productId > 0 && quantity > 0) result[productId] = quantity.coerceAtMost(CartStore.MAX_QUANTITY)
    }
    return result
}

fun Map<Int, Int>.toCartItems(): List<CartItemIn> = map { CartItemIn(it.key, it.value) }

data class CatalogState(
    val loading: Boolean = false,
    val error: String? = null,
    val shop: Shop? = null,
    val menu: Menu? = null,
)

/** Menyu va kafe ma'lumotlari: bir marta yuklanadi va barcha ekranlarda ishlatiladi. */
class Catalog(private val api: ApiClient) {
    private val _state = MutableStateFlow(CatalogState(loading = true))
    val state: StateFlow<CatalogState> = _state.asStateFlow()

    private val refreshLock = Mutex()
    private var requested = 0L
    private var completed = 0L

    /**
     * Menyu va kafe ma'lumotini serverdan qayta o'qiydi.
     *
     * Bir vaqtda bir nechta so'rov kelsa (ekran ochildi, jonli xabar keldi), ular navbat bilan
     * bajariladi va ortiqchasi tashlab yuboriladi: har bir chaqiruv o'zidan KEYIN boshlangan
     * o'qish tugashini kutadi, shuning uchun eskirgan ma'lumot ustiga yozilib qolmaydi.
     */
    suspend fun refresh(showLoading: Boolean = false) {
        val wanted = ++requested
        if (showLoading || _state.value.menu == null) {
            _state.update { it.copy(loading = true, error = null) }
        }
        refreshLock.withLock {
            if (completed >= wanted) return
            val covers = requested
            try {
                coroutineScope {
                    val shop = async { api.shop() }
                    val menu = async { api.menu() }
                    _state.value = CatalogState(shop = shop.await(), menu = menu.await())
                }
            } catch (e: ApiException) {
                // Avval yuklangan menyu bo'lsa, u ekranda qolaveradi
                _state.update { it.copy(loading = false, error = e.message) }
            }
            completed = covers
        }
    }
}

/** Mijozning tugallanmagan buyurtmalari: bosh sahifadagi belgi va bildirishnomalar shunga tayanadi. */
class ActiveOrders(private val api: ApiClient, private val session: SessionStore) {
    private val _orders = MutableStateFlow<List<Order>>(emptyList())
    val orders: StateFlow<List<Order>> = _orders.asStateFlow()

    private val _statusChanges = MutableSharedFlow<Order>(
        extraBufferCapacity = 16,
        onBufferOverflow = BufferOverflow.DROP_OLDEST,
    )

    /**
     * Kuzatilayotgan (faol) buyurtma boshqa holatga o'tgani qayta o'qishda aniqlandi. Jonli ulanish
     * uzilib turgan paytda o'tkazib yuborilgan o'zgarishlar ham shu yerdan chiqadi.
     */
    val statusChanges: SharedFlow<Order> = _statusChanges.asSharedFlow()

    suspend fun refresh() {
        if (session.token == null) {
            _orders.value = emptyList()
            return
        }
        val before = _orders.value
        try {
            val latest = api.orders(limit = 5).orders
            _orders.value = latest.filter { it.isActive }
            changedOrders(before, latest).forEach { _statusChanges.tryEmit(it) }
        } catch (e: ApiException) {
            if (e.isUnauthorized) _orders.value = emptyList()
        }
    }
}

/** Avval faol bo'lgan buyurtmalardan qaysilari boshqa holatga o'tgan (tugaganlari ham). */
fun changedOrders(before: List<Order>, latest: List<Order>): List<Order> {
    val known = before.associate { it.id to it.status }
    return latest.filter { order -> known[order.id].let { it != null && it != order.status } }
}

/** Telegram orqali tasdiqlash natijasi. */
sealed interface VerificationResult {
    data object Pending : VerificationResult

    data class Verified(val profile: Profile) : VerificationResult
}

/**
 * Hisob va profil. Mijoz raqamini Telegram orqali tasdiqlaydi: ilova botni ochadi, mijoz u yerda
 * "📱 Raqamni yuborish" ni bosadi, ilova natijani so'rab turadi. Bitta raqam = bitta hisob:
 * boshqa telefondan kirsa ham eski buyurtmalari chiqadi.
 */
class Account(
    private val api: ApiClient,
    private val session: SessionStore,
    private val scope: CoroutineScope,
) {
    /** Ismni o'zgartiradi (raqam faqat Telegram orqali almashadi). */
    fun saveName(name: String) {
        val profile = session.profile.value ?: return
        session.saveProfile(profile.copy(name = name))
        if (session.token == null) return
        scope.launch {
            try {
                api.updateName(name)
            } catch (e: ApiException) {
                // Muhim emas: ism har bir buyurtma bilan birga ham yuboriladi
                if (e.isUnauthorized) session.signOut()
            }
        }
    }

    fun refreshInBackground() {
        scope.launch { refresh() }
    }

    suspend fun startVerification(name: String?): TelegramStart = api.startTelegramVerification(name)

    /** Mijoz botda raqamini yubordimi. Yuborgan bo'lsa, kalit va profil saqlanadi. */
    suspend fun checkVerification(code: String): VerificationResult {
        val result = api.checkTelegramVerification(code)
        val token = result.token
        val customer = result.customer
        if (result.status != "verified" || token == null || customer == null) {
            return VerificationResult.Pending
        }
        val profile = Profile(customer.name, customer.phone, verified = customer.phoneVerified)
        session.saveProfile(profile)
        session.saveToken(token)
        return VerificationResult.Verified(profile)
    }

    /**
     * Serverdagi profil bilan solishtiradi: boshqa telefonda ism o'zgargan bo'lishi yoki bu
     * telefon hisobdan chiqarilgan bo'lishi mumkin (masalan eski hisob tasdiqlangan hisobga qo'shildi).
     */
    suspend fun refresh() {
        if (session.token == null) return
        try {
            val customer = api.me()
            session.saveProfile(Profile(customer.name, customer.phone, verified = customer.phoneVerified))
        } catch (e: ApiException) {
            if (e.isUnauthorized) session.signOut()
        }
    }

    /**
     * Kirish kaliti kerak bo'lgan so'rovni bajaradi. Raqam tasdiqlanmagan yoki server kalitni
     * tanimasa, mijozga raqamni tasdiqlashni aytadigan xato chiqadi.
     */
    suspend fun <T> withAuth(block: suspend () -> T): T {
        if (session.token == null || session.profile.value?.verified != true) {
            throw ApiException(403, CODE_NOT_VERIFIED, NOT_VERIFIED_MESSAGE)
        }
        return try {
            block()
        } catch (e: ApiException) {
            when {
                e.isUnauthorized -> {
                    session.signOut()
                    throw ApiException(401, CODE_NOT_VERIFIED, NOT_VERIFIED_MESSAGE)
                }
                e.code == CODE_NOT_VERIFIED -> {
                    session.signOut()
                    throw e
                }
                else -> throw e
            }
        }
    }

    companion object {
        const val CODE_NOT_VERIFIED = "phone_not_verified"
        const val NOT_VERIFIED_MESSAGE = "Buyurtma berish uchun raqamingizni Telegram orqali tasdiqlang"
    }
}
