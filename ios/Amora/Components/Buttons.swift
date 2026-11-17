/// Buttons (port of the button parts of android ui/components/Components.kt).
/// Parameter names follow the Kotlin ones (`onClick`, `onMinus`, `onPlus`, ...).
///
/// Surface (all `View` structs):
/// - `BigButton(text: String, onClick: @escaping () -> Void, enabled: Bool = true, loading: Bool = false, trailing: String? = nil)`
/// - `SoftButton(text: String, onClick: @escaping () -> Void, icon: AppIcon? = nil, enabled: Bool = true, accent: Bool = false, danger: Bool = false)`
/// - `PillButton(text: String, onClick: @escaping () -> Void)`
/// - `TextButton(text: String, onClick: @escaping () -> Void, color: Color? = nil)`   (Material TextButton)
/// - `RoundButton(icon: AppIcon, label: String, onClick: @escaping () -> Void, size: CGFloat = 44, cornerRadius: CGFloat? = nil, tint: Color? = nil, glass: Bool = false)`
///   `RoundButton(icon:label:onClick:size:cornerRadius:tint:glass:) { custom content }`  (cornerRadius nil = circle)
/// - `AddButton(onClick: @escaping () -> Void)`
/// - `QuantityStepper(quantity: Int, onMinus: @escaping () -> Void, onPlus: @escaping () -> Void, height: CGFloat = 38, corner: CGFloat = 13, buttonWidth: CGFloat = 28, tonal: Bool = false, label: String? = nil, expand: Bool = false)`
/// - `TabChip(text: String, selected: Bool, onClick: @escaping () -> Void)`

import SwiftUI

// MARK: - Asosiy tugma

/// Asosiy tugma: qizil, ostida o'z rangidagi yorug' soya. Butun kenglikni egallaydi, balandligi 58.
/// `trailing` berilsa, matn chapda, u (masalan narx) o'ngdagi shaffof "tabletka" ichida turadi.
struct BigButton: View {
    let text: String
    let onClick: () -> Void
    var enabled: Bool = true
    var loading: Bool = false
    var trailing: String? = nil
    @Environment(\.amoraColors) private var colors

    init(text: String, onClick: @escaping () -> Void, enabled: Bool = true, loading: Bool = false, trailing: String? = nil) {
        self.text = text
        self.onClick = onClick
        self.enabled = enabled
        self.loading = loading
        self.trailing = trailing
    }

    var body: some View {
        let lit = enabled || loading
        let shape = RoundedRectangle(cornerRadius: 20, style: .continuous)
        let content = lit ? colors.onPrimary : colors.hint
        Button(action: onClick) {
            HStack(spacing: 0) {
                if loading {
                    ProgressView()
                        .progressViewStyle(.circular)
                        .tint(content)
                        .frame(width: 22, height: 22)
                } else if let trailing {
                    Text(text)
                        .amoraText(.titleMedium)
                        .lineLimit(1)
                        .truncationMode(.tail)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    Spacer().frame(width: 10)
                    Text(trailing)
                        .amoraText(.titleSmall)
                        .lineLimit(1)
                        .fixedSize()
                        .padding(.horizontal, 14)
                        .padding(.vertical, 10)
                        .background(
                            RoundedRectangle(cornerRadius: 13, style: .continuous)
                                .fill(Color.white.opacity(lit ? 0.18 : 0))
                        )
                } else {
                    Text(text)
                        .amoraText(.titleMedium)
                        .lineLimit(1)
                        .truncationMode(.tail)
                }
            }
            .padding(.leading, 22)
            .padding(.trailing, trailing != nil && !loading ? 9 : 22)
            .foregroundColor(content)
            .frame(maxWidth: .infinity)
            .frame(height: 58)
            .background(
                ZStack {
                    shape
                        .fill(lit ? colors.primary : colors.outlineVariant)
                        .shadow(color: lit ? colors.primary.opacity(0.45) : Color.clear, radius: 12, x: 0, y: 7)
                    // Ustki qismdagi yengil yaltirash: tugma shishadek bo'rtib ko'rinadi
                    shape.fill(
                        LinearGradient(
                            colors: [Color.white.opacity(lit ? 0.16 : 0), Color.clear],
                            startPoint: .top,
                            endPoint: .bottom
                        )
                    )
                }
            )
            .contentShape(shape)
        }
        .buttonStyle(PressScaleStyle())
        .disabled(!enabled || loading)
        // Avtomatik sinov tugmani "Buyurtma berish · 45 000 so'm" ko'rinishida izlaydi
        .accessibilityLabel(trailing != nil ? "\(text) · \(trailing ?? "")" : text)
    }
}

/// Ikkinchi darajali tugma: oq fonli, ingichka hoshiyali, ixtiyoriy belgi bilan. Balandligi 52.
/// `accent`: yozuvi qizil (qo'ng'iroq qilish). `danger`: xavfli amal (bekor qilish).
struct SoftButton: View {
    let text: String
    let onClick: () -> Void
    var icon: AppIcon? = nil
    var enabled: Bool = true
    var accent: Bool = false
    var danger: Bool = false
    @Environment(\.amoraColors) private var colors

    init(
        text: String,
        onClick: @escaping () -> Void,
        icon: AppIcon? = nil,
        enabled: Bool = true,
        accent: Bool = false,
        danger: Bool = false
    ) {
        self.text = text
        self.onClick = onClick
        self.icon = icon
        self.enabled = enabled
        self.accent = accent
        self.danger = danger
    }

    private var content: Color {
        if !enabled {
            return colors.hint
        }
        if accent {
            return colors.primary
        }
        if danger {
            return colors.onSurfaceVariant
        }
        return colors.onSurface
    }

    var body: some View {
        let shape = RoundedRectangle(cornerRadius: 18, style: .continuous)
        Button(action: onClick) {
            HStack(spacing: 8) {
                if let icon {
                    IconImage(icon, size: 19)
                }
                Text(text)
                    .amoraText(.labelLarge)
                    .lineLimit(1)
                    .truncationMode(.tail)
            }
            .foregroundColor(content)
            .padding(.horizontal, 16)
            .frame(maxWidth: .infinity)
            .frame(height: 52)
            .background(shape.fill(colors.surface))
            .overlay(shape.strokeBorder(colors.outlineVariant, lineWidth: 1))
            .contentShape(shape)
        }
        .buttonStyle(PressScaleStyle())
        .disabled(!enabled)
        .accessibilityLabel(text)
    }
}

/// Matn kengligidagi asosiy tugma (bo'sh holatlarda).
struct PillButton: View {
    let text: String
    let onClick: () -> Void
    @Environment(\.amoraColors) private var colors

    init(text: String, onClick: @escaping () -> Void) {
        self.text = text
        self.onClick = onClick
    }

    var body: some View {
        Button(action: onClick) {
            Text(text)
                .amoraText(.labelLarge)
                .lineLimit(1)
                .foregroundColor(colors.onPrimary)
                .padding(.horizontal, 28)
                .padding(.vertical, 15)
                .background(RoundedRectangle(cornerRadius: 18, style: .continuous).fill(colors.primary))
                .contentShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        }
        .buttonStyle(PressScaleStyle())
    }
}

/// Faqat yozuvdan iborat tugma (Material TextButton): "Tozalash", "Bekor qilish".
struct TextButton: View {
    let text: String
    let onClick: () -> Void
    var color: Color? = nil
    @Environment(\.amoraColors) private var colors
    @Environment(\.isEnabled) private var isEnabled

    init(text: String, onClick: @escaping () -> Void, color: Color? = nil) {
        self.text = text
        self.onClick = onClick
        self.color = color
    }

    var body: some View {
        Button(action: onClick) {
            Text(text)
                .amoraText(.labelLarge)
                .lineLimit(1)
                .foregroundColor(isEnabled ? (color ?? colors.primary) : colors.hint)
                .padding(.horizontal, 12)
                .padding(.vertical, 10)
                .contentShape(Rectangle())
        }
        .buttonStyle(PressScaleStyle(scale: 0.95))
    }
}

// MARK: - Yumaloq va kichik tugmalar

/// Yumaloq belgili tugma: orqaga, buyurtmalar, profil.
/// `glass` = true: tugma shishadan bo'ladi (xarita ustida), aks holda oq va ingichka hoshiyali.
/// `cornerRadius` nil bo'lsa doira, aks holda shu burchakli kvadrat. `label` ekran o'quvchisi va sinov uchun.
struct RoundButton: View {
    let icon: AppIcon
    let label: String
    let onClick: () -> Void
    var size: CGFloat = 44
    var cornerRadius: CGFloat? = nil
    var tint: Color? = nil
    var glass: Bool = false
    private let customContent: AnyView?
    @Environment(\.amoraColors) private var colors

    init(
        icon: AppIcon,
        label: String,
        onClick: @escaping () -> Void,
        size: CGFloat = 44,
        cornerRadius: CGFloat? = nil,
        tint: Color? = nil,
        glass: Bool = false
    ) {
        self.icon = icon
        self.label = label
        self.onClick = onClick
        self.size = size
        self.cornerRadius = cornerRadius
        self.tint = tint
        self.glass = glass
        self.customContent = nil
    }

    /// Belgi o'rniga boshqa narsa (masalan aylanuvchi yuklanish belgisi yoki nishon bilan belgi).
    init<C: View>(
        icon: AppIcon,
        label: String,
        onClick: @escaping () -> Void,
        size: CGFloat = 44,
        cornerRadius: CGFloat? = nil,
        tint: Color? = nil,
        glass: Bool = false,
        @ViewBuilder content: () -> C
    ) {
        self.icon = icon
        self.label = label
        self.onClick = onClick
        self.size = size
        self.cornerRadius = cornerRadius
        self.tint = tint
        self.glass = glass
        self.customContent = AnyView(content())
    }

    private var shape: AnyShape {
        if let cornerRadius {
            return AnyShape(RoundedRectangle(cornerRadius: cornerRadius, style: .continuous))
        }
        return AnyShape(Circle())
    }

    @ViewBuilder
    private var inner: some View {
        if let customContent {
            customContent.foregroundStyle(tint ?? colors.onSurface)
        } else {
            IconImage(icon, size: 22, tint: tint ?? colors.onSurface)
        }
    }

    var body: some View {
        Button(action: onClick) {
            if glass {
                GlassBox(shape: shape, elevation: 8, alignment: .center) {
                    inner.frame(width: size, height: size)
                }
            } else {
                inner
                    .frame(width: size, height: size)
                    .background(shape.fill(colors.surface))
                    .overlay(shape.stroke(colors.outlineVariant, lineWidth: 2).clipShape(shape))
                    .contentShape(shape)
            }
        }
        .buttonStyle(PressScaleStyle(scale: 0.92))
        .accessibilityLabel(label)
    }
}

/// Taom kartochkasidagi "+" tugmasi: bosilganda taom savatga tushadi.
struct AddButton: View {
    let onClick: () -> Void
    @Environment(\.amoraColors) private var colors

    init(onClick: @escaping () -> Void) {
        self.onClick = onClick
    }

    var body: some View {
        let shape = RoundedRectangle(cornerRadius: 13, style: .continuous)
        Button(action: onClick) {
            IconImage(.plus, size: 22, tint: colors.onSurface)
                .frame(width: 38, height: 38)
                .background(shape.fill(colors.surfaceVariant))
                .contentShape(shape)
        }
        .buttonStyle(PressScaleStyle(scale: 0.88))
        .accessibilityLabel("Qo'shish")
    }
}

/// "−  2  +" ko'rinishidagi son tanlagich.
/// `tonal`: neytral ko'rinish (savat qatorlarida), aks holda qizil.
/// `label`: son o'rniga ko'rsatiladigan matn, masalan "2 ta · 70 000 so'm".
/// `expand`: bor kenglikni egallaydi (son o'rtada turadi).
struct QuantityStepper: View {
    let quantity: Int
    let onMinus: () -> Void
    let onPlus: () -> Void
    var height: CGFloat = 38
    var corner: CGFloat = 13
    var buttonWidth: CGFloat = 28
    var tonal: Bool = false
    var label: String? = nil
    var expand: Bool = false
    @Environment(\.amoraColors) private var colors

    init(
        quantity: Int,
        onMinus: @escaping () -> Void,
        onPlus: @escaping () -> Void,
        height: CGFloat = 38,
        corner: CGFloat = 13,
        buttonWidth: CGFloat = 28,
        tonal: Bool = false,
        label: String? = nil,
        expand: Bool = false
    ) {
        self.quantity = quantity
        self.onMinus = onMinus
        self.onPlus = onPlus
        self.height = height
        self.corner = corner
        self.buttonWidth = buttonWidth
        self.tonal = tonal
        self.label = label
        self.expand = expand
    }

    var body: some View {
        let container = tonal ? colors.surfaceVariant : colors.primary
        let content = tonal ? colors.onSurface : colors.onPrimary
        let value = label ?? String(quantity)
        HStack(spacing: 0) {
            StepperButton(icon: .minus, label: "Kamaytirish", width: buttonWidth, tint: content, onClick: onMinus)
            ZStack {
                Text(value)
                    .amoraText(.titleSmall)
                    .foregroundColor(content)
                    .lineLimit(1)
                    .fixedSize()
                    .id(value)
                    .transition(
                        .asymmetric(
                            insertion: .offset(y: height / 4).combined(with: .opacity),
                            removal: .offset(y: -height / 4).combined(with: .opacity)
                        )
                    )
            }
            .frame(minWidth: 16)
            .frame(maxWidth: expand ? .infinity : nil)
            .frame(height: height)
            .clipped()
            .animation(.easeOut(duration: 0.2), value: value)
            .accessibilityElement(children: .combine)
            StepperButton(
                icon: .plus,
                label: "Ko'paytirish",
                width: buttonWidth,
                tint: tonal ? colors.primary : content,
                onClick: onPlus
            )
        }
        .frame(height: height)
        .frame(maxWidth: expand ? .infinity : nil)
        .background(RoundedRectangle(cornerRadius: corner, style: .continuous).fill(container))
        .clipShape(RoundedRectangle(cornerRadius: corner, style: .continuous))
    }
}

private struct StepperButton: View {
    let icon: AppIcon
    let label: String
    let width: CGFloat
    let tint: Color
    let onClick: () -> Void

    var body: some View {
        Button(action: onClick) {
            IconImage(icon, size: 18, tint: tint)
                .frame(width: width)
                .frame(maxHeight: .infinity)
                .contentShape(Rectangle())
        }
        .buttonStyle(PressScaleStyle(scale: 0.85))
        .accessibilityLabel(label)
    }
}

/// Filtr yoki bo'lim tugmasi: tanlangani ko'mir rangda, qolganlari oq.
struct TabChip: View {
    let text: String
    let selected: Bool
    let onClick: () -> Void
    @Environment(\.amoraColors) private var colors

    init(text: String, selected: Bool, onClick: @escaping () -> Void) {
        self.text = text
        self.selected = selected
        self.onClick = onClick
    }

    var body: some View {
        let shape = RoundedRectangle(cornerRadius: 13, style: .continuous)
        Button(action: onClick) {
            Text(text)
                .amoraText(.labelMedium)
                .lineLimit(1)
                .foregroundColor(selected ? colors.onSecondary : colors.onSurfaceVariant)
                .padding(.horizontal, 16)
                .padding(.vertical, 10)
                .background(shape.fill(selected ? colors.secondary : colors.surface))
                .overlay(shape.strokeBorder(selected ? Color.clear : colors.outlineVariant, lineWidth: 1))
                .contentShape(shape)
        }
        .buttonStyle(PressScaleStyle(scale: 0.95))
        .accessibilityAddTraits(selected ? .isSelected : [])
    }
}
