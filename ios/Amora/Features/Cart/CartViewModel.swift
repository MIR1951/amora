/// Cart screen state (port of android ui/cart/CartViewModel.kt).
///
/// Surface (used only by CartScreen.swift):
/// - `struct CartQuoteRequest: Equatable` - what the quote depends on (cart, address, promo, profile, tick);
///   CartScreen runs `.task(id: request)`, which restarts on change like Kotlin `collectLatest`.
/// - `@MainActor @Observable final class CartViewModel`
///   - state: `quote`, `quoteLoading`, `quoteError`, `comment`, `promoInput`, `appliedPromo`, `quotePromo`,
///     `submitting`, `submitError`, `createdOrderId`, `refreshTick`
///   - `func runQuote(_ request: CartQuoteRequest, container: AppContainer) async`
///   - `func refreshQuote()`, `func setPromoInput(_:)`, `func applyPromo()`, `func removePromo()`,
///     `func setComment(_:)`, `func clearSubmitError()`
///   - `func submit(_ container: AppContainer, onCreated: @escaping @MainActor (Int) -> Void)`

import Foundation
import Observation

/// Summa shu qiymatlarga bog'liq: birortasi o'zgarsa, summa serverdan qayta so'raladi.
struct CartQuoteRequest: Equatable {
    var lines: [CartLine]
    var address: Address?
    var promo: String?
    // Ro'yxatdan o'tgach (yoki raqam o'zgargach) birinchi buyurtma chegirmasi qayta tekshiriladi
    var profile: Profile?
    var tick: Int
}

@MainActor
@Observable
final class CartViewModel {
    // Server hisoblagan summa. Savat o'zgarganda qayta so'raladi.
    var quote: Quote? = nil
    var quoteLoading: Bool = false
    var quoteError: String? = nil
    var comment: String = ""
    // Mijoz yozayotgan promokod va "Qo'llash" bosilgandan keyin serverga yuborilgani
    var promoInput: String = ""
    var appliedPromo: String? = nil
    // Ko'rsatilayotgan summa qaysi kod bilan hisoblangan: yangi kod tekshirilguncha eski
    // natija uning ostida ko'rinmasin
    var quotePromo: String? = nil
    var submitting: Bool = false
    var submitError: String? = nil
    var createdOrderId: Int? = nil

    // Qiymati o'zgarsa, summa serverdan qayta so'raladi
    private(set) var refreshTick: Int = 0

    // Bitta buyurtma uchun bitta kalit: internet uzilib qayta yuborilsa, buyurtma ikkilanmaydi.
    // Savat, manzil yoki izoh o'zgarsa, bu endi boshqa buyurtma: kalit ham yangilanadi.
    @ObservationIgnored private var clientOrderId: String = UUID().uuidString
    @ObservationIgnored private var orderFingerprint: String = ""

    static let quoteDebounceNanos: UInt64 = 300_000_000
    static let maxCommentLength = 500
    static let maxPromoLength = 20

    init() {}

    /// Kotlin `collectLatest { ... }` tanasi. Chaqiruvchi `.task(id:)` so'rov o'zgarsa buni bekor qiladi.
    func runQuote(_ request: CartQuoteRequest, container: AppContainer) async {
        if request.lines.isEmpty {
            quote = nil
            quoteLoading = false
            quoteError = nil
            return
        }
        quoteLoading = true
        // Tugma ketma-ket bosilganda faqat oxirgi holat so'raladi
        do {
            try await Task.sleep(nanoseconds: CartViewModel.quoteDebounceNanos)
        } catch {
            return
        }
        if Task.isCancelled {
            return
        }
        await loadQuote(request, container: container)
    }

    private func loadQuote(_ request: CartQuoteRequest, container: AppContainer) async {
        let items = request.lines.map { CartItemIn(productId: $0.productId, quantity: $0.quantity) }
        do {
            let result = try await container.api.quote(
                items: items,
                latitude: request.address?.latitude,
                longitude: request.address?.longitude,
                promoCode: request.promo,
                phone: request.profile?.phone
            )
            if Task.isCancelled {
                return
            }
            quote = result
            quotePromo = request.promo
            quoteLoading = false
            quoteError = nil
        } catch {
            // Bekor qilingan so'rov (yangi so'rov boshlandi yoki ekran yopildi) e'tiborsiz qoldiriladi
            guard let apiError = ApiError.from(error), !Task.isCancelled else { return }
            quoteLoading = false
            quoteError = apiError.message
        }
    }

    func refreshQuote() {
        refreshTick += 1
    }

    func setPromoInput(_ value: String) {
        let filtered = value.filter { $0.isLetter || $0.isNumber || $0 == "-" || $0 == "_" }
        let cleaned = String(filtered.uppercased().prefix(CartViewModel.maxPromoLength))
        if cleaned != promoInput {
            promoInput = cleaned
        }
    }

    func applyPromo() {
        let code = promoInput.trimmingCharacters(in: .whitespacesAndNewlines)
        if code.isEmpty {
            return
        }
        appliedPromo = code
    }

    func removePromo() {
        appliedPromo = nil
        promoInput = ""
    }

    func setComment(_ value: String) {
        let next = String(value.prefix(CartViewModel.maxCommentLength))
        if next != comment {
            comment = next
        }
    }

    func clearSubmitError() {
        submitError = nil
    }

    func submit(_ container: AppContainer, onCreated: @escaping @MainActor (Int) -> Void) {
        if submitting {
            return
        }
        let lines = container.cart.lines
        guard !lines.isEmpty,
              let address = container.session.address,
              let profile = container.session.profile,
              profile.verified,
              let quote = quote
        else {
            return
        }
        // Yangi kiritilgan kod hali tekshirilmagan: summa boshqacha bo'lishi mumkin
        if quotePromo != appliedPromo {
            return
        }

        let comment = self.comment.trimmingCharacters(in: .whitespacesAndNewlines)
        // Ishlamagan kod buyurtmaga yuborilmaydi: mijoz sababini ko'rgan, summa usiz hisoblangan
        let promo: String? = quote.promoError == nil ? appliedPromo : nil
        let itemsKey = lines.map { "\($0.productId)x\($0.quantity)" }.joined(separator: ",")
        let addressKey = "\(address.latitude),\(address.longitude),\(address.note)"
        let fingerprint = "\(itemsKey)|\(addressKey)|\(comment)|\(profile.phone)|\(promo ?? "null")"
        if fingerprint != orderFingerprint {
            orderFingerprint = fingerprint
            clientOrderId = UUID().uuidString
        }
        let order = OrderIn(
            items: lines.map { CartItemIn(productId: $0.productId, quantity: $0.quantity) },
            latitude: address.latitude,
            longitude: address.longitude,
            addressNote: address.note,
            comment: comment,
            name: profile.name,
            phone: profile.phone,
            clientOrderId: clientOrderId,
            expectedTotal: quote.total,
            promoCode: promo
        )

        submitting = true
        submitError = nil
        Task { @MainActor in
            do {
                let api = container.api
                let created = try await container.account.withAuth {
                    try await api.createOrder(order)
                }
                orderFingerprint = ""
                container.cart.clear()
                // Yangi buyurtma darhol "faol buyurtmalar"ga qo'shiladi: bosh sahifadagi belgi va
                // bildirishnomalar shunga tayanadi
                container.live.orderPlaced()
                submitting = false
                self.comment = ""
                promoInput = ""
                appliedPromo = nil
                createdOrderId = created.id
                onCreated(created.id)
            } catch {
                submitting = false
                guard let apiError = ApiError.from(error) else { return }
                submitError = apiError.message
                // Narx yoki taom holati o'zgargan bo'lishi mumkin: summani qayta so'raymiz
                if !apiError.isNetwork {
                    refreshQuote()
                }
            }
        }
    }
}
