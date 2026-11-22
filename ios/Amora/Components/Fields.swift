/// Text input styling (port of fieldColors / fieldBorder from
/// android ui/components/Components.kt).
///
/// Surface:
/// - `View.fieldStyle(container: Color? = nil, cornerRadius: CGFloat = 18, border: Bool = true, minHeight: CGFloat = 56)`
///   for a `TextField`/`SecureField`: body font, padding 16, white (surface) rounded background, thin border,
///   red caret. Inside a card pass `container: .clear, border: false`.
/// - `View.fieldBorder(cornerRadius: CGFloat = 18)` - only the thin outlineVariant border
/// - `fieldPrompt(_ text: String, _ colors: AmoraColors) -> Text` - placeholder in the hint color:
///     `TextField("", text: $name, prompt: fieldPrompt("Ismingiz", colors))`

import SwiftUI

/// Matn kiritish maydoni ko'rinishi: chiziqsiz, yumaloq burchakli, fon odatda oq.
struct FieldStyleModifier: ViewModifier {
    let container: Color?
    let cornerRadius: CGFloat
    let border: Bool
    let minHeight: CGFloat
    @Environment(\.amoraColors) private var colors

    init(container: Color?, cornerRadius: CGFloat, border: Bool, minHeight: CGFloat) {
        self.container = container
        self.cornerRadius = cornerRadius
        self.border = border
        self.minHeight = minHeight
    }

    func body(content: Content) -> some View {
        let shape = RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
        return content
            .font(AmoraTextStyle.bodyLarge.font)
            .foregroundColor(colors.onSurface)
            .tint(colors.primary)
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .frame(minHeight: minHeight)
            .background(shape.fill(container ?? colors.surface))
            .overlay(shape.strokeBorder(border ? colors.outlineVariant : Color.clear, lineWidth: 1))
            .contentShape(shape)
    }
}

/// Oq maydon atrofidagi ingichka hoshiya (maketdagidek).
struct FieldBorderModifier: ViewModifier {
    let cornerRadius: CGFloat
    @Environment(\.amoraColors) private var colors

    init(cornerRadius: CGFloat) {
        self.cornerRadius = cornerRadius
    }

    func body(content: Content) -> some View {
        content.overlay(
            RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                .strokeBorder(colors.outlineVariant, lineWidth: 1)
        )
    }
}

extension View {
    /// Matn kiritish maydoni uchun Amora ko'rinishi (Android `fieldColors()` + `fieldBorder()`).
    func fieldStyle(container: Color? = nil, cornerRadius: CGFloat = 18, border: Bool = true, minHeight: CGFloat = 56) -> some View {
        modifier(FieldStyleModifier(container: container, cornerRadius: cornerRadius, border: border, minHeight: minHeight))
    }

    /// Faqat ingichka hoshiya.
    func fieldBorder(cornerRadius: CGFloat = 18) -> some View {
        modifier(FieldBorderModifier(cornerRadius: cornerRadius))
    }
}

/// Maydon bo'sh paytdagi xira yozuv.
func fieldPrompt(_ text: String, _ colors: AmoraColors) -> Text {
    Text(text).foregroundColor(colors.hint)
}
