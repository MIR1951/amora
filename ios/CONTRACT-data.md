# Data layer contract (ios/Amora/Data, ios/Amora/Util)

Everything below is `internal` and lives in module `Amora`. All stores are `@MainActor`; SwiftUI views are
main-actor, so call them directly. `@Observable` classes re-render views that read their properties.
Kotlin -> Swift mapping: `StateFlow.value` -> plain property, `suspend fun` -> `async`, `SharedFlow` ->
`AsyncStream` from `realtime.events()`.

Access in a screen:

```swift
@Environment(AppContainer.self) private var container
```

## Errors

| Swift | Notes |
|---|---|
| `struct ApiError: Error, LocalizedError, Equatable` | Kotlin `ApiException` |
| `var status: Int?` | HTTP status; nil = never reached the server |
| `var code: String?` | server `error.code` (`"shop_closed"`, `"price_changed"`, `"phone_not_verified"`, ...), `"network"`, `"bad_response"`, `"error"` |
| `var message: String` | Uzbek text, show it as is |
| `var total: Int?` | from error body (price_changed) |
| `var isNetwork: Bool` | `code == "network"` |
| `var isUnauthorized: Bool` | `status == 401` |
| `var errorDescription: String?` | `message` |
| `init(status: Int?, code: String?, message: String, total: Int? = nil)` | |
| `static let codeNetwork = "network"`, `static let codeBadResponse = "bad_response"`, `static let network: ApiError` | |
| `static func from(_ error: Error) -> ApiError?` | convert any caught error; **returns nil for task cancellation -> ignore it** |

Every `async throws` API method throws `ApiError`, or `CancellationError` when the calling task is
cancelled (e.g. a `.task` whose view went away). Recommended pattern:

```swift
do { order = try await container.api.order(id: orderId) }
catch { if let e = ApiError.from(error) { self.error = e.message } }
```

## Models (Models.swift) — `Codable, Equatable, Hashable` structs, `var` properties, memberwise init

| Type | Properties |
|---|---|
| `Category` (Identifiable) | `id: Int`, `name: String` |
| `Product` (Identifiable) | `id: Int`, `categoryId: Int?`, `name: String`, `description: String`, `price: Int`, `imageUrl: String?`, `isAvailable: Bool` |
| `MenuData` (Kotlin `Menu`; renamed so it does not shadow `SwiftUI.Menu`) | `categories: [Category]`, `products: [Product]` |
| `Shop` | `cafeName: String`, `phone: String?`, `isOpen: Bool`, `isAcceptingOrders: Bool`, `openTime: String`, `closeTime: String`, `deliveryFee: Int`, `freeDeliveryFrom: Int?`, `minOrderAmount: Int`, `maxDeliveryKm: Double?`, `cafeLatitude: Double?`, `cafeLongitude: Double?`, `bannerTitle: String?`, `bannerText: String?` |
| `Customer` (Identifiable) | `id: Int`, `name: String`, `phone: String`, `phoneVerified: Bool` |
| `TelegramStart` | `code: String`, `appUrl: String` (tg://...), `botUrl: String` (https://t.me/...), `expiresIn: Int` (seconds) |
| `TelegramCheck` | `status: String` ("pending" / "verified"), `token: String?`, `customer: Customer?` |
| `CartItemIn` | `productId: Int`, `quantity: Int` |
| `Problem` | `code: String`, `message: String`, `productId: Int?` |
| `QuoteLine` | `productId: Int`, `name: String`, `price: Int`, `quantity: Int`, `lineTotal: Int` |
| `Quote` | `lines: [QuoteLine]`, `itemsTotal: Int`, `deliveryFee: Int`, `total: Int`, `distanceKm: Double?`, `canOrder: Bool`, `problems: [Problem]`, `discount: Int`, `promoTitle: String?`, `promoError: String?` |
| `OrderIn` | `OrderIn(items: [CartItemIn], latitude: Double, longitude: Double, addressNote: String = "", comment: String = "", name: String? = nil, phone: String? = nil, clientOrderId: String? = nil, expectedTotal: Int? = nil, promoCode: String? = nil, applyAutoPromo: Bool = true)` — `clientOrderId` = `UUID().uuidString` |
| `OrderItem` | `productId: Int?`, `name: String`, `price: Int`, `quantity: Int`, `lineTotal: Int` |
| `StatusEvent` | `status: String`, `statusLabel: String`, `createdAt: String` (ISO, format with `formatTime`) |
| `Order` (Identifiable) | `id: Int`, `status: String`, `statusLabel: String`, `isActive: Bool`, `canCancel: Bool`, `items: [OrderItem]`, `itemsTotal: Int`, `deliveryFee: Int`, `discount: Int`, `promoCode: String?`, `total: Int`, `customerName: String`, `phone: String`, `latitude: Double`, `longitude: Double`, `addressNote: String`, `comment: String`, `rejectReason: String?`, `createdAt: String`, `updatedAt: String`, `history: [StatusEvent]` |
| `OrderList` | `orders: [Order]`, `hasMore: Bool` |
| `QuoteIn`, `TelegramStartIn`, `TelegramCheckIn`, `CustomerUpdate`, `PushTokenUpdate`, `ApiErrorBody`, `ApiErrorInfo` | request/error bodies, used inside ApiClient only |
| `enum OrderStatus` | `static let new = "new"`, `accepted`, `delivering`, `delivered`, `rejected`, `cancelled` (String constants; `Order.status` is a plain String, unknown values are kept) |

Money is `Int` so'm everywhere. Decoding is lenient (missing/null fields take the Kotlin defaults).

## ApiClient (ApiClient.swift) — `container.api`

| Signature | |
|---|---|
| `let baseUrl: String` | without trailing slash |
| `func menu() async throws -> MenuData` | GET /menu |
| `func shop() async throws -> Shop` | GET /shop |
| `func startTelegramVerification(name: String?) async throws -> TelegramStart` | prefer `account.startVerification` |
| `func checkTelegramVerification(code: String) async throws -> TelegramCheck` | prefer `account.checkVerification` |
| `func me() async throws -> Customer` | |
| `func updateName(_ name: String) async throws -> Customer` | prefer `account.saveName` |
| `func updatePushToken(_ token: String) async throws -> Customer` | |
| `func quote(items: [CartItemIn], latitude: Double?, longitude: Double?, promoCode: String? = nil, phone: String? = nil) async throws -> Quote` | sends token if any, `apply_auto_promo: true` |
| `func createOrder(_ order: OrderIn) async throws -> Order` | wrap in `account.withAuth { }` |
| `func orders(limit: Int = 20, offset: Int = 0) async throws -> OrderList` | |
| `func order(id: Int) async throws -> Order` | |
| `func cancelOrder(id: Int) async throws -> Order` | |
| `func imageURL(_ imageUrl: String?) -> URL?` | product image URL rewritten to this server |
| `func resolveImageUrl(_ baseUrl: String, _ imageUrl: String?) -> String?` | free function (Kotlin `resolveImageUrl`) |

## SessionStore (Stores.swift) — `container.session`

| Signature | |
|---|---|
| `struct Profile: Codable, Equatable, Hashable { var name: String; var phone: String; var verified: Bool = false }` | phone is "+998XXXXXXXXX" |
| `struct Address: Codable, Equatable, Hashable { var latitude: Double; var longitude: Double; var note: String }` | |
| `private(set) var profile: Profile?` | observable |
| `private(set) var address: Address?` | observable |
| `private(set) var token: String?` | observable; Keychain-backed |
| `func saveProfile(_ profile: Profile)` | |
| `func saveAddress(_ address: Address)` | AddressScreen "confirm" |
| `func saveToken(_ token: String?)` | |
| `func signOut()` | token removed, profile kept with `verified = false` |
| `var notificationsAsked: Bool` | get/set (UserDefaults, not observable) |
| `var pushToken: String?`, `var pushTokenSentWith: String?` | push stub |
| `func onTokenChange(_ observer: @escaping @MainActor (String?) -> Void)` | internal plumbing |
| `static func resetAll()` | wipe all saved state (launch arg `--amora-reset` does this) |

## CartStore (Stores.swift) — `container.cart`

| Signature | |
|---|---|
| `struct CartLine: Codable, Equatable, Hashable, Identifiable { var productId: Int; var quantity: Int; var id: Int { productId } }` | |
| `static let maxQuantity = 50` | |
| `private(set) var lines: [CartLine]` | observable, insertion order (Kotlin `items.entries` order) — use for lists |
| `var items: [Int: Int]` | productId -> quantity (unordered) |
| `var isEmpty: Bool` | |
| `var totalQuantity: Int` | Kotlin `cart.values.sum()` |
| `var cartItems: [CartItemIn]` | Kotlin `items.toCartItems()` |
| `func quantity(_ productId: Int) -> Int` | |
| `func add(_ productId: Int)`, `func remove(_ productId: Int)` | +1 / -1 (0 removes the line) |
| `func set(_ productId: Int, quantity: Int)` | |
| `func replace(_ lines: [CartLine])` | ordered replace (repeat order) |
| `func replace(_ items: [Int: Int])` | unordered replace (sorted by id) |
| `func retain(_ productIds: Set<Int>)` | drop products no longer on the menu |
| `func clear()` | |

## Catalog (Stores.swift) — `container.catalog`

| Signature | |
|---|---|
| `struct CatalogState: Equatable { var loading: Bool; var error: String?; var shop: Shop?; var menu: MenuData? }` | |
| `private(set) var state: CatalogState` | observable; starts with `loading = true` |
| `var loading: Bool`, `var error: String?`, `var shop: Shop?`, `var menu: MenuData?` | shortcuts into `state` |
| `func refresh(showLoading: Bool = false) async` | never throws; error -> `state.error`, old menu stays; concurrent calls coalesce |

## ActiveOrders (ActiveOrders.swift) — `container.activeOrders`

| Signature | |
|---|---|
| `private(set) var orders: [Order]` | observable; active orders only (menu badge) |
| `func refresh() async` | never throws |
| `func reset()` | signed out / account deleted |
| `var onStatusChange: (@MainActor (Order) -> Void)?` | used by LiveUpdates (missed status changes) |

## Account (Account.swift) — `container.account`

| Signature | |
|---|---|
| `enum VerificationResult: Equatable { case pending; case verified(Profile) }` | |
| `static let codeNotVerified = "phone_not_verified"` | |
| `static let notVerifiedMessage = "Buyurtma berish uchun raqamingizni Telegram orqali tasdiqlang"` | |
| `func saveName(_ name: String)` | saves locally, PATCH /me in background |
| `func refresh() async`, `func refreshInBackground()` | |
| `func startVerification(name: String?) async throws -> TelegramStart` | then open `appUrl` (tg://) if `canOpenURL`, else `botUrl` |
| `func checkVerification(code: String) async throws -> VerificationResult` | poll every ~2 s; saves token + profile on `.verified`; 410 `verification_expired` thrown as ApiError |
| `func withAuth<T>(_ block: () async throws -> T) async throws -> T` | throws `ApiError(code: "phone_not_verified")` if not verified; 401 -> signOut + same error |

## Realtime (Realtime.swift) — `container.realtime`

| Signature | |
|---|---|
| `struct OrderChange: Equatable, Hashable { var orderId: Int; var status: String; var statusLabel: String = ""; var rejectReason: String? = nil }` | |
| `enum LiveEvent: Equatable { case resync, menuChanged, shopChanged, orderChanged(OrderChange) }` | |
| `var orderChange: OrderChange?` (on LiveEvent) | non-nil only for `.orderChanged` |
| `private(set) var connected: Bool` | observable; Kotlin `liveConnected` (poll slower when true) |
| `var isRunning: Bool` | |
| `func events() -> AsyncStream<LiveEvent>` | new subscription per call; ends when the consuming task is cancelled |
| `func start()`, `func stop()`, `func restart()` | managed by AppContainer/LiveUpdates; screens don't call |
| `struct SseMessage`, `struct SseParser`, `func parseLiveEvent(_ message: SseMessage) -> LiveEvent?` | internals |

Screen pattern (Kotlin `container.realtime.events.collect { ... }`):

```swift
.task {
    for await event in container.realtime.events() {
        if event == .resync || event.orderChange?.orderId == orderId { await reload() }
    }
}
```

## LiveUpdates (LiveUpdates.swift) — `container.live`

| Signature | |
|---|---|
| `func setVisibleOrder(_ orderId: Int, status: String? = nil)` | OrderScreen appear / status shown (Kotlin LifecycleResumeEffect) |
| `func clearVisibleOrder(_ orderId: Int)` | OrderScreen disappear |
| `func orderPlaced()` | after successful `createOrder` |
| `func onPush(_ change: OrderChange)` | future push integration |
| `func onForeground()`, `func onBackground()` | called by AppContainer |
| `func isNewerStatus(_ last: String?, _ status: String) -> Bool` | free function |

## OrderNotifier (Notifications.swift) — `container.notifications`

| Signature | |
|---|---|
| `struct OrderNotice: Equatable { var title: String; var text: String }`, `func orderNotice(_ change: OrderChange) -> OrderNotice?` | texts identical to Android |
| `static let extraOrderId = "order_id"` | userInfo key |
| `nonisolated static func orderId(from userInfo: [AnyHashable: Any]) -> Int?` | for the UNUserNotificationCenter delegate (tap -> open order) |
| `private(set) var enabled: Bool` | observable permission state (profile "Bildirishnomalar" row) |
| `func refreshEnabled() async` | call on appear / scenePhase active |
| `func isEnabled() async -> Bool` | |
| `func askPermissionOnce() async` | Kotlin `AskNotificationPermissionOnce` (OrderScreen with active order) |
| `func toggle() async` | Kotlin `NotificationSwitch.toggle`: system prompt if never asked, else opens Settings |
| `func openSettings()` | |
| `func show(_ change: OrderChange, skipIfDelivered: Bool = true)`, `func dismiss(_ orderId: Int)` | used by LiveUpdates |

## LocationFinder (LocationFinder.swift) — `container.location`

| Signature | |
|---|---|
| `enum LocationPermission: Equatable { case notDetermined, denied, restricted, granted }` | |
| `private(set) var permission: LocationPermission` | observable |
| `func hasPermission() -> Bool` | |
| `func requestPermission() async -> Bool` | system prompt if not determined; true if granted (Kotlin permissionLauncher) |
| `func isEnabled() async -> Bool` | location services on (Kotlin `isEnabled()`) |
| `func lastKnown() -> CLLocation?` | instant, maybe stale |
| `func current(timeout: TimeInterval = 15) async -> CLLocation?` | nil on timeout / failure / no permission |
| `func openSettings()` | app page in Settings |

Address "my location" flow (Kotlin `onMyLocation`/`locate`): `if !container.location.hasPermission() { guard await container.location.requestPermission() else { notice = "Joylashuvga ruxsat berilmadi. ..."; return } }`, then `guard await container.location.isEnabled() else { notice = "Telefonda joylashuv (GPS) o'chirilgan. ..." }`, then `lastKnown()` and `await current()`. Screens `import CoreLocation` for `CLLocation`.

## AppContainer (AppContainer.swift)

| Signature | |
|---|---|
| `@MainActor @Observable final class AppContainer` + `init()` | |
| `let baseUrl: String` | Info.plist `AmoraApiBaseUrl`; env var `AMORA_API_BASE_URL` overrides; fallback `https://amora.mirjoy.uz` |
| `let api: ApiClient`, `let session: SessionStore`, `let catalog: Catalog`, `let cart: CartStore`, `let activeOrders: ActiveOrders`, `let account: Account`, `let realtime: Realtime`, `let notifications: OrderNotifier`, `let location: LocationFinder`, `let live: LiveUpdates`, `let push: PushTokens` | |
| `func onAppForeground()` | scenePhase `.active`: realtime start, refresh catalog/account/active orders, push retry |
| `func onAppBackground()` | scenePhase `.background`: stops realtime (kept while iOS grants background time if there are active orders) |
| `func imageURL(_ imageUrl: String?) -> URL?` | same as `api.imageURL` |
| `static let defaultBaseUrl = "https://amora.mirjoy.uz"` | |
| launch argument `--amora-reset` | clears token, profile, address, cart before stores load (UI tests) |

## PushTokens (Push.swift) — `container.push` (stub, no provider yet)

`func start()`, `func onNewToken(_ token: String)`, `func retry()`.

## Format (Util/Format.swift) — free functions

| Signature | Example |
|---|---|
| `let localPhoneLength: Int` | 9 |
| `func formatSum(_ amount: Int) -> String` | 35000 -> "35 000 so'm" |
| `func formatNumber(_ amount: Int) -> String` | 1250000 -> "1 250 000" |
| `func localPhoneDigits(_ input: String) -> String` | "+998 90 123 45 67" -> "901234567" |
| `func fullPhone(_ localDigits: String) -> String?` | "901234567" -> "+998901234567" |
| `func formatPhone(_ phone: String) -> String` | "+998901234567" -> "+998 90 123 45 67" |
| `func parseIsoDate(_ text: String) -> Date?` | |
| `func parseIsoMillis(_ text: String) -> Int64?` | |
| `func formatTime(_ iso: String) -> String` | "19:03" (Asia/Tashkent) |
| `func formatDateTime(_ iso: String) -> String` | "15-noyabr, 19:03" |
| `func distanceKm(_ lat1: Double, _ lon1: Double, _ lat2: Double, _ lon2: Double) -> Double` | |
