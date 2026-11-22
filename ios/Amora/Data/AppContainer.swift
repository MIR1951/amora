/// Single app-wide dependency container (port of android AmoraApp.kt `AppContainer` + lifecycle hooks).
/// Created once by `AmoraApp`, injected with `.environment(container)`; screens read
/// `@Environment(AppContainer.self) private var container`.
///
/// Surface:
/// - `@MainActor @Observable final class AppContainer`
///   - `init()`
///   - `let baseUrl: String`            // Info.plist `AmoraApiBaseUrl` (Debug builds only: env `AMORA_API_BASE_URL`
///                                      // overrides it), default https://amora.mirjoy.uz
///   - `let api: ApiClient`, `let session: SessionStore`, `let catalog: Catalog`, `let cart: CartStore`,
///     `let activeOrders: ActiveOrders`, `let account: Account`, `let realtime: Realtime`,
///     `let notifications: OrderNotifier`, `let location: LocationFinder`, `let live: LiveUpdates`, `let push: PushTokens`
///   - `func onAppForeground()`         // scenePhase .active: start realtime, refresh catalog/account/active orders
///                                      // (once: the live connection's "resync" does it, with a fallback)
///   - `func signOut() async`           // "Chiqish"
///   - `func deleteAccount() async throws`   // "Hisobni o'chirish": also wipes address, cart, known order statuses
///   - `func onAppBackground()`         // scenePhase .background
///   - `func imageURL(_ imageUrl: String?) -> URL?`
///   - `static let defaultBaseUrl = "https://amora.mirjoy.uz"`
/// Launch argument `--amora-reset` wipes saved session/cart/token first (UI tests).

import Foundation
import Observation

/// Ilova davomida bitta nusxada yashaydigan qismlar. Ekranlar shu yerdan oladi.
@MainActor
@Observable
final class AppContainer {
    static let defaultBaseUrl = "https://amora.mirjoy.uz"

    let baseUrl: String
    let session: SessionStore
    let cart: CartStore
    let api: ApiClient
    let catalog: Catalog
    let account: Account

    // Jonli yangilanishlar: server bilan doimiy ulanish va unga tayanadigan qismlar
    let realtime: Realtime
    let activeOrders: ActiveOrders
    let notifications: OrderNotifier
    let live: LiveUpdates

    // Push: APNs qurilma manzilini serverga yuboradi
    let push: PushTokens

    let location: LocationFinder

    @ObservationIgnored private var foregroundRefresh: Task<Void, Never>?
    // Jonli ulanish shuncha vaqt ichida o'rnatilmasa, ma'lumot odatdagi so'rov bilan o'qiladi
    private static let resyncWaitNanos: UInt64 = 2_500_000_000

    init() {
        if ProcessInfo.processInfo.arguments.contains("--amora-reset") {
            SessionStore.resetAll()
        }
        let url = AppContainer.resolveBaseUrl()
        baseUrl = url
        let session = SessionStore()
        self.session = session
        cart = CartStore()
        let api = ApiClient(baseUrl: url, tokenProvider: { session.token })
        self.api = api
        // Server kirish kalitini tanimadi (401): qaysi so'rov bo'lishidan qat'i nazar, telefon hisobdan
        // chiqadi. Shu orada yangi kalit olingan bo'lsa, eski kalitning xatosi uni o'chirmaydi
        api.onUnauthorized = { [weak session] sentToken in
            guard let session, session.token == sentToken else { return }
            session.signOut()
        }
        let catalog = Catalog(api: api)
        self.catalog = catalog
        account = Account(api: api, session: session)
        let realtime = Realtime(baseUrl: url, tokenProvider: { session.token })
        self.realtime = realtime
        let activeOrders = ActiveOrders(api: api, session: session)
        self.activeOrders = activeOrders
        let notifications = OrderNotifier(session: session)
        self.notifications = notifications
        let live = LiveUpdates(
            realtime: realtime,
            catalog: catalog,
            activeOrders: activeOrders,
            notifier: notifications,
            session: session
        )
        self.live = live
        let push = PushTokens(api: api, session: session)
        self.push = push
        location = LocationFinder()
        push.start()
        // Ilova delegati APNs'dan olgan qurilma manzili shu yerga keladi
        PushTokenInbox.shared.attach { [weak push] token in
            push?.onNewToken(token)
        }
        // Ilova ochiq paytda kelgan buyurtma pushi (bildirishnomalar delegatidan)
        OrderPushInbox.shared.attach { [weak live] change in
            live?.onPush(change)
        }
    }

    private static func resolveBaseUrl() -> String {
        // Muhit o'zgaruvchisi faqat sinov (Debug) yig'ishida ishlaydi: mijozlarga chiqadigan ilovani
        // boshqa serverga burib bo'lmaydi
        #if DEBUG
        if let env = ProcessInfo.processInfo.environment["AMORA_API_BASE_URL"], isUsable(env) {
            return env.trimmingCharacters(in: .whitespacesAndNewlines)
        }
        #endif
        if let plist = Bundle.main.object(forInfoDictionaryKey: "AmoraApiBaseUrl") as? String, isUsable(plist) {
            return plist.trimmingCharacters(in: .whitespacesAndNewlines)
        }
        return defaultBaseUrl
    }

    private static func isUsable(_ value: String) -> Bool {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        return !trimmed.isEmpty && !trimmed.contains("$(") && URL(string: trimmed)?.scheme != nil
    }

    /// Ilova ekranga chiqdi (Android `onStart`): jonli ulanish, menyu, profil va faol buyurtmalar yangilanadi.
    ///
    /// Menyu va faol buyurtmalar bir marta o'qiladi: jonli ulanish o'rnatilishi bilan "resync" keladi va
    /// `LiveUpdates` ikkalasini qayta o'qiydi (ulanishdan oldin boshlangan o'qish o'zgarishni o'tkazib
    /// yuborishi mumkin, shuning uchun aynan o'sha o'qish asosiy). Ulanish kechiksa yoki ishlamasa,
    /// qisqa kutishdan keyin shu yerda o'qiladi. Menyu hali umuman yuklanmagan bo'lsa (ilova endi
    /// ochildi), u kutmasdan darhol so'raladi.
    func onAppForeground() {
        let resyncsBefore = live.resyncCount
        live.onForeground()
        push.retry()
        account.onForeground()
        account.refreshInBackground()
        let catalog = self.catalog
        let activeOrders = self.activeOrders
        let live = self.live
        if catalog.menu == nil {
            Task {
                await catalog.refresh()
            }
        }
        foregroundRefresh?.cancel()
        foregroundRefresh = Task {
            try? await Task.sleep(nanoseconds: AppContainer.resyncWaitNanos)
            if Task.isCancelled || live.resyncCount != resyncsBefore {
                return
            }
            async let menu: Void = catalog.refresh()
            async let orders: Void = activeOrders.refresh()
            _ = await (menu, orders)
        }
    }

    /// Ilova orqa fonga o'tdi (Android `onStop`).
    func onAppBackground() {
        foregroundRefresh?.cancel()
        foregroundRefresh = nil
        live.onBackground()
        account.onBackground()
    }

    /// "Chiqish": server kalitni bekor qiladi, telefondan kalit va profil o'chadi (manzil va savat qoladi).
    func signOut() async {
        await account.signOut()
    }

    /// "Hisobni o'chirish": server hisobni o'chirgach, telefondagi hamma shaxsiy ma'lumot ham o'chadi
    /// (kalit, profil, manzil, savat, buyurtmalarning oxirgi ma'lum holatlari). Server rad etsa
    /// (masalan, tugallanmagan buyurtma bor), xato chiqadi va hech narsa o'zgarmaydi.
    func deleteAccount() async throws {
        try await account.deleteAccount()
        session.clearAddress()
        cart.clear()
        cart.clearOrderKey()
        activeOrders.reset()
        live.resetNotified()
    }

    /// Taom rasmi manzili (server manziliga moslangan).
    func imageURL(_ imageUrl: String?) -> URL? {
        api.imageURL(imageUrl)
    }
}
