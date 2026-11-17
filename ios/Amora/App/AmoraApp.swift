/// App entry point (port of android AmoraApp.kt + MainActivity.kt).
///
/// - Creates the single `AppContainer` and `Router`, injects both with `.environment(...)`.
/// - Enlarges `URLCache.shared` (AsyncImage food photos) before anything loads.
/// - Lifecycle: scene becomes active -> `container.onAppForeground()` (+ refresh notification permission
///   state, Android LifecycleResumeEffect); scene goes to background -> `container.onAppBackground()`.
///   Like Android onStart/onStop: a short `.inactive` (Control Center, notification shade) changes nothing.
/// - Notifications: `NotificationDelegate` shows order notifications as banners while the app is open
///   and, when one is tapped, opens that order (`NotificationInbox` -> `Router.openOrderFromNotification`).
///
/// Surface:
/// - `@main struct AmoraApp: App`
/// - `final class AppDelegate: NSObject, UIApplicationDelegate`
/// - `final class NotificationDelegate: NSObject, UNUserNotificationCenterDelegate` (`static let shared`)

import SwiftUI
import UIKit
import UserNotifications

@main
struct AmoraApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @Environment(\.scenePhase) private var scenePhase

    @State private var container: AppContainer
    @State private var router: Router
    @State private var inForeground = false

    init() {
        AmoraApp.configureUrlCache()
        _container = State(initialValue: AppContainer())
        _router = State(initialValue: Router())
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(container)
                .environment(router)
                .onChange(of: scenePhase, initial: true) { _, phase in
                    handle(phase)
                }
        }
    }

    /// Ilova ekranda turganda server bilan jonli ulanish ushlab turiladi (Android ProcessLifecycleOwner).
    private func handle(_ phase: ScenePhase) {
        switch phase {
        case .active:
            if !inForeground {
                inForeground = true
                container.onAppForeground()
            }
            // Mijoz sozlamalardan qaytganda bildirishnoma ruxsati holati qayta o'qiladi
            let notifications = container.notifications
            Task {
                await notifications.refreshEnabled()
            }
        case .background:
            if inForeground {
                inForeground = false
                container.onAppBackground()
            }
        default:
            break
        }
    }

    /// Taom rasmlari uchun kattaroq kesh (AsyncImage URLCache.shared dan foydalanadi).
    private static func configureUrlCache() {
        URLCache.shared = URLCache(
            memoryCapacity: 48 * 1024 * 1024,
            diskCapacity: 200 * 1024 * 1024,
            directory: nil
        )
    }
}

/// UIKit ilova delegati: bildirishnomalar delegatini ilova ochilishi bilanoq o'rnatadi
/// (ilova bildirishnoma bosilib ochilganda ham bosish yo'qolmasin).
final class AppDelegate: NSObject, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        UNUserNotificationCenter.current().delegate = NotificationDelegate.shared
        return true
    }
}

/// Bildirishnomalar: ilova ochiq paytda ham banner ko'rinadi; bosilganda o'sha buyurtma ochiladi.
final class NotificationDelegate: NSObject, UNUserNotificationCenterDelegate {
    static let shared = NotificationDelegate()

    private static let orderIdKey = "order_id"

    /// Bildirishnomadagi buyurtma raqami (OrderNotifier.extraOrderId = "order_id").
    static func orderId(from userInfo: [AnyHashable: Any]) -> Int? {
        let raw = userInfo[orderIdKey]
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

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .list, .sound])
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        if response.actionIdentifier == UNNotificationDefaultActionIdentifier,
           let orderId = NotificationDelegate.orderId(from: response.notification.request.content.userInfo) {
            Task { @MainActor in
                NotificationInbox.shared.open(orderId: orderId)
            }
        }
        completionHandler()
    }
}
