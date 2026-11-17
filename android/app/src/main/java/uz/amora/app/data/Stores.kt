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

/** Mijozning ismi va telefoni. Telefon har doim `+998XXXXXXXXX` ko'rinishida. */
data class Profile(val name: String, val phone: String)

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
            .apply()
        _profile.value = profile
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
        return if (name.isNullOrBlank() || phone.isNullOrBlank()) null else Profile(name, phone)
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

/** Ro'yxatdan o'tish va profil. Mijoz birinchi buyurtma paytida ro'yxatdan o'tadi. */
class Account(
    private val api: ApiClient,
    private val session: SessionStore,
    private val scope: CoroutineScope,
) {
    /** Profilni telefonda saqlaydi. Mijoz ro'yxatdan o'tgan bo'lsa, serverdagi profil ham yangilanadi. */
    fun saveProfile(name: String, phone: String) {
        session.saveProfile(Profile(name, phone))
        if (session.token == null) return
        scope.launch {
            try {
                api.updateMe(name, phone)
            } catch (e: ApiException) {
                // Muhim emas: ism va telefon har bir buyurtma bilan birga yuboriladi.
                if (e.isUnauthorized) session.saveToken(null)
            }
        }
    }

    /**
     * Kirish kaliti kerak bo'lgan so'rovni bajaradi. Kalit hali yo'q yoki eskirgan bo'lsa,
     * saqlangan ism va telefon bilan ro'yxatdan o'tib, so'rovni qayta yuboradi.
     */
    suspend fun <T> withAuth(block: suspend () -> T): T {
        if (session.token == null) register()
        return try {
            block()
        } catch (e: ApiException) {
            if (!e.isUnauthorized) throw e
            register()
            block()
        }
    }

    private suspend fun register() {
        val profile = session.profile.value
            ?: throw ApiException(401, "unauthorized", "Avval ism va telefon raqamingizni kiriting")
        val result = api.register(profile.name, profile.phone)
        session.saveToken(result.token)
    }
}
