/// Notification permission helpers for screens (port of android ui/components/Notifications.kt).
/// The permission logic itself lives in Data/Notifications.swift (`OrderNotifier`); this file only
/// gives screens a one-liner.
///
/// Surface:
/// - `View.askNotificationPermissionOnce()` - on appear asks for notification permission once
///   (Android `AskNotificationPermissionOnce(container)`, used on the active order screen)
/// - Profile "Bildirishnomalar" row: read `container.notifications.enabled`, call
///   `Task { await container.notifications.toggle() }`; the app refreshes `enabled` on every return
///   to the foreground (AmoraApp), like Android `LifecycleResumeEffect`.

import SwiftUI

/// Bildirishnomaga ruxsatni bir marta so'raydi. Mijoz faol buyurtma ekraniga kelganda chaqiriladi:
/// nega kerakligi shu yerda tushunarli. Rad etilsa, qayta so'ralmaydi.
struct AskNotificationPermissionOnceModifier: ViewModifier {
    @Environment(AppContainer.self) private var container

    init() {}

    func body(content: Content) -> some View {
        content.task {
            await container.notifications.askPermissionOnce()
        }
    }
}

extension View {
    func askNotificationPermissionOnce() -> some View {
        modifier(AskNotificationPermissionOnceModifier())
    }
}
