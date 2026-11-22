package uz.amora.app.data

import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlin.coroutines.resume
import kotlin.math.roundToLong
import kotlin.random.Random
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.Call
import okhttp3.Callback
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response

/** Serverdan kelgan jonli xabar: ilova shunga qarab kerakli ma'lumotni o'zi qayta o'qiydi. */
sealed interface LiveEvent {
    /**
     * Ulanish (qayta) o'rnatildi yoki ba'zi xabarlar o'tkazib yuborilgan bo'lishi mumkin:
     * ekrandagi hamma narsa qayta o'qiladi.
     */
    data object Resync : LiveEvent

    /** Taom qo'shildi, o'zgardi, tugadi yoki o'chirildi. */
    data object MenuChanged : LiveEvent

    /** Kafe sozlamalari o'zgardi: ish vaqti, yetkazish narxi, buyurtma qabul qilish. */
    data object ShopChanged : LiveEvent

    /** Mijozning buyurtmasi boshqa holatga o'tdi. */
    data class OrderChanged(
        val orderId: Int,
        val status: String,
        val statusLabel: String = "",
        val rejectReason: String? = null,
    ) : LiveEvent
}

/** Server-Sent Events oqimidagi bitta xabar: nomi va matni. */
data class SseMessage(val name: String, val data: String)

/**
 * SSE oqimini satrma-satr o'qiydi. Xabar bo'sh satr bilan tugaydi; ":" bilan boshlangan
 * satr izoh (server aloqa tirikligini bildirish uchun yuboradigan "ping").
 */
class SseParser {
    private var name: String? = null
    private val data = StringBuilder()
    private var hasData = false

    /** Satrni qabul qiladi. Shu satr bilan xabar tugagan bo'lsa, uni qaytaradi. */
    fun feed(line: String): SseMessage? {
        if (line.isEmpty()) {
            val message = if (hasData) SseMessage(name ?: "message", data.toString()) else null
            name = null
            data.setLength(0)
            hasData = false
            return message
        }
        if (line.startsWith(":")) return null
        val colon = line.indexOf(':')
        val field = if (colon < 0) line else line.substring(0, colon)
        val value = if (colon < 0) "" else line.substring(colon + 1).removePrefix(" ")
        when (field) {
            "event" -> name = value
            "data" -> {
                if (hasData) data.append('\n')
                data.append(value)
                hasData = true
            }
        }
        return null
    }
}

@Serializable
private data class OrderEventBody(
    @SerialName("order_id") val orderId: Int,
    val status: String,
    @SerialName("status_label") val statusLabel: String = "",
    @SerialName("reject_reason") val rejectReason: String? = null,
)

private val liveJson = Json {
    ignoreUnknownKeys = true
    coerceInputValues = true
}

/** Server xabarini ilova tushunadigan hodisaga aylantiradi. Notanish xabar bo'lsa null. */
fun parseLiveEvent(message: SseMessage): LiveEvent? = when (message.name) {
    "ready", "resync" -> LiveEvent.Resync
    "menu" -> LiveEvent.MenuChanged
    "shop" -> LiveEvent.ShopChanged
    "order" -> try {
        val body = liveJson.decodeFromString(OrderEventBody.serializer(), message.data)
        LiveEvent.OrderChanged(body.orderId, body.status, body.statusLabel, body.rejectReason)
    } catch (e: IllegalArgumentException) {
        null
    }

    else -> null
}

// Ketma-ket muvaffaqiyatsiz urinishlardan keyin kutish vaqti
private val RETRY_DELAYS_MS = longArrayOf(1_000, 2_000, 5_000, 10_000, 20_000, 30_000)
private const val RETRY_JITTER = 0.3

// Ulanish shuncha vaqt yashagan bo'lsa, u barqaror hisoblanadi
const val STABLE_CONNECTION_MS = 5_000L

/**
 * Qayta ulanishdan oldingi kutish vaqti. Server qayta ishga tushganda hamma telefon bir lahzada
 * qayta ulanmasligi uchun vaqt ±30% ga tasodifiy suriladi. [random]: 0 dan 1 gacha son.
 */
fun retryDelayMs(failures: Int, random: Double): Long {
    val base = RETRY_DELAYS_MS[failures.coerceIn(0, RETRY_DELAYS_MS.lastIndex)]
    // Yaxlitlab qo'shiladi: kasr sonlar xatosi (0.7 * 1000 = 699.99...) natijani bir millisekundga surmasin
    return base + (base * RETRY_JITTER * (2 * random.coerceIn(0.0, 1.0) - 1)).roundToLong()
}

/**
 * Navbatdagi urinishdan keyingi muvaffaqiyatsizliklar soni. Hisob faqat ulanish bir necha
 * soniya yashagandan keyin nolga tushadi: ulanib, darhol uzilib turadigan aloqada ilova
 * serverni har soniyada bezovta qilmaydi. [livedMs]: ulanish qancha yashagani (ulanmagan bo'lsa null).
 */
fun nextFailures(failures: Int, livedMs: Long?): Int =
    if (livedMs != null && livedMs >= STABLE_CONNECTION_MS) 0 else failures + 1

/**
 * Server bilan doimiy ulanish (`GET /api/v1/events`). Ilova ochiq turganda ushlab turiladi:
 * serverda nimadir o'zgarsa, xabar shu ulanish orqali darhol keladi. Aloqa uzilsa, o'zi
 * qayta ulanadi; server bu imkoniyatni bilmasa (eski versiya), ilova avvalgidek vaqti-vaqti
 * bilan so'rab turaveradi.
 */
class Realtime(
    baseUrl: String,
    private val tokenProvider: () -> String?,
    private val scope: CoroutineScope,
) {
    private val url = baseUrl.trimEnd('/') + "/api/v1/events"

    // Server har 20 soniyada "ping" yuboradi: 45 soniya jimlik ulanish o'lganini bildiradi
    private val http = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(45, TimeUnit.SECONDS)
        .build()

    private val _events = MutableSharedFlow<LiveEvent>(
        extraBufferCapacity = 64,
        onBufferOverflow = BufferOverflow.DROP_OLDEST,
    )
    val events: SharedFlow<LiveEvent> = _events.asSharedFlow()

    private val _connected = MutableStateFlow(false)

    /** Ulanish hozir tirikmi. Tirik bo'lmasa, ekranlar serverdan tez-tez o'zi so'rab turadi. */
    val connected: StateFlow<Boolean> = _connected.asStateFlow()

    private var job: Job? = null

    val isRunning: Boolean get() = job?.isActive == true

    fun start() {
        if (isRunning) return
        job = scope.launch { runForever() }
    }

    fun stop() {
        job?.cancel()
        job = null
        _connected.value = false
    }

    /** Kirish kaliti o'zgarganda: buyurtma xabarlari yangi kalit egasiga kelishi kerak. */
    fun restart() {
        if (!isRunning) return
        stop()
        start()
    }

    private suspend fun runForever() {
        var failures = 0
        while (true) {
            val livedMs = connectOnce()
            _connected.value = false
            failures = nextFailures(failures, livedMs)
            delay(retryDelayMs(failures, Random.nextDouble()))
        }
    }

    /**
     * Bir marta ulanadi va uzilguncha xabarlarni o'qiydi. Ulanish o'rnatilgan bo'lsa, u qancha
     * yashaganini (millisekund) qaytaradi, aks holda null.
     */
    private suspend fun connectOnce(): Long? = suspendCancellableCoroutine { continuation ->
        val builder = Request.Builder()
            .url(url)
            .header("Accept", "text/event-stream")
            .header("Cache-Control", "no-cache")
        val token = tokenProvider()
        if (!token.isNullOrEmpty()) builder.header("Authorization", "Bearer $token")
        val call = http.newCall(builder.build())
        continuation.invokeOnCancellation { call.cancel() }
        call.enqueue(
            object : Callback {
                override fun onFailure(call: Call, e: IOException) {
                    if (continuation.isActive) continuation.resume(null)
                }

                override fun onResponse(call: Call, response: Response) {
                    var readyAt: Long? = null
                    try {
                        response.use {
                            val source = it.body?.source()
                            if (it.isSuccessful && source != null) {
                                val parser = SseParser()
                                while (true) {
                                    val line = source.readUtf8Line() ?: break
                                    val message = parser.feed(line) ?: continue
                                    if (message.name == "ready" && continuation.isActive) {
                                        if (readyAt == null) readyAt = System.nanoTime()
                                        _connected.value = true
                                    }
                                    parseLiveEvent(message)?.let { event -> _events.tryEmit(event) }
                                }
                            }
                        }
                    } catch (e: IOException) {
                        // Aloqa uzildi yoki ulanish bekor qilindi: tashqaridagi sikl qayta ulanadi
                    }
                    val livedMs = readyAt?.let { (System.nanoTime() - it) / 1_000_000 }
                    if (continuation.isActive) continuation.resume(livedMs)
                }
            },
        )
    }
}
