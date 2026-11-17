/// Product card, floating cart bar and loading skeleton of the menu
/// (port of ProductCard, CartBar, MenuSkeleton, ProductCardSkeleton in android ui/menu/MenuScreen.kt).
///
/// Surface (used only inside Features/Menu):
/// - `MenuProductCard(product: Product, imageURL: URL?, quantity: Int, onAdd: @escaping () -> Void, onRemove: @escaping () -> Void, onClick: @escaping () -> Void)`
///   (accessibility identifier "product-name" on the tappable image+name part, like the Android testTag)
/// - `MenuCartBar(count: Int, total: Int, onClick: @escaping () -> Void)`
/// - `MenuSkeleton()`, `MenuProductCardSkeleton()`

import SwiftUI

/// Kartochka bosilganini tashqariga bildiradigan uslub: butun kartochka (pastki qatori bilan) kichrayadi.
private struct MenuCardPressStyle: ButtonStyle {
    @Binding var pressed: Bool

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .onChange(of: configuration.isPressed) { _, value in
                pressed = value
            }
    }
}

/// Taom kartochkasi: rasm, nom, qisqa tavsif, pastda narx va "+" (savatda bo'lsa son tanlagich).
struct MenuProductCard: View {
    let product: Product
    let imageURL: URL?
    let quantity: Int
    let onAdd: () -> Void
    let onRemove: () -> Void
    let onClick: () -> Void
    @Environment(\.amoraColors) private var colors
    @State private var pressed = false

    init(
        product: Product,
        imageURL: URL?,
        quantity: Int,
        onAdd: @escaping () -> Void,
        onRemove: @escaping () -> Void,
        onClick: @escaping () -> Void
    ) {
        self.product = product
        self.imageURL = imageURL
        self.quantity = quantity
        self.onAdd = onAdd
        self.onRemove = onRemove
        self.onClick = onClick
    }

    var body: some View {
        let shape = RoundedRectangle(cornerRadius: AmoraRadius.large, style: .continuous)
        VStack(alignment: .leading, spacing: 0) {
            Button(action: onClick) {
                VStack(alignment: .leading, spacing: 0) {
                    imageBlock
                    textBlock
                        .padding(.horizontal, 6)
                        .padding(.top, 10)
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(MenuCardPressStyle(pressed: $pressed))
            .accessibilityIdentifier("product-name")
            Color.clear.frame(height: 8)
            bottomRow
                .padding(.horizontal, 6)
        }
        .padding(.horizontal, 6)
        .padding(.top, 6)
        .padding(.bottom, 10)
        .background(shape.fill(colors.surface).softShadow())
        .contentShape(shape)
        // Narx qatorining bo'sh joyi bosilsa ham taom oynasi ochiladi
        .onTapGesture(perform: onClick)
        .scaleEffect(pressed ? 0.98 : 1)
        .animation(AmoraMotion.press, value: pressed)
    }

    private var imageBlock: some View {
        Color.clear
            .aspectRatio(1.2, contentMode: .fit)
            .frame(maxWidth: .infinity)
            .overlay { ProductImage(url: imageURL, seed: product.id) }
            .clipShape(RoundedRectangle(cornerRadius: 19, style: .continuous))
            .opacity(product.isAvailable ? 1 : 0.5)
            .overlay(alignment: .topLeading) {
                if !product.isAvailable {
                    Text("Tugagan")
                        .amoraText(AmoraTextStyle.labelSmall.with(size: 12, tracking: 0))
                        .foregroundColor(colors.onSurface)
                        .padding(.horizontal, 9)
                        .padding(.vertical, 5)
                        .background(RoundedRectangle(cornerRadius: 9, style: .continuous).fill(colors.surface))
                        .padding(8)
                }
            }
    }

    /// Nom bir qatorga sig'sa, ostida tavsif; ikki qatorga cho'zilsa, tavsif ko'rsatilmaydi:
    /// hamma kartochka bir xil balandlikda qoladi.
    private var textBlock: some View {
        let nameStyle = AmoraTextStyle.titleMedium.with(size: 16, lineHeight: 20)
        let nameColor = product.isAvailable ? colors.onSurface : colors.onSurfaceVariant
        let description = product.description.trimmingCharacters(in: .whitespacesAndNewlines)
        return ViewThatFits(in: .horizontal) {
            VStack(alignment: .leading, spacing: 2) {
                Text(product.name)
                    .amoraText(nameStyle)
                    .foregroundColor(nameColor)
                    .lineLimit(1)
                    .fixedSize(horizontal: true, vertical: false)
                if !description.isEmpty {
                    Text(product.description)
                        .amoraText(.bodySmall)
                        .foregroundColor(colors.hint)
                        .lineLimit(1)
                        .truncationMode(.tail)
                        // Tavsif kenglikni tanlashga ta'sir qilmaydi: faqat nom sig'adimi, shu hal qiladi
                        .frame(minWidth: 0, idealWidth: 0, maxWidth: .infinity, alignment: .leading)
                }
            }
            Text(product.name)
                .amoraText(nameStyle)
                .foregroundColor(nameColor)
                .lineLimit(2)
                .truncationMode(.tail)
                .multilineTextAlignment(.leading)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .frame(maxWidth: .infinity, alignment: .topLeading)
        .frame(height: 42, alignment: .topLeading)
    }

    private var bottomRow: some View {
        HStack(spacing: 0) {
            if !product.isAvailable {
                Text("Hozircha yo'q")
                    .amoraText(.labelMedium)
                    .foregroundColor(colors.hint)
                Spacer(minLength: 0)
            } else {
                // Savatga qo'shilgach "so'm" yozuvi yashiriladi: tor ekranda son tanlagichga joy qoladi
                PriceText(amount: product.price, unit: quantity == 0)
                    .foregroundStyle(colors.onSurface)
                    .frame(maxWidth: .infinity, alignment: .leading)
                if quantity == 0 {
                    AddButton(onClick: onAdd)
                } else {
                    QuantityStepper(quantity: quantity, onMinus: onRemove, onPlus: onAdd)
                }
            }
        }
        .frame(height: 38)
        .contentShape(Rectangle())
    }
}

// MARK: - Savat paneli

/// Pastda suzib turadigan to'q shisha "Savat" paneli: savatda taom bo'lsa ko'rinadi.
struct MenuCartBar: View {
    let count: Int
    let total: Int
    let onClick: () -> Void
    @Environment(\.amoraColors) private var colors

    init(count: Int, total: Int, onClick: @escaping () -> Void) {
        self.count = count
        self.total = total
        self.onClick = onClick
    }

    var body: some View {
        let ink = AmoraColors.inkBlack
        Button(action: onClick) {
            GlassBox(cornerRadius: 22, tone: .dark, elevation: 16, alignment: .leading) {
                HStack(spacing: 0) {
                    bagTile(ink: ink)
                    Spacer().frame(width: 14)
                    VStack(alignment: .leading, spacing: 0) {
                        Text("Savat")
                            .amoraText(.bodySmall)
                            .foregroundColor(colors.onInkMuted)
                        Text(formatSum(total))
                            .amoraText(AmoraTextStyle.price.with(size: 17))
                            .foregroundColor(.white)
                            .lineLimit(1)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    HStack(spacing: 2) {
                        Text("Savatga")
                            .amoraText(.labelLarge)
                            .foregroundColor(ink)
                            .lineLimit(1)
                        IconImage(.chevron, size: 18, tint: ink)
                    }
                    .padding(.leading, 14)
                    .padding(.trailing, 8)
                    .frame(height: 40)
                    .background(RoundedRectangle(cornerRadius: 13, style: .continuous).fill(Color.white))
                }
                .padding(.horizontal, 10)
                .frame(maxWidth: .infinity)
                .frame(height: 64)
            }
            .contentShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
        }
        .buttonStyle(PressScaleStyle())
        .padding(.horizontal, 16)
        .padding(.top, 8)
        .padding(.bottom, AmoraWindow.bottomInset > 0 ? 4 : 12)
    }

    private func bagTile(ink: Color) -> some View {
        RoundedRectangle(cornerRadius: 15, style: .continuous)
            .fill(colors.primary)
            .frame(width: 44, height: 44)
            .overlay { IconImage(.bag, size: 22, tint: .white) }
            .overlay(alignment: .topTrailing) {
                Text(String(count))
                    .amoraText(AmoraTextStyle.labelSmall.with(size: 11, tracking: 0))
                    .foregroundColor(ink)
                    .lineLimit(1)
                    .fixedSize()
                    .padding(.horizontal, 5)
                    .frame(minWidth: 19, minHeight: 19)
                    .background(Capsule().fill(Color.white))
                    .offset(x: 5, y: -5)
            }
    }
}

// MARK: - Skelet

/// Menyu birinchi marta yuklanayotganda ko'rinadigan "skelet": haqiqiy sahifa shaklini takrorlaydi.
struct MenuSkeleton: View {
    init() {}

    var body: some View {
        VStack(spacing: 12) {
            SkeletonBox(height: 154, cornerRadius: 28)
            HStack(alignment: .bottom, spacing: 0) {
                SkeletonBox(width: 110, height: 26)
                Spacer(minLength: 0)
                SkeletonBox(width: 64, height: 14)
            }
            .padding(.horizontal, 4)
            .padding(.top, 12)
            .padding(.bottom, 2)
            ForEach(0..<2, id: \.self) { _ in
                HStack(alignment: .top, spacing: 12) {
                    MenuProductCardSkeleton()
                    MenuProductCardSkeleton()
                }
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 16)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .accessibilityHidden(true)
    }
}

struct MenuProductCardSkeleton: View {
    @Environment(\.amoraColors) private var colors

    init() {}

    var body: some View {
        let shape = RoundedRectangle(cornerRadius: AmoraRadius.large, style: .continuous)
        VStack(alignment: .leading, spacing: 0) {
            Color.clear
                .aspectRatio(1.2, contentMode: .fit)
                .frame(maxWidth: .infinity)
                .shimmer(cornerRadius: 19)
            VStack(alignment: .leading, spacing: 0) {
                SkeletonBox(width: 84, height: 16)
                Spacer().frame(height: 8)
                SkeletonBox(width: 112, height: 12)
                Spacer().frame(height: 12)
                HStack(spacing: 0) {
                    SkeletonBox(width: 72, height: 18)
                    Spacer(minLength: 0)
                    SkeletonBox(width: 38, height: 38)
                }
            }
            .padding(.horizontal, 6)
            .padding(.top, 12)
        }
        .padding(.horizontal, 6)
        .padding(.top, 6)
        .padding(.bottom, 10)
        .frame(maxWidth: .infinity)
        .background(shape.fill(colors.surface).softShadow())
    }
}
