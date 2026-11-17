/// Amora theme (port of android ui/theme/Theme.kt): colors (light + dark), fonts, text styles, radii.
///
/// Surface:
/// - `struct AmoraColors` - every Material scheme role of Theme.kt plus the extra roles
///   (hint, ink, onInk, onInkMuted, success, successContainer, amber, info, infoContainer, ...).
///   `static let light`, `static let dark`, `static func resolve(_ scheme: ColorScheme) -> AmoraColors`.
/// - `@Environment(\.amoraColors) private var colors` (installed by `.amoraTheme()` in RootView).
/// - `extension Color { init(argb: UInt32) }`             // Color(argb: 0xFFE5432A)
/// - `enum AmoraFont { display, displayBold, body, bodyBold }` (Bricolage Grotesque / Instrument Sans)
/// - `struct AmoraTextStyle` + `.amoraText(_:)` modifier (font + letter spacing + line height),
///   styles: displayLarge ... labelSmall, price, priceLarge (same sizes as Theme.kt).
/// - `extension Font { static let amoraHeadlineLarge ... amoraLabelSmall, amoraPrice, amoraPriceLarge }`
/// - `enum AmoraRadius` (extraSmall 10, small 13, medium 18, large 24, extraLarge 30), `enum AmoraSpacing`.

import SwiftUI
import UIKit

// Amora dizayn asosi ("Issiq tandir" maketi). To'rtta rang, har biri o'z ma'nosiga ega:
//   pomidor qizil  - faqat harakat uchun: tugma, "+", narx tanlagich
//   ko'mir         - kuchli bloklar: banner, savat paneli, buyurtma holati
//   non oq         - iliq fon, ustida oq kartochkalar
//   rayhon yashil  - faqat ijobiy holat: "Ochiq", "Bepul", "Yetkazildi"
// Kafe o'z logotipi va ranglarini bersa, faqat shu fayl o'zgaradi.

extension Color {
    /// Android uslubidagi rang: 0xAARRGGBB.
    init(argb: UInt32) {
        let alpha = Double((argb >> 24) & 0xFF) / 255.0
        let red = Double((argb >> 16) & 0xFF) / 255.0
        let green = Double((argb >> 8) & 0xFF) / 255.0
        let blue = Double(argb & 0xFF) / 255.0
        self.init(.sRGB, red: red, green: green, blue: blue, opacity: alpha)
    }
}

/// Ilova ranglari. Ekranlarda: `@Environment(\.amoraColors) private var colors`.
struct AmoraColors {
    var isDark: Bool

    var primary: Color
    var onPrimary: Color
    var primaryContainer: Color
    var onPrimaryContainer: Color
    var secondary: Color
    var onSecondary: Color
    var secondaryContainer: Color
    var onSecondaryContainer: Color
    var tertiary: Color
    var onTertiary: Color
    var tertiaryContainer: Color
    var onTertiaryContainer: Color
    var background: Color
    var onBackground: Color
    var surface: Color
    var onSurface: Color
    var surfaceVariant: Color
    var onSurfaceVariant: Color
    var outline: Color
    var outlineVariant: Color
    var error: Color
    var onError: Color
    var errorContainer: Color
    var onErrorContainer: Color
    var surfaceContainerLowest: Color
    var surfaceContainerLow: Color
    var surfaceContainer: Color
    var surfaceContainerHigh: Color
    var surfaceContainerHighest: Color
    var scrim: Color

    // Material sxemasida yo'q, lekin maketda bor ranglar.

    /// Ikkinchi darajali yozuvlar: belgilar ostidagi izoh, sana, maydon nomi.
    var hint: Color
    /// "Ko'mir" bloklar foni: banner, savat paneli, buyurtma holati. Ustidagi yozuv har doim oq.
    var ink: Color
    /// Ko'mir blok ustidagi asosiy yozuv (oq).
    var onInk: Color
    /// Ko'mir blok ustidagi ikkinchi darajali yozuv.
    var onInkMuted: Color
    var success: Color
    var successContainer: Color
    /// Sariq urg'u: "jonli holat" nuqtasi, chaqmoq belgisi.
    var amber: Color
    /// Qabul qiluvchi qatoridagi ko'k belgi.
    var info: Color
    var infoContainer: Color
    /// Bekor qilingan buyurtma belgisi foni va yozuvi (statusContainerColor / statusContentColor).
    var cancelledContainer: Color
    var onCancelledContainer: Color

    /// Ikkala mavzuda ham bir xil "ko'mir" (Android `Color(0xFF17130F)`): savat paneli, soyalar.
    static let inkBlack = Color(argb: 0xFF17130F)
    /// Soyalar rangi (Android softShadow).
    static let shadow = Color(argb: 0xFF17130F)

    static let light = AmoraColors(
        isDark: false,
        primary: Color(argb: 0xFFE5432A),
        onPrimary: Color(argb: 0xFFFFFFFF),
        primaryContainer: Color(argb: 0xFFFDECE7),
        onPrimaryContainer: Color(argb: 0xFFC7321C),
        secondary: Color(argb: 0xFF17130F),
        onSecondary: Color(argb: 0xFFFFFFFF),
        secondaryContainer: Color(argb: 0xFFF6F2EC),
        onSecondaryContainer: Color(argb: 0xFF17130F),
        tertiary: Color(argb: 0xFFF2A33A),
        onTertiary: Color(argb: 0xFF17130F),
        tertiaryContainer: Color(argb: 0xFFFDF1DD),
        onTertiaryContainer: Color(argb: 0xFF6B4410),
        background: Color(argb: 0xFFF6F2EC),
        onBackground: Color(argb: 0xFF17130F),
        surface: Color(argb: 0xFFFFFFFF),
        onSurface: Color(argb: 0xFF17130F),
        surfaceVariant: Color(argb: 0xFFF6F2EC),
        onSurfaceVariant: Color(argb: 0xFF5E564F),
        outline: Color(argb: 0xFFD8D0C5),
        outlineVariant: Color(argb: 0xFFECE6DE),
        error: Color(argb: 0xFFC7321C),
        onError: Color(argb: 0xFFFFFFFF),
        errorContainer: Color(argb: 0xFFFDECE7),
        onErrorContainer: Color(argb: 0xFFC7321C),
        surfaceContainerLowest: Color(argb: 0xFFFFFFFF),
        surfaceContainerLow: Color(argb: 0xFFFFFFFF),
        surfaceContainer: Color(argb: 0xFFFFFFFF),
        surfaceContainerHigh: Color(argb: 0xFFFFFFFF),
        surfaceContainerHighest: Color(argb: 0xFFF6F2EC),
        scrim: Color(argb: 0xFF000000),
        hint: Color(argb: 0xFF9C938A),
        ink: Color(argb: 0xFF17130F),
        onInk: Color(argb: 0xFFFFFFFF),
        onInkMuted: Color(argb: 0xFFBDB3A9),
        success: Color(argb: 0xFF1E9E61),
        successContainer: Color(argb: 0xFFE3F5EB),
        amber: Color(argb: 0xFFF2A33A),
        info: Color(argb: 0xFF3B4A8C),
        infoContainer: Color(argb: 0xFFEEF0F6),
        cancelledContainer: Color(argb: 0xFFEFEAE3),
        onCancelledContainer: Color(argb: 0xFF6F665E)
    )

    static let dark = AmoraColors(
        isDark: true,
        primary: Color(argb: 0xFFF0563C),
        onPrimary: Color(argb: 0xFFFFFFFF),
        primaryContainer: Color(argb: 0xFF3D1B13),
        onPrimaryContainer: Color(argb: 0xFFFFB4A3),
        secondary: Color(argb: 0xFFF4EFE8),
        onSecondary: Color(argb: 0xFF17130F),
        secondaryContainer: Color(argb: 0xFF28241F),
        onSecondaryContainer: Color(argb: 0xFFF4EFE8),
        tertiary: Color(argb: 0xFFF2A33A),
        onTertiary: Color(argb: 0xFF17130F),
        tertiaryContainer: Color(argb: 0xFF443008),
        onTertiaryContainer: Color(argb: 0xFFFFDFA8),
        background: Color(argb: 0xFF12100E),
        onBackground: Color(argb: 0xFFF4EFE8),
        surface: Color(argb: 0xFF1D1A17),
        onSurface: Color(argb: 0xFFF4EFE8),
        surfaceVariant: Color(argb: 0xFF28241F),
        onSurfaceVariant: Color(argb: 0xFFB9B0A6),
        outline: Color(argb: 0xFF4A443E),
        outlineVariant: Color(argb: 0xFF2F2A25),
        error: Color(argb: 0xFFFF8A75),
        onError: Color(argb: 0xFF4A0F05),
        errorContainer: Color(argb: 0xFF3D1B13),
        onErrorContainer: Color(argb: 0xFFFFB4A3),
        surfaceContainerLowest: Color(argb: 0xFF12100E),
        surfaceContainerLow: Color(argb: 0xFF1D1A17),
        surfaceContainer: Color(argb: 0xFF1D1A17),
        surfaceContainerHigh: Color(argb: 0xFF24201C),
        surfaceContainerHighest: Color(argb: 0xFF28241F),
        scrim: Color(argb: 0xFF000000),
        hint: Color(argb: 0xFF8A8178),
        ink: Color(argb: 0xFF26221E),
        onInk: Color(argb: 0xFFFFFFFF),
        onInkMuted: Color(argb: 0xFFBDB3A9),
        success: Color(argb: 0xFF4CCB8C),
        successContainer: Color(argb: 0xFF123624),
        amber: Color(argb: 0xFFF2A33A),
        info: Color(argb: 0xFFA9B6F0),
        infoContainer: Color(argb: 0xFF232838),
        cancelledContainer: Color(argb: 0xFF28241F),
        onCancelledContainer: Color(argb: 0xFFB9B0A6)
    )

    static func resolve(_ scheme: ColorScheme) -> AmoraColors {
        scheme == .dark ? dark : light
    }
}

private struct AmoraColorsKey: EnvironmentKey {
    static let defaultValue: AmoraColors = .light
}

extension EnvironmentValues {
    /// Joriy mavzu ranglari (yorug' yoki tungi). `.amoraTheme()` o'rnatadi.
    var amoraColors: AmoraColors {
        get { self[AmoraColorsKey.self] }
        set { self[AmoraColorsKey.self] = newValue }
    }
}

/// Tizim mavzusiga qarab `amoraColors` ni o'rnatadi va asosiy rangni tugmalar uchun beradi.
struct AmoraThemeModifier: ViewModifier {
    @Environment(\.colorScheme) private var colorScheme

    init() {}

    func body(content: Content) -> some View {
        let colors = AmoraColors.resolve(colorScheme)
        return content
            .environment(\.amoraColors, colors)
            .tint(colors.primary)
    }
}

extension View {
    /// Ranglarni o'rnatadi. RootView'da bir marta qo'llangan; alohida oynalar (sheet) ham uni meros oladi.
    func amoraTheme() -> some View {
        modifier(AmoraThemeModifier())
    }
}

// MARK: - Shriftlar

// Sarlavha va narxlar: Bricolage Grotesque (xarakterli, zich). Matn: Instrument Sans (toza, o'qilishi oson).
// Ikkalasi ham ochiq litsenziyali (OFL), matni Resources/Fonts papkasida.
enum AmoraFont {
    static let displayRegularName = "BricolageGrotesque-Regular"
    static let displayBoldName = "BricolageGrotesque-Bold"
    static let bodyRegularName = "InstrumentSans-Regular"
    static let bodyBoldName = "InstrumentSans-Bold"

    /// Bricolage Grotesque, oddiy.
    static func display(_ size: CGFloat) -> Font {
        Font.custom(displayRegularName, size: size)
    }

    /// Bricolage Grotesque, qalin: sarlavhalar va narxlar.
    static func displayBold(_ size: CGFloat) -> Font {
        Font.custom(displayBoldName, size: size)
    }

    /// Instrument Sans, oddiy: matn.
    static func body(_ size: CGFloat) -> Font {
        Font.custom(bodyRegularName, size: size)
    }

    /// Instrument Sans, qalin: tugmalar, sarlavhachalar.
    static func bodyBold(_ size: CGFloat) -> Font {
        Font.custom(bodyBoldName, size: size)
    }
}

/// Android `TextStyle` ning o'xshashi: shrift, o'lcham, qator balandligi va harflar orasidagi masofa.
struct AmoraTextStyle {
    var size: CGFloat
    var lineHeight: CGFloat
    var tracking: CGFloat
    var heading: Bool
    var bold: Bool

    var font: Font {
        if heading {
            return bold ? AmoraFont.displayBold(size) : AmoraFont.display(size)
        }
        return bold ? AmoraFont.bodyBold(size) : AmoraFont.body(size)
    }

    /// Qatorlar orasidagi qo'shimcha masofa (SwiftUI `lineSpacing`): qator balandligi - shriftning o'z balandligi.
    var lineSpacing: CGFloat {
        max(0, lineHeight - size * 1.2)
    }

    /// Shu uslubning boshqa o'lchamdagi nusxasi.
    func with(size newSize: CGFloat, lineHeight newLineHeight: CGFloat? = nil, tracking newTracking: CGFloat? = nil) -> AmoraTextStyle {
        AmoraTextStyle(
            size: newSize,
            lineHeight: newLineHeight ?? lineHeight * newSize / size,
            tracking: newTracking ?? tracking,
            heading: heading,
            bold: bold
        )
    }

    private static func headingStyle(_ size: CGFloat, _ line: CGFloat, _ spacing: CGFloat) -> AmoraTextStyle {
        AmoraTextStyle(size: size, lineHeight: line, tracking: spacing, heading: true, bold: true)
    }

    private static func bodyStyle(_ size: CGFloat, _ line: CGFloat, bold: Bool, _ spacing: CGFloat = 0) -> AmoraTextStyle {
        AmoraTextStyle(size: size, lineHeight: line, tracking: spacing, heading: false, bold: bold)
    }

    static let displayLarge = headingStyle(40, 42, -1.4)
    static let displayMedium = headingStyle(36, 38, -1.2)
    static let displaySmall = headingStyle(32, 33, -1.1)
    static let headlineLarge = headingStyle(30, 32, -0.9)
    static let headlineMedium = headingStyle(26, 30, -0.6)
    static let headlineSmall = headingStyle(24, 28, -0.5)
    static let titleLarge = headingStyle(20, 24, -0.4)
    static let titleMedium = bodyStyle(16, 22, bold: true)
    static let titleSmall = bodyStyle(15, 20, bold: true)
    static let bodyLarge = bodyStyle(15, 22, bold: false)
    static let bodyMedium = bodyStyle(14, 20, bold: false)
    static let bodySmall = bodyStyle(12.5, 17, bold: false)
    static let labelLarge = bodyStyle(15, 20, bold: true)
    static let labelMedium = bodyStyle(13, 18, bold: true)
    static let labelSmall = bodyStyle(12, 16, bold: true, 0.7)

    /// Narx: raqam sarlavha shriftida, katta va zich. Ko'z avval raqamni ko'radi.
    static let price = headingStyle(15.5, 20, -0.3)
    /// Jami summa kabi asosiy narxlar.
    static let priceLarge = headingStyle(22, 26, -0.4)
}

extension View {
    /// Matnga Amora uslubini beradi: shrift, harflar orasidagi masofa va qator balandligi.
    func amoraText(_ style: AmoraTextStyle) -> some View {
        self
            .font(style.font)
            .tracking(style.tracking)
            .lineSpacing(style.lineSpacing)
    }
}

extension Font {
    static let amoraDisplayLarge = AmoraTextStyle.displayLarge.font
    static let amoraDisplayMedium = AmoraTextStyle.displayMedium.font
    static let amoraDisplaySmall = AmoraTextStyle.displaySmall.font
    static let amoraHeadlineLarge = AmoraTextStyle.headlineLarge.font
    static let amoraHeadlineMedium = AmoraTextStyle.headlineMedium.font
    static let amoraHeadlineSmall = AmoraTextStyle.headlineSmall.font
    static let amoraTitleLarge = AmoraTextStyle.titleLarge.font
    static let amoraTitleMedium = AmoraTextStyle.titleMedium.font
    static let amoraTitleSmall = AmoraTextStyle.titleSmall.font
    static let amoraBodyLarge = AmoraTextStyle.bodyLarge.font
    static let amoraBodyMedium = AmoraTextStyle.bodyMedium.font
    static let amoraBodySmall = AmoraTextStyle.bodySmall.font
    static let amoraLabelLarge = AmoraTextStyle.labelLarge.font
    static let amoraLabelMedium = AmoraTextStyle.labelMedium.font
    static let amoraLabelSmall = AmoraTextStyle.labelSmall.font
    static let amoraPrice = AmoraTextStyle.price.font
    static let amoraPriceLarge = AmoraTextStyle.priceLarge.font
}

// MARK: - Burchaklar va chekinishlar

/// Android `AmoraShapes`: burchaklar oilasi.
enum AmoraRadius {
    static let extraSmall: CGFloat = 10
    static let small: CGFloat = 13
    static let medium: CGFloat = 18
    static let large: CGFloat = 24
    static let extraLarge: CGFloat = 30
}

/// Bir xil chekinishlar: ekran cheti 16, kartochkalar orasi 12.
enum AmoraSpacing {
    static let screen: CGFloat = 16
    static let cardGap: CGFloat = 12
    static let card: CGFloat = 16
}

// MARK: - Oyna o'lchamlari

/// Ilova oynasi (kalit oyna) haqida: kenglik va pastki xavfsiz hudud (uy tugmasi chizig'i).
@MainActor
enum AmoraWindow {
    static var keyWindow: UIWindow? {
        let scenes = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
        for scene in scenes {
            if let window = scene.windows.first(where: { $0.isKeyWindow }) {
                return window
            }
        }
        return scenes.first?.windows.first
    }

    /// Oyna kengligi (yo'q bo'lsa 0).
    static var width: CGFloat {
        keyWindow?.bounds.width ?? 0
    }

    /// Pastki xavfsiz hudud: uy tugmasi chizig'i balandligi (eski iPhone'larda 0). Klaviatura kirmaydi.
    static var bottomInset: CGFloat {
        keyWindow?.safeAreaInsets.bottom ?? 0
    }
}
