/// Menu screen building blocks (port of the matching composables in android ui/menu/MenuScreen.kt):
/// top bar, banner (ShopHero + PizzaArt), search field, live active-order cards, closed notice,
/// category chips (inline and pinned), section header, empty hint.
///
/// Surface (used only inside Features/Menu):
/// - `MenuTopBar(shop: Shop?, hasActiveOrders: Bool, onOpenOrders: @escaping () -> Void, onOpenProfile: @escaping () -> Void)`
/// - `MenuShopHero(shop: Shop?)`, `MenuPizzaArt()`
/// - `MenuSearchField(query: Binding<String>)`
/// - `MenuActiveOrders(orders: [Order], onOpenOrder: @escaping (Int) -> Void)`
/// - `MenuClosedNotice(shop: Shop)`
/// - `MenuCategoryChips(titles: [String], selectedIndex: Int, autoScroll: Bool, onSelect: @escaping (Int) -> Void)`
/// - `MenuPinnedChips(titles: [String], selectedIndex: Int, onSelect: @escaping (Int) -> Void)`
/// - `MenuSectionHeader(title: String, count: Int)`, `MenuEmptyHint(icon: AppIcon, title: String, text: String)`
/// - `func menuCafeName(_ shop: Shop?) -> String`, `func menuShopStatusLine(_ shop: Shop) -> String`,
///   `func menuHeroLines(_ shop: Shop?) -> (title: String, sub: String)`, `func menuHeroTitleSize(_ title: String) -> Int`

import SwiftUI

func menuCafeName(_ shop: Shop?) -> String {
    if let name = shop?.cafeName, !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
        return name
    }
    return "Amora"
}

func menuShopStatusLine(_ shop: Shop) -> String {
    if !shop.isAcceptingOrders {
        return "Buyurtma olinmayapti"
    }
    if !shop.isOpen {
        return "Yopiq · \(shop.openTime)–\(shop.closeTime)"
    }
    if shop.openTime == shop.closeTime {
        return "Ochiq · kecha-kunduz"
    }
    return "Ochiq · \(shop.openTime)–\(shop.closeTime)"
}

// MARK: - Yuqori satr

/// Yuqori satr: kafe nomi va holati, o'ngda "Buyurtmalarim" va "Profil" tugmalari.
struct MenuTopBar: View {
    let shop: Shop?
    let hasActiveOrders: Bool
    let onOpenOrders: () -> Void
    let onOpenProfile: () -> Void
    @Environment(\.amoraColors) private var colors

    init(shop: Shop?, hasActiveOrders: Bool, onOpenOrders: @escaping () -> Void, onOpenProfile: @escaping () -> Void) {
        self.shop = shop
        self.hasActiveOrders = hasActiveOrders
        self.onOpenOrders = onOpenOrders
        self.onOpenProfile = onOpenProfile
    }

    var body: some View {
        let name = menuCafeName(shop)
        HStack(spacing: 0) {
            LogoTile(letter: String(name.prefix(1)).uppercased())
            Spacer().frame(width: 12)
            VStack(alignment: .leading, spacing: 0) {
                Text(name)
                    .amoraText(.titleLarge)
                    .foregroundColor(colors.onBackground)
                    .lineLimit(1)
                    .truncationMode(.tail)
                    .accessibilityAddTraits(.isHeader)
                if let shop {
                    statusRow(shop)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            Spacer().frame(width: 8)
            RoundButton(icon: .receipt, label: "Buyurtmalarim", onClick: onOpenOrders)
                .overlay(alignment: .topTrailing) {
                    if hasActiveOrders {
                        // Faol buyurtma borligini bildiruvchi nuqta
                        Circle()
                            .fill(colors.primary)
                            .frame(width: 6, height: 6)
                            .padding(2)
                            .background(Circle().fill(colors.background))
                            .offset(x: -2, y: 2)
                            .allowsHitTesting(false)
                            .accessibilityHidden(true)
                    }
                }
            Spacer().frame(width: 8)
            RoundButton(icon: .user, label: "Profil", onClick: onOpenProfile)
        }
        .padding(.horizontal, 16)
        .padding(.top, 8)
        .padding(.bottom, 16)
        .frame(maxWidth: .infinity)
        .background(GlassStrip(fade: .bottom).ignoresSafeArea(edges: .top))
    }

    private func statusRow(_ shop: Shop) -> some View {
        let open = shop.isOpen && shop.isAcceptingOrders
        let color = open ? colors.success : colors.hint
        return HStack(spacing: 6) {
            Circle()
                .fill(color)
                .frame(width: 6, height: 6)
            Text(menuShopStatusLine(shop))
                .amoraText(AmoraTextStyle.labelSmall.with(size: 12, tracking: 0))
                .foregroundColor(color)
                .lineLimit(1)
                .truncationMode(.tail)
        }
        .accessibilityElement(children: .combine)
    }
}

// MARK: - Banner

/// Banner sarlavhasi va izohi. Kafe botda o'z matnini (aksiya) yozgan bo'lsa o'sha,
/// aks holda yetkazish shartlari ko'rsatiladi.
func menuHeroLines(_ shop: Shop?) -> (title: String, sub: String) {
    let warm = "Issiq holda, eshigingizgacha"
    guard let shop else {
        return ("Mazali taomlar\nuyingizgacha", warm)
    }
    let defaultTitle: String
    let defaultSub: String
    if shop.deliveryFee <= 0 {
        defaultTitle = "Yetkazish\nbepul"
        defaultSub = warm
    } else if let freeFrom = shop.freeDeliveryFrom {
        defaultTitle = "Yetkazish\n" + formatSum(shop.deliveryFee)
        defaultSub = formatSum(freeFrom) + "dan yetkazish bepul"
    } else {
        defaultTitle = "Yetkazish\n" + formatSum(shop.deliveryFee)
        defaultSub = warm
    }
    let customTitle = (shop.bannerTitle ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
    let customSub = (shop.bannerText ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
    return (customTitle.isEmpty ? defaultTitle : customTitle, customSub.isEmpty ? defaultSub : customSub)
}

/// Uzun sarlavha ikki qatorga sig'ishi uchun harf kichrayadi.
func menuHeroTitleSize(_ title: String) -> Int {
    let normalized = title.replacingOccurrences(of: "\r\n", with: "\n").replacingOccurrences(of: "\r", with: "\n")
    let lines = normalized.split(separator: "\n", omittingEmptySubsequences: false)
    let longest = lines.map { $0.count }.max() ?? 0
    // Bitta qatorli uzun matn ikki qatorga bo'linadi
    let perLine = (lines.count == 1 && longest > 13) ? (longest + 1) / 2 + 3 : longest
    if perLine <= 13 {
        return 29
    }
    if perLine <= 16 {
        return 24
    }
    if perLine <= 20 {
        return 20
    }
    return 17
}

/// Ko'mir rangli banner: kafe nomi, yetkazish sharti va o'ngda pitsa rasmi.
struct MenuShopHero: View {
    let shop: Shop?
    @Environment(\.amoraColors) private var colors

    init(shop: Shop?) {
        self.shop = shop
    }

    var body: some View {
        let name = menuCafeName(shop)
        let lines = menuHeroLines(shop)
        let titleSize = CGFloat(menuHeroTitleSize(lines.title))
        let shape = RoundedRectangle(cornerRadius: 28, style: .continuous)
        ZStack(alignment: .topLeading) {
            MenuPizzaArt()
            VStack(alignment: .leading, spacing: 0) {
                Text(name.uppercased())
                    .amoraText(AmoraTextStyle.labelSmall.with(size: 11, tracking: 1.4))
                    .foregroundColor(Color(argb: 0xFFF7B8A8))
                    .lineLimit(1)
                    .truncationMode(.tail)
                Spacer().frame(height: 6)
                Text(lines.title)
                    .amoraText(AmoraTextStyle.headlineLarge.with(size: titleSize, lineHeight: titleSize + 1))
                    .foregroundColor(.white)
                    .lineLimit(2)
                    .truncationMode(.tail)
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
                HStack(spacing: 6) {
                    IconImage(.bolt, size: 14, tint: colors.amber)
                    Text(lines.sub)
                        .amoraText(.bodySmall)
                        .foregroundColor(colors.onInkMuted)
                        .lineLimit(2)
                        .truncationMode(.tail)
                }
            }
            .padding(.leading, 18)
            .padding(.top, 18)
            .padding(.bottom, 14)
            .padding(.trailing, 104)
        }
        .frame(maxWidth: .infinity)
        .frame(height: 154)
        .dynamicTypeSize(...amoraControlTypeLimit)
        .clipShape(shape)
        .background(shape.fill(colors.ink).softShadow(elevation: 14, alpha: 0.22))
        .accessibilityElement(children: .combine)
    }
}

// Pitsa ustidagi kolbasa va rayhon joylari (markazdan, radius ulushida)
private let pizzaSpots: [(CGFloat, CGFloat)] = [
    (-0.52, -0.34),
    (-0.08, -0.58),
    (-0.60, 0.16),
    (-0.14, -0.06),
    (-0.34, 0.52),
    (0.12, 0.40),
    (0.28, -0.26),
]

private let pizzaLeaves: [(CGFloat, CGFloat, CGFloat)] = [
    (-0.34, -0.02, 30),
    (-0.02, -0.30, -40),
    (-0.12, 0.24, 70),
    (-0.50, -0.10, -20),
]

/// Bannerning o'ng chetidan yarmi ko'rinib turadigan pitsa (oddiy shakllardan chizilgan).
struct MenuPizzaArt: View {
    init() {}

    var body: some View {
        Canvas { context, size in
            let radius = size.height * 0.56
            let center = CGPoint(x: size.width - radius * 0.42, y: size.height * 0.48)
            context.fill(MenuPizzaArt.circle(center, radius), with: .color(Color(argb: 0xFFD08A3C)))
            context.fill(MenuPizzaArt.circle(center, radius * 0.955), with: .color(Color(argb: 0xFFEFB45F)))
            context.fill(MenuPizzaArt.circle(center, radius * 0.83), with: .color(Color(argb: 0xFFE5432A)))
            context.fill(MenuPizzaArt.circle(center, radius * 0.79), with: .color(Color(argb: 0xFFF7D98B)))
            for spot in pizzaSpots {
                let point = CGPoint(x: center.x + spot.0 * radius, y: center.y + spot.1 * radius)
                context.fill(MenuPizzaArt.circle(point, radius * 0.135), with: .color(Color(argb: 0xFFC7321C)))
                context.fill(MenuPizzaArt.circle(point, radius * 0.105), with: .color(Color(argb: 0xFFE5432A)))
            }
            for leaf in pizzaLeaves {
                let point = CGPoint(x: center.x + leaf.0 * radius, y: center.y + leaf.1 * radius)
                let width = radius * 0.17
                let height = radius * 0.085
                let rect = CGRect(x: point.x - width / 2, y: point.y - height / 2, width: width, height: height)
                let transform = CGAffineTransform(translationX: point.x, y: point.y)
                    .rotated(by: leaf.2 * .pi / 180)
                    .translatedBy(x: -point.x, y: -point.y)
                context.fill(Path(ellipseIn: rect).applying(transform), with: .color(Color(argb: 0xFF1E9E61)))
            }
        }
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }

    nonisolated private static func circle(_ center: CGPoint, _ radius: CGFloat) -> Path {
        Path(ellipseIn: CGRect(x: center.x - radius, y: center.y - radius, width: radius * 2, height: radius * 2))
    }
}

// MARK: - Qidiruv

struct MenuSearchField: View {
    @Binding var query: String
    @FocusState private var focused: Bool
    @Environment(\.amoraColors) private var colors

    init(query: Binding<String>) {
        self._query = query
    }

    var body: some View {
        let text = Binding<String>(
            get: { query },
            set: { value in query = String(value.prefix(40)) }
        )
        HStack(spacing: 12) {
            IconImage(.search, size: 20, tint: colors.hint)
            TextField("", text: text, prompt: fieldPrompt("Taom qidirish", colors))
                .focused($focused)
                .submitLabel(.search)
                .onSubmit { focused = false }
                .frame(maxWidth: .infinity)
            if !query.isEmpty {
                Button(action: { query = "" }) {
                    IconImage(.close, size: 20, tint: colors.onSurfaceVariant)
                        .frame(width: 36, height: 36)
                        .contentShape(Rectangle())
                }
                .buttonStyle(PressScaleStyle(scale: 0.9))
                .accessibilityLabel("Qidiruvni tozalash")
                .padding(.trailing, -6)
            }
        }
        .fieldStyle()
    }
}

// MARK: - Faol buyurtmalar va yopiq kafe

/// Faol buyurtmalar: bosilsa, buyurtma holati ekrani ochiladi.
struct MenuActiveOrders: View {
    let orders: [Order]
    let onOpenOrder: (Int) -> Void
    @Environment(\.amoraColors) private var colors

    init(orders: [Order], onOpenOrder: @escaping (Int) -> Void) {
        self.orders = orders
        self.onOpenOrder = onOpenOrder
    }

    var body: some View {
        VStack(spacing: 10) {
            ForEach(orders) { order in
                SectionCard(padding: 14, onClick: { onOpenOrder(order.id) }) {
                    HStack(spacing: 0) {
                        IconTile(icon: statusIcon(order.status))
                        Spacer().frame(width: 12)
                        VStack(alignment: .leading, spacing: 0) {
                            Text("Buyurtma №" + String(order.id))
                                .amoraText(.bodySmall)
                                .foregroundColor(colors.hint)
                            Text(order.statusLabel)
                                .amoraText(.titleMedium)
                                .foregroundColor(colors.onSurface)
                                .lineLimit(1)
                                .truncationMode(.tail)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        IconImage(.chevron, size: 20, tint: colors.hint)
                    }
                    Spacer().frame(height: 12)
                    OrderProgressBar(status: order.status)
                }
            }
        }
    }
}

struct MenuClosedNotice: View {
    let shop: Shop
    @Environment(\.amoraColors) private var colors

    init(shop: Shop) {
        self.shop = shop
    }

    var body: some View {
        let text = shop.isAcceptingOrders
            ? "Kafe hozir yopiq. Ish vaqti: \(shop.openTime) dan \(shop.closeTime) gacha. "
                + "Menyuni ko'rishingiz mumkin, buyurtma esa ish vaqtida qabul qilinadi."
            : "Kafe hozir buyurtma qabul qilmayapti. Birozdan keyin qayta urinib ko'ring."
        Text(text)
            .amoraText(.bodyMedium)
            .foregroundColor(colors.onErrorContainer)
            .fixedSize(horizontal: false, vertical: true)
            .padding(.horizontal, 16)
            .padding(.vertical, 14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: AmoraRadius.large, style: .continuous)
                    .fill(colors.errorContainer)
            )
    }
}

// MARK: - Bo'limlar

/// Bo'limlar qatori. Tanlangan bo'lim tugmasi har doim ko'rinib turadi (`autoScroll`).
struct MenuCategoryChips: View {
    let titles: [String]
    let selectedIndex: Int
    let autoScroll: Bool
    let onSelect: (Int) -> Void

    init(titles: [String], selectedIndex: Int, autoScroll: Bool, onSelect: @escaping (Int) -> Void) {
        self.titles = titles
        self.selectedIndex = selectedIndex
        self.autoScroll = autoScroll
        self.onSelect = onSelect
    }

    private static func chipId(_ index: Int) -> String {
        "menu-chip-\(index)"
    }

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView(.horizontal, showsIndicators: false) {
                // Har tugmaning chap chekinishi (16) unga qo'shib o'lchanadi: surilganda tugma chetga yopishmaydi.
                // Manfiy oraliq bilan tugmalar orasi 8 bo'lib qoladi.
                HStack(spacing: -8) {
                    ForEach(Array(titles.enumerated()), id: \.offset) { index, title in
                        TabChip(text: title, selected: index == selectedIndex, onClick: { onSelect(index) })
                            .padding(.leading, 16)
                            .id(MenuCategoryChips.chipId(index))
                    }
                }
                .padding(.trailing, 16)
            }
            .onAppear {
                if autoScroll && selectedIndex > 0 {
                    proxy.scrollTo(MenuCategoryChips.chipId(selectedIndex), anchor: .leading)
                }
            }
            .onChange(of: selectedIndex) { _, index in
                if autoScroll {
                    withAnimation(.easeInOut(duration: 0.3)) {
                        proxy.scrollTo(MenuCategoryChips.chipId(index), anchor: .leading)
                    }
                }
            }
            .onChange(of: autoScroll) { _, enabled in
                if enabled {
                    proxy.scrollTo(MenuCategoryChips.chipId(selectedIndex), anchor: .leading)
                }
            }
        }
    }
}

/// Yuqori satr ostida qotib turgan bo'limlar qatori: ustki 18 pt satrning tumaniga kirib turadi,
/// pastki cheti asta yo'qoladi.
struct MenuPinnedChips: View {
    let titles: [String]
    let selectedIndex: Int
    let onSelect: (Int) -> Void
    @Environment(\.amoraColors) private var colors

    init(titles: [String], selectedIndex: Int, onSelect: @escaping (Int) -> Void) {
        self.titles = titles
        self.selectedIndex = selectedIndex
        self.onSelect = onSelect
    }

    var body: some View {
        let total = menuPinnedChipsOverlap + menuPinnedChipsHeight + 14
        VStack(spacing: 0) {
            Color.clear
                .frame(height: menuPinnedChipsOverlap)
                .allowsHitTesting(false)
            MenuCategoryChips(titles: titles, selectedIndex: selectedIndex, autoScroll: true, onSelect: onSelect)
                .frame(height: menuPinnedChipsHeight)
                // Qator balandligi qat'iy: juda katta shriftda yozuv kesilib qolmasin
                .dynamicTypeSize(...amoraControlTypeLimit)
                .padding(.bottom, 14)
                // Bo'sh joyiga bosilganda bosish ostidagi ro'yxatga o'tib ketmaydi
                .background(Color.clear.contentShape(Rectangle()).onTapGesture {})
        }
        .frame(maxWidth: .infinity)
        .background(
            ZStack {
                Rectangle().fill(Material.ultraThinMaterial)
                Rectangle().fill(glassTint(.fog, colors))
            }
            .mask {
                LinearGradient(
                    stops: [
                        Gradient.Stop(color: .clear, location: 0),
                        Gradient.Stop(color: .black, location: menuPinnedChipsOverlap / total),
                        Gradient.Stop(color: .black, location: 0.70),
                        Gradient.Stop(color: .clear, location: 1),
                    ],
                    startPoint: .top,
                    endPoint: .bottom
                )
            }
            .allowsHitTesting(false)
            .accessibilityHidden(true)
        )
    }
}

struct MenuSectionHeader: View {
    let title: String
    let count: Int
    @Environment(\.amoraColors) private var colors

    init(title: String, count: Int) {
        self.title = title
        self.count = count
    }

    var body: some View {
        HStack(alignment: .bottom, spacing: 0) {
            Text(title)
                .amoraText(.headlineSmall)
                .foregroundColor(colors.onBackground)
                .lineLimit(1)
                .truncationMode(.tail)
                .frame(maxWidth: .infinity, alignment: .leading)
            Text(String(count) + " ta taom")
                .amoraText(.bodySmall)
                .foregroundColor(colors.hint)
                .lineLimit(1)
                .fixedSize()
                .padding(.bottom, 4)
        }
        .padding(.horizontal, 4)
        .padding(.top, 12)
        .padding(.bottom, 2)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isHeader)
    }
}

/// Ro'yxat ichidagi bo'sh holat (masalan, qidiruvda hech narsa topilmadi).
struct MenuEmptyHint: View {
    let icon: AppIcon
    let title: String
    let text: String
    @Environment(\.amoraColors) private var colors

    init(icon: AppIcon, title: String, text: String) {
        self.icon = icon
        self.title = title
        self.text = text
    }

    var body: some View {
        VStack(spacing: 0) {
            IconTile(icon: icon, size: 80, iconSize: 34)
            Spacer().frame(height: 16)
            Text(title)
                .amoraText(.titleLarge)
                .foregroundColor(colors.onBackground)
                .multilineTextAlignment(.center)
            Spacer().frame(height: 4)
            Text(text)
                .amoraText(.bodyMedium)
                .foregroundColor(colors.onSurfaceVariant)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 40)
    }
}
