package uz.amora.app.data

import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.serialization.DeserializationStrategy
import kotlinx.serialization.json.Json
import okhttp3.Call
import okhttp3.Callback
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response

/**
 * Serverdan kelgan xato. `message` o'zbekcha va mijozga to'g'ridan-to'g'ri ko'rsatiladi,
 * `code` esa ilova ichidagi shartlar uchun (masalan "shop_closed", "price_changed").
 */
class ApiException(
    val status: Int,
    val code: String,
    override val message: String,
    val total: Int? = null,
) : Exception(message) {
    val isNetwork: Boolean get() = code == CODE_NETWORK
    val isUnauthorized: Boolean get() = status == 401
    val isNotFound: Boolean get() = status == 404

    companion object {
        const val CODE_NETWORK = "network"
        const val CODE_BAD_RESPONSE = "bad_response"
    }
}

/**
 * Amora serveri bilan aloqa. Barcha manzillar `/api/v1` ostida.
 *
 * `onUnauthorized`: server so'rov bilan yuborilgan kirish kalitini tanimadi (401). Qaysi so'rov
 * bo'lishidan qat'i nazar shu bitta joydan xabar beriladi; yuborilgan kalit ham beriladi, chunki
 * javob kelguncha telefonda yangi kalit saqlangan bo'lishi mumkin.
 */
class ApiClient(
    baseUrl: String,
    private val tokenProvider: () -> String?,
    private val onUnauthorized: (tokenUsed: String) -> Unit = {},
) {
    private val apiUrl = baseUrl.trimEnd('/') + "/api/v1"

    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
        coerceInputValues = true
    }

    private val http = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .writeTimeout(20, TimeUnit.SECONDS)
        .build()

    // ---------- Menyu ----------

    suspend fun menu(): Menu = call("GET", "/menu", Menu.serializer())

    suspend fun shop(): Shop = call("GET", "/shop", Shop.serializer())

    // ---------- Mijoz ----------

    // Kirish kaliti bo'lsa yuboriladi: shu telefondagi eski buyurtmalar tasdiqlangan hisobga o'tadi
    suspend fun startTelegramVerification(name: String?): TelegramStart = call(
        "POST",
        "/auth/telegram",
        TelegramStart.serializer(),
        body = json.encodeToString(TelegramStartIn.serializer(), TelegramStartIn(name = name)),
        auth = true,
    )

    suspend fun checkTelegramVerification(code: String): TelegramCheck = call(
        "POST",
        "/auth/telegram/check",
        TelegramCheck.serializer(),
        body = json.encodeToString(TelegramCheckIn.serializer(), TelegramCheckIn(code)),
    )

    suspend fun me(): Customer = call("GET", "/me", Customer.serializer(), auth = true)

    suspend fun updateName(name: String): Customer = call(
        "PATCH",
        "/me",
        Customer.serializer(),
        body = json.encodeToString(CustomerUpdate.serializer(), CustomerUpdate(name = name)),
        auth = true,
    )

    /** Hisobdan chiqish: server shu telefonning kirish kalitini bekor qiladi. */
    suspend fun logout() {
        request("POST", "/auth/logout", body = "", auth = true)
    }

    /** Hisobni o'chirish. Tugallanmagan buyurtma bo'lsa, server 409 (`has_active_orders`) qaytaradi. */
    suspend fun deleteAccount() {
        request("DELETE", "/me", auth = true)
    }

    suspend fun updatePushToken(token: String): Customer = call(
        "PATCH",
        "/me",
        Customer.serializer(),
        body = json.encodeToString(PushTokenUpdate.serializer(), PushTokenUpdate(token)),
        auth = true,
    )

    // ---------- Buyurtma ----------

    // Token bo'lsa yuboriladi: server mijozning oldingi buyurtmalarini ko'rib, birinchi buyurtma
    // chegirmasini va promokodni to'g'ri hisoblaydi. Tokensiz ham ishlaydi.
    suspend fun quote(
        items: List<CartItemIn>,
        latitude: Double?,
        longitude: Double?,
        promoCode: String? = null,
        phone: String? = null,
    ): Quote = call(
        "POST",
        "/orders/quote",
        Quote.serializer(),
        body = json.encodeToString(
            QuoteIn.serializer(),
            QuoteIn(items, latitude, longitude, promoCode = promoCode, phone = phone),
        ),
        auth = true,
    )

    // Bu so'rov ekran yopilganda ham bekor qilinmaydi: buyurtma serverga yetib borgan bo'lsa,
    // javobi ham albatta o'qilishi kerak (aks holda mijoz uni ikkinchi marta yuboradi)
    suspend fun createOrder(order: OrderIn): Order = withContext(NonCancellable) {
        call(
            "POST",
            "/orders",
            Order.serializer(),
            body = json.encodeToString(OrderIn.serializer(), order),
            auth = true,
            cancellable = false,
        )
    }

    suspend fun orders(limit: Int = 20, offset: Int = 0): OrderList = call(
        "GET",
        "/orders?limit=$limit&offset=$offset",
        OrderList.serializer(),
        auth = true,
    )

    suspend fun order(id: Int): Order = call("GET", "/orders/$id", Order.serializer(), auth = true)

    suspend fun cancelOrder(id: Int): Order =
        call("POST", "/orders/$id/cancel", Order.serializer(), body = "", auth = true)

    // ---------- Ichki qism ----------

    private suspend fun <T> call(
        method: String,
        path: String,
        serializer: DeserializationStrategy<T>,
        body: String? = null,
        auth: Boolean = false,
        cancellable: Boolean = true,
    ): T {
        val text = request(method, path, body, auth, cancellable)
        // Katta javobni (menyu) o'qish asosiy oqimni band qilmasin
        return withContext(Dispatchers.Default) {
            try {
                json.decodeFromString(serializer, text)
            } catch (e: IllegalArgumentException) {
                throw ApiException(
                    200,
                    ApiException.CODE_BAD_RESPONSE,
                    "Serverdan tushunarsiz javob keldi. Birozdan keyin qayta urinib ko'ring",
                )
            }
        }
    }

    /** So'rovni yuboradi va muvaffaqiyatli javob matnini qaytaradi. Xato bo'lsa [ApiException]. */
    private suspend fun request(
        method: String,
        path: String,
        body: String? = null,
        auth: Boolean = false,
        cancellable: Boolean = true,
    ): String {
        val builder = Request.Builder()
            .url(apiUrl + path)
            .header("Accept", "application/json")
        val token = if (auth) tokenProvider()?.takeIf { it.isNotEmpty() } else null
        if (token != null) builder.header("Authorization", "Bearer $token")
        when {
            method == "GET" -> builder.get()
            method == "DELETE" && body == null -> builder.delete()
            else -> builder.method(method, (body ?: "").toRequestBody(JSON_MEDIA_TYPE))
        }

        val (status, text) = execute(http.newCall(builder.build()), cancellable)
        if (status in 200..299) return text
        if (status == 401 && token != null) onUnauthorized(token)
        throw parseError(status, text)
    }

    /**
     * Javobni kutadi. So'rovni kutayotgan ish bekor qilinsa (ekran yopildi), tarmoq so'rovi ham
     * to'xtatiladi; `cancellable = false` bo'lsa, so'rov oxirigacha boradi.
     */
    private suspend fun execute(call: Call, cancellable: Boolean): Pair<Int, String> =
        suspendCancellableCoroutine { continuation ->
            if (cancellable) continuation.invokeOnCancellation { call.cancel() }
            call.enqueue(
                object : Callback {
                    override fun onFailure(call: Call, e: IOException) {
                        if (continuation.isActive) continuation.resumeWithException(networkError())
                    }

                    override fun onResponse(call: Call, response: Response) {
                        val result = try {
                            response.use { Pair(it.code, it.body?.string() ?: "") }
                        } catch (e: IOException) {
                            if (continuation.isActive) continuation.resumeWithException(networkError())
                            return
                        }
                        if (continuation.isActive) continuation.resume(result)
                    }
                },
            )
        }

    private fun networkError() = ApiException(
        0,
        ApiException.CODE_NETWORK,
        "Internet bilan aloqa yo'q. Tarmoqni tekshirib, qayta urinib ko'ring",
    )

    private fun parseError(status: Int, text: String): ApiException {
        val info = try {
            json.decodeFromString(ApiErrorBody.serializer(), text).error
        } catch (e: IllegalArgumentException) {
            null
        }
        val message = info?.message?.takeIf { it.isNotBlank() }
            ?: "Serverda xatolik yuz berdi ($status). Birozdan keyin qayta urinib ko'ring"
        return ApiException(status, info?.code ?: "error", message, info?.total)
    }

    private companion object {
        val JSON_MEDIA_TYPE = "application/json; charset=utf-8".toMediaType()
    }
}

/**
 * Rasm manzilini ilova ishlatayotgan server manziliga moslaydi.
 * Serverda tashqi manzil noto'g'ri sozlangan bo'lsa ham rasmlar ochilaveradi.
 */
fun resolveImageUrl(baseUrl: String, imageUrl: String?): String? {
    if (imageUrl.isNullOrBlank()) return null
    val index = imageUrl.indexOf("/media/")
    return if (index >= 0) baseUrl.trimEnd('/') + imageUrl.substring(index) else imageUrl
}
