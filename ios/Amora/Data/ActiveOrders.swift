/// The customer's unfinished orders (port of `ActiveOrders` in android data/Stores.kt).
///
/// Surface:
/// - `@MainActor @Observable final class ActiveOrders`
///   - `init(api: ApiClient, session: SessionStore)`
///   - `private(set) var orders: [Order]`                 // only `isActive` orders, newest first
///   - `func refresh() async`
///   - `func reset()`                                      // signed out / account deleted
///   - `var onStatusChange: (@MainActor (Order) -> Void)?` // used by LiveUpdates (missed status changes)

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
    @ObservationIgnored private var requested = 0
    @ObservationIgnored private var completed = 0
    @ObservationIgnored private var inFlight: Task<Void, Never>?

    init(api: ApiClient, session: SessionStore) {
        self.api = api
        self.session = session
        // Hisobdan chiqildi (mijoz o'zi chiqdi yoki server kalitni tanimadi): ro'yxat darhol bo'shaydi
        session.onTokenChange { [weak self] token in
            if token == nil { self?.reset() }
        }
    }

    /// Faol buyurtmalarni serverdan qayta o'qiydi.
    ///
    /// Bir vaqtda bir nechta so'rov kelsa (ilova ochildi, jonli xabar, ekrandagi takroriy tekshiruv),
    /// ular bittaga birlashadi: har bir chaqiruv o'zidan KEYIN boshlangan o'qish tugashini kutadi.
    func refresh() async {
        requested += 1
        let wanted = requested
        while let running = inFlight {
            await running.value
        }
        if completed >= wanted { return }
        let covers = requested
        let task = Task { @MainActor [weak self] in
            guard let self else { return }
            await self.load()
            self.completed = max(self.completed, covers)
            self.inFlight = nil
        }
        inFlight = task
        await task.value
    }

    /// Ro'yxat va oxirgi ko'rilgan holatlar o'chiriladi (hisobdan chiqish, hisobni o'chirish).
    func reset() {
        orders = []
        saveKnown([])
    }

    private func load() async {
        guard let sent = session.token else {
            reset()
            return
        }
        // iOS ilovani fonda tez to'xtatadi va ko'pincha butunlay yopadi. Shuning uchun oxirgi ko'rilgan
        // holatlar telefonda saqlanadi: ilova qayta ochilganda shu orada o'zgargan buyurtma ham aytiladi.
        let known = orders.isEmpty ? loadKnown() : Dictionary(
            orders.map { ($0.id, $0.status) }, uniquingKeysWith: { first, _ in first }
        )
        do {
            let latest = try await api.orders(limit: 5).orders
            // Javob kelguncha hisobdan chiqilgan yoki boshqa hisobga kirilgan: eski javob tashlab yuboriladi
            guard session.token == sent else { return }
            orders = latest.filter { $0.isActive }
            saveKnown(orders)
            for order in latest where known[order.id].map({ $0 != order.status }) ?? false {
                onStatusChange?(order)
            }
        } catch {
            // 401: `ApiClient.onUnauthorized` hisobdan chiqaradi va ro'yxat yuqoridagi kuzatuvchi orqali
            // bo'shaydi. Boshqa xatoda avvalgi ro'yxat qoladi
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
