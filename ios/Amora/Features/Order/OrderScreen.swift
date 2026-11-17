/// One order (port of android ui/order/OrderScreen.kt): live status block, steps, call the cafe,
/// cancel (with confirm dialog), items and totals, address and recipient. An active order refreshes
/// itself (live events + polling); a finished one offers "Yana shunday buyurtma berish".
///
/// Surface:
/// - `struct OrderScreen: View` - `OrderScreen(orderId: Int)`; needs `AppContainer` and `Router` in the environment.

import SwiftUI
import UIKit

struct OrderScreen: View {
    let orderId: Int

    init(orderId: Int) {
        self.orderId = orderId
    }

    var body: some View {
        // Boshqa buyurtma ochilsa (masalan, bildirishnoma bosildi), holat noldan boshlanadi
        OrderScreenContent(orderId: orderId)
            .id(orderId)
    }
}

/// Ekran ko'rinishini kuzatish kaliti: ilova ochiq (faol) va ko'rsatilayotgan holat.
private struct OrderVisibleKey: Equatable {
    var active: Bool
    var status: String?
}

private let orderDeliveredGreen = Color(argb: 0xFF4CCB8C)

private struct OrderScreenContent: View {
    let orderId: Int
    @Environment(AppContainer.self) private var container
    @Environment(Router.self) private var router
    @Environment(\.amoraColors) private var colors
    @Environment(\.scenePhase) private var scenePhase

    @State private var vm: OrderViewModel
    @State private var toast = ToastCenter()
    @State private var confirmCancel = false

    init(orderId: Int) {
        self.orderId = orderId
        _vm = State(initialValue: OrderViewModel(orderId: orderId))
    }

    /// Tugagan buyurtmani bir bosishda takrorlash mumkin (pastki panel)
    private var docked: Bool {
        if let order = vm.order {
            return !order.isActive
        }
        return false
    }

    private var visibleKey: OrderVisibleKey {
        OrderVisibleKey(active: scenePhase == .active, status: vm.order?.status)
    }

    var body: some View {
        content
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .amoraRefreshable(action: {
                await vm.refresh(container)
            })
            .toastHost(toast)
            .safeAreaInset(edge: .top, spacing: 0) {
                GlassTopBar(title: "Buyurtma №\(orderId)", onBack: { router.back() })
            }
            .safeAreaInset(edge: .bottom, spacing: 0) {
                if docked {
                    BottomDock {
                        BigButton(
                            text: "Yana shunday buyurtma berish",
                            onClick: {
                                if vm.repeatOrder(container) > 0 {
                                    router.openCartFromOrders()
                                }
                            }
                        )
                    }
                }
            }
            .background(colors.background.ignoresSafeArea())
            .background {
                // Birinchi faol buyurtmada bildirishnomaga ruxsat so'raladi: "qabul qilindi", "kuryer yo'lda"
                if vm.order?.isActive == true {
                    Color.clear
                        .frame(width: 0, height: 0)
                        .askNotificationPermissionOnce()
                }
            }
            .toolbar(.hidden, for: .navigationBar)
            .confirmDialog(
                isPresented: $confirmCancel,
                title: "Buyurtmani bekor qilasizmi?",
                text: "Kafe buyurtmani hali qabul qilmagan. Bekor qilsangiz, u kafega yuborilmaydi.",
                confirmLabel: "Bekor qilish",
                dismissLabel: "Yo'q, qolsin",
                onConfirm: { vm.cancel(container) }
            )
            // Ekran ko'rinib turganda holat yangilanib turadi; buyurtma tugagach so'rovlar to'xtaydi
            .task(id: scenePhase != .background) {
                if scenePhase == .background {
                    return
                }
                await vm.poll(container)
            }
            // Shu buyurtma haqida jonli xabar keldi: holat darhol qayta o'qiladi
            .task {
                for await event in container.realtime.events() {
                    if event == .resync || event.orderChange?.orderId == orderId {
                        await vm.refresh(container)
                    }
                }
            }
            // Mijoz shu buyurtmaga qarab turibdi: u haqidagi bildirishnoma ko'rsatilmaydi (va bori yopiladi)
            .onChange(of: visibleKey, initial: true) { _, key in
                if key.active {
                    container.live.setVisibleOrder(orderId, status: key.status)
                } else {
                    container.live.clearVisibleOrder(orderId)
                }
            }
            .onAppear {
                if scenePhase == .active {
                    container.live.setVisibleOrder(orderId, status: vm.order?.status)
                }
            }
            .onDisappear {
                container.live.clearVisibleOrder(orderId)
            }
            .onChange(of: vm.message) { _, message in
                if let message {
                    toast.show(message)
                    vm.clearMessage()
                }
            }
    }

    @ViewBuilder
    private var content: some View {
        if let order = vm.order {
            ScrollView {
                orderColumn(order)
                    .padding(.horizontal, 16)
                    .padding(.bottom, 16)
            }
            .scrollIndicators(.hidden)
        } else if vm.loading {
            OrderDetailSkeleton()
        } else {
            MessageBox(
                icon: .refresh,
                title: "Buyurtma yuklanmadi",
                text: vm.error,
                actionLabel: "Qayta urinish",
                onAction: { vm.retry(container) }
            )
        }
    }

    private func orderColumn(_ order: Order) -> some View {
        let stopped = order.status == OrderStatus.rejected || order.status == OrderStatus.cancelled
        let cafePhone = container.catalog.shop?.phone?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return VStack(alignment: .leading, spacing: 12) {
            OrderStatusHero(order: order)

            if !stopped {
                OrderTimelineCard(order: order)
            }

            if order.isActive && !cafePhone.isEmpty {
                SoftButton(
                    text: "Kafega qo'ng'iroq",
                    onClick: { orderDialPhone(cafePhone) },
                    icon: .phone,
                    accent: true
                )
            }

            if order.canCancel {
                SoftButton(
                    text: vm.cancelling ? "Bekor qilinmoqda…" : "Buyurtmani bekor qilish",
                    onClick: { confirmCancel = true },
                    icon: .close,
                    enabled: !vm.cancelling,
                    danger: true
                )
            }

            OrderItemsCard(order: order)
            OrderDetailsCard(order: order)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

/// Qo'ng'iroq oynasini ochadi. Qo'ng'iroq qila olmaydigan qurilmada (iPad, simulyator) hech narsa bo'lmaydi.
@MainActor
private func orderDialPhone(_ phone: String) {
    let number = phone.filter { $0.isNumber || $0 == "+" }
    guard !number.isEmpty, let url = URL(string: "tel:\(number)") else { return }
    UIApplication.shared.open(url, options: [:], completionHandler: nil)
}

// MARK: - Holat matnlari

private func orderStatusDescription(_ order: Order) -> String {
    switch order.status {
    case OrderStatus.new:
        return "Buyurtmangiz kafega yuborildi. Tasdiqlanishini kuting."
    case OrderStatus.accepted:
        return "Kafe buyurtmani qabul qildi va tayyorlamoqda."
    case OrderStatus.delivering:
        return "Kuryer buyurtmangizni olib yo'lga chiqdi."
    case OrderStatus.delivered:
        return "Buyurtma yetkazildi. Yoqimli ishtaha!"
    case OrderStatus.rejected:
        let reason = order.rejectReason?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        if reason.isEmpty {
            return "Afsuski, kafe buyurtmani qabul qila olmadi."
        }
        return "Afsuski, kafe buyurtmani qabul qila olmadi. Sabab: \(order.rejectReason ?? "")"
    case OrderStatus.cancelled:
        return "Siz bu buyurtmani bekor qilgansiz."
    default:
        return ""
    }
}

/// Holat vaqti ostidagi qisqa izoh: shu vaqtda nima bo'lgani.
private func orderStatusTimeCaption(_ status: String) -> String {
    switch status {
    case OrderStatus.new:
        return "yuborildi"
    case OrderStatus.accepted:
        return "qabul qilindi"
    case OrderStatus.delivering:
        return "yo'lga chiqdi"
    case OrderStatus.delivered:
        return "yetkazildi"
    case OrderStatus.rejected:
        return "javob berildi"
    case OrderStatus.cancelled:
        return "to'xtatildi"
    default:
        return ""
    }
}

private struct OrderStep {
    let status: String
    let label: String
    let icon: AppIcon
}

private let orderSteps: [OrderStep] = [
    OrderStep(status: OrderStatus.new, label: "Buyurtma yuborildi", icon: .send),
    OrderStep(status: OrderStatus.accepted, label: "Kafe qabul qildi", icon: .chef),
    OrderStep(status: OrderStatus.delivering, label: "Kuryer yo'lga chiqdi", icon: .bike),
    OrderStep(status: OrderStatus.delivered, label: "Yetkazildi", icon: .home),
]

// MARK: - Jonli holat bloki

/// Ko'mir rangli blok: buyurtma hozir qaysi holatda, qachondan beri va umumiy yo'lning qancha qismi o'tilgan.
private struct OrderStatusHero: View {
    let order: Order
    @Environment(\.amoraColors) private var colors

    init(order: Order) {
        self.order = order
    }

    var body: some View {
        let stopped = order.status == OrderStatus.rejected || order.status == OrderStatus.cancelled
        let delivered = order.status == OrderStatus.delivered
        let dotColor: Color = order.isActive ? colors.amber : (delivered ? orderDeliveredGreen : colors.onInkMuted)
        let time = order.history.last(where: { $0.status == order.status })?.createdAt ?? order.updatedAt
        let shape = RoundedRectangle(cornerRadius: 30, style: .continuous)
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .top, spacing: 0) {
                VStack(alignment: .leading, spacing: 0) {
                    HStack(spacing: 6) {
                        OrderLiveDot(color: dotColor, pulsing: order.isActive)
                        Text(order.isActive ? "Jonli holat" : "Yakunlangan")
                            .amoraText(.bodySmall)
                            .foregroundColor(colors.onInkMuted)
                    }
                    Spacer().frame(height: 8)
                    // Holat o'zgarganda yangi nom pastdan chiqadi, eskisi tepaga ketadi
                    ZStack(alignment: .topLeading) {
                        Text(order.statusLabel)
                            .amoraText(.headlineLarge)
                            .foregroundColor(.white)
                            .fixedSize(horizontal: false, vertical: true)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .id(order.statusLabel)
                            .transition(
                                .asymmetric(
                                    insertion: AnyTransition.opacity.combined(with: .offset(y: 12)),
                                    removal: AnyTransition.opacity.combined(with: .offset(y: -12))
                                )
                            )
                    }
                    .animation(.easeOut(duration: 0.3), value: order.statusLabel)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                Spacer().frame(width: 12)
                VStack(alignment: .trailing, spacing: 0) {
                    Text(formatTime(time))
                        .amoraText(.priceLarge)
                        .foregroundColor(.white)
                        .lineLimit(1)
                    Text(orderStatusTimeCaption(order.status))
                        .amoraText(.bodySmall)
                        .foregroundColor(colors.onInkMuted)
                        .lineLimit(1)
                        .multilineTextAlignment(.trailing)
                }
                .padding(.top, 2)
                .fixedSize()
            }
            Spacer().frame(height: 8)
            Text(orderStatusDescription(order))
                .amoraText(.bodyMedium)
                .foregroundColor(colors.onInkMuted)
                .fixedSize(horizontal: false, vertical: true)
                .frame(maxWidth: .infinity, alignment: .leading)
            if !stopped {
                Spacer().frame(height: 16)
                OrderProgressBar(
                    status: order.status,
                    color: delivered ? orderDeliveredGreen : colors.primary,
                    track: Color.white.opacity(0.14)
                )
            }
        }
        .padding(.horizontal, 18)
        .padding(.top, 16)
        .padding(.bottom, 18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(shape.fill(colors.ink).softShadow(elevation: 16, alpha: 0.24))
        .accessibilityElement(children: .combine)
    }
}

/// Kichik nuqta. Buyurtma faol bo'lsa, atrofida to'lqin tarqalib turadi: holat jonli kuzatilmoqda.
private struct OrderLiveDot: View {
    let color: Color
    let pulsing: Bool
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    init(color: Color, pulsing: Bool) {
        self.color = color
        self.pulsing = pulsing
    }

    private static let period: Double = 1.5

    var body: some View {
        ZStack {
            if pulsing {
                if reduceMotion {
                    Circle()
                        .fill(color.opacity(0.3))
                        .frame(width: 14, height: 14)
                } else {
                    TimelineView(.animation) { timeline in
                        let seconds = timeline.date.timeIntervalSinceReferenceDate
                        let pulse = CGFloat(seconds.truncatingRemainder(dividingBy: OrderLiveDot.period) / OrderLiveDot.period)
                        Circle()
                            .fill(color)
                            .frame(width: 14, height: 14)
                            .scaleEffect(0.45 + pulse * 0.55)
                            .opacity(Double((1 - pulse) * 0.55))
                    }
                }
            }
            Circle()
                .fill(color)
                .frame(width: 7, height: 7)
        }
        .frame(width: 14, height: 14)
        .accessibilityHidden(true)
    }
}

// MARK: - Bosqichlar

/// Buyurtma bosqichlari: o'tilgani belgilangan, hozirgisi ajratilgan, kelgusisi xira.
private struct OrderTimelineCard: View {
    let order: Order
    @Environment(\.amoraColors) private var colors

    init(order: Order) {
        self.order = order
    }

    var body: some View {
        let currentIndex = orderSteps.firstIndex(where: { $0.status == order.status }) ?? -1
        let finished = order.status == OrderStatus.delivered
        SectionCard(padding: 16) {
            ForEach(Array(orderSteps.enumerated()), id: \.offset) { index, step in
                let done = index < currentIndex || (finished && index == currentIndex)
                let now = !finished && index == currentIndex
                let time = order.history.last(where: { $0.status == step.status })?.createdAt
                HStack(spacing: 0) {
                    OrderStepTile(icon: step.icon, done: done, now: now)
                    Spacer().frame(width: 14)
                    Text(step.label)
                        .amoraText((done || now) ? AmoraTextStyle.titleSmall : AmoraTextStyle.bodyLarge)
                        .foregroundColor((done || now) ? colors.onSurface : colors.hint)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    if (done || now), let time {
                        Text(formatTime(time))
                            .amoraText(.bodySmall)
                            .foregroundColor(colors.hint)
                    }
                }
                .accessibilityElement(children: .combine)
                if index < orderSteps.count - 1 {
                    OrderStepConnector(solid: index < currentIndex)
                }
            }
        }
    }
}

private struct OrderStepTile: View {
    let icon: AppIcon
    let done: Bool
    let now: Bool
    @Environment(\.amoraColors) private var colors

    init(icon: AppIcon, done: Bool, now: Bool) {
        self.icon = icon
        self.done = done
        self.now = now
    }

    var body: some View {
        let shape = RoundedRectangle(cornerRadius: 12, style: .continuous)
        let fill: Color = done ? colors.primary : (now ? colors.primaryContainer : colors.surfaceVariant)
        let tint: Color = done ? Color.white : (now ? colors.primary : colors.hint)
        ZStack {
            shape.fill(fill)
            if now {
                shape.strokeBorder(colors.primary, lineWidth: 1.5)
            }
            IconImage(done ? .check : icon, size: 18, tint: tint)
        }
        .frame(width: 34, height: 34)
    }
}

/// Ikki bosqich orasidagi chiziq: o'tilgan yo'l uzluksiz, kelgusi yo'l punktir.
private struct OrderStepConnector: View {
    let solid: Bool
    @Environment(\.amoraColors) private var colors

    init(solid: Bool) {
        self.solid = solid
    }

    var body: some View {
        OrderVerticalLine()
            .stroke(
                solid ? colors.primary : colors.outline,
                style: StrokeStyle(lineWidth: 2, lineCap: .round, dash: solid ? [] : [3, 4])
            )
            .frame(width: 2, height: 14)
            .padding(.leading, 16)
            .padding(.vertical, 3)
            .accessibilityHidden(true)
    }
}

private struct OrderVerticalLine: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        path.move(to: CGPoint(x: rect.midX, y: 0))
        path.addLine(to: CGPoint(x: rect.midX, y: rect.height))
        return path
    }
}

// MARK: - Tarkib va summa

/// Buyurtma tarkibi va summasi: chekdagidek qisqa qatorlar.
private struct OrderItemsCard: View {
    let order: Order
    @Environment(\.amoraColors) private var colors

    init(order: Order) {
        self.order = order
    }

    var body: some View {
        SectionCard(padding: 0) {
            ForEach(Array(order.items.enumerated()), id: \.offset) { _, item in
                OrderMiniRow {
                    (
                        Text("\(item.quantity)×")
                            .font(AmoraFont.bodyBold(AmoraTextStyle.bodyLarge.size))
                            .foregroundColor(colors.primary)
                        + Text("  " + item.name)
                    )
                    .amoraText(.bodyLarge)
                    .foregroundColor(colors.onSurface)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    Spacer().frame(width: 12)
                    Text(formatSum(item.lineTotal))
                        .amoraText(.bodyLarge)
                        .foregroundColor(colors.onSurface)
                        .lineLimit(1)
                        .fixedSize()
                }
                RowDivider(inset: 16)
            }
            OrderMiniRow {
                Text("Yetkazish")
                    .amoraText(.bodyLarge)
                    .foregroundColor(colors.onSurfaceVariant)
                    .frame(maxWidth: .infinity, alignment: .leading)
                if order.deliveryFee == 0 {
                    Text("Bepul")
                        .amoraText(.titleSmall)
                        .foregroundColor(colors.success)
                } else {
                    Text(formatSum(order.deliveryFee))
                        .amoraText(.bodyLarge)
                        .foregroundColor(colors.onSurface)
                        .lineLimit(1)
                        .fixedSize()
                }
            }
            if order.discount > 0 {
                RowDivider(inset: 16)
                OrderMiniRow {
                    Text(order.promoCode.map { "Chegirma · \($0)" } ?? "Chegirma")
                        .amoraText(.bodyLarge)
                        .foregroundColor(colors.onSurfaceVariant)
                        .lineLimit(1)
                        .truncationMode(.tail)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    Spacer().frame(width: 12)
                    Text("−\(formatSum(order.discount))")
                        .amoraText(.titleSmall)
                        .foregroundColor(colors.success)
                        .lineLimit(1)
                        .fixedSize()
                }
            }
            RowDivider(inset: 16)
            OrderMiniRow(vertical: 15) {
                Text("Jami · naqd")
                    .amoraText(.titleMedium)
                    .foregroundColor(colors.onSurface)
                    .frame(maxWidth: .infinity, alignment: .leading)
                PriceText(
                    amount: order.total,
                    style: AmoraTextStyle.priceLarge.with(size: AmoraTextStyle.priceLarge.size * 0.86),
                    color: colors.onSurface,
                    unitColor: colors.onSurface
                )
            }
        }
    }
}

private struct OrderMiniRow<Content: View>: View {
    let vertical: CGFloat
    let content: Content

    init(vertical: CGFloat = 13, @ViewBuilder content: () -> Content) {
        self.vertical = vertical
        self.content = content()
    }

    var body: some View {
        HStack(alignment: .center, spacing: 0) {
            content
        }
        .padding(.horizontal, 16)
        .padding(.vertical, vertical)
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

/// Qayerga, kimga va qachon: manzil, qabul qiluvchi, izoh.
private struct OrderDetailsCard: View {
    let order: Order
    @Environment(\.amoraColors) private var colors

    init(order: Order) {
        self.order = order
    }

    var body: some View {
        let note = order.addressNote.trimmingCharacters(in: .whitespacesAndNewlines)
        let comment = order.comment.trimmingCharacters(in: .whitespacesAndNewlines)
        SectionCard(padding: 0) {
            LinkRow(
                icon: .pin,
                label: "Manzil · \(formatDateTime(order.createdAt))",
                value: note.isEmpty ? "Xaritada belgilangan joy" : order.addressNote
            )
            RowDivider()
            LinkRow(
                icon: .user,
                label: "Qabul qiluvchi",
                value: "\(order.customerName), \(formatPhone(order.phone))",
                tileContainer: colors.infoContainer,
                tileTint: colors.info
            )
            if !comment.isEmpty {
                RowDivider()
                LinkRow(
                    icon: .message,
                    label: "Izoh",
                    value: order.comment,
                    tileContainer: colors.surfaceVariant,
                    tileTint: colors.onSurfaceVariant
                )
            }
        }
    }
}

// MARK: - Skelet

/// Buyurtma birinchi marta yuklanayotganda: sahifa shaklini takrorlaydigan skelet.
private struct OrderDetailSkeleton: View {
    @Environment(\.amoraColors) private var colors

    init() {}

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            SkeletonBox(height: 178, cornerRadius: 30)
            VStack(alignment: .leading, spacing: 20) {
                ForEach(0..<4, id: \.self) { index in
                    HStack(spacing: 0) {
                        SkeletonBox(width: 34, height: 34, cornerRadius: 12)
                        Spacer().frame(width: 14)
                        SkeletonBox(width: CGFloat(150 - index * 14), height: 14)
                        Spacer(minLength: 0)
                        SkeletonBox(width: 36, height: 12)
                    }
                }
            }
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .cardBackground()
            VStack(alignment: .leading, spacing: 18) {
                ForEach(0..<3, id: \.self) { index in
                    HStack(spacing: 0) {
                        SkeletonBox(width: CGFloat(130 - index * 22), height: 14)
                        Spacer(minLength: 0)
                        SkeletonBox(width: 84, height: 14)
                    }
                }
            }
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .cardBackground()
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 16)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .accessibilityHidden(true)
    }
}
