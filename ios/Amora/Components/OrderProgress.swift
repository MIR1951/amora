/// Order status visuals (port of the "Buyurtma holati" part of android ui/components/Components.kt).
///
/// Surface:
/// - `func orderStep(_ status: String) -> Int`                       // 1 new, 2 accepted, 3 delivering, 4 delivered, 0 cancelled/rejected
/// - `func statusContainerColor(_ status: String, _ colors: AmoraColors) -> Color`
/// - `func statusContentColor(_ status: String, _ colors: AmoraColors) -> Color`
/// - `func statusIcon(_ status: String) -> AppIcon`                  // clock, chef, bike, check, close
/// - `StatusChip(status: String, label: String)`
/// - `OrderProgressBar(status: String, color: Color? = nil, track: Color? = nil)`
///   four segments; passed ones full, the current one 55% with a live left-to-right wave
///   (no wave when Reduce Motion is on or the order is finished). Height 6, full width.

import SwiftUI

/// Buyurtma nechanchi bosqichda: 1 yuborildi, 2 qabul qilindi, 3 yo'lda, 4 yetkazildi, 0 bekor bo'lgan.
func orderStep(_ status: String) -> Int {
    switch status {
    case OrderStatus.new:
        return 1
    case OrderStatus.accepted:
        return 2
    case OrderStatus.delivering:
        return 3
    case OrderStatus.delivered:
        return 4
    default:
        return 0
    }
}

/// Buyurtma holatiga mos fon rangi: yashil (yetkazildi), qizil (rad etildi), kulrang (bekor), sariq (faol).
func statusContainerColor(_ status: String, _ colors: AmoraColors) -> Color {
    switch status {
    case OrderStatus.delivered:
        return colors.successContainer
    case OrderStatus.rejected:
        return colors.errorContainer
    case OrderStatus.cancelled:
        return colors.cancelledContainer
    default:
        return colors.tertiaryContainer
    }
}

/// `statusContainerColor` ustidagi belgi va yozuv rangi.
func statusContentColor(_ status: String, _ colors: AmoraColors) -> Color {
    switch status {
    case OrderStatus.delivered:
        return colors.success
    case OrderStatus.rejected:
        return colors.onErrorContainer
    case OrderStatus.cancelled:
        return colors.onCancelledContainer
    default:
        return colors.onTertiaryContainer
    }
}

/// Buyurtma holatiga mos belgi: soat, oshpaz qalpog'i, kuryer, tasdiq yoki xoch.
func statusIcon(_ status: String) -> AppIcon {
    switch status {
    case OrderStatus.new:
        return .clock
    case OrderStatus.accepted:
        return .chef
    case OrderStatus.delivering:
        return .bike
    case OrderStatus.delivered:
        return .check
    default:
        return .close
    }
}

/// Buyurtma holati yozilgan rangli belgi: nuqta va yozuv.
struct StatusChip: View {
    let status: String
    let label: String
    @Environment(\.amoraColors) private var colors

    init(status: String, label: String) {
        self.status = status
        self.label = label
    }

    var body: some View {
        let content = statusContentColor(status, colors)
        HStack(spacing: 6) {
            Circle()
                .fill(content)
                .frame(width: 6, height: 6)
            Text(label)
                .font(AmoraTextStyle.labelSmall.font)
                .foregroundColor(content)
                .lineLimit(1)
                .truncationMode(.tail)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .fill(statusContainerColor(status, colors))
        )
        .accessibilityElement(children: .combine)
    }
}

/// To'rt bo'lakli chiziq (Android `OrderProgress.kt` bilan bir xil): o'tilgan bosqichlar to'la,
/// hozirgi bosqich och rangda va ichida chapdan o'ngga to'lqin oqib turadi (to'lib boradi, so'ng
/// o'ngga oqib chiqadi va yana boshlanadi). Holat o'zgarganda tugagan bo'lak ohista to'ladi.
/// "Harakatni kamaytirish" yoqilgan bo'lsa, hozirgi bo'lak yarim to'lgan holda jim turadi.
struct OrderProgressBar: View {
    let status: String
    var color: Color? = nil
    var track: Color? = nil
    @Environment(\.amoraColors) private var colors
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    init(status: String, color: Color? = nil, track: Color? = nil) {
        self.status = status
        self.color = color
        self.track = track
    }

    var body: some View {
        let step = orderStep(status)
        let fill = color ?? colors.primary
        let trackColor = track ?? colors.outlineVariant
        let delivered = status == OrderStatus.delivered
        HStack(spacing: 6) {
            ForEach(0..<4, id: \.self) { index in
                let active = !delivered && step > 0 && index == step - 1
                ProgressSegment(
                    fraction: OrderProgressBar.fraction(
                        delivered: delivered, step: step, index: index, animated: !reduceMotion
                    ),
                    color: fill,
                    track: trackColor,
                    active: active,
                    live: active && !reduceMotion
                )
            }
        }
        .frame(maxWidth: .infinity)
        .frame(height: 6)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Bosqich \(max(step, 0)) / 4")
    }

    static func fraction(delivered: Bool, step: Int, index: Int, animated: Bool) -> CGFloat {
        if delivered || index < step - 1 {
            return 1
        }
        if index == step - 1 && !animated {
            return 0.55
        }
        return 0
    }
}

private struct ProgressSegment: View {
    let fraction: CGFloat
    let color: Color
    let track: Color
    let active: Bool
    let live: Bool

    var body: some View {
        GeometryReader { geo in
            let width = geo.size.width
            ZStack(alignment: .leading) {
                Rectangle().fill(track)
                if active {
                    Rectangle().fill(color.opacity(0.22))
                }
                Rectangle()
                    .fill(color)
                    .frame(width: width * fraction)
                    .animation(.easeInOut(duration: 0.6), value: fraction)
                if live {
                    SweepLayer(width: width, color: color)
                }
            }
        }
        .frame(height: 6)
        .clipShape(Capsule())
    }
}

/// To'lqinning ikki uchi: oldingi uchi 0-1.15 s da bo'lakni to'ldiradi, orqa uchi 0.55-1.8 s da
/// ergashadi. Aylanish oxirida ikkalasi o'ng chetda uchrashadi, shuning uchun qayta boshlanganda
/// sakrash ko'rinmaydi (Android'dagi keyframes bilan bir xil).
private struct SweepLayer: View {
    let width: CGFloat
    let color: Color

    private static let period: Double = 1.8
    private static let curve = UnitCurve.bezier(
        startControlPoint: UnitPoint(x: 0.4, y: 0),
        endControlPoint: UnitPoint(x: 0.2, y: 1)
    )

    private static func eased(_ time: Double, from start: Double, to end: Double) -> CGFloat {
        if time <= start { return 0 }
        if time >= end { return 1 }
        return CGFloat(curve.value(at: (time - start) / (end - start)))
    }

    var body: some View {
        TimelineView(.animation) { timeline in
            let time = timeline.date.timeIntervalSinceReferenceDate
                .truncatingRemainder(dividingBy: SweepLayer.period)
            let head = SweepLayer.eased(time, from: 0, to: 1.15)
            let tail = SweepLayer.eased(time, from: 0.55, to: SweepLayer.period)
            let left = width * tail
            let band = max(width * head - left, 0)
            Capsule()
                .fill(
                    LinearGradient(
                        colors: [color.opacity(0.45), color],
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                )
                .frame(width: band)
                .offset(x: left)
                .frame(width: width, alignment: .leading)
        }
        .allowsHitTesting(false)
    }
}
