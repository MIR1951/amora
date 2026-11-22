/// App-wide reaction to live events (port of android data/LiveUpdates.kt): refreshes catalog and active
/// orders, shows status-change notifications, restarts the stream when the auth token changes.
/// Individual screens (order, orders list, cart) consume `container.realtime.events()` themselves.
///
/// Surface:
/// - `@MainActor final class LiveUpdates`
///   - `init(realtime: Realtime, catalog: Catalog, activeOrders: ActiveOrders, notifier: OrderNotifier, session: SessionStore)`
///   - `func onForeground()`, `func onBackground()`
///   - `func setVisibleOrder(_ orderId: Int, status: String? = nil)`   // order screen visible: no notification for it
///   - `func clearVisibleOrder(_ orderId: Int)`
///   - `func onPush(_ change: OrderChange)`                            // APNs order push received in foreground
///   - `private(set) var resyncCount: Int`                             // number of `.resync` events handled
///   - `func resetNotified()`                                          // account deleted
///   - `func orderPlaced()`                                            // call after a successful createOrder
/// - `func isNewerStatus(_ last: String?, _ status: String) -> Bool`

import Foundation
import UIKit

/// Jonli xabarlarni ilova bo'ylab tarqatadi.
@MainActor
final class LiveUpdates {
    private let realtime: Realtime
    private let catalog: Catalog
    private let activeOrders: ActiveOrders
    private let notifier: OrderNotifier

    private var foreground = false
    private var visibleOrderId: Int?
    private var lingerTask: Task<Void, Never>?
    private var backgroundTaskId: UIBackgroundTaskIdentifier = .invalid
    private var listenTask: Task<Void, Never>?

    /// Har bir buyurtma bo'yicha mijozga oxirgi bildirilgan (yoki ekranda ko'rsatilgan) holat.
    /// Telefonda saqlanadi: ilova yopilib ochilganda aytib bo'lingan holat qayta aytilmaydi.
    private var notified: [Int: String] = LiveUpdates.loadNotified() {
        didSet { LiveUpdates.saveNotified(notified) }
    }

    /// Nechta "resync" (jonli ulanish o'rnatildi) qayta ishlangan. `AppContainer` ilova ochilganda
    /// shunga qaraydi: ulanish o'zi hammasini qayta o'qigan bo'lsa, ikkinchi marta o'qimaydi.
    private(set) var resyncCount = 0

    private static let notifiedKey = "amora.live.notified"
    // Eski buyurtmalar yig'ilib qolmasin: eng oxirgi shuncha buyurtma saqlanadi
    private static let notifiedLimit = 20

    private static let backgroundLingerNs: UInt64 = 20 * 60 * 1_000_000_000

    init(
        realtime: Realtime,
        catalog: Catalog,
        activeOrders: ActiveOrders,
        notifier: OrderNotifier,
        session: SessionStore
    ) {
        self.realtime = realtime
        self.catalog = catalog
        self.activeOrders = activeOrders
        self.notifier = notifier

        let stream = realtime.events()
        listenTask = Task { [weak self] in
            for await event in stream {
                self?.handle(event)
            }
        }
        // Ulanish uzilib turganda o'tkazib yuborilgan o'zgarish: qayta o'qishda aniqlanadi va
        // xuddi jonli xabar kelgandek bildiriladi
        activeOrders.onStatusChange = { [weak self] order in
            self?.notify(
                OrderChange(
                    orderId: order.id,
                    status: order.status,
                    statusLabel: order.statusLabel,
                    rejectReason: order.rejectReason
                )
            )
        }
        // Mijoz ro'yxatdan o'tdi yoki kalit yangilandi: ulanish yangi kalit bilan qayta o'rnatiladi
        session.onTokenChange { [weak realtime] _ in
            realtime?.restart()
        }
    }

    private func handle(_ event: LiveEvent) {
        switch event {
        case .resync:
            resyncCount += 1
            Task { await catalog.refresh() }
            Task { await refreshActiveOrders() }
        case .menuChanged, .shopChanged:
            Task { await catalog.refresh() }
        case .orderChanged(let change):
            notify(change)
            Task { await refreshActiveOrders() }
        }
    }

    /// Ilova ekranga chiqdi.
    func onForeground() {
        foreground = true
        lingerTask?.cancel()
        lingerTask = nil
        endBackgroundTime()
        // Orqa fonda ushlab turilgan ulanish tizim ilovani to'xtatgan paytda o'lgan bo'lishi mumkin:
        // yangidan ulanamiz. Yangi ulanish "resync" yuboradi va menyu, faol buyurtmalar bir marta o'qiladi
        if realtime.isRunning {
            realtime.restart()
        } else {
            realtime.start()
        }
    }

    /// Ilova orqa fonga o'tdi. Faol buyurtma bo'lsa, ulanish tizim ruxsat bergancha ushlab turiladi
    /// (iOS odatda ~30 soniya beradi; 20 daqiqa faqat yuqori chegara). Undan keyingi o'zgarishlar
    /// ilova qayta ochilganda aytiladi (`ActiveOrders` oxirgi holatlarni saqlaydi). Ilova yopiq
    /// paytda bildirishnomani server APNs push orqali yuboradi (`PushTokens`).
    func onBackground() {
        foreground = false
        lingerTask?.cancel()
        lingerTask = nil
        if activeOrders.orders.isEmpty {
            realtime.stop()
            endBackgroundTime()
            return
        }
        beginBackgroundTime()
        lingerTask = Task { [weak self] in
            do {
                try await Task.sleep(nanoseconds: LiveUpdates.backgroundLingerNs)
            } catch {
                return
            }
            self?.stopInBackground()
        }
    }

    private func stopInBackground() {
        if foreground { return }
        realtime.stop()
        endBackgroundTime()
    }

    private func beginBackgroundTime() {
        if backgroundTaskId != .invalid { return }
        backgroundTaskId = UIApplication.shared.beginBackgroundTask(withName: "amora.live") { [weak self] in
            // Tizim vaqt tugaganini aytdi: ulanish yopiladi
            MainActor.assumeIsolated {
                self?.expireBackgroundTime()
            }
        }
    }

    private func expireBackgroundTime() {
        lingerTask?.cancel()
        lingerTask = nil
        if !foreground { realtime.stop() }
        endBackgroundTime()
    }

    private func endBackgroundTime() {
        if backgroundTaskId == .invalid { return }
        let id = backgroundTaskId
        backgroundTaskId = .invalid
        UIApplication.shared.endBackgroundTask(id)
    }

    /// Mijoz shu buyurtma ekraniga qarab turibdi: u haqidagi bildirishnoma kerak emas.
    /// `status` ekranda ko'rinib turgan holat: u haqida keyin ham alohida bildirilmaydi.
    func setVisibleOrder(_ orderId: Int, status: String? = nil) {
        visibleOrderId = orderId
        if let status { notified[orderId] = status }
        notifier.dismiss(orderId)
    }

    /// Buyurtma ekrani yopildi. Shu orada boshqa buyurtma ochilgan bo'lsa, unga tegilmaydi.
    func clearVisibleOrder(_ orderId: Int) {
        if visibleOrderId == orderId { visibleOrderId = nil }
    }

    /// Ilova ochiq paytda APNs push orqali kelgan holat (tizim banneri ko'rsatilmaydi, bildirishnomani
    /// ilova o'zi chiqaradi). Jonli ulanish orqali kelgan xuddi shu xabar bilan ikkilanmaydi.
    func onPush(_ change: OrderChange) {
        notify(change, fromPush: true)
        Task { await refreshActiveOrders() }
    }

    /// Mijoz hozirgina buyurtma berdi: u darhol faol buyurtmalar qatoriga qo'shiladi.
    func orderPlaced() {
        Task { await refreshActiveOrders() }
    }

    /// Holat o'zgarishi haqida bildiradi. Bitta o'zgarish ikki yo'ldan kelishi mumkin: ikkinchisi va
    /// kechikib kelgan eski holat e'tiborsiz qoldiriladi.
    private func notify(_ change: OrderChange, fromPush: Bool = false) {
        if !isNewerStatus(notified[change.orderId], change.status) { return }
        notified[change.orderId] = change.status
        // Mijoz aynan shu buyurtma ekraniga qarab turgan bo'lsa, o'zgarishni ekranda ko'radi
        if foreground && visibleOrderId == change.orderId { return }
        // Ilova yopiq paytda shu holat haqida push kelgan va u hali bildirishnomalar markazida turgan
        // bo'lishi mumkin: o'shanda ikkinchi marta ovoz chiqarilmaydi. Hozirgina kelgan pushni esa
        // tizim ko'rsatmagan: uni ilova o'zi chiqaradi
        notifier.show(change, skipIfDelivered: !fromPush)
    }

    /// Hisob o'chirildi: kimga nima bildirilgani ham unutiladi.
    func resetNotified() {
        notified = [:]
    }

    private static func loadNotified() -> [Int: String] {
        guard let saved = UserDefaults.standard.dictionary(forKey: notifiedKey) as? [String: String] else {
            return [:]
        }
        var result: [Int: String] = [:]
        for (key, status) in saved {
            if let id = Int(key) { result[id] = status }
        }
        return result
    }

    private static func saveNotified(_ notified: [Int: String]) {
        var saved: [String: String] = [:]
        for id in notified.keys.sorted(by: >).prefix(notifiedLimit) {
            saved[String(id)] = notified[id]
        }
        UserDefaults.standard.set(saved, forKey: notifiedKey)
    }

    private func refreshActiveOrders() async {
        await activeOrders.refresh()
        // Orqa fonda kutilayotgan buyurtma qolmadi: ulanishni ushlab turishning hojati yo'q
        if !foreground && activeOrders.orders.isEmpty {
            lingerTask?.cancel()
            lingerTask = nil
            realtime.stop()
            endBackgroundTime()
        }
    }
}

// Buyurtma faqat oldinga yuradi: yangi, tayyorlanmoqda, yo'lda, tugadi (yetkazildi yoki bekor bo'ldi)
private func statusStep(_ status: String) -> Int {
    switch status {
    case OrderStatus.new: return 0
    case OrderStatus.accepted: return 1
    case OrderStatus.delivering: return 2
    default: return 3
    }
}

/// `status` mijozga oxirgi bildirilgan `last` holatdan keyingi bosqichmi.
func isNewerStatus(_ last: String?, _ status: String) -> Bool {
    guard let last else { return true }
    return statusStep(status) > statusStep(last)
}
