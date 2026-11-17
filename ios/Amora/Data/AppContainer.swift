/// Single app-wide dependency container (port of android AmoraApp.kt `AppContainer` + lifecycle hooks).
/// Created once by `AmoraApp`, injected with `.environment(container)`; screens read
/// `@Environment(AppContainer.self) private var container`.
///
/// Surface:
/// - `@MainActor @Observable final class AppContainer`
///   - `init()`
///   - `let baseUrl: String`            // Info.plist `AmoraApiBaseUrl`, env `AMORA_API_BASE_URL` overrides, default https://amora.mirjoy.uz
///   - `let api: ApiClient`, `let session: SessionStore`, `let catalog: Catalog`, `let cart: CartStore`,
///     `let activeOrders: ActiveOrders`, `let account: Account`, `let realtime: Realtime`,
///     `let notifications: OrderNotifier`, `let location: LocationFinder`, `let live: LiveUpdates`, `let push: PushTokens`
///   - `func onAppForeground()`         // scenePhase .active: start realtime, refresh catalog/account/active orders
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

    // Push (hozircha faqat tayyor turgan oqim)
    let push: PushTokens

    let location: LocationFinder

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
        let catalog = Catalog(api: api)
        self.catalog = catalog
        account = Account(api: api, session: session)
        let realtime = Realtime(baseUrl: url, tokenProvider: { session.token })
        self.realtime = realtime
        let activeOrders = ActiveOrders(api: api, session: session)
        self.activeOrders = activeOrders
        let notifications = OrderNotifier(session: session)
        self.notifications = notifications
        live = LiveUpdates(
            realtime: realtime,
            catalog: catalog,
            activeOrders: activeOrders,
            notifier: notifications,
            session: session
        )
        let push = PushTokens(api: api, session: session)
        self.push = push
        location = LocationFinder()
        push.start()
    }

    private static func resolveBaseUrl() -> String {
        if let env = ProcessInfo.processInfo.environment["AMORA_API_BASE_URL"], isUsable(env) {
            return env.trimmingCharacters(in: .whitespacesAndNewlines)
        }
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
    func onAppForeground() {
        live.onForeground()
        push.retry()
        account.refreshInBackground()
        let catalog = self.catalog
        let activeOrders = self.activeOrders
        Task {
            await catalog.refresh()
        }
        Task {
            await activeOrders.refresh()
        }
    }

    /// Ilova orqa fonga o'tdi (Android `onStop`).
    func onAppBackground() {
        live.onBackground()
    }

    /// Taom rasmi manzili (server manziliga moslangan).
    func imageURL(_ imageUrl: String?) -> URL? {
        api.imageURL(imageUrl)
    }
}
