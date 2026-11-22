/// Push token flow (port of android data/Push.kt). iOS uses APNs directly (no Firebase SDK): the app delegate
/// gets the APNs device token (hex) and hands it to `PushTokenInbox`, which forwards it to `PushTokens`.
/// The token is sent to the server (`PATCH /me {"fcm_token": ...}`; the device is registered with
/// platform "ios", so the server sends to APNs) once the customer has an auth token, and re-sent whenever
/// the auth token changes. The server pushes order status and promo messages while the app is closed.
///
/// Surface:
/// - `@MainActor final class PushTokenInbox` (`static let shared`): `receive(_ token:)` from the app delegate,
///   `attach(_ handler:)` from AppContainer (the last token received before attach is delivered then)
/// - `@MainActor final class OrderPushInbox` (`static let shared`): `receive(_ change:)` from the notification
///   delegate (APNs order push while the app is open), `attach(_ handler:)` from AppContainer (-> LiveUpdates.onPush)
/// - `@MainActor final class PushTokens`
///   - `init(api: ApiClient, session: SessionStore)`
///   - `func start()`                       // subscribe to auth-token changes (called by AppContainer)
///   - `func onNewToken(_ token: String)`   // push provider gave a (new) device token
///   - `func retry()`                       // app returned to foreground: re-send if it failed earlier

import Foundation

@MainActor
final class PushTokens {
    private let api: ApiClient
    private let session: SessionStore
    private var started = false
    private var syncing = false
    private var syncAgain = false

    init(api: ApiClient, session: SessionStore) {
        self.api = api
        self.session = session
    }

    func start() {
        if started { return }
        started = true
        // Mijoz ro'yxatdan o'tdi yoki qayta ro'yxatdan o'tdi: manzil yangi kalit bilan yuboriladi
        session.onTokenChange { [weak self] _ in
            self?.retry()
        }
        retry()
    }

    func onNewToken(_ token: String) {
        if token == session.pushToken { return }
        session.pushToken = token
        session.pushTokenSentWith = nil
        retry()
    }

    /// Ilova ekranga qaytdi: oldin yuborilmay qolgan bo'lsa, yana urinadi.
    func retry() {
        Task { [weak self] in
            await self?.sync()
        }
    }

    private func sync() async {
        // Bir vaqtda faqat bitta yuborish (Kotlin Mutex o'rniga)
        if syncing {
            syncAgain = true
            return
        }
        syncing = true
        defer { syncing = false }
        repeat {
            syncAgain = false
            await syncOnce()
        } while syncAgain
    }

    private func syncOnce() async {
        guard let pushToken = session.pushToken, let authToken = session.token else { return }
        // Qaysi manzil qaysi kalit bilan yuborilgani: yuborish paytida manzil yangilansa, yangisi ham yuboriladi
        // Telefonda juftlikning o'zi emas, xeshi saqlanadi: kirish kaliti UserDefaults'ga tushmaydi
        let sent = sha256Hex("\(authToken)|\(pushToken)")
        if session.pushTokenSentWith == sent { return }
        do {
            _ = try await api.updatePushToken(pushToken)
            session.pushTokenSentWith = sent
        } catch {
            // Keyingi safar (ilova qayta ochilganda yoki kalit yangilanganda) yana urinamiz
        }
    }
}

/// APNs qurilma manzili ilova delegatidan keladi, `AppContainer` esa SwiftUI tomonda yaratiladi:
/// ular orasidagi ko'prik. Manzil container tayyor bo'lishidan oldin kelsa, saqlab turiladi.
@MainActor
final class PushTokenInbox {
    static let shared = PushTokenInbox()

    private var pending: String?
    private var handler: ((String) -> Void)?

    func receive(_ token: String) {
        if let handler {
            handler(token)
        } else {
            pending = token
        }
    }

    func attach(_ handler: @escaping (String) -> Void) {
        self.handler = handler
        if let token = pending {
            pending = nil
            handler(token)
        }
    }
}

/// Ilova ochiq paytda kelgan buyurtma pushi bildirishnomalar delegatidan keladi, `LiveUpdates` esa
/// `AppContainer` ichida: ular orasidagi ko'prik. Container tayyor bo'lguncha kelganlari saqlab turiladi.
@MainActor
final class OrderPushInbox {
    static let shared = OrderPushInbox()

    private var pending: [OrderChange] = []
    private var handler: ((OrderChange) -> Void)?

    func receive(_ change: OrderChange) {
        if let handler {
            handler(change)
        } else {
            pending.append(change)
        }
    }

    func attach(_ handler: @escaping (OrderChange) -> Void) {
        self.handler = handler
        let waiting = pending
        pending = []
        for change in waiting {
            handler(change)
        }
    }
}

/// APNs qurilma manzili (32 bayt) serverga 64 belgili hex matn bo'lib boradi.
func apnsTokenString(_ deviceToken: Data) -> String {
    deviceToken.map { String(format: "%02x", $0) }.joined()
}
