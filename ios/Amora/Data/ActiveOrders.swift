/// The customer's unfinished orders (port of `ActiveOrders` in android data/Stores.kt).
///
/// Surface:
/// - `@MainActor @Observable final class ActiveOrders`
///   - `init(api: ApiClient, session: SessionStore)`
///   - `private(set) var orders: [Order]`                 // only `isActive` orders, newest first
///   - `func refresh() async`
///   - `var onStatusChange: (@MainActor (Order) -> Void)?` // used by LiveUpdates (missed status changes)
/// - `func changedOrders(before: [Order], latest: [Order]) -> [Order]`

import Foundation
import Observation

/// Mijozning tugallanmagan buyurtmalari: bosh sahifadagi belgi va bildirishnomalar shunga tayanadi.
@MainActor
@Observable
final class ActiveOrders {
    private(set) var orders: [Order] = []

    /// Kuzatilayotgan (faol) buyurtma boshqa holatga o'tgani qayta o'qishda aniqlandi. Jonli ulanish
    /// uzilib turgan paytda o'tkazib yuborilgan o'zgarishlar ham shu yerdan chiqadi.
    @ObservationIgnored var onStatusChange: (@MainActor (Order) -> Void)?

    private let api: ApiClient
    private let session: SessionStore

    init(api: ApiClient, session: SessionStore) {
        self.api = api
        self.session = session
    }

    func refresh() async {
        if session.token == nil {
            orders = []
            saveKnown([])
            return
        }
        // iOS ilovani fonda tez to'xtatadi va ko'pincha butunlay yopadi. Shuning uchun oxirgi ko'rilgan
        // holatlar telefonda saqlanadi: ilova qayta ochilganda shu orada o'zgargan buyurtma ham aytiladi.
        let known = orders.isEmpty ? loadKnown() : Dictionary(
            orders.map { ($0.id, $0.status) }, uniquingKeysWith: { first, _ in first }
        )
        do {
            let latest = try await api.orders(limit: 5).orders
            orders = latest.filter { $0.isActive }
            saveKnown(orders)
            for order in latest where known[order.id].map({ $0 != order.status }) ?? false {
                onStatusChange?(order)
            }
        } catch {
            if let apiError = error as? ApiError, apiError.isUnauthorized {
                orders = []
                saveKnown([])
            }
        }
    }

    private static let knownKey = "amora.activeOrderStatuses"

    private func loadKnown() -> [Int: String] {
        guard let saved = UserDefaults.standard.dictionary(forKey: ActiveOrders.knownKey) as? [String: String] else {
            return [:]
        }
        var result: [Int: String] = [:]
        for (key, status) in saved {
            if let id = Int(key) { result[id] = status }
        }
        return result
    }

    private func saveKnown(_ active: [Order]) {
        var saved: [String: String] = [:]
        for order in active { saved[String(order.id)] = order.status }
        UserDefaults.standard.set(saved, forKey: ActiveOrders.knownKey)
    }
}

/// Avval faol bo'lgan buyurtmalardan qaysilari boshqa holatga o'tgan (tugaganlari ham).
func changedOrders(before: [Order], latest: [Order]) -> [Order] {
    var known: [Int: String] = [:]
    for order in before { known[order.id] = order.status }
    return latest.filter { order in
        guard let previous = known[order.id] else { return false }
        return previous != order.status
    }
}
