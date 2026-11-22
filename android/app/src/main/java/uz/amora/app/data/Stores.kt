package uz.amora.app.data

import android.content.Context
import android.content.SharedPreferences
import java.security.MessageDigest
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

/**
 * Telegram orqali tasdiqlash boshlangan, lekin hali tugamagan: mijoz Telegramga o'tgan paytda
 * tizim ilovani yopib qo'ysa ham, qaytganda tekshirish shu yerdan davom etadi.
 * `expiresAt`: kod eskiradigan vaqt (telefon soati bo'yicha, millisekund).
 */
data class PendingVerification(
    val code: String,
    val appUrl: String,
    val botUrl: String,
    val expiresAt: Long,
)

/** Telefonda saqlanadigan ma'lumotlar: kirish kaliti (token), profil va oxirgi manzil. */
class SessionStore(context: Context) {
    private val prefs: SharedPreferences =
        context.applicationContext.getSharedPreferences("amora_session", Context.MODE_PRIVATE)

    // Profildan oldin o'qiladi: "tasdiqlangan" belgisi kalit bor-yo'qligiga ham bog'liq
    private val _tokenFlow = MutableStateFlow(readToken())

    private val _profile = MutableStateFlow(readProfile())
    val profile: StateFlow<Profile?> = _profile.asStateFlow()

    private val _address = MutableStateFlow(readAddress())
    val address: StateFlow<Address?> = _address.asStateFlow()

    /** Kirish kaliti o'zgarganda jonli ulanish yangi kalit bilan qayta o'rnatiladi. */
    val tokenFlow: StateFlow<String?> = _tokenFlow.asStateFlow()

    val token: String?
        get() = _tokenFlow.value

    /**
     * Kalit xotiraga faqat shifrlangan holda yoziladi. Shifrlab bo'lmasa (telefonning Keystore'i
     * ishlamayapti), kalit shu ishga tushirish davomidagina ishlaydi va xotiraga yozilmaydi.
     */
    fun saveToken(token: String?) {
        val editor = prefs.edit().remove(KEY_TOKEN_PLAIN)
        val encrypted = token?.let { TokenCipher.encrypt(it) }
        if (encrypted == null) editor.remove(KEY_TOKEN) else editor.putString(KEY_TOKEN, encrypted)
        editor.apply()
        _tokenFlow.value = token
    }

    /**
     * Saqlangan kalitni o'qiydi. Ilovaning eski versiyasi uni ochiq matn qilib yozgan: u birinchi
     * o'qishda shifrlab qayta yoziladi. Shifrni ochib bo'lmasa, telefon hisobdan chiqqan hisoblanadi.
     */
    private fun readToken(): String? {
        val legacy = prefs.getString(KEY_TOKEN_PLAIN, null)
        if (legacy != null) {
            val editor = prefs.edit().remove(KEY_TOKEN_PLAIN)
                // Eski versiya bu yerga ham kalitni ochiq matnda yozgan
                .remove(KEY_PUSH_SENT_WITH)
            TokenCipher.encrypt(legacy)?.let { editor.putString(KEY_TOKEN, it) }
            editor.apply()
            return legacy
        }
        val stored = prefs.getString(KEY_TOKEN, null) ?: return null
        val token = TokenCipher.decrypt(stored)
        if (token == null) prefs.edit().remove(KEY_TOKEN).apply()
        return token
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

    /**
     * Hisobdan chiqish yoki hisobni o'chirish: kalit va profil telefondan butunlay o'chadi
     * (ism va raqam ham). Manzil alohida: [clearAddress].
     */
    fun clearAccount() {
        prefs.edit()
            .remove(KEY_NAME)
            .remove(KEY_PHONE)
            .remove(KEY_PHONE_VERIFIED)
            .remove(KEY_PUSH_SENT_WITH)
            .apply()
        pendingVerification = null
        _profile.value = null
        saveToken(null)
    }

    fun clearAddress() {
        prefs.edit().remove(KEY_LATITUDE).remove(KEY_LONGITUDE).remove(KEY_NOTE).apply()
        _address.value = null
    }

    /** Tugallanmagan Telegram tasdiqlashi (yo'q bo'lsa null). */
    var pendingVerification: PendingVerification?
        get() {
            val code = prefs.getString(KEY_VERIFY_CODE, null) ?: return null
            return PendingVerification(
                code = code,
                appUrl = prefs.getString(KEY_VERIFY_APP_URL, null) ?: "",
                botUrl = prefs.getString(KEY_VERIFY_BOT_URL, null) ?: "",
                expiresAt = prefs.getLong(KEY_VERIFY_EXPIRES_AT, 0L),
            )
        }
        set(value) {
            val editor = prefs.edit()
            if (value == null) {
                editor.remove(KEY_VERIFY_CODE)
                    .remove(KEY_VERIFY_APP_URL)
                    .remove(KEY_VERIFY_BOT_URL)
                    .remove(KEY_VERIFY_EXPIRES_AT)
            } else {
                editor.putString(KEY_VERIFY_CODE, value.code)
                    .putString(KEY_VERIFY_APP_URL, value.appUrl)
                    .putString(KEY_VERIFY_BOT_URL, value.botUrl)
                    .putLong(KEY_VERIFY_EXPIRES_AT, value.expiresAt)
            }
            editor.apply()
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
        val verified = prefs.getBoolean(KEY_PHONE_VERIFIED, false) && _tokenFlow.value != null
        return Profile(name, phone, verified)
    }

    private fun readAddress(): Address? {
        val latitude = prefs.getString(KEY_LATITUDE, null)?.toDoubleOrNull()
        val longitude = prefs.getString(KEY_LONGITUDE, null)?.toDoubleOrNull()
        if (latitude == null || longitude == null) return null
        return Address(latitude, longitude, prefs.getString(KEY_NOTE, null) ?: "")
    }

    private companion object {
        // Eski versiyalardagi ochiq matnli kalit: birinchi o'qishda shifrlangani bilan almashtiriladi
        const val KEY_TOKEN_PLAIN = "token"
        const val KEY_TOKEN = "token_enc"
        const val KEY_NAME = "name"
        const val KEY_PHONE = "phone"
        const val KEY_PHONE_VERIFIED = "phone_verified"
        const val KEY_LATITUDE = "latitude"
        const val KEY_LONGITUDE = "longitude"
        const val KEY_NOTE = "address_note"
        const val KEY_NOTIFICATIONS_ASKED = "notifications_asked"
        const val KEY_PUSH_TOKEN = "push_token"
        const val KEY_PUSH_SENT_WITH = "push_token_sent_with"
        const val KEY_VERIFY_CODE = "verify_code"
        const val KEY_VERIFY_APP_URL = "verify_app_url"
        const val KEY_VERIFY_BOT_URL = "verify_bot_url"
        const val KEY_VERIFY_EXPIRES_AT = "verify_expires_at"
    }
}

/** Matnning SHA-256 izi (o'n oltilik): maxfiy qiymatni o'zini saqlamasdan solishtirish uchun. */
fun sha256Hex(text: String): String =
    MessageDigest.getInstance("SHA-256").digest(text.toByteArray(Charsets.UTF_8))
        .joinToString("") { "%02x".format(it) }

/**
 * Yuborilayotgan buyurtmaning kaliti (`client_order_id`) va u qaysi buyurtmaga tegishli ekani
 * (`fingerprint`: savat, manzil, izoh va promokod izi).
 */
data class PendingOrder(val clientOrderId: String, val fingerprint: String)

/**
 * Buyurtma tarkibining izi. Taomlar raqami bo'yicha tartiblanadi: savat telefondan qayta o'qilganda
 * tartibi boshqacha chiqsa ham, o'sha buyurtmaning izi o'zgarmaydi (kalit ham o'sha qoladi).
 */
fun orderFingerprint(items: Map<Int, Int>, address: Address, comment: String, phone: String, promo: String?): String =
    "${items.toSortedMap()}|$address|$comment|$phone|$promo"

/**
 * Buyurtma qaysi kalit bilan yuboriladi. Tarkibi o'zgarmagan buyurtma (javobi yo'qolgan, qayta
 * yuborilmoqda) avvalgi kalitni oladi: server uni ikkinchi marta yaratmaydi. Savat, manzil, izoh
 * yoki promokod o'zgargan bo'lsa, bu boshqa buyurtma: kalit ham yangi.
 */
fun orderKeyFor(pending: PendingOrder?, fingerprint: String, newId: () -> String): PendingOrder =
    if (pending != null && pending.fingerprint == fingerprint) pending else PendingOrder(newId(), fingerprint)

/**
 * Server buyurtmani aniq rad etdimi (4xx): bunday javobdan keyin buyurtma yaratilmagani ma'lum va
 * kalit o'chiriladi. Tarmoq xatosi, 5xx yoki tushunarsiz javobda buyurtma yaratilgan bo'lishi
 * mumkin: kalit saqlanib qoladi va qayta yuborishda o'sha kalit ishlatiladi.
 */
fun isDefinitiveRejection(status: Int): Boolean = status in 400..499 && status != 408

/**
 * Savat: taom raqami -> soni. Ilova yopilsa ham saqlanib qoladi. Izoh, promokod va yuborilayotgan
 * buyurtmaning kaliti ham shu yerda: ular savat bo'shaganda birga o'chadi.
 */
class CartStore(context: Context) {
    private val prefs: SharedPreferences =
        context.applicationContext.getSharedPreferences("amora_cart", Context.MODE_PRIVATE)

    private val _items = MutableStateFlow(decodeCart(prefs.getString(KEY_ITEMS, null)))
    val items: StateFlow<Map<Int, Int>> = _items.asStateFlow()

    /** Kafe uchun izoh: mijoz yozib bo'lgach ilova yopilib qolsa ham yo'qolmaydi. */
    var comment: String
        get() = prefs.getString(KEY_COMMENT, null) ?: ""
        set(value) = prefs.edit().putString(KEY_COMMENT, value).apply()

    /** Mijoz "Qo'llash" ni bosgan promokod. */
    var promo: String?
        get() = prefs.getString(KEY_PROMO, null)
        set(value) = prefs.edit().putString(KEY_PROMO, value).apply()

    /**
     * Yuborilgan, lekin natijasi hali aniq bo'lmagan buyurtma. Darhol diskka yoziladi (commit):
     * so'rov ketgan zahoti ilova yopilib qolsa ham keyingi urinish o'sha kalit bilan ketadi.
     */
    var pendingOrder: PendingOrder?
        get() {
            val id = prefs.getString(KEY_PENDING_ID, null) ?: return null
            val fingerprint = prefs.getString(KEY_PENDING_FINGERPRINT, null) ?: return null
            return PendingOrder(id, fingerprint)
        }
        set(value) {
            val editor = prefs.edit()
            if (value == null) {
                editor.remove(KEY_PENDING_ID).remove(KEY_PENDING_FINGERPRINT)
            } else {
                editor.putString(KEY_PENDING_ID, value.clientOrderId)
                    .putString(KEY_PENDING_FINGERPRINT, value.fingerprint)
            }
            editor.commit()
        }

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
        val editor = prefs.edit().putString(KEY_ITEMS, encodeCart(next))
        if (next.isEmpty()) {
            // Bo'sh savat: izoh, promokod va eski buyurtma kaliti keyingi buyurtmaga o'tib ketmasin
            editor.remove(KEY_COMMENT).remove(KEY_PROMO).remove(KEY_PENDING_ID).remove(KEY_PENDING_FINGERPRINT)
        }
        editor.apply()
    }

    companion object {
        const val MAX_QUANTITY = 50
        private const val KEY_ITEMS = "items"
        private const val KEY_COMMENT = "comment"
        private const val KEY_PROMO = "promo"
        private const val KEY_PENDING_ID = "pending_order_id"
        private const val KEY_PENDING_FINGERPRINT = "pending_order_fingerprint"
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

    private val refreshLock = Mutex()
    private var requested = 0L
    private var completed = 0L

    /**
     * Faol buyurtmalarni serverdan qayta o'qiydi. Bir vaqtda bir nechta chaqiruv kelsa (ekran,
     * jonli xabar, push), ular navbat bilan bajariladi: kechikkan eski javob yangisining ustiga
     * yozilib qolmaydi (xuddi [Catalog.refresh] kabi).
     */
    suspend fun refresh() {
        val wanted = ++requested
        refreshLock.withLock {
            if (completed >= wanted) return
            val covers = requested
            val sent = session.token
            if (sent == null) {
                _orders.value = emptyList()
            } else {
                val before = _orders.value
                try {
                    val latest = api.orders(limit = 5).orders
                    // Javob kelguncha mijoz hisobdan chiqqan yoki boshqa hisobga kirgan bo'lishi mumkin
                    if (session.token == sent) {
                        _orders.value = latest.filter { it.isActive }
                        changedOrders(before, latest).forEach { _statusChanges.tryEmit(it) }
                    }
                } catch (e: ApiException) {
                    // 401: kalit bekor bo'lgan (hisobdan chiqarish ApiClient ichida bir joyda qilinadi)
                    if (e.isUnauthorized) _orders.value = emptyList()
                }
            }
            completed = covers
        }
    }

    /** Hisobdan chiqildi: avvalgi hisobning buyurtmalari ko'rinmaydi. */
    fun clear() {
        _orders.value = emptyList()
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

    /** Bu kod endi kutilmayapti: mijoz bekor qilgan yoki yangisini boshlagan. */
    data object Cancelled : VerificationResult
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
    private val verifyLock = Mutex()

    // Shu ishga tushirishda tasdiqlangan oxirgi kod: ikkinchi marta so'ralsa, serverga bormaydi
    private var verifiedCode: String? = null

    /**
     * Ismni o'zgartiradi (raqam faqat Telegram orqali almashadi). Avval serverga yuboriladi va
     * faqat u qabul qilgach telefonda saqlanadi. Saqlanmasa, mijozga ko'rsatiladigan xato matni
     * qaytadi (null: saqlandi). Ekran yopilsa ham so'rov oxirigacha boradi.
     */
    suspend fun saveName(name: String): String? = scope.async {
        val profile = session.profile.value ?: return@async null
        val sent = session.token
        if (sent == null) {
            // Hisob hali ochilmagan: ism tasdiqlash paytida serverga ketadi
            session.saveProfile(profile.copy(name = name))
            return@async null
        }
        try {
            val customer = api.updateName(name)
            // Javob kelguncha boshqa hisobga kirilgan bo'lsa, uning profiliga tegilmaydi
            if (session.token == sent) {
                session.saveProfile(Profile(customer.name, customer.phone, verified = customer.phoneVerified))
            }
            null
        } catch (e: ApiException) {
            if (e.isUnauthorized) NOT_VERIFIED_AGAIN_MESSAGE else e.message
        }
    }.await()

    fun refreshInBackground() {
        scope.launch { refresh() }
    }

    /** Tasdiqlashni boshlaydi. Kod va eskirish vaqti saqlanadi: ilova yopilsa ham davom ettiriladi. */
    suspend fun startVerification(name: String?): PendingVerification {
        val started = api.startTelegramVerification(name)
        val pending = PendingVerification(
            code = started.code,
            appUrl = started.appUrl,
            botUrl = started.botUrl,
            expiresAt = System.currentTimeMillis() + started.expiresIn * 1000L,
        )
        session.pendingVerification = pending
        return pending
    }

    /** Hali eskirmagan tugallanmagan tasdiqlash (yo'q yoki eskirgan bo'lsa null). */
    fun pendingVerification(): PendingVerification? {
        val pending = session.pendingVerification ?: return null
        val left = pending.expiresAt - System.currentTimeMillis()
        // Telefon soati o'zgartirilgan bo'lsa ham kod cheksiz kutilmaydi
        if (left <= 0 || left > MAX_VERIFICATION_MS) {
            session.pendingVerification = null
            return null
        }
        return pending
    }

    fun cancelVerification() {
        session.pendingVerification = null
    }

    /**
     * Ilova ekranga qaytdi: profil ekrani ochiq bo'lmasa ham (masalan tizim ilovani yopib,
     * qayta ochgan) tugallanmagan tasdiqlash bir marta tekshiriladi.
     */
    fun checkPendingVerificationInBackground() {
        val pending = pendingVerification() ?: return
        scope.launch {
            try {
                checkVerification(pending.code)
            } catch (e: ApiException) {
                // Profil ekrani ochilganda xato o'sha yerda ko'rsatiladi
            }
        }
    }

    /**
     * Mijoz botda raqamini yubordimi. Yuborgan bo'lsa, kalit va profil saqlanadi. Bir kod bir
     * vaqtda ikki joydan so'ralsa (ekran va ilovaga qaytish), so'rovlar navbat bilan ketadi.
     */
    suspend fun checkVerification(code: String): VerificationResult = verifyLock.withLock {
        if (session.pendingVerification?.code != code) {
            val profile = session.profile.value
            return if (code == verifiedCode && profile != null) {
                VerificationResult.Verified(profile)
            } else {
                VerificationResult.Cancelled
            }
        }
        val result = try {
            api.checkTelegramVerification(code)
        } catch (e: ApiException) {
            // Kod eskirgan yoki server uni tanimadi: uni kutishning hojati yo'q
            if (!e.isNetwork && e.status in 400..499) session.pendingVerification = null
            throw e
        }
        val token = result.token
        val customer = result.customer
        if (result.status != "verified" || token == null || customer == null) {
            return VerificationResult.Pending
        }
        val profile = Profile(customer.name, customer.phone, verified = customer.phoneVerified)
        session.saveProfile(profile)
        session.saveToken(token)
        verifiedCode = code
        session.pendingVerification = null
        return VerificationResult.Verified(profile)
    }

    /**
     * Serverdagi profil bilan solishtiradi: boshqa telefonda ism o'zgargan bo'lishi yoki bu
     * telefon hisobdan chiqarilgan bo'lishi mumkin (masalan eski hisob tasdiqlangan hisobga qo'shildi).
     */
    suspend fun refresh() {
        val sent = session.token ?: return
        try {
            val customer = api.me()
            // Javob kelguncha raqam tasdiqlanib, yangi kalit va profil saqlangan bo'lishi mumkin
            if (session.token != sent) return
            session.saveProfile(Profile(customer.name, customer.phone, verified = customer.phoneVerified))
        } catch (e: ApiException) {
            // 401 bo'lsa, telefon hisobdan ApiClient ichida (bir joyda) chiqariladi
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
                // Telefon hisobdan ApiClient ichida (bir joyda) chiqariladi
                e.isUnauthorized -> throw ApiException(401, CODE_NOT_VERIFIED, NOT_VERIFIED_MESSAGE)
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
        const val NOT_VERIFIED_AGAIN_MESSAGE = "Raqamingizni Telegram orqali qayta tasdiqlang"
        private const val MAX_VERIFICATION_MS = 30 * 60 * 1000L
    }
}
