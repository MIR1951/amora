/// Orders list state (port of OrdersViewModel from android ui/orders/OrdersScreen.kt).
///
/// Surface (used by OrdersScreen.swift only):
/// - `@MainActor @Observable final class OrdersViewModel`
///   - state: `loading`, `refreshing`, `loadingMore`, `error`, `orders`, `hasMore`
///   - `static let pageSize = 20`
///   - `func reload(_ container: AppContainer, byUser: Bool = false)` - first page again (older pages loaded
///     with "Yana ko'rsatish" stay in the list)
///   - `func loadMore(_ container: AppContainer)`

import Foundation
import Observation

@MainActor
@Observable
final class OrdersViewModel {
    var loading: Bool = true
    var refreshing: Bool = false
    var loadingMore: Bool = false
    var error: String? = nil
    var orders: [Order] = []
    var hasMore: Bool = false

    static let pageSize = 20

    init() {}

    private func resetEmpty() {
        loading = false
        refreshing = false
        loadingMore = false
        error = nil
        orders = []
        hasMore = false
    }

    /// Birinchi sahifani qayta yuklaydi. `byUser`: mijoz ekranni pastga tortdi.
    func reload(_ container: AppContainer, byUser: Bool = false) {
        if container.session.token == nil {
            // Hali birorta buyurtma berilmagan: serverga murojaat qilishning hojati yo'q
            resetEmpty()
            return
        }
        refreshing = byUser
        loading = orders.isEmpty && !byUser
        error = nil
        Task {
            do {
                let page = try await container.api.orders(limit: OrdersViewModel.pageSize, offset: 0)
                // "Yana ko'rsatish" bilan yuklangan eski buyurtmalar ro'yxatda qoladi:
                // buyurtmani ochib qaytgan mijoz ro'yxatni yana boshidan varaqlamaydi
                let freshIds = Set(page.orders.map { $0.id })
                let tail = self.orders.filter { !freshIds.contains($0.id) }
                self.hasMore = tail.isEmpty ? page.hasMore : self.hasMore
                self.orders = page.orders + tail
                self.loading = false
                self.refreshing = false
                self.loadingMore = false
                self.error = nil
            } catch {
                guard let apiError = ApiError.from(error) else {
                    self.loading = false
                    self.refreshing = false
                    return
                }
                if apiError.isUnauthorized {
                    self.resetEmpty()
                } else {
                    self.loading = false
                    self.refreshing = false
                    self.error = apiError.message
                }
            }
        }
    }

    func loadMore(_ container: AppContainer) {
        if loadingMore || !hasMore { return }
        loadingMore = true
        let offset = orders.count
        Task {
            do {
                let page = try await container.api.orders(limit: OrdersViewModel.pageSize, offset: offset)
                let known = Set(self.orders.map { $0.id })
                self.orders = self.orders + page.orders.filter { !known.contains($0.id) }
                self.hasMore = page.hasMore
                self.loadingMore = false
            } catch {
                self.loadingMore = false
                if let apiError = ApiError.from(error) {
                    self.error = apiError.message
                }
            }
        }
    }
}
