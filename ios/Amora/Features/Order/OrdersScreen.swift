/// All of the customer's orders, newest first (port of android ui/orders/OrdersScreen.kt): filter chips
/// (Hammasi / Faol / Yakunlangan), order cards with status, progress and "Kuzatish" / "Yana shunday",
/// pagination ("Yana ko'rsatish"), pull to refresh, empty and error states. Opened from the menu's
/// "Buyurtmalarim" button.
///
/// Surface:
/// - `struct OrdersScreen: View` - `OrdersScreen()`; needs `AppContainer` and `Router` in the environment.

import SwiftUI

private let ordersFilters = ["Hammasi", "Faol", "Yakunlangan"]
// Tor ekranda holat belgisi sarlavha ostiga tushadi, aks holda u sarlavhani siqib qo'yadi
private let ordersCompactWidth: CGFloat = 380

struct OrdersScreen: View {
    @Environment(AppContainer.self) private var container
    @Environment(Router.self) private var router
    @Environment(\.amoraColors) private var colors
    @Environment(\.scenePhase) private var scenePhase

    @State private var vm = OrdersViewModel()
    @State private var toast = ToastCenter()
    @State private var filter = 0

    init() {}

    private var shown: [Order] {
        switch filter {
        case 1:
            return vm.orders.filter { $0.isActive }
        case 2:
            return vm.orders.filter { !$0.isActive }
        default:
            return vm.orders
        }
    }

    /// Kartochkadagi kichik rasm: buyurtmadagi birinchi taomning menyudagi rasmi
    private var imagesByProduct: [Int: String] {
        var result: [Int: String] = [:]
        for product in container.catalog.menu?.products ?? [] {
            if let url = product.imageUrl {
                result[product.id] = url
            }
        }
        return result
    }

    var body: some View {
        content
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .amoraRefreshable(
                onRefresh: { vm.reload(container, byUser: true) },
                isRefreshing: { vm.refreshing }
            )
            .toastHost(toast)
            .safeAreaInset(edge: .top, spacing: 0) {
                topBar
            }
            .background(colors.background.ignoresSafeArea())
            .toolbar(.hidden, for: .navigationBar)
            // Ekranga har qaytilganda ro'yxat yangilanadi (masalan, buyurtma holati o'zgargan bo'lishi mumkin)
            .onAppear {
                vm.reload(container)
            }
            .onChange(of: scenePhase) { _, phase in
                if phase == .active {
                    vm.reload(container)
                }
            }
            // Buyurtma holati o'zgargani haqida jonli xabar kelsa, ro'yxat o'zi yangilanadi
            .task {
                for await event in container.realtime.events() {
                    if event.orderChange != nil || event == .resync {
                        vm.reload(container)
                    }
                }
            }
    }

    @ViewBuilder
    private var topBar: some View {
        if vm.orders.isEmpty {
            GlassTopBar(title: "Buyurtmalarim", onBack: { router.back() })
        } else {
            GlassTopBar(title: "Buyurtmalarim", onBack: { router.back() }, below: {
                ScrollView(.horizontal) {
                    HStack(spacing: 8) {
                        ForEach(Array(ordersFilters.enumerated()), id: \.offset) { index, title in
                            TabChip(text: title, selected: filter == index, onClick: { filter = index })
                        }
                    }
                    .padding(.horizontal, 16)
                }
                .scrollIndicators(.hidden)
            })
        }
    }

    @ViewBuilder
    private var content: some View {
        if vm.loading {
            OrdersListSkeleton()
        } else if vm.orders.isEmpty, let error = vm.error {
            MessageBox(
                icon: .refresh,
                title: "Buyurtmalar yuklanmadi",
                text: error,
                actionLabel: "Qayta urinish",
                onAction: { vm.reload(container) }
            )
        } else if vm.orders.isEmpty {
            MessageBox(
                icon: .receipt,
                title: "Hali buyurtma yo'q",
                text: "Birinchi buyurtmangiz shu yerda ko'rinadi",
                actionLabel: "Menyuga o'tish",
                onAction: { router.back() }
            )
        } else {
            list
        }
    }

    private var list: some View {
        let items = shown
        let images = imagesByProduct
        let width = AmoraWindow.width
        let compact = width > 0 && width < ordersCompactWidth
        return ScrollView {
            LazyVStack(alignment: .leading, spacing: 12) {
                if items.isEmpty {
                    Text(filter == 1 ? "Hozir faol buyurtma yo'q" : "Yakunlangan buyurtma yo'q")
                        .amoraText(.bodyLarge)
                        .foregroundColor(colors.hint)
                        .multilineTextAlignment(.center)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 48)
                }
                ForEach(items) { order in
                    let firstProductId = order.items.first?.productId
                    OrdersOrderCard(
                        order: order,
                        imageURL: container.imageURL(firstProductId.flatMap { images[$0] }),
                        imageSeed: firstProductId ?? order.id,
                        compact: compact,
                        onClick: { router.open(.order(id: order.id)) },
                        onRepeat: { repeatOrder(order) }
                    )
                }
                if vm.hasMore {
                    HStack {
                        if vm.loadingMore {
                            ProgressView()
                                .progressViewStyle(.circular)
                                .tint(colors.primary)
                        } else {
                            OrdersSmallPill(text: "Yana ko'rsatish", icon: nil, onClick: { vm.loadMore(container) })
                        }
                    }
                    .frame(maxWidth: .infinity, minHeight: 40)
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 20)
            .animation(.easeInOut(duration: 0.25), value: items.map { $0.id })
        }
        .scrollIndicators(.hidden)
    }

    private func repeatOrder(_ order: Order) {
        if repeatOrderIntoCart(container, order) > 0 {
            router.openCartFromOrders()
        } else {
            toast.show(orderRepeatUnavailable)
        }
    }
}

// MARK: - Buyurtma kartochkasi

/// Kartochka bosilganini tashqariga bildiradi: butun kartochka (pastki qatori bilan) kichrayadi.
private struct OrdersCardPressStyle: ButtonStyle {
    @Binding var pressed: Bool

    init(pressed: Binding<Bool>) {
        self._pressed = pressed
    }

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .onChange(of: configuration.isPressed) { _, value in
                pressed = value
            }
    }
}

private struct OrdersOrderCard: View {
    let order: Order
    let imageURL: URL?
    let imageSeed: Int
    let compact: Bool
    let onClick: () -> Void
    let onRepeat: () -> Void
    @Environment(\.amoraColors) private var colors
    @State private var pressed = false

    init(
        order: Order,
        imageURL: URL?,
        imageSeed: Int,
        compact: Bool,
        onClick: @escaping () -> Void,
        onRepeat: @escaping () -> Void
    ) {
        self.order = order
        self.imageURL = imageURL
        self.imageSeed = imageSeed
        self.compact = compact
        self.onClick = onClick
        self.onRepeat = onRepeat
    }

    var body: some View {
        let shape = RoundedRectangle(cornerRadius: AmoraRadius.large, style: .continuous)
        VStack(alignment: .leading, spacing: 0) {
            Button(action: onClick) {
                topBlock
                    .contentShape(Rectangle())
            }
            .buttonStyle(OrdersCardPressStyle(pressed: $pressed))
            Spacer().frame(height: 12)
            bottomRow
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .foregroundStyle(colors.onSurface)
        .background(shape.fill(colors.surface).softShadow())
        .contentShape(shape)
        // Pastki qatorning bo'sh joyi bosilsa ham buyurtma ochiladi
        .onTapGesture(perform: onClick)
        .scaleEffect(pressed ? 0.98 : 1)
        .animation(AmoraMotion.press, value: pressed)
    }

    private var itemsText: String {
        order.items.map { "\($0.quantity)× \($0.name)" }.joined(separator: ", ")
    }

    private var topBlock: some View {
        let reason = order.rejectReason?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .top, spacing: 0) {
                ProductImage(url: imageURL, iconSize: 26, seed: imageSeed)
                    .frame(width: 52, height: 52)
                    .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                Spacer().frame(width: 12)
                VStack(alignment: .leading, spacing: 0) {
                    Text("Buyurtma №\(order.id)")
                        .amoraText(.titleMedium)
                        .foregroundColor(colors.onSurface)
                        .lineLimit(1)
                        .truncationMode(.tail)
                    if compact {
                        StatusChip(status: order.status, label: order.statusLabel)
                            .padding(.top, 4)
                            .padding(.bottom, 6)
                    }
                    Text(itemsText)
                        .amoraText(.bodySmall)
                        .foregroundColor(colors.hint)
                        .lineLimit(2)
                        .truncationMode(.tail)
                        .multilineTextAlignment(.leading)
                }
                .padding(.top, 4)
                .frame(maxWidth: .infinity, alignment: .leading)
                if !compact {
                    Spacer().frame(width: 8)
                    OrdersMaxWidthLayout(maxWidth: 136).callAsFunction {
                        StatusChip(status: order.status, label: order.statusLabel)
                    }
                    .layoutPriority(1)
                }
            }

            if order.status == OrderStatus.rejected && !reason.isEmpty {
                Spacer().frame(height: 12)
                Text(verbatim: "Sabab: " + (order.rejectReason ?? ""))
                    .amoraText(.bodySmall)
                    .foregroundColor(colors.onErrorContainer)
                    .multilineTextAlignment(.leading)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 9)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(RoundedRectangle(cornerRadius: 12, style: .continuous).fill(colors.errorContainer))
            }
            if order.isActive {
                Spacer().frame(height: 14)
                OrderProgressBar(status: order.status)
            }

            Spacer().frame(height: 12)
            Rectangle()
                .fill(colors.outlineVariant)
                .frame(height: 1)
                .frame(maxWidth: .infinity)
        }
    }

    private var bottomRow: some View {
        HStack(alignment: .center, spacing: 0) {
            VStack(alignment: .leading, spacing: 0) {
                Text(formatDateTime(order.createdAt))
                    .amoraText(.bodySmall)
                    .foregroundColor(colors.hint)
                    .lineLimit(1)
                PriceText(
                    amount: order.total,
                    style: AmoraTextStyle.price.with(size: AmoraTextStyle.price.size * 1.1),
                    color: colors.onSurface,
                    unitColor: colors.onSurface
                )
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            if order.isActive {
                OrdersSmallPill(text: "Kuzatish", icon: .clock, onClick: onClick)
            } else {
                OrdersSmallPill(text: "Yana shunday", icon: .`repeat`, onClick: onRepeat)
            }
        }
    }
}

/// Bolasiga ko'pi bilan `maxWidth` kenglik beradi va uni o'ngga tekislaydi (Compose `widthIn(max = ...)`):
/// bola qisqaroq bo'lsa, ortiqcha joy egallamaydi.
private struct OrdersMaxWidthLayout: Layout {
    let maxWidth: CGFloat

    init(maxWidth: CGFloat) {
        self.maxWidth = maxWidth
    }

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        guard let first = subviews.first else { return .zero }
        let width = min(proposal.width ?? maxWidth, maxWidth)
        return first.sizeThatFits(ProposedViewSize(width: width, height: proposal.height))
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        guard let first = subviews.first else { return }
        let width = min(bounds.width, maxWidth)
        first.place(
            at: CGPoint(x: bounds.maxX, y: bounds.minY),
            anchor: .topTrailing,
            proposal: ProposedViewSize(width: width, height: bounds.height)
        )
    }
}

/// Kartochka ichidagi kichik och-qizil tugma.
private struct OrdersSmallPill: View {
    let text: String
    let icon: AppIcon?
    let onClick: () -> Void
    @Environment(\.amoraColors) private var colors

    init(text: String, icon: AppIcon?, onClick: @escaping () -> Void) {
        self.text = text
        self.icon = icon
        self.onClick = onClick
    }

    var body: some View {
        let shape = RoundedRectangle(cornerRadius: 13, style: .continuous)
        Button(action: onClick) {
            HStack(spacing: 6) {
                if let icon {
                    IconImage(icon, size: 16, tint: colors.onPrimaryContainer)
                }
                Text(text)
                    .amoraText(.labelMedium)
                    .foregroundColor(colors.onPrimaryContainer)
                    .lineLimit(1)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(shape.fill(colors.primaryContainer))
            .contentShape(shape)
        }
        .buttonStyle(PressScaleStyle(scale: 0.94))
        .fixedSize()
        .accessibilityLabel(text)
    }
}

// MARK: - Skelet

/// Ro'yxat birinchi marta yuklanayotganda: buyurtma kartochkalari shaklidagi skelet.
private struct OrdersListSkeleton: View {
    init() {}

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            ForEach(0..<3, id: \.self) { _ in
                VStack(alignment: .leading, spacing: 0) {
                    HStack(alignment: .center, spacing: 0) {
                        SkeletonBox(width: 52, height: 52, cornerRadius: 16)
                        Spacer().frame(width: 12)
                        VStack(alignment: .leading, spacing: 8) {
                            SkeletonBox(width: 120, height: 16)
                            SkeletonBox(width: 90, height: 12)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        SkeletonBox(width: 74, height: 26, cornerRadius: 10)
                    }
                    Spacer().frame(height: 26)
                    HStack(alignment: .center, spacing: 0) {
                        VStack(alignment: .leading, spacing: 8) {
                            SkeletonBox(width: 96, height: 12)
                            SkeletonBox(width: 110, height: 18)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        SkeletonBox(width: 118, height: 38)
                    }
                }
                .padding(14)
                .frame(maxWidth: .infinity, alignment: .leading)
                .cardBackground()
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 16)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .accessibilityHidden(true)
    }
}
