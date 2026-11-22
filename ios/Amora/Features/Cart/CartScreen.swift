/// Cart screen (port of android ui/cart/CartScreen.kt).
///
/// Surface:
/// - `struct CartScreen: View` - `CartScreen()`; needs `AppContainer` and `Router` in the environment.
///   Items with steppers, free-delivery hint, address and recipient rows, comment, promo code, totals
///   from the server quote, confirm dialog; a created order opens with `router.openOrderAfterCreate(id:)`.

import SwiftUI

/// Savatdagi matn maydonlari (klaviatura ochiq paytda pastki tugma yashirinadi).
private enum CartField: Hashable {
    case comment
    case promo
}

struct CartScreen: View {
    @Environment(AppContainer.self) private var container
    @Environment(Router.self) private var router
    @Environment(\.amoraColors) private var colors

    @State private var vm = CartViewModel()
    @State private var toast = ToastCenter()
    @State private var confirming = false
    @FocusState private var focusedField: CartField?

    init() {}

    // MARK: - Hisoblangan qiymatlar

    private var quoteRequest: CartQuoteRequest {
        CartQuoteRequest(
            lines: container.cart.lines,
            address: container.session.address,
            promo: vm.appliedPromo,
            profile: container.session.profile,
            tick: vm.refreshTick
        )
    }

    private var productsById: [Int: Product] {
        let products = container.catalog.menu?.products ?? []
        return Dictionary(products.map { ($0.id, $0) }, uniquingKeysWith: { _, last in last })
    }

    private var itemsTotal: Int {
        if let quote = vm.quote {
            return quote.itemsTotal
        }
        let products = productsById
        return container.cart.lines.reduce(0) { sum, line in
            sum + (products[line.productId]?.price ?? 0) * line.quantity
        }
    }

    /// Summa hozir qo'llangan promokod bilan hisoblanganmi (yangi kod tekshirilayotgan bo'lishi mumkin)
    private var promoFresh: Bool {
        vm.quotePromo == vm.appliedPromo
    }

    private var codeWorks: Bool {
        promoFresh && vm.appliedPromo != nil && vm.quote?.promoError == nil
    }

    private var canOrder: Bool {
        guard let quote = vm.quote else { return false }
        return quote.canOrder && !vm.quoteLoading && vm.quoteError == nil && promoFresh
    }

    /// Summa birinchi marta serverdan kutilayotganda raqamlar o'rnida skelet ko'rinadi
    private var quotePending: Bool {
        vm.quote == nil && vm.quoteError == nil
    }

    /// "Bepul yetkazishgacha yana ..." qatori: kafe shunday chegara qo'ygan bo'lsa va
    /// server hisoblagan yetkazish narxi bunga zid kelmasa ko'rinadi
    private var freeDeliveryFrom: Int? {
        guard let shop = container.catalog.shop, shop.deliveryFee > 0,
              let freeFrom = shop.freeDeliveryFrom, freeFrom > 0
        else {
            return nil
        }
        if let quote = vm.quote, (quote.deliveryFee == 0) != (itemsTotal >= freeFrom) {
            return nil
        }
        return freeFrom
    }

    private var active: Bool {
        !container.cart.isEmpty && vm.createdOrderId == nil
    }

    /// Klaviatura ochiq paytda pastki tugma yashirinadi: yozilayotgan izoh uning ortida qolib ketmaydi
    private var docked: Bool {
        active && focusedField == nil
    }

    private var confirmBinding: Binding<Bool> {
        Binding(
            get: { confirming && vm.quote != nil },
            set: { confirming = $0 }
        )
    }

    // MARK: - Ekran

    var body: some View {
        mainContent
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .toastHost(toast)
            .safeAreaInset(edge: .top, spacing: 0) {
                topBar
            }
            .safeAreaInset(edge: .bottom, spacing: 0) {
                dock
            }
            .background(colors.background.ignoresSafeArea())
            .toolbar(.hidden, for: .navigationBar)
            .confirmDialog(
                isPresented: confirmBinding,
                title: "Buyurtmani tasdiqlaysizmi?",
                text: "Jami: \(formatSum(vm.quote?.total ?? 0)). To'lov kuryerga naqd pul bilan beriladi.",
                confirmLabel: "Tasdiqlash",
                dismissLabel: "Orqaga",
                onConfirm: { submit() }
            )
            .onAppear {
                vm.restoreDraft(container.cart)
            }
            .task(id: quoteRequest) {
                await vm.runQuote(quoteRequest, container: container)
            }
            .task {
                // Savat ochiq turganda menyu yoki kafe sozlamalari o'zgarsa (taom tugadi, narx o'zgardi,
                // kafe yopildi, aksiya o'zgardi), summa va ogohlantirishlar serverdan qayta so'raladi
                for await event in container.realtime.events() {
                    if event.orderChange == nil {
                        vm.refreshQuote()
                    }
                }
            }
            .onChange(of: vm.submitError) { _, error in
                if let error {
                    toast.show(error)
                    vm.clearSubmitError()
                }
            }
    }

    private func submit() {
        let router = self.router
        vm.submit(container) { orderId in
            // Savat ekrani tarixdan olib tashlanadi: "orqaga" menyuga qaytaradi
            router.openOrderAfterCreate(id: orderId)
        }
    }

    private var topBar: some View {
        GlassTopBar(title: "Savat", onBack: { router.back() }, actions: {
            if active {
                TextButton(text: "Tozalash", onClick: { container.cart.clear() })
            }
        })
    }

    @ViewBuilder
    private var dock: some View {
        if docked {
            BottomDock {
                if container.session.address == nil {
                    BigButton(text: "Manzilni tanlang", onClick: { router.open(.address) })
                } else if container.session.profile?.verified != true {
                    BigButton(text: "Raqamni tasdiqlang", onClick: { router.open(.profileEdit) })
                } else {
                    BigButton(
                        text: "Buyurtma berish",
                        onClick: { confirming = true },
                        enabled: canOrder,
                        loading: vm.submitting,
                        trailing: vm.quote.map { formatSum($0.total) }
                    )
                }
            }
        }
    }

    @ViewBuilder
    private var mainContent: some View {
        if vm.createdOrderId != nil {
            LoadingBox()
        } else if container.cart.isEmpty {
            MessageBox(
                icon: .bag,
                title: "Savat bo'sh",
                text: "Menyudan yoqqan taomingizni tanlang",
                actionLabel: "Menyuga qaytish",
                onAction: { router.back() }
            )
        } else {
            cartList
        }
    }

    private var cartList: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                if let freeFrom = freeDeliveryFrom {
                    CartFreeDeliveryCard(itemsTotal: itemsTotal, freeFrom: freeFrom)
                }
                itemsCard
                SectionLabel("Yetkazish")
                deliveryCard
                promoCard
                problemCards
                if let quoteError = vm.quoteError {
                    CartNoticeCard(
                        message: quoteError,
                        actionLabel: "Qayta urinish",
                        onAction: { vm.refreshQuote() }
                    )
                }
                summaryCard
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 8)
        }
        .scrollDismissesKeyboard(.interactively)
    }

    // MARK: - Taomlar

    private var itemsCard: some View {
        let products = productsById
        let quoteLines = Dictionary(
            (vm.quote?.lines ?? []).map { ($0.productId, $0) },
            uniquingKeysWith: { _, last in last }
        )
        let problems = vm.quote?.problems ?? []
        let lines = container.cart.lines
        return SectionCard(padding: 0) {
            ForEach(Array(lines.enumerated()), id: \.element.productId) { index, line in
                if index > 0 {
                    RowDivider(inset: 16)
                }
                CartItemRow(
                    productId: line.productId,
                    name: quoteLines[line.productId]?.name ?? products[line.productId]?.name ?? "Taom",
                    lineTotal: (quoteLines[line.productId]?.price ?? products[line.productId]?.price ?? 0) * line.quantity,
                    imageUrl: container.imageURL(products[line.productId]?.imageUrl),
                    quantity: line.quantity,
                    problem: problems.first(where: { $0.productId == line.productId })?.message,
                    onMinus: { container.cart.remove(line.productId) },
                    onPlus: { container.cart.add(line.productId) }
                )
            }
        }
    }

    // MARK: - Yetkazish

    private var addressValue: String {
        guard let address = container.session.address else { return "Xaritadan tanlang" }
        if address.note.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return "Xaritada belgilangan joy"
        }
        return address.note
    }

    private var recipientValue: String {
        guard let profile = container.session.profile, profile.verified else {
            return "Raqamni Telegram orqali tasdiqlang"
        }
        return "\(profile.name), \(formatPhone(profile.phone))"
    }

    private var commentBinding: Binding<String> {
        Binding(
            get: { vm.comment },
            set: { vm.setComment($0) }
        )
    }

    private var deliveryCard: some View {
        let verified = container.session.profile?.verified == true
        return SectionCard(padding: 0) {
            LinkRow(
                icon: .pin,
                label: "Yetkazish manzili",
                value: addressValue,
                onClick: { router.open(.address) },
                highlighted: container.session.address == nil
            )
            RowDivider()
            LinkRow(
                icon: .user,
                label: "Qabul qiluvchi",
                value: recipientValue,
                onClick: { router.open(.profileEdit) },
                highlighted: !verified,
                tileContainer: colors.infoContainer,
                tileTint: colors.info
            )
            RowDivider()
            HStack(spacing: 0) {
                IconTile(icon: .message, container: colors.surfaceVariant, tint: colors.onSurfaceVariant)
                TextField(
                    "",
                    text: commentBinding,
                    prompt: fieldPrompt("Kafe uchun izoh (ixtiyoriy)", colors),
                    axis: .vertical
                )
                .lineLimit(1...4)
                .textInputAutocapitalization(.sentences)
                .focused($focusedField, equals: .comment)
                .fieldStyle(container: .clear, border: false)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .padding(.leading, 16)
            .padding(.vertical, 4)
        }
    }

    // MARK: - Promokod

    private var promoBinding: Binding<String> {
        Binding(
            get: { vm.promoInput },
            set: { vm.setPromoInput($0) }
        )
    }

    /// Promokod maydoni: "Qo'llash" bosilgach server tekshiradi, natija pastda yoziladi.
    private var promoCard: some View {
        let input = vm.promoInput
        let applied = vm.appliedPromo
        let editing = applied == nil || input != applied
        let title: String? = codeWorks ? vm.quote?.promoTitle : nil
        let error: String? = (promoFresh && applied != nil) ? vm.quote?.promoError : nil
        let message: String?
        if editing {
            message = nil
        } else if let error {
            message = error
        } else if let title {
            message = "✓ \(title)"
        } else {
            message = nil
        }
        let canApply = !input.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        return SectionCard(padding: 0) {
            HStack(spacing: 0) {
                IconTile(icon: .tag, container: colors.successContainer, tint: colors.success)
                TextField("", text: promoBinding, prompt: fieldPrompt("Promokod", colors))
                    .textInputAutocapitalization(.characters)
                    .autocorrectionDisabled(true)
                    .submitLabel(.done)
                    .onSubmit {
                        if editing {
                            vm.applyPromo()
                        }
                    }
                    .focused($focusedField, equals: .promo)
                    .fieldStyle(container: .clear, border: false)
                    .frame(maxWidth: .infinity, alignment: .leading)
                if editing {
                    TextButton(text: "Qo'llash", onClick: { vm.applyPromo() })
                        .disabled(!canApply)
                } else {
                    TextButton(
                        text: "Olib tashlash",
                        onClick: { vm.removePromo() },
                        color: colors.onSurfaceVariant
                    )
                }
            }
            .padding(.leading, 16)
            .padding(.trailing, 8)
            .padding(.vertical, 4)
            if let message {
                Text(message)
                    .amoraText(.bodySmall)
                    .foregroundColor(error != nil ? colors.error : colors.success)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.leading, 72)
                    .padding(.trailing, 16)
                    .padding(.bottom, 12)
            }
        }
    }

    // MARK: - Ogohlantirishlar

    @ViewBuilder
    private var problemCards: some View {
        let general = (vm.quote?.problems ?? []).filter { $0.productId == nil }
        if !general.isEmpty {
            VStack(spacing: 8) {
                ForEach(Array(general.enumerated()), id: \.offset) { _, problem in
                    CartNoticeCard(message: problem.message)
                }
            }
        }
    }

    // MARK: - Jami

    private var deliveryValue: String {
        guard let quote = vm.quote else { return "—" }
        return quote.deliveryFee == 0 ? "Bepul" : formatSum(quote.deliveryFee)
    }

    private var summaryCard: some View {
        let quote = vm.quote
        let freeDelivery = quote != nil && quote?.deliveryFee == 0
        return SectionCard {
            SummaryRow(label: "Taomlar", value: formatSum(itemsTotal))
            SummaryRow(
                label: "Yetkazish",
                value: deliveryValue,
                valueColor: freeDelivery ? colors.success : nil,
                loading: quotePending
            )
            if let quote, quote.discount > 0 {
                SummaryRow(
                    label: codeWorks ? "Chegirma (\(vm.appliedPromo ?? ""))" : "Chegirma",
                    value: "−\(formatSum(quote.discount))",
                    valueColor: colors.success
                )
                // Kod kiritmasdan berilgan chegirma: nimaga berilganini aytamiz
                if !codeWorks, let autoTitle = quote.promoTitle {
                    Text("🎉 \(autoTitle)")
                        .amoraText(.bodySmall)
                        .foregroundColor(colors.success)
                        .fixedSize(horizontal: false, vertical: true)
                        .padding(.bottom, 4)
                }
            }
            Spacer().frame(height: 10)
            DashedDivider()
            Spacer().frame(height: 12)
            HStack(spacing: 0) {
                Text("Jami")
                    .amoraText(.titleMedium)
                    .frame(maxWidth: .infinity, alignment: .leading)
                if let quote {
                    PriceText(amount: quote.total, style: .priceLarge, unitColor: colors.onSurface)
                } else if quotePending {
                    SkeletonBox(width: 116, height: 24)
                } else {
                    Text("—")
                        .amoraText(.priceLarge)
                }
            }
            Spacer().frame(height: 14)
            HStack(spacing: 0) {
                IconImage(.cash, size: 18, tint: colors.success)
                Spacer().frame(width: 10)
                Text("To'lov: kuryerga naqd pul bilan")
                    .amoraText(.bodySmall)
                    .foregroundColor(colors.onSurfaceVariant)
                Spacer(minLength: 0)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 11)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .fill(colors.surfaceVariant)
            )
        }
    }
}

// MARK: - Bo'laklar

/// Bepul yetkazishgacha qancha qolganini ko'rsatadi: savatni to'ldirishga undaydi.
private struct CartFreeDeliveryCard: View {
    let itemsTotal: Int
    let freeFrom: Int
    @Environment(\.amoraColors) private var colors

    init(itemsTotal: Int, freeFrom: Int) {
        self.itemsTotal = itemsTotal
        self.freeFrom = freeFrom
    }

    var body: some View {
        let reached = itemsTotal >= freeFrom
        let fraction = min(max(CGFloat(itemsTotal) / CGFloat(freeFrom), 0), 1)
        let accent = reached ? colors.success : colors.primary
        SectionCard(padding: 14) {
            HStack(spacing: 0) {
                IconTile(
                    icon: .bike,
                    container: reached ? colors.successContainer : colors.primaryContainer,
                    tint: accent
                )
                Spacer().frame(width: 12)
                VStack(alignment: .leading, spacing: 0) {
                    Text(reached ? "Yetkazish bepul" : "Bepul yetkazishgacha yana \(formatSum(freeFrom - itemsTotal))")
                        .amoraText(.titleSmall)
                        .fixedSize(horizontal: false, vertical: true)
                    Spacer().frame(height: 8)
                    GeometryReader { geo in
                        ZStack(alignment: .leading) {
                            Capsule()
                                .fill(colors.surfaceVariant)
                            Capsule()
                                .fill(accent)
                                .frame(width: geo.size.width * fraction)
                        }
                        .animation(.timingCurve(0.4, 0, 0.2, 1, duration: 0.5), value: fraction)
                    }
                    .frame(height: 6)
                    .accessibilityHidden(true)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }
}

/// Savatdagi bitta taom: rasm, nom, summa, son tanlagich.
private struct CartItemRow: View {
    let productId: Int
    let name: String
    let lineTotal: Int
    let imageUrl: URL?
    let quantity: Int
    let problem: String?
    let onMinus: () -> Void
    let onPlus: () -> Void
    @Environment(\.amoraColors) private var colors

    init(
        productId: Int,
        name: String,
        lineTotal: Int,
        imageUrl: URL?,
        quantity: Int,
        problem: String?,
        onMinus: @escaping () -> Void,
        onPlus: @escaping () -> Void
    ) {
        self.productId = productId
        self.name = name
        self.lineTotal = lineTotal
        self.imageUrl = imageUrl
        self.quantity = quantity
        self.problem = problem
        self.onMinus = onMinus
        self.onPlus = onPlus
    }

    var body: some View {
        HStack(spacing: 0) {
            ProductImage(url: imageUrl, iconSize: 28, seed: productId)
                .frame(width: 58, height: 58)
                .clipShape(RoundedRectangle(cornerRadius: 17, style: .continuous))
            Spacer().frame(width: 12)
            VStack(alignment: .leading, spacing: 0) {
                Text(name)
                    .amoraText(.titleMedium)
                    .lineLimit(2)
                    .truncationMode(.tail)
                    .foregroundColor(colors.onSurface)
                Spacer().frame(height: 2)
                Text(formatSum(lineTotal))
                    .amoraText(.bodyMedium)
                    .foregroundColor(colors.hint)
                if let problem {
                    Text(problem)
                        .amoraText(.labelMedium)
                        .foregroundColor(colors.error)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            Spacer().frame(width: 8)
            QuantityStepper(
                quantity: quantity,
                onMinus: onMinus,
                onPlus: onPlus,
                height: 40,
                corner: 14,
                buttonWidth: 36,
                tonal: true
            )
        }
        .padding(12)
    }
}

/// Buyurtma berishga to'sqinlik qilayotgan sabab (kafe yopiq, eng kam summa va h.k.).
private struct CartNoticeCard: View {
    let message: String
    let actionLabel: String?
    let onAction: (() -> Void)?
    @Environment(\.amoraColors) private var colors

    init(message: String, actionLabel: String? = nil, onAction: (() -> Void)? = nil) {
        self.message = message
        self.actionLabel = actionLabel
        self.onAction = onAction
    }

    var body: some View {
        HStack(spacing: 0) {
            Text(message)
                .amoraText(.bodyMedium)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.vertical, 6)
                .frame(maxWidth: .infinity, alignment: .leading)
            if let actionLabel, let onAction {
                Button(action: onAction) {
                    Text(actionLabel)
                        .amoraText(.labelLarge)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 10)
                        .contentShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                }
                .buttonStyle(PressScaleStyle(scale: 0.95))
            }
        }
        .foregroundStyle(colors.onErrorContainer)
        .padding(.leading, 16)
        .padding(.trailing, 8)
        .padding(.vertical, 8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: AmoraRadius.large, style: .continuous)
                .fill(colors.errorContainer)
        )
    }
}
