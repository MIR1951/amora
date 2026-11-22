/// Cards, rows, food image and price (port of the matching parts of android ui/components/Components.kt).
///
/// Surface (all `View` structs unless noted):
/// - `View.softShadow(elevation: CGFloat = 10, alpha: Double = 0.10)`  (apply to a background SHAPE)
/// - `View.cardBackground(cornerRadius: CGFloat = AmoraRadius.large, color: Color? = nil, shadow: Bool = true)`
/// - `ProductImage(url: URL?, iconSize: CGFloat = 44, seed: Int = 0)`         // fills the frame you give it
/// - `PriceText(amount: Int, style: AmoraTextStyle = .price, color: Color? = nil, unitColor: Color? = nil, unit: Bool = true)`
/// - `IconTile(icon: AppIcon, size: CGFloat = 42, container: Color? = nil, tint: Color? = nil, iconSize: CGFloat = 22)`
/// - `LogoTile(letter: String, size: CGFloat = 46)`
/// - `SectionCard(padding: CGFloat = 16, onClick: (() -> Void)? = nil, @ViewBuilder content:)`
/// - `SectionLabel(_ text: String)` / `SectionLabel(text: String)`
/// - `LinkRow(icon: AppIcon, label: String, value: String, onClick: (() -> Void)? = nil, highlighted: Bool = false, tileContainer: Color? = nil, tileTint: Color? = nil)`
/// - `RowDivider(inset: CGFloat = 72)`, `DashedDivider()`
/// - `SummaryRow(label: String, value: String, valueColor: Color? = nil, loading: Bool = false)`

import SwiftUI

// Ilovaning umumiy "g'ishtlari": kartochka, narx, belgi, qatorlar.
// Yangi ekran shu yerdagi bo'laklardan yig'iladi, shunda hamma joyda bir xil chekinish (16),
// bir xil burchaklar va bir xil belgilar uslubi saqlanadi.

// MARK: - Soya

extension View {
    /// Juda yengil soya: kartochka fon ustida qog'ozdek "suzib" turadi.
    /// Matnlarga soya tushmasligi uchun fon shakliga qo'llang: `.background(RoundedRectangle(...).fill(..).softShadow())`.
    func softShadow(elevation: CGFloat = 10, alpha: Double = 0.10) -> some View {
        shadow(color: AmoraColors.shadow.opacity(alpha), radius: elevation * 0.9, x: 0, y: elevation * 0.45)
    }

    /// Oq kartochka foni: yumaloq burchak va yengil soya (SectionCard foni).
    func cardBackground(cornerRadius: CGFloat = AmoraRadius.large, color: Color? = nil, shadow: Bool = true) -> some View {
        modifier(CardBackgroundModifier(cornerRadius: cornerRadius, color: color, shadow: shadow))
    }
}

struct CardBackgroundModifier: ViewModifier {
    let cornerRadius: CGFloat
    let color: Color?
    let shadow: Bool
    @Environment(\.amoraColors) private var colors

    init(cornerRadius: CGFloat, color: Color?, shadow: Bool) {
        self.cornerRadius = cornerRadius
        self.color = color
        self.shadow = shadow
    }

    func body(content: Content) -> some View {
        let shape = RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
        return content
            .clipShape(shape)
            .contentShape(shape)
            .background(
                shape
                    .fill(color ?? colors.surface)
                    .softShadow(elevation: shadow ? 10 : 0, alpha: shadow ? 0.10 : 0)
            )
    }
}

// MARK: - Taom rasmi va narx

// Rasmi yo'q taomlar uchun yumshoq fon ranglari (har taomga o'ziniki, maketdagidek)
private let placeholderTints: [Color] = [
    Color(argb: 0xFFFBE7D3),
    Color(argb: 0xFFE3EEF6),
    Color(argb: 0xFFF9E3DA),
    Color(argb: 0xFFF1E6DB),
    Color(argb: 0xFFE2F0EA),
    Color(argb: 0xFFEEF3DF),
]

/// Taom rasmi. Yuklanayotganda ustidan yorug'lik to'lqini o'tadi; rasm yo'q yoki yuklanmasa,
/// o'rnida rangli fon va likopcha belgisi turadi. `seed`: fon rangini tanlash uchun (taom raqami).
/// O'lchamni chaqiruvchi beradi: `.frame(width: 64, height: 64).clipShape(...)` yoki `.aspectRatio(...)`.
struct ProductImage: View {
    let url: URL?
    var iconSize: CGFloat = 44
    var seed: Int = 0
    @Environment(\.amoraColors) private var colors

    init(url: URL?, iconSize: CGFloat = 44, seed: Int = 0) {
        self.url = url
        self.iconSize = iconSize
        self.seed = seed
    }

    private var placeholderTint: Color {
        if colors.isDark {
            return colors.surfaceVariant
        }
        let count = placeholderTints.count
        return placeholderTints[((seed % count) + count) % count]
    }

    var body: some View {
        placeholderTint
            .overlay {
                if let url {
                    RemoteImage(url: url) { phase in
                        switch phase {
                        case .success(let image):
                            Image(uiImage: image)
                                .resizable()
                                .scaledToFill()
                                .transition(.opacity)
                        case .failure:
                            placeholderIcon
                        case .loading:
                            Color.clear.shimmer(Rectangle())
                        }
                    }
                } else {
                    placeholderIcon
                }
            }
            .clipped()
            .accessibilityHidden(true)
    }

    private var placeholderIcon: some View {
        IconImage(.dish, size: iconSize, tint: colors.onSurface.opacity(0.16))
    }
}

/// Narx: "60 000" katta va zich, " so'm" kichik va xira. `unit = false`: faqat raqam.
/// `color` berilmasa, joriy yozuv rangi (foregroundStyle) olinadi.
struct PriceText: View {
    let amount: Int
    var style: AmoraTextStyle = .price
    var color: Color? = nil
    var unitColor: Color? = nil
    var unit: Bool = true
    @Environment(\.amoraColors) private var colors

    init(amount: Int, style: AmoraTextStyle = .price, color: Color? = nil, unitColor: Color? = nil, unit: Bool = true) {
        self.amount = amount
        self.style = style
        self.color = color
        self.unitColor = unitColor
        self.unit = unit
    }

    var body: some View {
        let number = Text(formatNumber(amount))
            .font(style.font)
            .tracking(style.tracking)
        let text: Text
        if unit {
            text = number + Text(" so'm")
                .font(AmoraFont.body(style.size * 0.72))
                .foregroundColor(unitColor ?? colors.hint)
        } else {
            text = number
        }
        return Group {
            if let color {
                text.foregroundColor(color)
            } else {
                text
            }
        }
        .lineLimit(1)
        .fixedSize(horizontal: true, vertical: false)
    }
}

// MARK: - Belgilar

/// Burchaklari yumaloq kvadrat ichidagi belgi (ro'yxat qatorlari, holat kartochkalari).
struct IconTile: View {
    let icon: AppIcon
    var size: CGFloat = 42
    var container: Color? = nil
    var tint: Color? = nil
    var iconSize: CGFloat = 22
    @Environment(\.amoraColors) private var colors

    init(icon: AppIcon, size: CGFloat = 42, container: Color? = nil, tint: Color? = nil, iconSize: CGFloat = 22) {
        self.icon = icon
        self.size = size
        self.container = container
        self.tint = tint
        self.iconSize = iconSize
    }

    var body: some View {
        RoundedRectangle(cornerRadius: size / 3, style: .continuous)
            .fill(container ?? colors.primaryContainer)
            .frame(width: size, height: size)
            .overlay(IconImage(icon, size: iconSize, tint: tint ?? colors.primary))
            .accessibilityHidden(true)
    }
}

/// Kafe logotipi: qizil kvadrat ichida nomining bosh harfi.
struct LogoTile: View {
    let letter: String
    var size: CGFloat = 46
    @Environment(\.amoraColors) private var colors

    init(letter: String, size: CGFloat = 46) {
        self.letter = letter
        self.size = size
    }

    var body: some View {
        let shape = RoundedRectangle(cornerRadius: size / 3, style: .continuous)
        Text(letter)
            .amoraText(.headlineMedium)
            .foregroundColor(.white)
            .frame(width: size, height: size)
            .background(
                shape
                    .fill(colors.primary)
                    .shadow(color: colors.primary.opacity(0.55), radius: 7, x: 0, y: 4)
            )
            .accessibilityHidden(true)
    }
}

// MARK: - Kartochka va qatorlar

/// Oq fonli, burchaklari yumaloq, yengil soyali blok. `onClick` berilsa, bosiladigan bo'ladi
/// (bosilganda biroz kichrayadi). Ichidagi elementlar ustma-ust (VStack, oraliqsiz, chapga tekislangan).
struct SectionCard<Content: View>: View {
    var padding: CGFloat = 16
    var onClick: (() -> Void)? = nil
    let content: Content
    @Environment(\.amoraColors) private var colors

    init(padding: CGFloat = 16, onClick: (() -> Void)? = nil, @ViewBuilder content: () -> Content) {
        self.padding = padding
        self.onClick = onClick
        self.content = content()
    }

    private var card: some View {
        VStack(alignment: .leading, spacing: 0) {
            content
        }
        .padding(padding)
        .frame(maxWidth: .infinity, alignment: .leading)
        .foregroundStyle(colors.onSurface)
        .cardBackground()
    }

    var body: some View {
        if let onClick {
            Button(action: onClick) {
                card
            }
            .buttonStyle(PressScaleStyle(scale: 0.98))
        } else {
            card
        }
    }
}

/// Bloklar ustidagi kichik bosh harfli sarlavha: "YETKAZISH".
struct SectionLabel: View {
    let text: String
    @Environment(\.amoraColors) private var colors

    init(_ text: String) {
        self.text = text
    }

    init(text: String) {
        self.text = text
    }

    var body: some View {
        Text(text.uppercased())
            .amoraText(.labelSmall)
            .foregroundColor(colors.hint)
            .padding(.leading, 4)
            .padding(.top, 10)
            .frame(maxWidth: .infinity, alignment: .leading)
            .accessibilityAddTraits(.isHeader)
    }
}

/// Bosiladigan qator: chapda belgi, o'rtada sarlavha va qiymat, o'ngda strelka.
/// `highlighted`: hali to'ldirilmagan narsa (masalan, manzil tanlanmagan) rang bilan ajratiladi.
/// `onClick` berilmasa, qator faqat ma'lumot ko'rsatadi.
struct LinkRow: View {
    let icon: AppIcon
    let label: String
    let value: String
    var onClick: (() -> Void)? = nil
    var highlighted: Bool = false
    var tileContainer: Color? = nil
    var tileTint: Color? = nil
    @Environment(\.amoraColors) private var colors

    init(
        icon: AppIcon,
        label: String,
        value: String,
        onClick: (() -> Void)? = nil,
        highlighted: Bool = false,
        tileContainer: Color? = nil,
        tileTint: Color? = nil
    ) {
        self.icon = icon
        self.label = label
        self.value = value
        self.onClick = onClick
        self.highlighted = highlighted
        self.tileContainer = tileContainer
        self.tileTint = tileTint
    }

    private var row: some View {
        HStack(spacing: 0) {
            IconTile(icon: icon, container: tileContainer, tint: tileTint)
            Spacer().frame(width: 14)
            VStack(alignment: .leading, spacing: 2) {
                Text(label)
                    .amoraText(.bodySmall)
                    .foregroundColor(colors.hint)
                Text(value)
                    .amoraText(.titleSmall)
                    .foregroundColor(highlighted ? colors.primary : colors.onSurface)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            if onClick != nil {
                Spacer().frame(width: 8)
                IconImage(.chevron, size: 20, tint: colors.hint)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .contentShape(Rectangle())
    }

    var body: some View {
        if let onClick {
            Button(action: onClick) {
                row
            }
            .buttonStyle(RowButtonStyle())
            .accessibilityElement(children: .combine)
        } else {
            row
                .accessibilityElement(children: .combine)
        }
    }
}

/// Qator bosilganda yengil fon (Android ripple o'rniga).
struct RowButtonStyle: ButtonStyle {
    @Environment(\.amoraColors) private var colors

    init() {}

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .background(configuration.isPressed ? colors.onSurface.opacity(0.06) : Color.clear)
    }
}

/// Kartochka ichidagi qatorlar orasidagi ingichka chiziq (belgi ostidan boshlanmaydi).
struct RowDivider: View {
    var inset: CGFloat = 72
    @Environment(\.amoraColors) private var colors

    init(inset: CGFloat = 72) {
        self.inset = inset
    }

    var body: some View {
        Rectangle()
            .fill(colors.outlineVariant)
            .frame(height: 1)
            .padding(.leading, inset)
            .padding(.trailing, 16)
            .accessibilityHidden(true)
    }
}

/// Punktir chiziq: chekdagidek, jami summa ustida.
struct DashedDivider: View {
    @Environment(\.amoraColors) private var colors

    init() {}

    var body: some View {
        DashedLine()
            .stroke(colors.outline, style: StrokeStyle(lineWidth: 1, dash: [4, 4]))
            .frame(height: 1)
            .frame(maxWidth: .infinity)
            .accessibilityHidden(true)
    }
}

private struct DashedLine: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        path.move(to: CGPoint(x: 0, y: rect.midY))
        path.addLine(to: CGPoint(x: rect.width, y: rect.midY))
        return path
    }
}

/// "Taomlar ...... 35 000 so'm" qatori. `loading`: qiymat serverdan kutilmoqda (o'rnida skelet).
/// `valueColor` berilsa, qiymat qalin va shu rangda ("Bepul" yashil).
struct SummaryRow: View {
    let label: String
    let value: String
    var valueColor: Color? = nil
    var loading: Bool = false
    @Environment(\.amoraColors) private var colors

    init(label: String, value: String, valueColor: Color? = nil, loading: Bool = false) {
        self.label = label
        self.value = value
        self.valueColor = valueColor
        self.loading = loading
    }

    var body: some View {
        HStack(spacing: 8) {
            Text(label)
                .amoraText(.bodyLarge)
                .foregroundColor(colors.onSurfaceVariant)
                .frame(maxWidth: .infinity, alignment: .leading)
            if loading {
                SkeletonBox(width: 76, height: 16)
            } else if let valueColor {
                Text(value)
                    .amoraText(.titleSmall)
                    .foregroundColor(valueColor)
            } else {
                Text(value)
                    .amoraText(.bodyLarge)
                    .foregroundColor(colors.onSurface)
            }
        }
        .padding(.vertical, 5)
    }
}
