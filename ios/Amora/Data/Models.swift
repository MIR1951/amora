/// Server JSON models (port of android data/Models.kt). Field names match backend/app/schemas.py.
/// Decoding is lenient: missing/null/mistyped optional fields fall back to the Kotlin defaults, lists are
/// decoded element by element (one malformed element is dropped, the rest of the list survives),
/// unknown keys are ignored, order statuses are plain strings (unknown values survive).
///
/// Surface (all `Codable, Equatable, Hashable` structs with `var` properties + memberwise init):
/// - `Category { id: Int, name: String }` (Identifiable)
/// - `Product { id, categoryId: Int?, name, description: String, price: Int, imageUrl: String?, isAvailable: Bool }` (Identifiable)
/// - `MenuData { categories: [Category], products: [Product] }`   (Kotlin `Menu`; renamed so SwiftUI.Menu is not shadowed)
/// - `Shop { cafeName, phone: String?, isOpen, isAcceptingOrders, openTime, closeTime, deliveryFee: Int,
///          freeDeliveryFrom: Int?, minOrderAmount: Int, maxDeliveryKm: Double?, cafeLatitude: Double?,
///          cafeLongitude: Double?, bannerTitle: String?, bannerText: String? }`
/// - `Customer { id, name, phone, phoneVerified: Bool }` (Identifiable)
/// - `TelegramStartIn { name: String?, platform: String = "ios" }`
/// - `TelegramStart { code, appUrl, botUrl, expiresIn: Int }`
/// - `TelegramCheckIn { code }`, `TelegramCheck { status: String, token: String?, customer: Customer? }`
/// - `CustomerUpdate { name: String? }`, `PushTokenUpdate { fcmToken: String }`
/// - `CartItemIn { productId, quantity }`
/// - `QuoteIn { items, latitude?, longitude?, promoCode?, applyAutoPromo = true, phone? }`
/// - `Problem { code, message, productId: Int? }`
/// - `QuoteLine { productId, name, price, quantity, lineTotal }`
/// - `Quote { lines, itemsTotal, deliveryFee, total, distanceKm: Double?, canOrder, problems, discount,
///           promoTitle: String?, promoError: String? }`
/// - `OrderIn { items, latitude, longitude, addressNote = "", comment = "", name?, phone?, clientOrderId?,
///             expectedTotal: Int?, promoCode?, applyAutoPromo = true }`
/// - `OrderItem { productId: Int?, name, price, quantity, lineTotal }`
/// - `StatusEvent { status, statusLabel, createdAt: String }`
/// - `Order { id, status: String, statusLabel, isActive, canCancel, items: [OrderItem], itemsTotal, deliveryFee,
///           discount, promoCode: String?, total, customerName, phone, latitude, longitude, addressNote, comment,
///           rejectReason: String?, createdAt: String, updatedAt: String, history: [StatusEvent] }` (Identifiable)
/// - `OrderList { orders: [Order], hasMore: Bool }`
/// - `ApiErrorBody { error: ApiErrorInfo }`, `ApiErrorInfo { code, message, total: Int?, productId: Int? }`
/// - `enum OrderStatus { static let new, accepted, delivering, delivered, rejected, cancelled }` (String constants)

import Foundation

// MARK: - Lenient decoding helpers

extension KeyedDecodingContainer {
    /// Missing, null or mistyped value -> nil.
    func lenientOptional<T: Decodable>(_ type: T.Type, _ key: Key) -> T? {
        do {
            return try decodeIfPresent(type, forKey: key)
        } catch {
            return nil
        }
    }

    /// Missing, null or mistyped value -> `fallback`.
    func lenient<T: Decodable>(_ type: T.Type, _ key: Key, _ fallback: T) -> T {
        lenientOptional(type, key) ?? fallback
    }

    /// Array decoded element by element: a malformed element is dropped, the rest survive.
    /// Missing, null or non-array value -> [].
    func lenientArray<T: Decodable>(_ type: T.Type, _ key: Key) -> [T] {
        (lenientOptional([LossyElement<T>].self, key) ?? []).compactMap { $0.value }
    }
}

/// Ro'yxatning bitta elementi: o'qib bo'lmasa nil (butun ro'yxat bo'shab qolmaydi).
private struct LossyElement<T: Decodable>: Decodable {
    let value: T?

    init(from decoder: Decoder) throws {
        value = try? T(from: decoder)
    }
}

// MARK: - Menyu va kafe

struct Category: Codable, Equatable, Hashable, Identifiable {
    var id: Int
    var name: String

    enum CodingKeys: String, CodingKey {
        case id, name
    }
}

extension Category {
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(Int.self, forKey: .id)
        name = c.lenient(String.self, .name, "")
    }
}

struct Product: Codable, Equatable, Hashable, Identifiable {
    var id: Int
    var categoryId: Int? = nil
    var name: String
    var description: String = ""
    var price: Int
    var imageUrl: String? = nil
    var isAvailable: Bool = true

    enum CodingKeys: String, CodingKey {
        case id
        case categoryId = "category_id"
        case name, description, price
        case imageUrl = "image_url"
        case isAvailable = "is_available"
    }
}

extension Product {
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(Int.self, forKey: .id)
        categoryId = c.lenientOptional(Int.self, .categoryId)
        name = c.lenient(String.self, .name, "")
        description = c.lenient(String.self, .description, "")
        price = c.lenient(Int.self, .price, 0)
        imageUrl = c.lenientOptional(String.self, .imageUrl)
        isAvailable = c.lenient(Bool.self, .isAvailable, true)
    }
}

/// Kotlin `Menu`.
struct MenuData: Codable, Equatable, Hashable {
    var categories: [Category] = []
    var products: [Product] = []

    enum CodingKeys: String, CodingKey {
        case categories, products
    }
}

extension MenuData {
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        categories = c.lenientArray(Category.self, .categories)
        products = c.lenientArray(Product.self, .products)
    }
}

struct Shop: Codable, Equatable, Hashable {
    var cafeName: String = "Amora"
    var phone: String? = nil
    /// Ish vaqti va "buyurtma qabul qilish" tugmasi birga hisobga olingan
    var isOpen: Bool = true
    var isAcceptingOrders: Bool = true
    var openTime: String = ""
    var closeTime: String = ""
    var deliveryFee: Int = 0
    var freeDeliveryFrom: Int? = nil
    var minOrderAmount: Int = 0
    var maxDeliveryKm: Double? = nil
    var cafeLatitude: Double? = nil
    var cafeLongitude: Double? = nil
    /// Bosh sahifadagi banner: bo'sh bo'lsa ilova yetkazish shartini o'zi yozadi
    var bannerTitle: String? = nil
    var bannerText: String? = nil

    enum CodingKeys: String, CodingKey {
        case cafeName = "cafe_name"
        case phone
        case isOpen = "is_open"
        case isAcceptingOrders = "is_accepting_orders"
        case openTime = "open_time"
        case closeTime = "close_time"
        case deliveryFee = "delivery_fee"
        case freeDeliveryFrom = "free_delivery_from"
        case minOrderAmount = "min_order_amount"
        case maxDeliveryKm = "max_delivery_km"
        case cafeLatitude = "cafe_latitude"
        case cafeLongitude = "cafe_longitude"
        case bannerTitle = "banner_title"
        case bannerText = "banner_text"
    }
}

extension Shop {
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        cafeName = c.lenient(String.self, .cafeName, "Amora")
        phone = c.lenientOptional(String.self, .phone)
        isOpen = c.lenient(Bool.self, .isOpen, true)
        isAcceptingOrders = c.lenient(Bool.self, .isAcceptingOrders, true)
        openTime = c.lenient(String.self, .openTime, "")
        closeTime = c.lenient(String.self, .closeTime, "")
        deliveryFee = c.lenient(Int.self, .deliveryFee, 0)
        freeDeliveryFrom = c.lenientOptional(Int.self, .freeDeliveryFrom)
        minOrderAmount = c.lenient(Int.self, .minOrderAmount, 0)
        maxDeliveryKm = c.lenientOptional(Double.self, .maxDeliveryKm)
        cafeLatitude = c.lenientOptional(Double.self, .cafeLatitude)
        cafeLongitude = c.lenientOptional(Double.self, .cafeLongitude)
        bannerTitle = c.lenientOptional(String.self, .bannerTitle)
        bannerText = c.lenientOptional(String.self, .bannerText)
    }
}

// MARK: - Mijoz

struct Customer: Codable, Equatable, Hashable, Identifiable {
    var id: Int
    var name: String
    var phone: String
    /// Raqam Telegram orqali tasdiqlangan: buyurtma berish uchun shart
    var phoneVerified: Bool = false

    enum CodingKeys: String, CodingKey {
        case id, name, phone
        case phoneVerified = "phone_verified"
    }
}

extension Customer {
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(Int.self, forKey: .id)
        name = c.lenient(String.self, .name, "")
        phone = c.lenient(String.self, .phone, "")
        phoneVerified = c.lenient(Bool.self, .phoneVerified, false)
    }
}

/// Raqamni Telegram orqali tasdiqlashni boshlash.
struct TelegramStartIn: Codable, Equatable, Hashable {
    var name: String? = nil
    var platform: String = "ios"
}

struct TelegramStart: Codable, Equatable, Hashable {
    var code: String
    /// Telegram ilovasini ochadi; u o'rnatilmagan bo'lsa brauzer uchun havola (`botUrl`)
    var appUrl: String
    var botUrl: String
    var expiresIn: Int

    enum CodingKeys: String, CodingKey {
        case code
        case appUrl = "app_url"
        case botUrl = "bot_url"
        case expiresIn = "expires_in"
    }
}

extension TelegramStart {
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        code = try c.decode(String.self, forKey: .code)
        appUrl = c.lenient(String.self, .appUrl, "")
        botUrl = c.lenient(String.self, .botUrl, "")
        expiresIn = c.lenient(Int.self, .expiresIn, 600)
    }
}

struct TelegramCheckIn: Codable, Equatable, Hashable {
    var code: String
}

struct TelegramCheck: Codable, Equatable, Hashable {
    /// "pending" | "verified"
    var status: String
    var token: String? = nil
    var customer: Customer? = nil

    enum CodingKeys: String, CodingKey {
        case status, token, customer
    }
}

extension TelegramCheck {
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        status = c.lenient(String.self, .status, "pending")
        token = c.lenientOptional(String.self, .token)
        customer = c.lenientOptional(Customer.self, .customer)
    }
}

struct CustomerUpdate: Codable, Equatable, Hashable {
    var name: String? = nil
}

/// Faqat push manzilini yangilash: ism va telefonga tegilmaydi.
struct PushTokenUpdate: Codable, Equatable, Hashable {
    var fcmToken: String

    enum CodingKeys: String, CodingKey {
        case fcmToken = "fcm_token"
    }
}

// MARK: - Savat va buyurtma

struct CartItemIn: Codable, Equatable, Hashable {
    var productId: Int
    var quantity: Int

    enum CodingKeys: String, CodingKey {
        case productId = "product_id"
        case quantity
    }
}

struct QuoteIn: Codable, Equatable, Hashable {
    var items: [CartItemIn]
    var latitude: Double? = nil
    var longitude: Double? = nil
    var promoCode: String? = nil
    /// Birinchi buyurtma chegirmasi kod kiritmasdan qo'llanadi
    var applyAutoPromo: Bool = true
    /// Hali ro'yxatdan o'tilmagan bo'lsa: birinchi buyurtma chegirmasi shu raqam bo'yicha tekshiriladi
    var phone: String? = nil

    enum CodingKeys: String, CodingKey {
        case items, latitude, longitude
        case promoCode = "promo_code"
        case applyAutoPromo = "apply_auto_promo"
        case phone
    }
}

struct Problem: Codable, Equatable, Hashable {
    var code: String
    var message: String
    var productId: Int? = nil

    enum CodingKeys: String, CodingKey {
        case code, message
        case productId = "product_id"
    }
}

extension Problem {
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        code = c.lenient(String.self, .code, "")
        message = c.lenient(String.self, .message, "")
        productId = c.lenientOptional(Int.self, .productId)
    }
}

struct QuoteLine: Codable, Equatable, Hashable {
    var productId: Int
    var name: String
    var price: Int
    var quantity: Int
    var lineTotal: Int

    enum CodingKeys: String, CodingKey {
        case productId = "product_id"
        case name, price, quantity
        case lineTotal = "line_total"
    }
}

extension QuoteLine {
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        productId = try c.decode(Int.self, forKey: .productId)
        name = c.lenient(String.self, .name, "")
        price = c.lenient(Int.self, .price, 0)
        quantity = c.lenient(Int.self, .quantity, 0)
        lineTotal = c.lenient(Int.self, .lineTotal, 0)
    }
}

struct Quote: Codable, Equatable, Hashable {
    var lines: [QuoteLine] = []
    var itemsTotal: Int = 0
    var deliveryFee: Int = 0
    var total: Int = 0
    var distanceKm: Double? = nil
    var canOrder: Bool = false
    var problems: [Problem] = []
    var discount: Int = 0
    var promoTitle: String? = nil
    var promoError: String? = nil

    enum CodingKeys: String, CodingKey {
        case lines
        case itemsTotal = "items_total"
        case deliveryFee = "delivery_fee"
        case total
        case distanceKm = "distance_km"
        case canOrder = "can_order"
        case problems, discount
        case promoTitle = "promo_title"
        case promoError = "promo_error"
    }
}

extension Quote {
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        lines = c.lenientArray(QuoteLine.self, .lines)
        itemsTotal = c.lenient(Int.self, .itemsTotal, 0)
        deliveryFee = c.lenient(Int.self, .deliveryFee, 0)
        total = c.lenient(Int.self, .total, 0)
        distanceKm = c.lenientOptional(Double.self, .distanceKm)
        canOrder = c.lenient(Bool.self, .canOrder, false)
        problems = c.lenientArray(Problem.self, .problems)
        discount = c.lenient(Int.self, .discount, 0)
        promoTitle = c.lenientOptional(String.self, .promoTitle)
        promoError = c.lenientOptional(String.self, .promoError)
    }
}

struct OrderIn: Codable, Equatable, Hashable {
    var items: [CartItemIn]
    var latitude: Double
    var longitude: Double
    var addressNote: String = ""
    var comment: String = ""
    var name: String? = nil
    var phone: String? = nil
    /// Har bir buyurtma uchun UUID: internet uzilib qayta yuborilsa, buyurtma ikkilanmaydi
    var clientOrderId: String? = nil
    /// Ilova ko'rsatgan summa: narx o'zgargan bo'lsa server buyurtmani qabul qilmaydi
    var expectedTotal: Int? = nil
    var promoCode: String? = nil
    var applyAutoPromo: Bool = true

    enum CodingKeys: String, CodingKey {
        case items, latitude, longitude
        case addressNote = "address_note"
        case comment, name, phone
        case clientOrderId = "client_order_id"
        case expectedTotal = "expected_total"
        case promoCode = "promo_code"
        case applyAutoPromo = "apply_auto_promo"
    }
}

struct OrderItem: Codable, Equatable, Hashable {
    var productId: Int? = nil
    var name: String
    var price: Int
    var quantity: Int
    var lineTotal: Int

    enum CodingKeys: String, CodingKey {
        case productId = "product_id"
        case name, price, quantity
        case lineTotal = "line_total"
    }
}

extension OrderItem {
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        productId = c.lenientOptional(Int.self, .productId)
        name = c.lenient(String.self, .name, "")
        price = c.lenient(Int.self, .price, 0)
        quantity = c.lenient(Int.self, .quantity, 0)
        lineTotal = c.lenient(Int.self, .lineTotal, 0)
    }
}

struct StatusEvent: Codable, Equatable, Hashable {
    var status: String
    var statusLabel: String = ""
    var createdAt: String = ""

    enum CodingKeys: String, CodingKey {
        case status
        case statusLabel = "status_label"
        case createdAt = "created_at"
    }
}

extension StatusEvent {
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        status = c.lenient(String.self, .status, "")
        statusLabel = c.lenient(String.self, .statusLabel, "")
        createdAt = c.lenient(String.self, .createdAt, "")
    }
}

struct Order: Codable, Equatable, Hashable, Identifiable {
    var id: Int
    /// Plain string: see `OrderStatus` for known values; unknown values are kept as-is.
    var status: String
    var statusLabel: String = ""
    var isActive: Bool = false
    var canCancel: Bool = false
    var items: [OrderItem] = []
    var itemsTotal: Int = 0
    var deliveryFee: Int = 0
    var discount: Int = 0
    var promoCode: String? = nil
    var total: Int = 0
    var customerName: String = ""
    var phone: String = ""
    var latitude: Double = 0
    var longitude: Double = 0
    var addressNote: String = ""
    var comment: String = ""
    var rejectReason: String? = nil
    var createdAt: String = ""
    var updatedAt: String = ""
    var history: [StatusEvent] = []

    enum CodingKeys: String, CodingKey {
        case id, status
        case statusLabel = "status_label"
        case isActive = "is_active"
        case canCancel = "can_cancel"
        case items
        case itemsTotal = "items_total"
        case deliveryFee = "delivery_fee"
        case discount
        case promoCode = "promo_code"
        case total
        case customerName = "customer_name"
        case phone, latitude, longitude
        case addressNote = "address_note"
        case comment
        case rejectReason = "reject_reason"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case history
    }
}

extension Order {
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(Int.self, forKey: .id)
        status = c.lenient(String.self, .status, "")
        statusLabel = c.lenient(String.self, .statusLabel, "")
        isActive = c.lenient(Bool.self, .isActive, false)
        canCancel = c.lenient(Bool.self, .canCancel, false)
        items = c.lenientArray(OrderItem.self, .items)
        itemsTotal = c.lenient(Int.self, .itemsTotal, 0)
        deliveryFee = c.lenient(Int.self, .deliveryFee, 0)
        discount = c.lenient(Int.self, .discount, 0)
        promoCode = c.lenientOptional(String.self, .promoCode)
        total = c.lenient(Int.self, .total, 0)
        customerName = c.lenient(String.self, .customerName, "")
        phone = c.lenient(String.self, .phone, "")
        latitude = c.lenient(Double.self, .latitude, 0)
        longitude = c.lenient(Double.self, .longitude, 0)
        addressNote = c.lenient(String.self, .addressNote, "")
        comment = c.lenient(String.self, .comment, "")
        rejectReason = c.lenientOptional(String.self, .rejectReason)
        createdAt = c.lenient(String.self, .createdAt, "")
        updatedAt = c.lenient(String.self, .updatedAt, "")
        history = c.lenientArray(StatusEvent.self, .history)
    }
}

struct OrderList: Codable, Equatable, Hashable {
    var orders: [Order] = []
    var hasMore: Bool = false

    enum CodingKeys: String, CodingKey {
        case orders
        case hasMore = "has_more"
    }
}

extension OrderList {
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        orders = c.lenientArray(Order.self, .orders)
        hasMore = c.lenient(Bool.self, .hasMore, false)
    }
}

// MARK: - Xato

struct ApiErrorBody: Codable, Equatable, Hashable {
    var error: ApiErrorInfo = ApiErrorInfo()

    enum CodingKeys: String, CodingKey {
        case error
    }
}

extension ApiErrorBody {
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        error = try c.decode(ApiErrorInfo.self, forKey: .error)
    }
}

struct ApiErrorInfo: Codable, Equatable, Hashable {
    var code: String = "error"
    var message: String = ""
    var total: Int? = nil
    var productId: Int? = nil

    enum CodingKeys: String, CodingKey {
        case code, message, total
        case productId = "product_id"
    }
}

extension ApiErrorInfo {
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        code = c.lenient(String.self, .code, "error")
        message = c.lenient(String.self, .message, "")
        total = c.lenientOptional(Int.self, .total)
        productId = c.lenientOptional(Int.self, .productId)
    }
}

/// Buyurtma holatlari (backend/app/models.py dagi OrderStatus). `Order.status` oddiy satr.
enum OrderStatus {
    static let new = "new"
    static let accepted = "accepted"
    static let delivering = "delivering"
    static let delivered = "delivered"
    static let rejected = "rejected"
    static let cancelled = "cancelled"
}
