/// Push token flow (port of android data/Push.kt) kept as a stub: iOS has no Firebase yet, so nothing
/// produces a token today. When APNs/FCM is added, call `onNewToken(_:)` with the device token and the
/// existing flow sends it to the server (`PATCH /me {"fcm_token": ...}`) once the customer has an auth token,
/// and re-sends it whenever the auth token changes.
///
/// Surface:
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
        let sent = "\(authToken)|\(pushToken)"
        if session.pushTokenSentWith == sent { return }
        do {
            _ = try await api.updatePushToken(pushToken)
            session.pushTokenSentWith = sent
        } catch {
            // Keyingi safar (ilova qayta ochilganda yoki kalit yangilanganda) yana urinamiz
        }
    }
}
