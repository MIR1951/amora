/// On-device state (port of android data/Stores.kt): session (token, profile, address), cart, catalog.
/// Persistence: UserDefaults (Codable JSON) for profile/address/cart, Keychain for the auth token.
///
/// Surface:
/// - `struct Profile: Codable, Equatable, Hashable { var name: String; var phone: String; var verified: Bool = false }`
///   (phone is always "+998XXXXXXXXX")
/// - `struct Address: Codable, Equatable, Hashable { var latitude: Double; var longitude: Double; var note: String }`
/// - `@MainActor @Observable final class SessionStore`
///   - `private(set) var profile: Profile?`, `private(set) var address: Address?`, `private(set) var token: String?`
///   - `func saveToken(_ token: String?)`, `func saveProfile(_ profile: Profile)`, `func saveAddress(_ address: Address)`
///   - `func signOut()`  // token removed, profile kept but `verified = false`
///   - `var notificationsAsked: Bool`, `var pushToken: String?`, `var pushTokenSentWith: String?`
///   - `func onTokenChange(_ observer: @escaping @MainActor (String?) -> Void)`
///   - `static func resetAll()`  // wipes everything (UI tests)
/// - `struct CartLine: Codable, Equatable, Hashable, Identifiable { var productId: Int; var quantity: Int; var id: Int }`
/// - `@MainActor @Observable final class CartStore`
///   - `static let maxQuantity = 50`
///   - `private(set) var lines: [CartLine]` (insertion order, like Kotlin LinkedHashMap)
///   - `var items: [Int: Int]`, `var isEmpty: Bool`, `var totalQuantity: Int`, `var cartItems: [CartItemIn]`
///   - `func quantity(_ productId: Int) -> Int`, `func add(_ productId: Int)`, `func remove(_ productId: Int)`
///   - `func set(_ productId: Int, quantity: Int)`, `func replace(_ lines: [CartLine])`, `func replace(_ items: [Int: Int])`
///   - `func retain(_ productIds: Set<Int>)`, `func clear()`
/// - `struct CatalogState: Equatable { var loading = false; var error: String? = nil; var shop: Shop? = nil; var menu: MenuData? = nil }`
/// - `@MainActor @Observable final class Catalog`
///   - `init(api: ApiClient)`
///   - `private(set) var state: CatalogState`, convenience `var loading: Bool`, `var error: String?`,
///     `var shop: Shop?`, `var menu: MenuData?`
///   - `func refresh(showLoading: Bool = false) async`

import Foundation
import Observation

/// Mijozning ismi va telefoni. `verified`: raqam Telegram orqali tasdiqlangan.
struct Profile: Codable, Equatable, Hashable {
    var name: String
    var phone: String
    var verified: Bool = false
}

/// Yetkazish manzili: xaritadagi nuqta va mo'ljal.
struct Address: Codable, Equatable, Hashable {
    var latitude: Double
    var longitude: Double
    var note: String
}

private enum Keys {
    static let installed = "amora.installed"
    static let profile = "amora.session.profile"
    static let address = "amora.session.address"
    static let notificationsAsked = "amora.session.notifications_asked"
    static let pushToken = "amora.session.push_token"
    static let pushSentWith = "amora.session.push_token_sent_with"
    static let cart = "amora.cart.lines"
    static let tokenAccount = "token"
}

private func readJSON<T: Decodable>(_ type: T.Type, _ key: String) -> T? {
    guard let data = UserDefaults.standard.data(forKey: key) else { return nil }
    return try? JSONDecoder().decode(type, from: data)
}

private func writeJSON<T: Encodable>(_ value: T?, _ key: String) {
    if let value, let data = try? JSONEncoder().encode(value) {
        UserDefaults.standard.set(data, forKey: key)
    } else {
        UserDefaults.standard.removeObject(forKey: key)
    }
}

/// Telefonda saqlanadigan ma'lumotlar: kirish kaliti (token), profil va oxirgi manzil.
@MainActor
@Observable
final class SessionStore {
    private(set) var profile: Profile? = nil
    private(set) var address: Address? = nil
    /// Kirish kaliti. O'zgarganda jonli ulanish yangi kalit bilan qayta o'rnatiladi.
    private(set) var token: String? = nil

    @ObservationIgnored private var tokenObservers: [@MainActor (String?) -> Void] = []

    init() {
        let defaults = UserDefaults.standard
        // Keychain ilova o'chirilganda ham qoladi: qayta o'rnatilgan ilova (Android kabi) toza boshlanadi
        if !defaults.bool(forKey: Keys.installed) {
            Keychain.write(Keys.tokenAccount, nil)
            defaults.set(true, forKey: Keys.installed)
        }
        let storedToken = Keychain.read(Keys.tokenAccount)
        token = storedToken
        if var stored = readJSON(Profile.self, Keys.profile),
           !stored.name.trimmingCharacters(in: .whitespaces).isEmpty,
           !stored.phone.trimmingCharacters(in: .whitespaces).isEmpty {
            stored.verified = stored.verified && storedToken != nil
            profile = stored
        } else {
            profile = nil
        }
        address = readJSON(Address.self, Keys.address)
    }

    /// Kirish kaliti o'zgarganda chaqiriladi (jonli ulanish, push manzili).
    func onTokenChange(_ observer: @escaping @MainActor (String?) -> Void) {
        tokenObservers.append(observer)
    }

    func saveToken(_ token: String?) {
        Keychain.write(Keys.tokenAccount, token)
        let changed = self.token != token
        self.token = token
        if changed {
            for observer in tokenObservers {
                observer(token)
            }
        }
    }

    /// Bildirishnomaga ruxsat bir marta so'ralgan: mijoz rad etsa, qayta-qayta bezovta qilinmaydi.
    var notificationsAsked: Bool {
        get { UserDefaults.standard.bool(forKey: Keys.notificationsAsked) }
        set { UserDefaults.standard.set(newValue, forKey: Keys.notificationsAsked) }
    }

    /// Push xizmati bergan qurilma manzili va u qaysi kirish kaliti bilan serverga yuborilgani.
    var pushToken: String? {
        get { UserDefaults.standard.string(forKey: Keys.pushToken) }
        set { UserDefaults.standard.set(newValue, forKey: Keys.pushToken) }
    }

    var pushTokenSentWith: String? {
        get { UserDefaults.standard.string(forKey: Keys.pushSentWith) }
        set { UserDefaults.standard.set(newValue, forKey: Keys.pushSentWith) }
    }

    func saveProfile(_ profile: Profile) {
        writeJSON(profile, Keys.profile)
        self.profile = profile
    }

    /// Server kirish kalitini tanimadi: telefon hisobdan chiqdi, raqamni qayta tasdiqlash kerak.
    func signOut() {
        saveToken(nil)
        if var current = profile {
            current.verified = false
            saveProfile(current)
        }
    }

    func saveAddress(_ address: Address) {
        writeJSON(address, Keys.address)
        self.address = address
    }

    /// Hamma saqlangan ma'lumotni o'chiradi (UI testlari uchun: `--amora-reset` argumenti).
    static func resetAll() {
        let defaults = UserDefaults.standard
        for key in [Keys.profile, Keys.address, Keys.notificationsAsked, Keys.pushToken, Keys.pushSentWith, Keys.cart] {
            defaults.removeObject(forKey: key)
        }
        Keychain.write(Keys.tokenAccount, nil)
    }
}

/// Savatdagi bitta qator: taom raqami va soni.
struct CartLine: Codable, Equatable, Hashable, Identifiable {
    var productId: Int
    var quantity: Int
    var id: Int { productId }

    enum CodingKeys: String, CodingKey {
        case productId, quantity
    }
}

/// Savat: taom raqami -> soni. Ilova yopilsa ham saqlanib qoladi.
@MainActor
@Observable
final class CartStore {
    static let maxQuantity = 50

    /// Qo'shilish tartibida (Kotlin LinkedHashMap kabi).
    private(set) var lines: [CartLine] = []

    init() {
        let stored = readJSON([CartLine].self, Keys.cart) ?? []
        var seen = Set<Int>()
        var clean: [CartLine] = []
        for line in stored where line.productId > 0 && line.quantity > 0 && !seen.contains(line.productId) {
            seen.insert(line.productId)
            clean.append(CartLine(productId: line.productId, quantity: min(line.quantity, CartStore.maxQuantity)))
        }
        lines = clean
    }

    /// productId -> quantity (tartibsiz; tartib kerak bo'lsa `lines`).
    var items: [Int: Int] {
        var result: [Int: Int] = [:]
        for line in lines { result[line.productId] = line.quantity }
        return result
    }

    var isEmpty: Bool { lines.isEmpty }

    /// Savatdagi taomlar soni (hammasi qo'shib).
    var totalQuantity: Int { lines.reduce(0) { $0 + $1.quantity } }

    /// Serverga yuboriladigan ko'rinish (Kotlin `toCartItems()`).
    var cartItems: [CartItemIn] { lines.map { CartItemIn(productId: $0.productId, quantity: $0.quantity) } }

    func quantity(_ productId: Int) -> Int {
        lines.first(where: { $0.productId == productId })?.quantity ?? 0
    }

    func add(_ productId: Int) {
        set(productId, quantity: quantity(productId) + 1)
    }

    func remove(_ productId: Int) {
        set(productId, quantity: quantity(productId) - 1)
    }

    func set(_ productId: Int, quantity: Int) {
        var next = lines
        if let index = next.firstIndex(where: { $0.productId == productId }) {
            if quantity <= 0 {
                next.remove(at: index)
            } else {
                next[index].quantity = min(quantity, CartStore.maxQuantity)
            }
        } else if quantity > 0 {
            next.append(CartLine(productId: productId, quantity: min(quantity, CartStore.maxQuantity)))
        }
        publish(next)
    }

    func replace(_ lines: [CartLine]) {
        var next: [CartLine] = []
        for line in lines where line.quantity > 0 {
            let capped = min(line.quantity, CartStore.maxQuantity)
            if let index = next.firstIndex(where: { $0.productId == line.productId }) {
                next[index].quantity = capped
            } else {
                next.append(CartLine(productId: line.productId, quantity: capped))
            }
        }
        publish(next)
    }

    /// Tartibsiz variant: tartib productId bo'yicha.
    func replace(_ items: [Int: Int]) {
        replace(items.keys.sorted().map { CartLine(productId: $0, quantity: items[$0] ?? 0) })
    }

    /// Menyudan olib tashlangan taomlarni savatdan ham chiqaradi.
    func retain(_ productIds: Set<Int>) {
        if lines.allSatisfy({ productIds.contains($0.productId) }) { return }
        publish(lines.filter { productIds.contains($0.productId) })
    }

    func clear() {
        publish([])
    }

    private func publish(_ next: [CartLine]) {
        lines = next
        writeJSON(next, Keys.cart)
    }
}

struct CatalogState: Equatable {
    var loading: Bool = false
    var error: String? = nil
    var shop: Shop? = nil
    var menu: MenuData? = nil
}

/// Menyu va kafe ma'lumotlari: bir marta yuklanadi va barcha ekranlarda ishlatiladi.
@MainActor
@Observable
final class Catalog {
    private(set) var state = CatalogState(loading: true)

    var loading: Bool { state.loading }
    var error: String? { state.error }
    var shop: Shop? { state.shop }
    var menu: MenuData? { state.menu }

    private let api: ApiClient
    @ObservationIgnored private var requested = 0
    @ObservationIgnored private var completed = 0
    @ObservationIgnored private var inFlight: Task<Void, Never>?

    init(api: ApiClient) {
        self.api = api
    }

    /// Menyu va kafe ma'lumotini serverdan qayta o'qiydi.
    ///
    /// Bir vaqtda bir nechta so'rov kelsa, ular navbat bilan bajariladi va ortiqchasi tashlab
    /// yuboriladi: har bir chaqiruv o'zidan KEYIN boshlangan o'qish tugashini kutadi.
    func refresh(showLoading: Bool = false) async {
        requested += 1
        let wanted = requested
        if showLoading || state.menu == nil {
            state.loading = true
            state.error = nil
        }
        while let running = inFlight {
            await running.value
        }
        if completed >= wanted { return }
        let covers = requested
        let task = Task { @MainActor [weak self] in
            guard let self else { return }
            await self.load()
            self.completed = max(self.completed, covers)
            self.inFlight = nil
        }
        inFlight = task
        await task.value
    }

    private func load() async {
        do {
            async let shopResult = api.shop()
            async let menuResult = api.menu()
            let shop = try await shopResult
            let menu = try await menuResult
            state = CatalogState(loading: false, error: nil, shop: shop, menu: menu)
        } catch {
            // Avval yuklangan menyu bo'lsa, u ekranda qolaveradi
            state.loading = false
            if let apiError = ApiError.from(error) {
                state.error = apiError.message
            }
        }
    }
}
