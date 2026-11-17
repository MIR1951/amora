/// Product details sheet (port of ProductSheet in android ui/menu/MenuScreen.kt):
/// large photo, name, description and "Savatga qo'shish" / quantity stepper.
///
/// Surface (used only inside Features/Menu):
/// - `MenuProductSheet(container: AppContainer, product: Product)` - content of `.sheet(item:)`;
///   sizes itself to its content (like Android `skipPartiallyExpanded`), rounded 32 pt top corners.

import SwiftUI

private struct MenuSheetHeightKey: PreferenceKey {
    static let defaultValue: CGFloat = 0

    static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) {
        value = max(value, nextValue())
    }
}

/// Taom haqida to'liq ma'lumot: katta rasm, tavsif va savatga qo'shish.
struct MenuProductSheet: View {
    let container: AppContainer
    let product: Product
    @Environment(\.colorScheme) private var colorScheme
    @State private var contentHeight: CGFloat

    // Tepada tortish chizig'i uchun joy (Android ModalBottomSheet dastagi)
    private static let handleSpace: CGFloat = 28

    init(container: AppContainer, product: Product) {
        self.container = container
        self.product = product
        // Birinchi o'lchovgacha taxminiy balandlik: ochilishda oyna sakramasin
        let width = AmoraWindow.width > 0 ? AmoraWindow.width : 390
        _contentHeight = State(initialValue: (width - 32) / 1.3 + 240)
    }

    var body: some View {
        let colors = AmoraColors.resolve(colorScheme)
        ScrollView {
            content(colors)
                .padding(.horizontal, 16)
                .padding(.top, MenuProductSheet.handleSpace)
                .padding(.bottom, 20)
                .background(
                    GeometryReader { geo in
                        Color.clear.preference(key: MenuSheetHeightKey.self, value: geo.size.height)
                    }
                )
        }
        .scrollBounceBehavior(.basedOnSize)
        .onPreferenceChange(MenuSheetHeightKey.self) { height in
            // iOS 18 SDK: bu yopiq funksiya @Sendable; SwiftUI uni baribir asosiy oqimda chaqiradi
            MainActor.assumeIsolated {
                if height > 0 && abs(height - contentHeight) > 0.5 {
                    contentHeight = height
                }
            }
        }
        .presentationDetents([.height(contentHeight)])
        .presentationDragIndicator(.visible)
        .presentationCornerRadius(32)
        .presentationBackground(colors.surface)
        .amoraTheme()
    }

    private func content(_ colors: AmoraColors) -> some View {
        let description = product.description.trimmingCharacters(in: .whitespacesAndNewlines)
        return VStack(alignment: .leading, spacing: 0) {
            Color.clear
                .aspectRatio(1.3, contentMode: .fit)
                .frame(maxWidth: .infinity)
                .overlay { ProductImage(url: container.imageURL(product.imageUrl), iconSize: 76, seed: product.id) }
                .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
            Spacer().frame(height: 18)
            Text(product.name)
                .amoraText(.headlineMedium)
                .foregroundColor(colors.onSurface)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.horizontal, 4)
                .accessibilityAddTraits(.isHeader)
            if !description.isEmpty {
                Spacer().frame(height: 8)
                Text(product.description)
                    .amoraText(.bodyLarge)
                    .foregroundColor(colors.onSurfaceVariant)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.horizontal, 4)
            }
            Spacer().frame(height: 22)
            action
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    @ViewBuilder
    private var action: some View {
        let quantity = container.cart.quantity(product.id)
        if !product.isAvailable {
            BigButton(text: "Hozircha yo'q", onClick: {}, enabled: false)
        } else if quantity == 0 {
            BigButton(
                text: "Savatga qo'shish",
                onClick: { container.cart.add(product.id) },
                trailing: formatSum(product.price)
            )
        } else {
            QuantityStepper(
                quantity: quantity,
                onMinus: { container.cart.remove(product.id) },
                onPlus: { container.cart.add(product.id) },
                height: 58,
                corner: 20,
                buttonWidth: 60,
                label: String(quantity) + " ta · " + formatNumber(product.price * quantity) + " so'm",
                expand: true
            )
        }
    }
}
