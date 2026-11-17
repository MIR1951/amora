/// "Liquid glass" panels (port of android ui/components/Glass.kt). On iOS no glass state is needed:
/// SwiftUI materials blur whatever is drawn behind them, so a panel only has to sit ON TOP of the
/// scrolling content (overlay / `.safeAreaInset`), not inside it.
///
/// Surface:
/// - `enum GlassTone { case light, dark, fog }`, `enum GlassFade { case top, bottom }`
/// - `struct GlassBox<Content: View>: View`
///     `GlassBox(cornerRadius: CGFloat = 0, tone: GlassTone = .light, elevation: CGFloat = 0, alignment: Alignment = .topLeading, @ViewBuilder content: () -> Content)`
///     `GlassBox(shape: some Shape, tone:, elevation:, alignment:, content:)`  (e.g. `shape: Circle()`)
/// - `struct GlassStrip: View` - `GlassStrip(fade: GlassFade = .bottom)` fog behind a top/bottom bar
/// - `View.glassBackground(tone: GlassTone = .light, cornerRadius: CGFloat = 0, elevation: CGFloat = 0)`

import SwiftUI

/// Shisha turi: och (oq), to'q (ko'mir) yoki tuman (fon rangida, satrlar uchun).
enum GlassTone {
    case light
    case dark
    case fog
}

/// `GlassStrip` qaysi chetida asta yo'qolib boradi.
enum GlassFade {
    case top
    case bottom
}

/// Shisha ustidagi rang qatlami (Android HazeTint).
func glassTint(_ tone: GlassTone, _ colors: AmoraColors) -> Color {
    switch tone {
    case .light:
        // Tungi mavzuda xira qatlam quyuqroq: ostidagi xarita doim yorug', matn o'qilishi kerak
        return colors.isDark ? colors.surface.opacity(0.88) : Color.white.opacity(0.60)
    case .dark:
        return colors.ink.opacity(0.84)
    case .fog:
        return colors.background.opacity(0.68)
    }
}

/// Chetidagi yorug'lik aks etgandek ingichka hoshiya (yuqorisi yorqinroq).
func glassRim(_ tone: GlassTone, _ colors: AmoraColors) -> LinearGradient {
    let top: Double
    let bottom: Double
    if tone == .dark {
        top = 0.30
        bottom = 0.06
    } else if colors.isDark {
        top = 0.20
        bottom = 0.04
    } else {
        top = 0.95
        bottom = 0.30
    }
    return LinearGradient(
        colors: [Color.white.opacity(top), Color.white.opacity(bottom)],
        startPoint: .top,
        endPoint: .bottom
    )
}

/// Shisha fon: xiralashtirish, rang qatlami, hoshiya va (ixtiyoriy) soya.
struct GlassBackground<S: Shape>: View {
    let shape: S
    let tone: GlassTone
    var elevation: CGFloat = 0
    @Environment(\.amoraColors) private var colors

    init(shape: S, tone: GlassTone, elevation: CGFloat = 0) {
        self.shape = shape
        self.tone = tone
        self.elevation = elevation
    }

    var body: some View {
        ZStack {
            // Soya faqat eng pastki qatlamda: ichidagi matnlarga soya tushmaydi
            shape.fill(Material.ultraThinMaterial).glassElevation(elevation)
            shape.fill(glassTint(tone, colors))
            shape.stroke(glassRim(tone, colors), lineWidth: 2).clipShape(shape)
        }
    }
}

/// Shisha panel: ortidagi kontent xira ko'rinadi, chetida yorug'lik aks etgandek ingichka hoshiya bor.
/// `elevation`: panel ostidagi soya (suzib turgan panellar uchun).
struct GlassBox<Content: View>: View {
    private let shape: AnyShape
    private let tone: GlassTone
    private let elevation: CGFloat
    private let alignment: Alignment
    private let content: Content

    init(
        cornerRadius: CGFloat = 0,
        tone: GlassTone = .light,
        elevation: CGFloat = 0,
        alignment: Alignment = .topLeading,
        @ViewBuilder content: () -> Content
    ) {
        self.shape = AnyShape(RoundedRectangle(cornerRadius: cornerRadius, style: .continuous))
        self.tone = tone
        self.elevation = elevation
        self.alignment = alignment
        self.content = content()
    }

    init<S: Shape>(
        shape: S,
        tone: GlassTone = .light,
        elevation: CGFloat = 0,
        alignment: Alignment = .topLeading,
        @ViewBuilder content: () -> Content
    ) {
        self.shape = AnyShape(shape)
        self.tone = tone
        self.elevation = elevation
        self.alignment = alignment
        self.content = content()
    }

    var body: some View {
        ZStack(alignment: alignment) {
            content
        }
        .clipShape(shape)
        .contentShape(shape)
        .background(GlassBackground(shape: shape, tone: tone, elevation: elevation))
        // To'q shisha ostidagi xiralashtirish ham to'q bo'lsin
        .environment(\.colorScheme, tone == .dark ? .dark : colorScheme)
    }

    @Environment(\.colorScheme) private var colorScheme
}

extension View {
    /// Suzib turgan panel soyasi (Android `shadow(elevation, ambient 0.20, spot 0.35)` ga yaqin).
    func glassElevation(_ elevation: CGFloat) -> some View {
        shadow(
            color: elevation > 0 ? AmoraColors.shadow.opacity(0.30) : Color.clear,
            radius: elevation * 0.8,
            x: 0,
            y: elevation * 0.45
        )
    }
}

/// Yuqori yoki pastki satr ortidagi "tuman": kontent uning ostiga xiralashib kirib ketadi,
/// bir chetida esa asta yo'qoladi (keskin chegara ko'rinmaydi).
/// Bo'sh joyiga bosilganda bosish ostidagi ro'yxatga o'tib ketmaydi.
struct GlassStrip: View {
    var fade: GlassFade = .bottom
    @Environment(\.amoraColors) private var colors

    init(fade: GlassFade = .bottom) {
        self.fade = fade
    }

    var body: some View {
        ZStack {
            Rectangle().fill(Material.ultraThinMaterial)
            Rectangle().fill(glassTint(.fog, colors))
        }
        .mask { fadeMask }
        .contentShape(Rectangle())
        .onTapGesture {}
        .accessibilityHidden(true)
    }

    private var fadeMask: LinearGradient {
        switch fade {
        case .bottom:
            return LinearGradient(
                stops: [
                    .init(color: .black, location: 0),
                    .init(color: .black, location: 0.70),
                    .init(color: .clear, location: 1),
                ],
                startPoint: .top,
                endPoint: .bottom
            )
        case .top:
            return LinearGradient(
                stops: [
                    .init(color: .clear, location: 0),
                    .init(color: .black, location: 0.34),
                    .init(color: .black, location: 1),
                ],
                startPoint: .top,
                endPoint: .bottom
            )
        }
    }
}

extension View {
    /// Istalgan ko'rinish ortiga shisha fon (GlassBox'ning modifikator ko'rinishi).
    func glassBackground(tone: GlassTone = .light, cornerRadius: CGFloat = 0, elevation: CGFloat = 0) -> some View {
        let shape = RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
        return self
            .clipShape(shape)
            .background(GlassBackground(shape: shape, tone: tone, elevation: elevation))
    }
}
