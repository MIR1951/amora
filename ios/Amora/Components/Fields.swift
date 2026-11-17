/// Text input styling (port of fieldColors / fieldBorder / PhoneVisualTransformation from
/// android ui/components/Components.kt).
///
/// Surface:
/// - `View.fieldStyle(container: Color? = nil, cornerRadius: CGFloat = 18, border: Bool = true, minHeight: CGFloat = 56)`
///   for a `TextField`/`SecureField`: body font, padding 16, white (surface) rounded background, thin border,
///   red caret. Inside a card pass `container: .clear, border: false`.
/// - `View.fieldBorder(cornerRadius: CGFloat = 18)` - only the thin outlineVariant border
/// - `fieldPrompt(_ text: String, _ colors: AmoraColors) -> Text` - placeholder in the hint color:
///     `TextField("", text: $name, prompt: fieldPrompt("Ismingiz", colors))`
/// - `enum PhoneVisualTransformation`
///     `static func format(_ digits: String) -> String`               // "901234567" -> "90 123 45 67"
///     `static func binding(_ digits: Binding<String>) -> Binding<String>`  // field shows spaced, stores max 9 digits

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

/// Telefon raqamni "90 123 45 67" ko'rinishida ko'rsatadi (maydonda faqat 9 ta raqam saqlanadi).
enum PhoneVisualTransformation {
    static let maxDigits = 9

    /// "901234567" -> "90 123 45 67" (to'liq bo'lmasa ham shu tartibda).
    static func format(_ digits: String) -> String {
        var result = ""
        for (index, char) in digits.enumerated() {
            if index == 2 || index == 5 || index == 7 {
                result.append(" ")
            }
            result.append(char)
        }
        return result
    }

    /// Faqat raqamlar, ko'pi bilan 9 ta.
    static func digitsOnly(_ text: String) -> String {
        let digits = text.filter { $0.isASCII && $0.isNumber }
        return String(digits.prefix(maxDigits))
    }

    /// TextField uchun: maydonda bo'shliqlar bilan ko'rinadi, `digits` ga faqat raqamlar yoziladi.
    static func binding(_ digits: Binding<String>) -> Binding<String> {
        Binding<String>(
            get: { format(digits.wrappedValue) },
            set: { digits.wrappedValue = digitsOnly($0) }
        )
    }
}
