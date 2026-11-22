/// Order screen state (port of OrderViewModel + repeatOrder from android ui/order/OrderScreen.kt).
///
/// Surface (used by OrderScreen.swift and OrdersScreen.swift only):
/// - `let orderRepeatUnavailable: String`                              // Kotlin REPEAT_UNAVAILABLE
/// - `@MainActor func repeatOrderIntoCart(_ container: AppContainer, _ order: Order) -> Int`
///   puts the order's (still available) dishes into the cart instead of its old content; returns how many
///   kinds of dishes went in (0 = none of them is on the menu now)
/// - `@MainActor @Observable final class OrderViewModel`
///   - `init(orderId: Int)`, state: `loading`, `order`, `error`, `cancelling`, `message`
///   - `func refresh(_ container: AppContainer) async`, `func poll(_ container: AppContainer) async`,
///     `func retry(_ container: AppContainer)`, `func cancel(_ container: AppContainer)`,
///     `func clearMessage()`, `func repeatOrder(_ container: AppContainer) -> Int`

import Foundation
import Observation

/// "Yana shunday" bosilganda buyurtmadagi taomlarning birortasi ham hozir menyuda bo'lmasa.
let orderRepeatUnavailable = "Bu taomlar hozir menyuda yo'q"

/// Buyurtmadagi taomlarni savatga soladi (savatdagi eski taomlar o'rniga).
/// Savatga tushgan taomlar turini qaytaradi: 0 bo'lsa, hech biri hozir menyuda yo'q.
@MainActor
func repeatOrderIntoCart(_ container: AppContainer, _ order: Order) -> Int {
    let menuProducts = container.catalog.menu?.products
    var lines: [CartLine] = []
    for item in order.items {
        guard let productId = item.productId else { continue }
        // Menyu yuklangan bo'lsa, faqat hozir sotuvda bor taomlar olinadi
        if let menuProducts, !menuProducts.contains(where: { $0.id == productId && $0.isAvailable }) {
            continue
        }
        if let index = lines.firstIndex(where: { $0.productId == productId }) {
            lines[index].quantity += item.quantity
        } else {
            lines.append(CartLine(productId: productId, quantity: item.quantity))
        }
    }
    if !lines.isEmpty {
        container.cart.replace(lines)
    }
    return lines.count
}

@MainActor
@Observable
final class OrderViewModel {
    let orderId: Int

    var loading: Bool = true
    var order: Order? = nil
    var error: String? = nil
    var cancelling: Bool = false
    // Bir martalik xabar (masalan, bekor qilib bo'lmadi)
    var message: String? = nil

    // Buyurtma holati o'zgarsa, server jonli ulanish orqali o'zi xabar beradi. Ulanish uzilgan
    // bo'lsa (yoki server eski bo'lsa), holat shuncha vaqtda bir marta so'rab turiladi.
    static let pollIntervalNanos: UInt64 = 7_000_000_000
    // Jonli ulanish ishlab turganda bu so'rov faqat ehtiyot chorasi
    static let pollIntervalLiveNanos: UInt64 = 30_000_000_000

    // Har bir o'qish o'z raqami bilan ketadi: kechikib kelgan eski javob yangi holatni bosib ketmaydi
    @ObservationIgnored private var generation = 0
    // Server bu buyurtmani bermaydi (401: hisobdan chiqilgan, 404: bunday buyurtma yo'q):
    // qayta-qayta so'rashning foydasi yo'q
    @ObservationIgnored private var unavailable = false

    init(orderId: Int) {
        self.orderId = orderId
    }

    /// Buyurtmani serverdan qayta o'qiydi. Xato bo'lsa, avval yuklangan ma'lumot ekranda qoladi.
    func refresh(_ container: AppContainer) async {
        generation += 1
        let mine = generation
        do {
            let fresh = try await container.api.order(id: orderId)
            // Shu orada yangiroq o'qish boshlangan yoki buyurtma bekor qilingan: bu javob eskirgan
            guard mine == generation else { return }
            self.order = fresh
            self.loading = false
            self.error = nil
            self.unavailable = false
        } catch {
            // Vazifa bekor qilindi (ekran yopildi): hech narsa o'zgarmaydi
            guard let apiError = ApiError.from(error), mine == generation else { return }
            self.loading = false
            self.error = apiError.message
            if apiError.status == 401 || apiError.status == 404 {
                self.unavailable = true
            }
        }
    }

    /// Ekran ko'rinib turganda holat yangilanib turadi; buyurtma tugagach so'rovlar to'xtaydi.
    func poll(_ container: AppContainer) async {
        while !Task.isCancelled {
            await refresh(container)
            if let current = self.order, !current.isActive {
                break
            }
            if unavailable {
                break
            }
            let wait = container.realtime.connected
                ? OrderViewModel.pollIntervalLiveNanos
                : OrderViewModel.pollIntervalNanos
            do {
                try await Task.sleep(nanoseconds: wait)
            } catch {
                break
            }
        }
    }

    func retry(_ container: AppContainer) {
        loading = order == nil
        error = nil
        Task {
            await self.refresh(container)
        }
    }

    func cancel(_ container: AppContainer) {
        if cancelling { return }
        cancelling = true
        let id = orderId
        Task {
            do {
                let updated = try await container.api.cancelOrder(id: id)
                self.cancelling = false
                // Bekor qilishdan oldin boshlangan o'qishning javobi endi eskirgan
                self.generation += 1
                self.order = updated
                self.loading = false
                self.error = nil
            } catch {
                self.cancelling = false
                guard let apiError = ApiError.from(error) else { return }
                self.message = apiError.message
                // Kafe allaqachon qabul qilgan bo'lishi mumkin: holatni yangilaymiz
                if !apiError.isNetwork {
                    await self.refresh(container)
                }
            }
        }
    }

    func clearMessage() {
        message = nil
    }

    /// Xuddi shu taomlarni savatga soladi. Savatga tushgan taomlar sonini qaytaradi.
    func repeatOrder(_ container: AppContainer) -> Int {
        guard let current = order else { return 0 }
        let added = repeatOrderIntoCart(container, current)
        if added == 0 {
            message = orderRepeatUnavailable
        }
        return added
    }
}
