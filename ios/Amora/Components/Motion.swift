/// Motion (port of android ui/components/Motion.kt): press "squeeze", skeleton shimmer, timing constants.
/// Screen-to-screen transitions use the native NavigationStack push (same right-to-left slide as Android).
///
/// Surface:
/// - `struct PressScaleStyle: ButtonStyle` - `PressScaleStyle(scale: CGFloat = 0.97)`
/// - `View.pressScale(_ scale: CGFloat = 0.97)` - apply to a `Button` (sets PressScaleStyle on it)
/// - `View.shimmer(cornerRadius: CGFloat = AmoraRadius.small)`, `View.shimmer<S: Shape>(_ shape: S)`
/// - `struct SkeletonBox: View` - `SkeletonBox(width: CGFloat? = nil, height: CGFloat? = nil, cornerRadius: CGFloat = AmoraRadius.small)`
/// - `enum AmoraMotion { static let screen, press, quick }` animations

import SwiftUI

enum AmoraMotion {
    /// Bosilgandagi prujina (Android: dampingRatio 0.55, StiffnessMedium).
    static let press = Animation.spring(response: 0.16, dampingFraction: 0.55)
    /// Tez boshlanib, ohista to'xtaydi (Android ScreenEasing 0.22, 1, 0.36, 1; 420 ms).
    static let screen = Animation.timingCurve(0.22, 1, 0.36, 1, duration: 0.42)
    /// Kichik o'zgarishlar (son, holat): 200 ms.
    static let quick = Animation.easeInOut(duration: 0.2)
}

// MARK: - Bosilgandagi siqilish

/// Tugma bosib turilganda biroz kichrayadi va qo'yib yuborilganda prujinadek joyiga qaytadi.
struct PressScaleStyle: ButtonStyle {
    var scale: CGFloat = 0.97

    init(scale: CGFloat = 0.97) {
        self.scale = scale
    }

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? scale : 1)
            .animation(AmoraMotion.press, value: configuration.isPressed)
    }
}

extension View {
    /// `Button` ga qo'llanadi: bosilganda tugma `scale` gacha kichrayadi (Android `Modifier.pressScale`).
    /// Ichidagi barcha tugmalarga ham o'tadi (SwiftUI `buttonStyle` kabi).
    func pressScale(_ scale: CGFloat = 0.97) -> some View {
        buttonStyle(PressScaleStyle(scale: scale))
    }
}

// MARK: - Skelet

/// Yuklanayotgan kontent o'rnidagi kulrang blok ustidan yorug'lik to'lqini o'tib turadi.
/// To'lqin butun ekran bo'ylab bitta bo'lib yuradi: bloklar alohida-alohida miltillamaydi.
struct ShimmerModifier<S: Shape>: ViewModifier {
    let shape: S
    @Environment(\.amoraColors) private var colors
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    init(shape: S) {
        self.shape = shape
    }

    func body(content: Content) -> some View {
        content.overlay(
            GeometryReader { geo in
                ShimmerLayer(
                    frame: geo.frame(in: .global),
                    size: geo.size,
                    base: colors.outlineVariant,
                    highlight: colors.isDark ? Color.white.opacity(0.09) : Color.white.opacity(0.80),
                    paused: reduceMotion
                )
            }
            .clipShape(shape)
            .allowsHitTesting(false)
        )
    }
}

private struct ShimmerLayer: View {
    let frame: CGRect
    let size: CGSize
    let base: Color
    let highlight: Color
    let paused: Bool

    private static let period: Double = 1.3

    var body: some View {
        let window = AmoraWindow.width
        let total = window > 0 ? window : max(size.width, 1)
        TimelineView(.animation(minimumInterval: nil, paused: paused)) { timeline in
            let seconds = timeline.date.timeIntervalSinceReferenceDate
            let progress = CGFloat(seconds.truncatingRemainder(dividingBy: ShimmerLayer.period) / ShimmerLayer.period)
            let band = total * 0.6
            let start = -band + (total + band) * progress - frame.minX
            ZStack(alignment: .topLeading) {
                Rectangle().fill(base)
                if !paused {
                    LinearGradient(
                        colors: [Color.clear, highlight, Color.clear],
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                    .frame(width: band, height: size.height)
                    .offset(x: start)
                }
            }
            .frame(width: size.width, height: size.height, alignment: .topLeading)
        }
    }
}

extension View {
    /// Skelet to'lqini (burchaklari yumaloq to'rtburchak).
    func shimmer(cornerRadius: CGFloat = AmoraRadius.small) -> some View {
        modifier(ShimmerModifier(shape: RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)))
    }

    /// Skelet to'lqini berilgan shaklda (masalan `Circle()`, `Rectangle()`).
    func shimmer<S: Shape>(_ shape: S) -> some View {
        modifier(ShimmerModifier(shape: shape))
    }
}

/// Yuklanayotgan kontent o'rnida turadigan blok. `width`/`height` berilmasa, bor joyni egallaydi.
struct SkeletonBox: View {
    var width: CGFloat? = nil
    var height: CGFloat? = nil
    var cornerRadius: CGFloat = AmoraRadius.small

    init(width: CGFloat? = nil, height: CGFloat? = nil, cornerRadius: CGFloat = AmoraRadius.small) {
        self.width = width
        self.height = height
        self.cornerRadius = cornerRadius
    }

    var body: some View {
        Color.clear
            .frame(width: width, height: height)
            .frame(maxWidth: width == nil ? .infinity : nil)
            .shimmer(cornerRadius: cornerRadius)
            .accessibilityHidden(true)
    }
}
