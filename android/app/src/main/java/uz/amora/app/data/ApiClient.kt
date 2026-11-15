package uz.amora.app.data

import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.DeserializationStrategy
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

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

    companion object {
        const val CODE_NETWORK = "network"
        const val CODE_BAD_RESPONSE = "bad_response"
    }
}

/** Amora serveri bilan aloqa. Barcha manzillar `/api/v1` ostida. */
class ApiClient(
    baseUrl: String,
    private val tokenProvider: () -> String?,
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

    suspend fun register(name: String, phone: String): RegisterOut = call(
        "POST",
        "/auth/register",
        RegisterOut.serializer(),
        body = json.encodeToString(RegisterIn.serializer(), RegisterIn(name = name, phone = phone)),
    )

    suspend fun updateMe(name: String, phone: String): Customer = call(
        "PATCH",
        "/me",
        Customer.serializer(),
        body = json.encodeToString(CustomerUpdate.serializer(), CustomerUpdate(name = name, phone = phone)),
        auth = true,
    )

    // ---------- Buyurtma ----------

    suspend fun quote(items: List<CartItemIn>, latitude: Double?, longitude: Double?): Quote = call(
        "POST",
        "/orders/quote",
        Quote.serializer(),
        body = json.encodeToString(QuoteIn.serializer(), QuoteIn(items, latitude, longitude)),
    )

    suspend fun createOrder(order: OrderIn): Order = call(
        "POST",
        "/orders",
        Order.serializer(),
        body = json.encodeToString(OrderIn.serializer(), order),
        auth = true,
    )

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
    ): T = withContext(Dispatchers.IO) {
        val builder = Request.Builder()
            .url(apiUrl + path)
            .header("Accept", "application/json")
        if (auth) {
            val token = tokenProvider()
            if (!token.isNullOrEmpty()) builder.header("Authorization", "Bearer $token")
        }
        if (method == "GET") {
            builder.get()
        } else {
            builder.method(method, (body ?: "").toRequestBody(JSON_MEDIA_TYPE))
        }

        val (status, text) = try {
            http.newCall(builder.build()).execute().use { response ->
                Pair(response.code, response.body?.string() ?: "")
            }
        } catch (e: IOException) {
            throw ApiException(
                0,
                ApiException.CODE_NETWORK,
                "Internet bilan aloqa yo'q. Tarmoqni tekshirib, qayta urinib ko'ring",
            )
        }

        if (status in 200..299) {
            try {
                json.decodeFromString(serializer, text)
            } catch (e: IllegalArgumentException) {
                throw ApiException(
                    status,
                    ApiException.CODE_BAD_RESPONSE,
                    "Serverdan tushunarsiz javob keldi. Birozdan keyin qayta urinib ko'ring",
                )
            }
        } else {
            throw parseError(status, text)
        }
    }

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
