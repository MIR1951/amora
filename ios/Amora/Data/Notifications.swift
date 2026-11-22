/// Local order-status notifications (port of android notify/OrderNotifier.kt + permission helpers from
/// ui/components/Notifications.kt). Shown with UNUserNotificationCenter while the app runs; userInfo carries
/// `order_id` and `status` (same keys as the server's APNs payload, same identifier `order-<id>` as its
/// apns-collapse-id). Foreground banner presentation and tap handling live in the app delegate (AmoraApp.swift).
///
/// Surface:
/// - `struct OrderNotice: Equatable { var title: String; var text: String }`
/// - `func orderNotice(_ change: OrderChange) -> OrderNotice?`   // nil for statuses the customer caused (new, cancelled)
/// - `@MainActor @Observable final class OrderNotifier`
///   - `init(session: SessionStore)`
///   - `static let extraOrderId = "order_id"`
///   - `nonisolated static func orderId(from userInfo: [AnyHashable: Any]) -> Int?`
///   - `nonisolated static func orderChange(from userInfo: [AnyHashable: Any]) -> OrderChange?`   // APNs payload
///   - `private(set) var enabled: Bool`                      // last known permission state (call refreshEnabled())
///   - `func refreshEnabled() async`
///   - `func isEnabled() async -> Bool`
///   - `func askPermissionOnce() async`                      // Android AskNotificationPermissionOnce
///   - `func toggle() async`                                  // Android rememberNotificationSwitch().toggle
///   - `func openSettings()`
///   - `func show(_ change: OrderChange, skipIfDelivered: Bool = true)`, `func dismiss(_ orderId: Int)`

import Foundation
import Observation
import UIKit
import UserNotifications

/// Bildirishnomada ko'rinadigan matn.
struct OrderNotice: Equatable {
    var title: String
    var text: String
}

/// Buyurtma holati uchun bildirishnoma matni. Mijozning o'zi qilgan ishlar (yubordi, bekor qildi)
/// uchun bildirishnoma kerak emas: nil qaytadi.
func orderNotice(_ change: OrderChange) -> OrderNotice? {
    let id = change.orderId
    switch change.status {
    case OrderStatus.accepted:
        return OrderNotice(
            title: "Buyurtma №\(id) qabul qilindi",
            text: "Kafe buyurtmangizni tayyorlamoqda."
        )
    case OrderStatus.delivering:
        return OrderNotice(
            title: "Kuryer yo'lda",
            text: "Buyurtma №\(id) ni kuryer olib yo'lga chiqdi."
        )
    case OrderStatus.delivered:
        return OrderNotice(
            title: "Buyurtma yetkazildi",
            text: "Buyurtma №\(id) yetkazildi. Yoqimli ishtaha!"
        )
    case OrderStatus.rejected:
        let reason = change.rejectReason?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return OrderNotice(
            title: "Buyurtma №\(id) rad etildi",
            text: reason.isEmpty ? "Afsuski, kafe buyurtmani qabul qila olmadi." : "Sabab: \(change.rejectReason ?? "")"
        )
    default:
        return nil
    }
}

/// Buyurtma holati haqidagi tizim bildirishnomalari.
@MainActor
@Observable
final class OrderNotifier {
    static let extraOrderId = "order_id"
    static let extraStatus = "status"
    static let categoryOrders = "orders"

    /// Oxirgi ma'lum ruxsat holati. `refreshEnabled()` bilan yangilanadi.
    private(set) var enabled = false

    private let session: SessionStore

    init(session: SessionStore) {
        self.session = session
        Task { [weak self] in
            await self?.refreshEnabled()
        }
    }

    /// Bildirishnoma bosilganda ochilishi kerak bo'lgan buyurtma.
    /// Nonisolated: safe to call from UNUserNotificationCenterDelegate methods.
    nonisolated static func orderId(from userInfo: [AnyHashable: Any]) -> Int? {
        let raw = userInfo["order_id"]
        var id: Int?
        if let value = raw as? Int {
            id = value
        } else if let value = raw as? NSNumber {
            id = value.intValue
        } else if let value = raw as? String {
            id = Int(value)
        }
        guard let id, id > 0 else { return nil }
        return id
    }

    /// Serverdan kelgan APNs xabaridagi buyurtma holati (`order_id`, `status`, ixtiyoriy `reject_reason`).
    nonisolated static func orderChange(from userInfo: [AnyHashable: Any]) -> OrderChange? {
        guard let id = orderId(from: userInfo),
              let status = userInfo["status"] as? String, !status.isEmpty else { return nil }
        return OrderChange(
            orderId: id,
            status: status,
            statusLabel: userInfo["status_label"] as? String ?? "",
            rejectReason: userInfo["reject_reason"] as? String
        )
    }

    private static func isAllowed(_ status: UNAuthorizationStatus) -> Bool {
        switch status {
        case .authorized, .provisional, .ephemeral:
            return true
        default:
            return false
        }
    }

    private func authorizationStatus() async -> UNAuthorizationStatus {
        let settings = await UNUserNotificationCenter.current().notificationSettings()
        return settings.authorizationStatus
    }

    /// Telefon hozir bildirishnoma ko'rsatishga ruxsat beradimi.
    func isEnabled() async -> Bool {
        let status = await authorizationStatus()
        let allowed = OrderNotifier.isAllowed(status)
        if enabled != allowed { enabled = allowed }
        return allowed
    }

    func refreshEnabled() async {
        _ = await isEnabled()
    }

    private func requestAuthorization() async {
        session.notificationsAsked = true
        _ = try? await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge])
        await refreshEnabled()
    }

    /// Bildirishnomaga ruxsatni bir marta so'raydi. Mijoz faol buyurtma ekraniga kelganda chaqiriladi.
    /// Rad etilsa, qayta so'ralmaydi; keyin profil sahifasidagi "Bildirishnomalar" qatoridan yoqish mumkin.
    func askPermissionOnce() async {
        let status = await authorizationStatus()
        if status == .notDetermined && !session.notificationsAsked {
            await requestAuthorization()
        } else {
            let allowed = OrderNotifier.isAllowed(status)
            if enabled != allowed { enabled = allowed }
        }
    }

    /// Profil sahifasidagi "Bildirishnomalar" qatori: hali so'ralmagan bo'lsa tizim oynasi chiqadi,
    /// aks holda telefon sozlamalaridagi shu ilova sahifasi ochiladi.
    func toggle() async {
        let status = await authorizationStatus()
        if status == .notDetermined {
            await requestAuthorization()
        } else {
            openSettings()
        }
    }

    /// Telefon sozlamalaridagi shu ilovaning bildirishnomalar sahifasi.
    func openSettings() {
        if let url = URL(string: UIApplication.openNotificationSettingsURLString) {
            UIApplication.shared.open(url, options: [:], completionHandler: nil)
        } else if let url = URL(string: UIApplication.openSettingsURLString) {
            UIApplication.shared.open(url, options: [:], completionHandler: nil)
        }
    }

    /// Holat o'zgarishi haqida bildirishnoma chiqaradi. `skipIfDelivered`: shu buyurtmaning aynan shu
    /// holati haqidagi bildirishnoma (ilova yopiq paytda kelgan push yoki avval chiqarilgani) hali
    /// bildirishnomalar markazida turgan bo'lsa, qayta chiqarilmaydi.
    func show(_ change: OrderChange, skipIfDelivered: Bool = true) {
        guard let notice = orderNotice(change) else { return }
        let content = UNMutableNotificationContent()
        content.title = notice.title
        content.body = notice.text
        content.sound = .default
        content.categoryIdentifier = OrderNotifier.categoryOrders
        content.threadIdentifier = "order-\(change.orderId)"
        content.userInfo = [
            OrderNotifier.extraOrderId: change.orderId,
            OrderNotifier.extraStatus: change.status,
        ]
        let identifier = OrderNotifier.identifier(change.orderId)
        let status = change.status
        Task { [weak self] in
            guard let self, await self.isEnabled() else { return }
            let center = UNUserNotificationCenter.current()
            if skipIfDelivered {
                let delivered = await center.deliveredNotifications()
                let shown = delivered.contains { notification in
                    notification.request.identifier == identifier
                        && (notification.request.content.userInfo[OrderNotifier.extraStatus] as? String) == status
                }
                if shown { return }
            }
            let request = UNNotificationRequest(identifier: identifier, content: content, trigger: nil)
            try? await center.add(request)
        }
    }

    /// Mijoz buyurtma ekranini ochgan: shu buyurtma haqidagi bildirishnoma endi kerak emas.
    func dismiss(_ orderId: Int) {
        let identifier = OrderNotifier.identifier(orderId)
        let center = UNUserNotificationCenter.current()
        center.removeDeliveredNotifications(withIdentifiers: [identifier])
        center.removePendingNotificationRequests(withIdentifiers: [identifier])
    }

    private static func identifier(_ orderId: Int) -> String {
        "order-\(orderId)"
    }
}
