/// Home screen: menu (port of android ui/menu/MenuScreen.kt).
///
/// Surface:
/// - `struct MenuScreen: View` - `MenuScreen()`; needs `.environment(AppContainer)` and `.environment(Router)`.
///
/// Layout: glass top bar (cafe, open status, "Buyurtmalarim" + "Profil"), then a scrolling list:
/// banner, live active-order cards, closed notice, search (6+ products), category chips, and one
/// section (header + product grid) per category. The chips row pins under the top bar as glass once
/// it scrolls away; the selected chip follows the scroll position. A dark glass cart bar floats at the
/// bottom while the cart has items. Tapping a product opens `MenuProductSheet`.
///
/// Internal helpers shared by the Menu feature files: `MenuSection`, `buildMenuSections(_:)`,
/// `searchMenuProducts(_:_:)`, `menuPinnedChipsHeight`.

import SwiftUI

private let activeOrdersRefreshSeconds: UInt64 = 15
private let activeOrdersLiveRefreshSeconds: UInt64 = 60

// Qidiruv maydoni menyu shunchadan katta bo'lsagina ko'rinadi: bir nechta taomda u ortiqcha
private let searchMinProducts = 6

// Ro'yxat tepasida qotib turadigan bo'limlar qatorining balandligi
let menuPinnedChipsHeight: CGFloat = 52

// Qotib turgan qator yuqori satrning "tumaniga" shuncha kirib turadi: ikkalasi bitta shishadek ko'rinadi
let menuPinnedChipsOverlap: CGFloat = 18

// Ro'yxat elementlari orasidagi masofa
private let menuItemSpacing: CGFloat = 12

/// Menyudagi bitta bo'lim: kategoriya va uning taomlari.
struct MenuSection: Identifiable, Equatable {
    let id: Int
    let title: String
    let products: [Product]
}

func buildMenuSections(_ menu: MenuData) -> [MenuSection] {
    let byCategory = Dictionary(grouping: menu.products, by: { $0.categoryId })
    var sections: [MenuSection] = []
    for category in menu.categories {
        if let products = byCategory[category.id], !products.isEmpty {
            sections.append(MenuSection(id: category.id, title: category.name, products: products))
        }
    }
    if let withoutCategory = byCategory[nil], !withoutCategory.isEmpty {
        let title = sections.isEmpty ? "Menyu" : "Boshqa taomlar"
        sections.append(MenuSection(id: 0, title: title, products: withoutCategory))
    }
    return sections
}

func searchMenuProducts(_ menu: MenuData, _ query: String) -> [Product] {
    // Ikkala tomon ham bir xil ko'rinishga keltiriladi: "qo’y" yozilsa "Qo'y go'shti" topiladi
    let needle = normalizeSearchText(query)
    if needle.isEmpty { return menu.products }
    return menu.products.filter { product in
        normalizeSearchText(product.name).contains(needle)
            || normalizeSearchText(product.description).contains(needle)
    }
}

private func isBlankText(_ text: String) -> Bool {
    text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
}

/// Ro'yxat tuzilishi: qaysi bloklar ko'rinadi va qaysi bo'limlar chiziladi.
private struct MenuLayout {
    var sections: [MenuSection] = []
    var shownSections: [MenuSection] = []
    var searching = false
    var showSearch = false
    var showChips = false
    var closed = false
    /// Har bo'lim sarlavhasining ro'yxatdagi o'rni (Android headerIndexes): o'zgarsa, tanlangan bo'lim tashlanadi.
    var headerIndexes: [Int] = []
}

private func makeMenuLayout(menu: MenuData?, shop: Shop?, query: String, hasOrders: Bool) -> MenuLayout {
    var layout = MenuLayout()
    guard let menu else { return layout }
    let sections = buildMenuSections(menu)
    let searching = !isBlankText(query)
    layout.sections = sections
    layout.searching = searching
    layout.showSearch = menu.products.count >= searchMinProducts
    if let shop {
        layout.closed = !shop.isOpen
    }
    // Qidiruv paytida bo'limlar o'rniga bitta natijalar ro'yxati ko'rsatiladi
    if searching {
        let found = searchMenuProducts(menu, query)
        layout.shownSections = found.isEmpty ? [] : [MenuSection(id: -1, title: "Qidiruv natijalari", products: found)]
    } else {
        layout.shownSections = sections
    }
    layout.showChips = !searching && sections.count > 1

    // Ro'yxat boshidagi bloklar. Ulardan keyin har bo'lim: sarlavha + taomlar.
    var next = 1
    if hasOrders { next += 1 }
    if layout.closed { next += 1 }
    if layout.showSearch { next += 1 }
    if layout.showChips { next += 1 }
    var indexes: [Int] = []
    for section in layout.shownSections {
        indexes.append(next)
        next += 1 + section.products.count
    }
    layout.headerIndexes = indexes
    return layout
}

private func menuSectionAnchorId(_ index: Int) -> String {
    "menu-section-\(index)"
}

/// Taom oynasi uchun tanlangan taom.
private struct MenuSelectedProduct: Identifiable, Equatable {
    let id: Int
}

/// Surilish holatini kuzatish uchun (ekranni qayta chizdirmaydi).
private final class MenuScrollTracker {
    var tapTime: Date = .distantPast
    var settledTop: CGFloat = 0
}

// MARK: - Joylashuvni o'lchash

/// Ro'yxat ichidagi bloklarning ekrandagi joyi (global koordinatada).
private struct MenuFramesKey: PreferenceKey {
    static let defaultValue: [String: CGRect] = [:]

    static func reduce(value: inout [String: CGRect], nextValue: () -> [String: CGRect]) {
        value.merge(nextValue(), uniquingKeysWith: { _, new in new })
    }
}

private struct MenuBarFrameKey: PreferenceKey {
    static let defaultValue: CGRect = .zero

    static func reduce(value: inout CGRect, nextValue: () -> CGRect) {
        value = nextValue()
    }
}

private struct MenuDockTopKey: PreferenceKey {
    static let defaultValue: CGFloat = 0

    static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) {
        value = nextValue()
    }
}

private extension View {
    func menuFrame(_ name: String) -> some View {
        background(
            GeometryReader { geo in
                Color.clear.preference(key: MenuFramesKey.self, value: [name: geo.frame(in: .global)])
            }
        )
    }
}

// MARK: - Ekran

/// Bosh sahifa. Yuqorida kafe va ikki tugma (buyurtmalarim, profil), o'rtada menyu,
/// savatda taom bo'lsa pastda suzib turadigan shisha "Savat" paneli.
struct MenuScreen: View {
    @Environment(AppContainer.self) private var container

    init() {}

    var body: some View {
        MenuScreenContent(container: container)
    }
}

private struct MenuScreenContent: View {
    let container: AppContainer

    @Environment(Router.self) private var router
    @Environment(\.amoraColors) private var colors
    @Environment(\.scenePhase) private var scenePhase

    @State private var vm: MenuViewModel
    @State private var selected: MenuSelectedProduct? = nil
    @State private var query = ""

    // Surilish holati
    @State private var tracker = MenuScrollTracker()
    @State private var barHeight: CGFloat = 0
    @State private var barBottom: CGFloat = 0
    @State private var dockTop: CGFloat = 0
    @State private var chipsPinned = false
    @State private var scrolledSection = 0
    @State private var tappedSection: Int? = nil

    init(container: AppContainer) {
        self.container = container
        _vm = State(initialValue: MenuViewModel(container: container))
    }

    var body: some View {
        let catalog = container.catalog.state
        let activeOrders = vm.activeOrders
        let layout = makeMenuLayout(
            menu: catalog.menu,
            shop: catalog.shop,
            query: query,
            hasOrders: !activeOrders.isEmpty
        )
        let productsById = productLookup(catalog.menu)
        let current = currentSection(layout)

        ScrollViewReader { proxy in
            mainArea(catalog: catalog, layout: layout, activeOrders: activeOrders, current: current, proxy: proxy)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .safeAreaInset(edge: .top, spacing: 0) {
                    topBar(shop: catalog.shop, hasActiveOrders: !activeOrders.isEmpty)
                }
                .overlay(alignment: .top) {
                    pinnedChips(layout: layout, current: current, proxy: proxy)
                }
                .safeAreaInset(edge: .bottom, spacing: 0) {
                    cartDock(productsById: productsById)
                }
        }
        .background(colors.background.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
        .sheet(item: $selected) { item in
            productSheet(item, productsById: productsById)
        }
        // Boshqa ekran ochilsa (masalan, bildirishnoma bosildi), taom oynasi yopiladi: aks holda u
        // yangi ekranni to'sib qolardi
        .onChange(of: router.path.isEmpty) { _, isEmpty in
            if !isEmpty { selected = nil }
        }
        // Ekran ko'rinib turganda faol buyurtmalar tekshirib turiladi (ilova ochilgandagi birinchi
        // o'qishni `AppContainer.onAppForeground` bajaradi)
        .task(id: scenePhase == .active) {
            await poll()
        }
        .onChange(of: catalog.menu, initial: true) { _, menu in
            guard let menu else { return }
            container.cart.retain(Set(menu.products.map { $0.id }))
            // Menyudan olib tashlangan taomning oynasi yopiladi
            if let id = selected?.id, !menu.products.contains(where: { $0.id == id }) {
                selected = nil
            }
        }
        .onChange(of: layout.headerIndexes) { _, _ in
            tappedSection = nil
        }
    }

    // MARK: Ma'lumot

    private func productLookup(_ menu: MenuData?) -> [Int: Product] {
        var result: [Int: Product] = [:]
        for product in menu?.products ?? [] {
            result[product.id] = product
        }
        return result
    }

    /// Bo'lim tugmasi bosilgan bo'lsa o'sha, aks holda surilish joyiga qarab aniqlangan bo'lim.
    private func currentSection(_ layout: MenuLayout) -> Int {
        let count = layout.shownSections.count
        guard count > 0 else { return 0 }
        let index = tappedSection ?? scrolledSection
        return min(max(index, 0), count - 1)
    }

    private func poll() async {
        guard scenePhase == .active else { return }
        while !Task.isCancelled {
            // Jonli ulanish ishlayotgan bo'lsa, o'zgarish haqida server o'zi xabar beradi:
            // bu so'rov faqat ehtiyot chorasi bo'lib qoladi
            let seconds = vm.liveConnected ? activeOrdersLiveRefreshSeconds : activeOrdersRefreshSeconds
            do {
                try await Task.sleep(nanoseconds: seconds * 1_000_000_000)
            } catch {
                return
            }
            vm.refreshActiveOrders()
        }
    }

    // MARK: Asosiy qism

    @ViewBuilder
    private func mainArea(
        catalog: CatalogState,
        layout: MenuLayout,
        activeOrders: [Order],
        current: Int,
        proxy: ScrollViewProxy
    ) -> some View {
        if let menu = catalog.menu {
            menuList(menu: menu, shop: catalog.shop, layout: layout, activeOrders: activeOrders, current: current, proxy: proxy)
        } else if catalog.loading {
            MenuSkeleton()
        } else {
            MessageBox(
                icon: .refresh,
                title: "Menyu yuklanmadi",
                text: catalog.error,
                actionLabel: "Qayta urinish",
                onAction: { vm.retry() }
            )
            .amoraRefreshable(action: { await vm.pullToRefresh() })
        }
    }

    private func menuList(
        menu: MenuData,
        shop: Shop?,
        layout: MenuLayout,
        activeOrders: [Order],
        current: Int,
        proxy: ScrollViewProxy
    ) -> some View {
        ScrollView {
            VStack(spacing: menuItemSpacing) {
                leadingBlocks(shop: shop, layout: layout, activeOrders: activeOrders, current: current, proxy: proxy)
                if layout.shownSections.isEmpty {
                    emptyBlock(searching: layout.searching)
                        .padding(.horizontal, 16)
                }
                ForEach(Array(layout.shownSections.enumerated()), id: \.element.id) { index, section in
                    sectionBlock(index: index, section: section)
                }
            }
            .menuFrame("content")
            .padding(.bottom, 20)
        }
        .scrollDismissesKeyboard(.immediately)
        .amoraRefreshable(action: { await vm.pullToRefresh() })
        .onPreferenceChange(MenuFramesKey.self) { frames in
            // iOS 18 SDK: bu yopiq funksiya @Sendable; SwiftUI uni baribir asosiy oqimda chaqiradi
            MainActor.assumeIsolated {
                updateScroll(frames, sectionCount: layout.shownSections.count, chipsShown: layout.showChips)
            }
        }
    }

    @ViewBuilder
    private func leadingBlocks(
        shop: Shop?,
        layout: MenuLayout,
        activeOrders: [Order],
        current: Int,
        proxy: ScrollViewProxy
    ) -> some View {
        MenuShopHero(shop: shop)
            .padding(.horizontal, 16)
        if !activeOrders.isEmpty {
            MenuActiveOrders(orders: activeOrders, onOpenOrder: { id in router.open(.order(id: id)) })
                .padding(.horizontal, 16)
        }
        if layout.closed, let shop {
            MenuClosedNotice(shop: shop)
                .padding(.horizontal, 16)
        }
        if layout.showSearch {
            MenuSearchField(query: $query)
                .padding(.horizontal, 16)
        }
        if layout.showChips {
            // Ro'yxat ichidagi qator ekran chetigacha cho'ziladi
            MenuCategoryChips(
                titles: layout.sections.map { $0.title },
                selectedIndex: current,
                autoScroll: !chipsPinned,
                onSelect: { index in selectSection(index, count: layout.sections.count, proxy: proxy) }
            )
            .menuFrame("chips")
        }
    }

    @ViewBuilder
    private func emptyBlock(searching: Bool) -> some View {
        if searching {
            MenuEmptyHint(icon: .search, title: "Hech narsa topilmadi", text: "Boshqa so'z bilan qidirib ko'ring")
        } else {
            MenuEmptyHint(icon: .info, title: "Menyu hozircha bo'sh", text: "Taomlar tez orada qo'shiladi")
        }
    }

    private func sectionBlock(index: Int, section: MenuSection) -> some View {
        let cart = container.cart.items
        return VStack(spacing: 0) {
            // Bo'limga o'tilganda sarlavha qotib turgan bo'limlar qatori ostida to'xtaydi
            Color.clear
                .frame(height: menuPinnedChipsHeight)
                .id(menuSectionAnchorId(index))
                .padding(.top, -menuPinnedChipsHeight)
                .accessibilityHidden(true)
            MenuSectionHeader(title: section.title, count: section.products.count)
                .menuFrame("h\(index)")
            Color.clear.frame(height: menuItemSpacing)
            LazyVGrid(
                columns: [GridItem(.adaptive(minimum: 156), spacing: menuItemSpacing)],
                spacing: menuItemSpacing
            ) {
                ForEach(section.products) { product in
                    MenuProductCard(
                        product: product,
                        imageURL: container.imageURL(product.imageUrl),
                        quantity: cart[product.id] ?? 0,
                        onAdd: { container.cart.add(product.id) },
                        onRemove: { container.cart.remove(product.id) },
                        onClick: { selected = MenuSelectedProduct(id: product.id) }
                    )
                }
            }
        }
        .padding(.horizontal, 16)
    }

    // MARK: Surilish

    /// Qotib turgan qator, joriy bo'lim va "bo'lim tugmasi bosilgan" holatini surilish joyidan hisoblaydi.
    /// Hamma o'lchov global koordinatada; `barBottom` = yuqori satr osti chizig'i.
    private func updateScroll(_ frames: [String: CGRect], sectionCount: Int, chipsShown: Bool) {
        let line = barBottom
        guard line > 0 else { return }

        var pinned = false
        if chipsShown, let chips = frames["chips"] {
            pinned = chips.minY < line - 0.5
        }
        if pinned != chipsPinned {
            chipsPinned = pinned
        }

        let content = frames["content"]
        let contentTop = content?.minY ?? line
        let canScrollBack = contentTop < line - 1
        var section = 0
        if sectionCount > 0 {
            if canScrollBack, let content, dockTop > 0, content.maxY <= dockTop - 20 + 1.5 {
                // Ro'yxat oxiriga yetdi: oxirgi bo'lim qisqa bo'lsa ham u belgilanadi
                section = sectionCount - 1
            } else {
                // Qotib turgan bo'limlar qatori ostidan ko'rinib turgan birinchi element qaysi bo'limda?
                let threshold = line + menuPinnedChipsHeight + menuItemSpacing
                for index in 0..<sectionCount {
                    if let header = frames["h\(index)"], header.minY <= threshold {
                        section = index
                    }
                }
            }
        }
        if section != scrolledSection {
            scrolledSection = section
        }

        // Bo'lim tugmasi bosilganda aynan o'sha bo'lim belgilanadi (ro'yxat u yergacha surila olmasa ham).
        // Mijoz ro'yxatni o'zi sura boshlashi bilan yana surilish joyiga qarab aniqlanadi.
        if tappedSection != nil {
            if Date().timeIntervalSince(tracker.tapTime) < 0.8 {
                tracker.settledTop = contentTop
            } else if abs(contentTop - tracker.settledTop) > 4 {
                tappedSection = nil
            }
        }
    }

    private func selectSection(_ index: Int, count: Int, proxy: ScrollViewProxy) {
        guard index >= 0, index < count else { return }
        tappedSection = index
        tracker.tapTime = Date()
        withAnimation(.easeInOut(duration: 0.4)) {
            proxy.scrollTo(menuSectionAnchorId(index), anchor: .top)
        }
    }

    // MARK: Satrlar

    private func topBar(shop: Shop?, hasActiveOrders: Bool) -> some View {
        MenuTopBar(
            shop: shop,
            hasActiveOrders: hasActiveOrders,
            onOpenOrders: { router.open(.orders) },
            onOpenProfile: { router.open(.profile) }
        )
        .background(
            GeometryReader { geo in
                Color.clear.preference(key: MenuBarFrameKey.self, value: geo.frame(in: .global))
            }
        )
        .onPreferenceChange(MenuBarFrameKey.self) { frame in
            MainActor.assumeIsolated {
                if frame.height != barHeight {
                    barHeight = frame.height
                }
                if frame.maxY != barBottom {
                    barBottom = frame.maxY
                }
            }
        }
    }

    /// Bo'limlar qatori ro'yxat bilan birga surilib ketgach, yuqori satr ostida shisha bo'lib qotadi.
    private func pinnedChips(layout: MenuLayout, current: Int, proxy: ScrollViewProxy) -> some View {
        let visible = chipsPinned && layout.showChips && barHeight > 0
        return ZStack(alignment: .top) {
            if visible {
                MenuPinnedChips(
                    titles: layout.sections.map { $0.title },
                    selectedIndex: current,
                    onSelect: { index in selectSection(index, count: layout.sections.count, proxy: proxy) }
                )
                .padding(.top, max(barHeight - menuPinnedChipsOverlap, 0))
                .transition(.opacity)
            }
        }
        .frame(maxWidth: .infinity, alignment: .top)
        .animation(.easeInOut(duration: 0.2), value: visible)
    }

    /// Pastdagi "Savat" paneli. Savat bo'sh bo'lsa joy egallamaydi.
    private func cartDock(productsById: [Int: Product]) -> some View {
        let lines = container.cart.lines
        let count = lines.reduce(0) { $0 + $1.quantity }
        let total = lines.reduce(0) { sum, line in
            sum + (productsById[line.productId]?.price ?? 0) * line.quantity
        }
        let visible = count > 0
        return VStack(spacing: 0) {
            if visible {
                MenuCartBar(count: count, total: total, onClick: { router.open(.cart) })
                    .transition(
                        .asymmetric(
                            insertion: AnyTransition.move(edge: .bottom).combined(with: .opacity)
                                .animation(.easeOut(duration: 0.32)),
                            removal: AnyTransition.move(edge: .bottom).combined(with: .opacity)
                                .animation(.easeIn(duration: 0.24))
                        )
                    )
            }
        }
        .frame(maxWidth: .infinity)
        .animation(.easeOut(duration: 0.3), value: visible)
        .background(
            GeometryReader { geo in
                Color.clear.preference(key: MenuDockTopKey.self, value: geo.frame(in: .global).minY)
            }
        )
        .onPreferenceChange(MenuDockTopKey.self) { top in
            MainActor.assumeIsolated {
                if top != dockTop {
                    dockTop = top
                }
            }
        }
    }

    // MARK: Taom oynasi

    @ViewBuilder
    private func productSheet(_ item: MenuSelectedProduct, productsById: [Int: Product]) -> some View {
        if let product = productsById[item.id] {
            MenuProductSheet(container: container, product: product)
        }
    }
}
