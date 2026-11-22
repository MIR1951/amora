/// HTTP client for the Amora backend (port of android data/ApiClient.kt). Every path is under `<base>/api/v1`.
///
/// Surface:
/// - `struct ApiError: Error, LocalizedError` — `status: Int?`, `code: String?`, `message: String` (Uzbek, user-facing),
///   `total: Int?`, `isNetwork: Bool`, `isUnauthorized: Bool`, `errorDescription: String?`,
///   `static let codeNetwork = "network"`, `static let codeBadResponse = "bad_response"`,
///   `static func from(_ error: Error) -> ApiError?` (nil for task cancellation).
/// - `@MainActor final class ApiClient`
///   - `init(baseUrl: String, tokenProvider: @escaping @MainActor () -> String?)`
///   - `let baseUrl: String`
///   - `var onUnauthorized: (@MainActor (String) -> Void)?`   // a request sent WITH this token got 401
///   - `func logout() async throws`                            // POST /auth/logout -> 204
///   - `func deleteAccount() async throws`                     // DELETE /me -> 204 (409 `has_active_orders`)
///   - `func menu() async throws -> MenuData`
///   - `func shop() async throws -> Shop`
///   - `func startTelegramVerification(name: String?) async throws -> TelegramStart`
///   - `func checkTelegramVerification(code: String) async throws -> TelegramCheck`
///   - `func me() async throws -> Customer`
///   - `func updateName(_ name: String) async throws -> Customer`
///   - `func updatePushToken(_ token: String) async throws -> Customer`
///   - `func quote(items: [CartItemIn], latitude: Double?, longitude: Double?, promoCode: String? = nil, phone: String? = nil) async throws -> Quote`
///   - `func createOrder(_ order: OrderIn) async throws -> Order`
///   - `func orders(limit: Int = 20, offset: Int = 0) async throws -> OrderList`
///   - `func order(id: Int) async throws -> Order`
///   - `func cancelOrder(id: Int) async throws -> Order`
///   - `func imageURL(_ imageUrl: String?) -> URL?`
/// - `func resolveImageUrl(_ baseUrl: String, _ imageUrl: String?) -> String?`
///
/// All API methods throw `ApiError`, or `CancellationError` when the calling task was cancelled.

import Foundation

/// Serverdan kelgan xato. `message` o'zbekcha va mijozga to'g'ridan-to'g'ri ko'rsatiladi,
/// `code` esa ilova ichidagi shartlar uchun (masalan "shop_closed", "price_changed").
struct ApiError: Error, LocalizedError, Equatable {
    /// HTTP status; nil when the request never reached the server.
    var status: Int?
    var code: String?
    var message: String
    var total: Int?

    init(status: Int?, code: String?, message: String, total: Int? = nil) {
        self.status = status
        self.code = code
        self.message = message
        self.total = total
    }

    var isNetwork: Bool { code == ApiError.codeNetwork }
    var isUnauthorized: Bool { status == 401 }
    var errorDescription: String? { message }

    static let codeNetwork = "network"
    static let codeBadResponse = "bad_response"

    static let network = ApiError(
        status: nil,
        code: codeNetwork,
        message: "Internet bilan aloqa yo'q. Tarmoqni tekshirib, qayta urinib ko'ring"
    )

    /// Converts any thrown error to `ApiError`. Returns nil for task cancellation (ignore those).
    static func from(_ error: Error) -> ApiError? {
        if let apiError = error as? ApiError { return apiError }
        if error is CancellationError { return nil }
        if let urlError = error as? URLError {
            return urlError.code == .cancelled ? nil : ApiError.network
        }
        return ApiError(
            status: nil,
            code: "error",
            message: "Xatolik yuz berdi. Birozdan keyin qayta urinib ko'ring"
        )
    }
}

/// Amora serveri bilan aloqa. Barcha manzillar `/api/v1` ostida.
@MainActor
final class ApiClient {
    let baseUrl: String
    private let apiUrl: String
    private let tokenProvider: @MainActor () -> String?
    /// Server kirish kalitini tanimadi (401). Qaysi kalit yuborilgani beriladi: shu orada yangi kalit
    /// olingan bo'lsa, eski kalitning xatosi uni o'chirmasligi kerak. Hamma so'rovlar uchun bitta joy.
    var onUnauthorized: (@MainActor (String) -> Void)?
    private let session: URLSession
    private let decoder = JSONDecoder()
    private let encoder = JSONEncoder()

    init(baseUrl: String, tokenProvider: @escaping @MainActor () -> String?) {
        let trimmed = baseUrl.hasSuffix("/") ? String(baseUrl.dropLast()) : baseUrl
        self.baseUrl = trimmed
        self.apiUrl = trimmed + "/api/v1"
        self.tokenProvider = tokenProvider
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 20
        config.timeoutIntervalForResource = 60
        config.requestCachePolicy = .reloadIgnoringLocalCacheData
        config.urlCache = nil
        config.waitsForConnectivity = false
        self.session = URLSession(configuration: config)
    }

    // MARK: Menyu

    func menu() async throws -> MenuData {
        try await call("GET", "/menu", MenuData.self)
    }

    func shop() async throws -> Shop {
        try await call("GET", "/shop", Shop.self)
    }

    // MARK: Mijoz

    /// Kirish kaliti bo'lsa yuboriladi: shu telefondagi eski buyurtmalar tasdiqlangan hisobga o'tadi.
    func startTelegramVerification(name: String?) async throws -> TelegramStart {
        try await call(
            "POST", "/auth/telegram", TelegramStart.self,
            body: encode(TelegramStartIn(name: name, platform: "ios")),
            auth: true
        )
    }

    func checkTelegramVerification(code: String) async throws -> TelegramCheck {
        try await call(
            "POST", "/auth/telegram/check", TelegramCheck.self,
            body: encode(TelegramCheckIn(code: code))
        )
    }

    func me() async throws -> Customer {
        try await call("GET", "/me", Customer.self, auth: true)
    }

    func updateName(_ name: String) async throws -> Customer {
        try await call("PATCH", "/me", Customer.self, body: encode(CustomerUpdate(name: name)), auth: true)
    }

    func updatePushToken(_ token: String) async throws -> Customer {
        try await call("PATCH", "/me", Customer.self, body: encode(PushTokenUpdate(fcmToken: token)), auth: true)
    }

    /// Hisobdan chiqish: server shu telefonning kalitini bekor qiladi.
    func logout() async throws {
        _ = try await send("POST", "/auth/logout", body: Data(), auth: true)
    }

    /// Hisobni o'chirish. Tugallanmagan buyurtma bo'lsa server 409 `has_active_orders` qaytaradi.
    func deleteAccount() async throws {
        _ = try await send("DELETE", "/me", body: nil, auth: true)
    }

    // MARK: Buyurtma

    /// Token bo'lsa yuboriladi: server birinchi buyurtma chegirmasini va promokodni to'g'ri hisoblaydi.
    func quote(
        items: [CartItemIn],
        latitude: Double?,
        longitude: Double?,
        promoCode: String? = nil,
        phone: String? = nil
    ) async throws -> Quote {
        let body = QuoteIn(
            items: items,
            latitude: latitude,
            longitude: longitude,
            promoCode: promoCode,
            applyAutoPromo: true,
            phone: phone
        )
        return try await call("POST", "/orders/quote", Quote.self, body: encode(body), auth: true)
    }

    func createOrder(_ order: OrderIn) async throws -> Order {
        try await call("POST", "/orders", Order.self, body: encode(order), auth: true)
    }

    func orders(limit: Int = 20, offset: Int = 0) async throws -> OrderList {
        try await call("GET", "/orders?limit=\(limit)&offset=\(offset)", OrderList.self, auth: true)
    }

    func order(id: Int) async throws -> Order {
        try await call("GET", "/orders/\(id)", Order.self, auth: true)
    }

    func cancelOrder(id: Int) async throws -> Order {
        try await call("POST", "/orders/\(id)/cancel", Order.self, body: Data(), auth: true)
    }

    /// Product image URL rewritten to this app's server (see `resolveImageUrl`).
    func imageURL(_ imageUrl: String?) -> URL? {
        guard let resolved = resolveImageUrl(baseUrl, imageUrl) else { return nil }
        return URL(string: resolved)
    }

    // MARK: Ichki qism

    private func encode<T: Encodable>(_ value: T) -> Data {
        (try? encoder.encode(value)) ?? Data("{}".utf8)
    }

    private func call<T: Decodable>(
        _ method: String,
        _ path: String,
        _ type: T.Type,
        body: Data? = nil,
        auth: Bool = false
    ) async throws -> T {
        let data = try await send(method, path, body: body, auth: auth)
        do {
            return try decoder.decode(type, from: data)
        } catch {
            throw ApiError(
                status: 200,
                code: ApiError.codeBadResponse,
                message: "Serverdan tushunarsiz javob keldi. Birozdan keyin qayta urinib ko'ring"
            )
        }
    }

    /// So'rovni yuboradi va muvaffaqiyatli (2xx) javobning matnini qaytaradi (204 da bo'sh).
    private func send(_ method: String, _ path: String, body: Data?, auth: Bool) async throws -> Data {
        guard let url = URL(string: apiUrl + path) else {
            throw ApiError(
                status: nil,
                code: ApiError.codeBadResponse,
                message: "Serverdan tushunarsiz javob keldi. Birozdan keyin qayta urinib ko'ring"
            )
        }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        var sentToken: String?
        if auth, let token = tokenProvider(), !token.isEmpty {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
            sentToken = token
        }
        if method != "GET" {
            request.setValue("application/json; charset=utf-8", forHTTPHeaderField: "Content-Type")
            request.httpBody = body ?? Data()
        }

        let result: (Data, URLResponse)
        do {
            result = try await session.data(for: request)
        } catch {
            if error is CancellationError || Task.isCancelled {
                throw CancellationError()
            }
            if let urlError = error as? URLError, urlError.code == .cancelled {
                throw CancellationError()
            }
            throw ApiError.network
        }
        let data = result.0
        let response = result.1

        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        if (200...299).contains(status) {
            return data
        }
        if status == 401, let sentToken {
            onUnauthorized?(sentToken)
        }
        throw parseError(status: status, data: data)
    }

    private func parseError(status: Int, data: Data) -> ApiError {
        let info = (try? decoder.decode(ApiErrorBody.self, from: data))?.error
        let trimmed = info?.message.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        let message = trimmed.isEmpty
            ? "Serverda xatolik yuz berdi (\(status)). Birozdan keyin qayta urinib ko'ring"
            : (info?.message ?? "")
        return ApiError(status: status, code: info?.code ?? "error", message: message, total: info?.total)
    }
}

/// Rasm manzilini ilova ishlatayotgan server manziliga moslaydi.
/// Serverda tashqi manzil noto'g'ri sozlangan bo'lsa ham rasmlar ochilaveradi.
func resolveImageUrl(_ baseUrl: String, _ imageUrl: String?) -> String? {
    guard let imageUrl, !imageUrl.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return nil }
    var base = baseUrl
    while base.hasSuffix("/") { base.removeLast() }
    if let range = imageUrl.range(of: "/media/") {
        return base + String(imageUrl[range.lowerBound...])
    }
    return imageUrl
}
