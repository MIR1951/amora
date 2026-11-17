package uz.amora.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// Server bilan almashinadigan ma'lumotlar. Maydon nomlari backend/app/schemas.py bilan bir xil.

// ---------- Menyu va kafe ----------

@Serializable
data class Category(
    val id: Int,
    val name: String,
)

@Serializable
data class Product(
    val id: Int,
    @SerialName("category_id") val categoryId: Int? = null,
    val name: String,
    val description: String = "",
    val price: Int,
    @SerialName("image_url") val imageUrl: String? = null,
    @SerialName("is_available") val isAvailable: Boolean = true,
)

@Serializable
data class Menu(
    val categories: List<Category> = emptyList(),
    val products: List<Product> = emptyList(),
)

@Serializable
data class Shop(
    @SerialName("cafe_name") val cafeName: String = "Amora",
    val phone: String? = null,
    // Ish vaqti va "buyurtma qabul qilish" tugmasi birga hisobga olingan
    @SerialName("is_open") val isOpen: Boolean = true,
    @SerialName("is_accepting_orders") val isAcceptingOrders: Boolean = true,
    @SerialName("open_time") val openTime: String = "",
    @SerialName("close_time") val closeTime: String = "",
    @SerialName("delivery_fee") val deliveryFee: Int = 0,
    @SerialName("free_delivery_from") val freeDeliveryFrom: Int? = null,
    @SerialName("min_order_amount") val minOrderAmount: Int = 0,
    @SerialName("max_delivery_km") val maxDeliveryKm: Double? = null,
    @SerialName("cafe_latitude") val cafeLatitude: Double? = null,
    @SerialName("cafe_longitude") val cafeLongitude: Double? = null,
    // Bosh sahifadagi banner: bo'sh bo'lsa ilova yetkazish shartini o'zi yozadi
    @SerialName("banner_title") val bannerTitle: String? = null,
    @SerialName("banner_text") val bannerText: String? = null,
)

// ---------- Mijoz ----------

@Serializable
data class Customer(
    val id: Int,
    val name: String,
    val phone: String,
    // Raqam Telegram orqali tasdiqlangan: buyurtma berish uchun shart
    @SerialName("phone_verified") val phoneVerified: Boolean = false,
)

/** Raqamni Telegram orqali tasdiqlashni boshlash. */
@Serializable
data class TelegramStartIn(
    val name: String?,
    val platform: String = "android",
)

@Serializable
data class TelegramStart(
    val code: String,
    // Telegram ilovasini ochadi; u o'rnatilmagan bo'lsa brauzer uchun havola
    @SerialName("app_url") val appUrl: String,
    @SerialName("bot_url") val botUrl: String,
    @SerialName("expires_in") val expiresIn: Int,
)

@Serializable
data class TelegramCheckIn(val code: String)

@Serializable
data class TelegramCheck(
    val status: String, // pending | verified
    val token: String? = null,
    val customer: Customer? = null,
)

@Serializable
data class CustomerUpdate(
    val name: String? = null,
)

/** Faqat push manzilini yangilash: ism va telefonga tegilmaydi. */
@Serializable
data class PushTokenUpdate(
    @SerialName("fcm_token") val fcmToken: String,
)

// ---------- Savat va buyurtma ----------

@Serializable
data class CartItemIn(
    @SerialName("product_id") val productId: Int,
    val quantity: Int,
)

@Serializable
data class QuoteIn(
    val items: List<CartItemIn>,
    val latitude: Double? = null,
    val longitude: Double? = null,
    @SerialName("promo_code") val promoCode: String? = null,
    // Birinchi buyurtma chegirmasi kod kiritmasdan qo'llanadi
    @SerialName("apply_auto_promo") val applyAutoPromo: Boolean = true,
    // Hali ro'yxatdan o'tilmagan bo'lsa: birinchi buyurtma chegirmasi shu raqam bo'yicha tekshiriladi
    val phone: String? = null,
)

@Serializable
data class Problem(
    val code: String,
    val message: String,
    @SerialName("product_id") val productId: Int? = null,
)

@Serializable
data class QuoteLine(
    @SerialName("product_id") val productId: Int,
    val name: String,
    val price: Int,
    val quantity: Int,
    @SerialName("line_total") val lineTotal: Int,
)

@Serializable
data class Quote(
    val lines: List<QuoteLine> = emptyList(),
    @SerialName("items_total") val itemsTotal: Int = 0,
    @SerialName("delivery_fee") val deliveryFee: Int = 0,
    val total: Int = 0,
    @SerialName("distance_km") val distanceKm: Double? = null,
    @SerialName("can_order") val canOrder: Boolean = false,
    val problems: List<Problem> = emptyList(),
    val discount: Int = 0,
    @SerialName("promo_title") val promoTitle: String? = null,
    @SerialName("promo_error") val promoError: String? = null,
)

@Serializable
data class OrderIn(
    val items: List<CartItemIn>,
    val latitude: Double,
    val longitude: Double,
    @SerialName("address_note") val addressNote: String = "",
    val comment: String = "",
    val name: String? = null,
    val phone: String? = null,
    // Har bir buyurtma uchun UUID: internet uzilib qayta yuborilsa, buyurtma ikkilanmaydi
    @SerialName("client_order_id") val clientOrderId: String? = null,
    // Ilova ko'rsatgan summa: narx o'zgargan bo'lsa server buyurtmani qabul qilmaydi
    @SerialName("expected_total") val expectedTotal: Int? = null,
    @SerialName("promo_code") val promoCode: String? = null,
    @SerialName("apply_auto_promo") val applyAutoPromo: Boolean = true,
)

@Serializable
data class OrderItem(
    @SerialName("product_id") val productId: Int? = null,
    val name: String,
    val price: Int,
    val quantity: Int,
    @SerialName("line_total") val lineTotal: Int,
)

@Serializable
data class StatusEvent(
    val status: String,
    @SerialName("status_label") val statusLabel: String = "",
    @SerialName("created_at") val createdAt: String = "",
)

@Serializable
data class Order(
    val id: Int,
    val status: String,
    @SerialName("status_label") val statusLabel: String = "",
    @SerialName("is_active") val isActive: Boolean = false,
    @SerialName("can_cancel") val canCancel: Boolean = false,
    val items: List<OrderItem> = emptyList(),
    @SerialName("items_total") val itemsTotal: Int = 0,
    @SerialName("delivery_fee") val deliveryFee: Int = 0,
    val discount: Int = 0,
    @SerialName("promo_code") val promoCode: String? = null,
    val total: Int = 0,
    @SerialName("customer_name") val customerName: String = "",
    val phone: String = "",
    val latitude: Double = 0.0,
    val longitude: Double = 0.0,
    @SerialName("address_note") val addressNote: String = "",
    val comment: String = "",
    @SerialName("reject_reason") val rejectReason: String? = null,
    @SerialName("created_at") val createdAt: String = "",
    @SerialName("updated_at") val updatedAt: String = "",
    val history: List<StatusEvent> = emptyList(),
)

@Serializable
data class OrderList(
    val orders: List<Order> = emptyList(),
    @SerialName("has_more") val hasMore: Boolean = false,
)

// ---------- Xato ----------

@Serializable
data class ApiErrorBody(
    val error: ApiErrorInfo = ApiErrorInfo(),
)

@Serializable
data class ApiErrorInfo(
    val code: String = "error",
    val message: String = "",
    val total: Int? = null,
    @SerialName("product_id") val productId: Int? = null,
)

/** Buyurtma holatlari (backend/app/models.py dagi OrderStatus). */
object OrderStatus {
    const val NEW = "new"
    const val ACCEPTED = "accepted"
    const val DELIVERING = "delivering"
    const val DELIVERED = "delivered"
    const val REJECTED = "rejected"
    const val CANCELLED = "cancelled"
}
