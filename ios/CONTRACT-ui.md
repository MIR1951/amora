# UI kit contract (ios/Amora/App, Theme, Components)

Everything here is `internal` and lives in the `Amora` target. Names and labels are exact.
Kotlin -> Swift: composables became `View` structs with the same name; Kotlin `onClick`/`onBack`/...
parameter names are kept; `@DrawableRes icon: Int` became `icon: AppIcon`; `Modifier` arguments are gone
(use SwiftUI modifiers: `.frame`, `.padding`, ...); colors that defaulted to `MaterialTheme.colorScheme.x`
are `Color? = nil` (nil = that same theme color).

Do NOT redeclare any of these names in feature files (Swift reports "invalid redeclaration" even for
`fileprivate` types with the same name). Avoid also `Color(argb:)`, `Icon*`, `Toast*`, `Glass*`.

## Typical screen skeleton

```swift
struct CartScreen: View {
    @Environment(AppContainer.self) private var container
    @Environment(Router.self) private var router
    @Environment(\.amoraColors) private var colors
    @State private var toast = ToastCenter()
    @State private var confirming = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) { ... }
                .padding(.horizontal, 16)
        }
        .amoraRefreshable(onRefresh: { vm.pullToRefresh() }, isRefreshing: { vm.refreshing })
        .toastHost(toast)                                   // before the bottom inset: sits above the dock
        .safeAreaInset(edge: .top, spacing: 0) {
            GlassTopBar(title: "Savat", onBack: { router.back() }, actions: {
                TextButton(text: "Tozalash", onClick: { container.cart.clear() })
            })
        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            BottomDock { BigButton(text: "Buyurtma berish", onClick: { confirming = true }, trailing: "45 000 so'm") }
        }
        .background(colors.background.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
        .confirmDialog(isPresented: $confirming, title: "Buyurtmani tasdiqlaysizmi?", text: "...",
                       confirmLabel: "Tasdiqlash", dismissLabel: "Bekor qilish", onConfirm: { vm.submit() })
    }
}
```

Glass on iOS needs no state object: Android `rememberGlassState()` / `Modifier.glassSource(glass)` /
`glass = glass` arguments are simply dropped. Any panel drawn ON TOP of scrolling content (overlay,
`.safeAreaInset`, ZStack above a Map) blurs what is behind it.

## App shell (App/)

| Declaration | Notes |
|---|---|
| `@main struct AmoraApp: App` | creates `AppContainer()` + `Router()`, `.environment(container)`, `.environment(router)`; scene active -> `container.onAppForeground()` and `notifications.refreshEnabled()`; background -> `container.onAppBackground()`; URLCache 48 MB / 200 MB |
| `final class AppDelegate: NSObject, UIApplicationDelegate` | sets `UNUserNotificationCenter.current().delegate` |
| `final class NotificationDelegate: NSObject, UNUserNotificationCenterDelegate` | `static let shared`; foreground: banner+list+sound; tap: `NotificationInbox.shared.open(orderId:)` (userInfo `"order_id"`) |
| `@MainActor @Observable final class NotificationInbox` | `static let shared`, `var pendingOrderId: Int?`, `func open(orderId: Int)`; RootView turns it into `router.openOrderFromNotification(id:)` |
| `enum Route: Hashable` | `case orders, profile, cart, address, profileEdit, order(id: Int)` |
| `@MainActor @Observable final class Router` | `init()`, `var path: [Route]` |
| `func open(_ route: Route)` | push; ignored if the same route is on top or within 0.45 s of the previous navigation (double tap) |
| `func back()` | pop one; no-op on the menu; ignored within 0.45 s of the previous navigation |
| `func popToRoot()` | back to the menu |
| `func openCartFromOrders()` | `path = [.cart]` |
| `func openOrderAfterCreate(id: Int)` | `path = [.order(id:)]` |
| `func openOrderFromNotification(id: Int)` | `path = [.order(id:)]` |
| `struct RootView: View` | `RootView()`; `NavigationStack(path:)` rooted at `MenuScreen()`; destinations `OrdersScreen()`, `ProfileScreen(quickEdit: false)`, `CartScreen()`, `AddressScreen()`, `ProfileScreen(quickEdit: true)`, `OrderScreen(orderId: id)`. Applies `.amoraTheme()`, and to every screen `.toolbar(.hidden, for: .navigationBar)` + opaque background (screens may repeat both). Swipe-back stays enabled (UINavigationController extension). |

Screens read: `@Environment(AppContainer.self) private var container`, `@Environment(Router.self) private var router`.

## Theme (Theme/Theme.swift)

| Declaration | Notes |
|---|---|
| `extension Color { init(argb: UInt32) }` | `Color(argb: 0xFFE5432A)` like Kotlin `Color(0xFFE5432A)` |
| `struct AmoraColors` | `isDark: Bool` and `primary, onPrimary, primaryContainer, onPrimaryContainer, secondary, onSecondary, secondaryContainer, onSecondaryContainer, tertiary, onTertiary, tertiaryContainer, onTertiaryContainer, background, onBackground, surface, onSurface, surfaceVariant, onSurfaceVariant, outline, outlineVariant, error, onError, errorContainer, onErrorContainer, surfaceContainerLowest, surfaceContainerLow, surfaceContainer, surfaceContainerHigh, surfaceContainerHighest, scrim` (all `Color`) |
| extra roles (Theme.kt extension properties) | `hint, ink, onInk (white), onInkMuted, success, successContainer, amber, info, infoContainer, cancelledContainer, onCancelledContainer` |
| `static let light`, `static let dark`, `static func resolve(_ scheme: ColorScheme) -> AmoraColors` | |
| `static let inkBlack` | `#17130F` in both themes (Android literal `Color(0xFF17130F)`, e.g. menu cart bar) |
| `static let shadow` | `#17130F`, shadow color |
| `@Environment(\.amoraColors) private var colors` | `EnvironmentValues.amoraColors: AmoraColors` (default `.light`) |
| `View.amoraTheme()` | installs `amoraColors` from `colorScheme` + `.tint(primary)`; RootView does it, sheets inherit it |
| `enum AmoraFont` | `static func display(_ size: CGFloat) -> Font` (Bricolage Regular), `displayBold(_:)`, `body(_:)` (Instrument Sans Regular), `bodyBold(_:)`; names `displayRegularName`, `displayBoldName`, `bodyRegularName`, `bodyBoldName` |
| `struct AmoraTextStyle` | `size, lineHeight, tracking: CGFloat`, `heading, bold: Bool`, `var font: Font`, `var lineSpacing: CGFloat`, `func with(size:lineHeight:tracking:) -> AmoraTextStyle` |
| styles (Theme.kt sizes) | `.displayLarge` 40, `.displayMedium` 36, `.displaySmall` 32, `.headlineLarge` 30, `.headlineMedium` 26, `.headlineSmall` 24, `.titleLarge` 20 (all Bricolage Bold, negative tracking); `.titleMedium` 16, `.titleSmall` 15, `.labelLarge` 15, `.labelMedium` 13, `.labelSmall` 12 +0.7 tracking (Instrument Bold); `.bodyLarge` 15, `.bodyMedium` 14, `.bodySmall` 12.5 (Instrument Regular); `.price` 15.5 / `.priceLarge` 22 (Bricolage Bold, Kotlin `PriceStyle` / `PriceLargeStyle`) |
| `View.amoraText(_ style: AmoraTextStyle)` | font + tracking + line height. Preferred over `.font` for headings (keeps the tight tracking). Kotlin `style = MaterialTheme.typography.titleSmall` -> `.amoraText(.titleSmall)` |
| `extension Font` | `.amoraDisplayLarge, .amoraDisplayMedium, .amoraDisplaySmall, .amoraHeadlineLarge, .amoraHeadlineMedium, .amoraHeadlineSmall, .amoraTitleLarge, .amoraTitleMedium, .amoraTitleSmall, .amoraBodyLarge, .amoraBodyMedium, .amoraBodySmall, .amoraLabelLarge, .amoraLabelMedium, .amoraLabelSmall, .amoraPrice, .amoraPriceLarge` (font only) |
| `enum AmoraRadius` | `extraSmall` 10, `small` 13, `medium` 18, `large` 24, `extraLarge` 30 (Kotlin `MaterialTheme.shapes.*`) |
| `enum AmoraSpacing` | `screen` 16, `cardGap` 12, `card` 16 |
| `@MainActor enum AmoraWindow` | `static var keyWindow: UIWindow?`, `static var width: CGFloat`, `static var bottomInset: CGFloat` (home indicator, no keyboard) |

## Icons (Components/Icons.swift)

| Declaration | Notes |
|---|---|
| `enum AppIcon: String, CaseIterable` | `back, bag, bell, bike, bolt, cash, check, chef, chevron, clock, close, dish, gps, home, info, message, minus, myLocation, phone, pin, plus, receipt, refresh, repeat, search, send, tag, user` (`R.drawable.ic_bag` -> `.bag`, `ic_my_location` -> `.myLocation`) |
| `var assetName: String` | `"ic_back"`, `"ic_my_location"` |
| `var image: Image` | template image (tinted by `foregroundStyle`); `.myLocation` keeps its blue colors |
| `IconImage(_ icon: AppIcon, size: CGFloat = 24, tint: Color? = nil)` | Kotlin `Icon(painterResource(..), null, tint = .., modifier = Modifier.size(..))`; nil tint = current foreground; hidden from VoiceOver |

## Glass (Components/Glass.swift)

| Declaration | Notes |
|---|---|
| `enum GlassTone { case light, dark, fog }` | |
| `enum GlassFade { case top, bottom }` | |
| `GlassBox(cornerRadius: CGFloat = 0, tone: GlassTone = .light, elevation: CGFloat = 0, alignment: Alignment = .topLeading, @ViewBuilder content: () -> Content)` | material blur + tint + light rim + optional shadow; content is clipped to the shape |
| `GlassBox(shape: S, tone: GlassTone = .light, elevation: CGFloat = 0, alignment: Alignment = .topLeading, @ViewBuilder content: () -> Content)` | any `Shape`, e.g. `shape: Circle()`, `shape: Capsule()` |
| `GlassStrip(fade: GlassFade = .bottom)` | fog behind a bar; `.bottom` = fades out at its bottom edge (top bar), `.top` = fades out at its top edge (bottom dock); swallows taps |
| `GlassBackground(shape: S, tone: GlassTone, elevation: CGFloat = 0)` | the glass layers alone (use in `.background(...)`) |
| `View.glassBackground(tone: GlassTone = .light, cornerRadius: CGFloat = 0, elevation: CGFloat = 0)` | modifier form of GlassBox |
| `View.glassElevation(_ elevation: CGFloat)` | the floating-panel shadow |
| `func glassTint(_ tone: GlassTone, _ colors: AmoraColors) -> Color`, `func glassRim(_ tone: GlassTone, _ colors: AmoraColors) -> LinearGradient` | |

## Bars (Components/TopBar.swift)

| Declaration | Notes |
|---|---|
| `GlassTopBar(title: String, onBack: (() -> Void)?)` | back RoundButton (label "Orqaga") + headlineSmall title, fog strip behind (extends under the status bar). Put it in `.safeAreaInset(edge: .top, spacing: 0)` |
| `GlassTopBar(title: String, onBack: (() -> Void)?, @ViewBuilder actions: () -> Actions)` | trailing buttons |
| `GlassTopBar(title: String, onBack: (() -> Void)?, @ViewBuilder below: () -> Below)` | extra row under the title (12 pt gap), e.g. filter chips; give it its own horizontal padding |
| `GlassTopBar(title: String, onBack: (() -> Void)?, @ViewBuilder actions: () -> Actions, @ViewBuilder below: () -> Below)` | both. Always write the `actions:` / `below:` labels (bare trailing closure is ambiguous) |
| `BottomDock(@ViewBuilder content: () -> Content)` | padding 16 sides / 26 top / home-indicator-aware bottom, fog strip fading upwards; put it in `.safeAreaInset(edge: .bottom, spacing: 0)`. Content in a VStack(spacing: 0) |

## Buttons (Components/Buttons.swift)

| Declaration | Notes |
|---|---|
| `BigButton(text: String, onClick: @escaping () -> Void, enabled: Bool = true, loading: Bool = false, trailing: String? = nil)` | full width, height 58, red + glow; disabled = grey; loading = spinner; `trailing` pill on the right. Accessibility label `"text · trailing"` |
| `SoftButton(text: String, onClick: @escaping () -> Void, icon: AppIcon? = nil, enabled: Bool = true, accent: Bool = false, danger: Bool = false)` | full width, height 52, white + border |
| `PillButton(text: String, onClick: @escaping () -> Void)` | text-width red button |
| `TextButton(text: String, onClick: @escaping () -> Void, color: Color? = nil)` | Material TextButton (labelLarge, primary by default) |
| `RoundButton(icon: AppIcon, label: String, onClick: @escaping () -> Void, size: CGFloat = 44, cornerRadius: CGFloat? = nil, tint: Color? = nil, glass: Bool = false)` | `label` = accessibility label (tests tap "Orqaga", "Buyurtmalarim", "Profil"); `cornerRadius` nil = circle; Kotlin `glass = glass` -> `glass: true` |
| `RoundButton(icon:label:onClick:size:cornerRadius:tint:glass:, @ViewBuilder content: () -> C)` | custom inner content instead of the icon (spinner, badge) |
| `AddButton(onClick: @escaping () -> Void)` | 38x38 "+" (accessibility "Qo'shish") |
| `QuantityStepper(quantity: Int, onMinus: @escaping () -> Void, onPlus: @escaping () -> Void, height: CGFloat = 38, corner: CGFloat = 13, buttonWidth: CGFloat = 28, tonal: Bool = false, label: String? = nil, expand: Bool = false)` | buttons "Kamaytirish" / "Ko'paytirish"; animated number |
| `TabChip(text: String, selected: Bool, onClick: @escaping () -> Void)` | |
| `struct PressScaleStyle: ButtonStyle` | `PressScaleStyle(scale: CGFloat = 0.97)` |
| `View.pressScale(_ scale: CGFloat = 0.97)` | Kotlin `Modifier.pressScale(source, x)`: put it on a `Button` (it sets `PressScaleStyle`) |
| `struct RowButtonStyle: ButtonStyle` | `RowButtonStyle()`: light pressed background for list rows |

## Cards and rows (Components/Cards.swift)

| Declaration | Notes |
|---|---|
| `View.softShadow(elevation: CGFloat = 10, alpha: Double = 0.10)` | apply to a background shape (else texts get shadows too) |
| `View.cardBackground(cornerRadius: CGFloat = AmoraRadius.large, color: Color? = nil, shadow: Bool = true)` | clip + white rounded background + soft shadow |
| `SectionCard(padding: CGFloat = 16, onClick: (() -> Void)? = nil, @ViewBuilder content: () -> Content)` | full width, radius 24, content in VStack(alignment: .leading, spacing: 0); with `onClick` it is a Button (scale 0.98) |
| `SectionLabel(_ text: String)` / `SectionLabel(text: String)` | uppercased labelSmall hint, leading 4 / top 10 |
| `LinkRow(icon: AppIcon, label: String, value: String, onClick: (() -> Void)? = nil, highlighted: Bool = false, tileContainer: Color? = nil, tileTint: Color? = nil)` | chevron only with onClick |
| `RowDivider(inset: CGFloat = 72)` | 1 pt outlineVariant, trailing 16 |
| `DashedDivider()` | |
| `SummaryRow(label: String, value: String, valueColor: Color? = nil, loading: Bool = false)` | valueColor set -> titleSmall in that color |
| `IconTile(icon: AppIcon, size: CGFloat = 42, container: Color? = nil, tint: Color? = nil, iconSize: CGFloat = 22)` | defaults primaryContainer / primary, radius size/3 |
| `LogoTile(letter: String, size: CGFloat = 46)` | |
| `ProductImage(url: URL?, iconSize: CGFloat = 44, seed: Int = 0)` | fills the frame you give it (`.frame(...)` + your own `.clipShape`); shimmer while loading, dish icon if nil/failed. `url: container.imageURL(product.imageUrl)` |
| `PriceText(amount: Int, style: AmoraTextStyle = .price, color: Color? = nil, unitColor: Color? = nil, unit: Bool = true)` | "60 000" + small " so'm" (hint); nil color = current foreground |

## Order status (Components/OrderProgress.swift)

| Declaration | Notes |
|---|---|
| `func orderStep(_ status: String) -> Int` | new 1, accepted 2, delivering 3, delivered 4, else 0 |
| `func statusContainerColor(_ status: String, _ colors: AmoraColors) -> Color` | |
| `func statusContentColor(_ status: String, _ colors: AmoraColors) -> Color` | |
| `func statusIcon(_ status: String) -> AppIcon` | clock / chef / bike / check / close |
| `StatusChip(status: String, label: String)` | |
| `OrderProgressBar(status: String, color: Color? = nil, track: Color? = nil)` | 4 segments, height 6, full width; current segment 55% + live left-to-right wave (off with Reduce Motion / when delivered). On the ink card: `OrderProgressBar(status: s, color: delivered ? Color(argb: 0xFF4CCB8C) : colors.primary, track: Color.white.opacity(0.14))` |

## Loading, empty, refresh, dialog (Components/States.swift, Motion.swift)

| Declaration | Notes |
|---|---|
| `LoadingBox()` | centered large spinner, fills space |
| `MessageBox(icon: AppIcon, title: String, text: String? = nil, actionLabel: String? = nil, onAction: (() -> Void)? = nil)` | fills space, centered, scrollable (so `.amoraRefreshable` works on it) |
| `SkeletonBox(width: CGFloat? = nil, height: CGFloat? = nil, cornerRadius: CGFloat = AmoraRadius.small)` | nil width = full width |
| `View.shimmer(cornerRadius: CGFloat = AmoraRadius.small)`, `View.shimmer(_ shape: some Shape)` | overlay skeleton wave (one wave across the whole screen) |
| `View.amoraRefreshable(onRefresh: @escaping () -> Void, isRefreshing: @escaping () -> Bool)` | Kotlin `RefreshBox(refreshing, onRefresh)`: native pull-to-refresh on a ScrollView/List; spinner stays while `isRefreshing()` (max 30 s) |
| `View.amoraRefreshable(action: @escaping () async -> Void)` | same for an async refresh (or use SwiftUI `.refreshable` directly) |
| `ConfirmDialog(title: String, text: String, confirmLabel: String, dismissLabel: String, onConfirm: @escaping () -> Void, onDismiss: @escaping () -> Void)` | the card itself |
| `View.confirmDialog(isPresented: Binding<Bool>, title: String, text: String, confirmLabel: String, dismissLabel: String, onConfirm: @escaping () -> Void, onDismiss: (() -> Void)? = nil)` | blurred dim + card; sets `isPresented = false` itself before calling `onConfirm`/`onDismiss`; apply to the screen's outermost view |
| `enum AmoraMotion` | `static let press, screen, quick: Animation` |

## Toast / snackbar (Components/Toast.swift)

| Declaration | Notes |
|---|---|
| `@MainActor @Observable final class ToastCenter` | `init()`, `private(set) var current: ToastMessage?`, `func show(_ text: String, duration: TimeInterval = ToastCenter.defaultDuration)`, `func dismiss()`, `static let defaultDuration: TimeInterval = 4`. Kotlin `snackbar.showSnackbar(msg)` -> `toast.show(msg)` (no await) |
| `struct ToastMessage: Identifiable, Equatable` | `id: UUID`, `text: String`, `init(text:)` |
| `View.toastHost(_ center: ToastCenter, bottomPadding: CGFloat = 12)` | shows the center's message at the bottom; apply before `.safeAreaInset(edge: .bottom)` so it floats above the dock |
| `View.toast(message: Binding<String?>, duration: TimeInterval = 4, bottomPadding: CGFloat = 12)` | binding API: set a string to show; reset to nil when hidden |
| `ToastHost(center: ToastCenter, bottomPadding: CGFloat = 12)`, `ToastView(text: String, onTap: (() -> Void)? = nil)` | building blocks |

## Fields (Components/Fields.swift)

| Declaration | Notes |
|---|---|
| `View.fieldStyle(container: Color? = nil, cornerRadius: CGFloat = 18, border: Bool = true, minHeight: CGFloat = 56)` | for TextField: bodyLarge, padding, surface background, thin border, red caret. Inside a card: `.fieldStyle(container: .clear, border: false)` |
| `View.fieldBorder(cornerRadius: CGFloat = 18)` | border only |
| `func fieldPrompt(_ text: String, _ colors: AmoraColors) -> Text` | hint-colored placeholder: `TextField("", text: $x, prompt: fieldPrompt("Ism", colors))` |

## Notifications (Components/NotificationPermission.swift)

| Declaration | Notes |
|---|---|
| `View.askNotificationPermissionOnce()` | Kotlin `AskNotificationPermissionOnce(container)`; needs AppContainer in the environment |
| Profile switch | `container.notifications.enabled` + `Task { await container.notifications.toggle() }` (state refreshed on every foreground by AmoraApp) |

## Resources

- `Assets.xcassets`: `ic_*` vector imagesets (template; `ic_my_location` original colors), `AppIcon` (1024 px),
  `AccentColor` (primary light/dark), `LaunchBackground` (brand red, like the Android splash), `LaunchLogo` (white "A").
  Asset symbol generation is OFF (no `Color.accent` / `ImageResource.icBack`); use `AppIcon` / `Image("name")`.
- Fonts: `Resources/Fonts/*.ttf` (registered via `UIAppFonts`) + OFL license texts.
- Regenerate icons: `python3 ios/tools/vector_to_svg.py [--check DIR]`; app icon + launch logo: `python3 ios/tools/make_app_icon.py`.
