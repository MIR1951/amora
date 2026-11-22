/// Account and Telegram phone verification (port of `Account` in android data/Stores.kt).
///
/// Surface:
/// - `enum VerificationOutcome: Equatable { case verified; case expired; case failed(String) }`
/// - `@MainActor @Observable final class Account`
///   - `init(api: ApiClient, session: SessionStore)`
///   - `static let codeNotVerified = "phone_not_verified"`
///   - `static let notVerifiedMessage = "Buyurtma berish uchun raqamingizni Telegram orqali tasdiqlang"`
///   - `func saveName(_ name: String) async -> String?`      // local save + PATCH /me; nil = saved on the server,
///                                                           // otherwise the message to show
///   - `func refreshInBackground()`
///   - `func refresh() async`                                // sync profile with GET /me (unsent name goes first)
///   - `private(set) var pendingVerification: PendingVerification?`   // persisted; UI shows "waiting" while non-nil
///   - `private(set) var verificationOutcome: VerificationOutcome?`   // one-shot, `consumeVerificationOutcome()`
///   - `func startVerification(name: String?) async throws -> TelegramStart`
///   - `func cancelVerification()`
///   - `func onForeground()`, `func onBackground()`          // the pending verification is checked while in foreground
///   - `func signOut() async`                                // POST /auth/logout, then local sign-out (even offline)
///   - `func deleteAccount() async throws`                   // DELETE /me, then local token/profile removed
///   - `func withAuth<T>(_ block: () async throws -> T) async throws -> T`
///     (throws ApiError(code: "phone_not_verified") when not verified / token rejected)
///
/// A rejected token (401) is handled in one place: `ApiClient.onUnauthorized` (set by AppContainer) signs out.

import Foundation
import Observation

/// Telegram orqali tasdiqlash qanday tugadi (ekran bir marta ko'rsatadi).
enum VerificationOutcome: Equatable {
    case verified
    case expired
    case failed(String)
}

/// Hisob va profil. Mijoz raqamini Telegram orqali tasdiqlaydi: ilova botni ochadi, mijoz u yerda
/// "📱 Raqamni yuborish" ni bosadi, ilova natijani so'rab turadi.
@MainActor
@Observable
final class Account {
    static let codeNotVerified = "phone_not_verified"
    static let notVerifiedMessage = "Buyurtma berish uchun raqamingizni Telegram orqali tasdiqlang"
    static let verificationExpiredMessage = "Vaqt tugadi. Qaytadan urinib ko'ring"
    static let nameNotSentMessage = "Ism serverga yuborilmadi. Internet qaytgach o'zi qayta yuboriladi"

    /// Boshlangan, hali tugamagan tasdiqlash. Telefonda saqlanadi: profil ekranidan chiqilsa yoki ilova
    /// yopilib ochilsa ham natija olinadi.
    private(set) var pendingVerification: PendingVerification?
    /// Tasdiqlash natijasi: profil ekrani ko'rsatadi va `consumeVerificationOutcome()` bilan o'chiradi.
    private(set) var verificationOutcome: VerificationOutcome?

    private let api: ApiClient
    private let session: SessionStore
    @ObservationIgnored private var foreground = false
    // Har bir "so'rab turish" sikli o'z raqami bilan: yangisi boshlansa, eskisi to'xtaydi
    @ObservationIgnored private var pollGeneration = 0

    private static let verificationPollNanos: UInt64 = 2_000_000_000

    init(api: ApiClient, session: SessionStore) {
        self.api = api
        self.session = session
        if let stored = session.pendingVerification {
            if stored.expiresAt > Date() {
                pendingVerification = stored
            } else {
                session.pendingVerification = nil
            }
        }
    }

    // MARK: Ism

    /// Ismni o'zgartiradi (raqam faqat Telegram orqali almashadi). Telefonda darhol saqlanadi.
    /// Serverga yetib borsa nil, aks holda mijozga ko'rsatiladigan xabar qaytadi.
    func saveName(_ name: String) async -> String? {
        guard var profile = session.profile else { return nil }
        let previous = profile.name
        profile.name = name
        session.saveProfile(profile)
        guard let sent = session.token else { return nil }
        session.nameDirty = true
        do {
            _ = try await api.updateName(name)
            if session.token == sent, session.profile?.name == name {
                session.nameDirty = false
            }
            return nil
        } catch {
            guard let apiError = ApiError.from(error) else { return nil }
            guard session.token == sent else { return apiError.message }
            if let status = apiError.status, (400..<500).contains(status) {
                // Server bu ismni qabul qilmadi: telefonda ham avvalgisi qoladi
                session.nameDirty = false
                if var current = session.profile, current.name == name {
                    current.name = previous
                    session.saveProfile(current)
                }
                return apiError.message
            }
            // Internet yo'q yoki server vaqtincha ishlamayapti: ism telefonda qoladi va keyingi
            // `refresh()` da qayta yuboriladi (serverdagi eski ism uni bosib ketmaydi)
            return Account.nameNotSentMessage
        }
    }

    func refreshInBackground() {
        Task { [weak self] in
            await self?.refresh()
        }
    }

    /// Serverdagi profil bilan solishtiradi: boshqa telefonda ism o'zgargan bo'lishi yoki bu
    /// telefon hisobdan chiqarilgan bo'lishi mumkin (401: `ApiClient.onUnauthorized`).
    func refresh() async {
        guard let sent = session.token else { return }
        // Telefonda o'zgartirilgan ism serverga yetmagan bo'lsa, avval u yuboriladi
        let unsentName: String? = session.nameDirty ? session.profile?.name : nil
        do {
            let customer: Customer
            if let unsentName, !unsentName.isEmpty {
                customer = try await api.updateName(unsentName)
                if session.token == sent, session.profile?.name == unsentName {
                    session.nameDirty = false
                }
            } else {
                customer = try await api.me()
            }
            // Javob kelguncha raqam tasdiqlanib, yangi kalit va profil saqlangan bo'lishi mumkin
            if session.token != sent { return }
            var profile = Profile(name: customer.name, phone: customer.phone, verified: customer.phoneVerified)
            // Javob kelguncha ism yana o'zgartirilgan: telefondagisi qoladi
            if session.nameDirty, let local = session.profile?.name {
                profile.name = local
            }
            session.saveProfile(profile)
        } catch {
            guard unsentName != nil, session.token == sent, let apiError = error as? ApiError,
                  let status = apiError.status, (400..<500).contains(status) else { return }
            // Server bu ismni qabul qilmadi: keyingi safar serverdagi ism olinadi
            session.nameDirty = false
        }
    }

    // MARK: Telegram orqali tasdiqlash

    /// Serverdan kod oladi va natijani so'rab turishni boshlaydi.
    @discardableResult
    func startVerification(name: String?) async throws -> TelegramStart {
        let started = try await api.startTelegramVerification(name: name)
        let pending = PendingVerification(
            code: started.code,
            expiresAt: Date().addingTimeInterval(TimeInterval(max(started.expiresIn, 0))),
            appUrl: started.appUrl,
            botUrl: started.botUrl
        )
        verificationOutcome = nil
        setPending(pending)
        startVerificationPolling()
        return started
    }

    /// Mijoz "Bekor qilish"ni bosdi. Shu paytda ketayotgan tekshiruv javobi endi hisobga olinmaydi.
    func cancelVerification() {
        pollGeneration += 1
        setPending(nil)
    }

    func consumeVerificationOutcome() {
        verificationOutcome = nil
    }

    /// Ilova ekranga chiqdi: tugallanmagan tasdiqlash bo'lsa, natija darhol va muddati tugaguncha
    /// so'rab turiladi (mijoz Telegram'dan qaytdi yoki ilova yopilib ochildi).
    func onForeground() {
        foreground = true
        startVerificationPolling()
    }

    func onBackground() {
        foreground = false
    }

    private func setPending(_ pending: PendingVerification?) {
        pendingVerification = pending
        session.pendingVerification = pending
    }

    private func startVerificationPolling() {
        guard foreground, pendingVerification != nil else { return }
        pollGeneration += 1
        let generation = pollGeneration
        Task { [weak self] in
            while let self, self.pollGeneration == generation, self.foreground {
                if await self.checkPendingVerification() {
                    return
                }
                try? await Task.sleep(nanoseconds: Account.verificationPollNanos)
            }
        }
    }

    /// Natijani bir marta so'raydi. Kutish tugagan bo'lsa (tasdiqlandi, eskirdi, bekor qilindi) true.
    private func checkPendingVerification() async -> Bool {
        guard let pending = pendingVerification else { return true }
        if Date() >= pending.expiresAt {
            setPending(nil)
            verificationOutcome = .expired
            return true
        }
        do {
            let result = try await api.checkTelegramVerification(code: pending.code)
            // Javob kelguncha mijoz bekor qilgan yoki yangi kod olgan bo'lishi mumkin: eski kodning
            // javobi hisobga kirmaydi (kirish bajarilmaydi)
            guard pendingVerification?.code == pending.code else {
                return pendingVerification == nil
            }
            guard result.status == "verified", let token = result.token, let customer = result.customer else {
                return false
            }
            setPending(nil)
            session.nameDirty = false
            session.saveProfile(Profile(name: customer.name, phone: customer.phone, verified: customer.phoneVerified))
            session.saveToken(token)
            verificationOutcome = .verified
            return true
        } catch {
            guard let apiError = ApiError.from(error) else { return true }
            if apiError.isNetwork {
                return false // internet qaytgach yana so'raladi
            }
            guard pendingVerification?.code == pending.code else {
                return pendingVerification == nil
            }
            if let status = apiError.status, !(400..<500).contains(status) {
                return false // server vaqtincha ishlamayapti: kod hali yaroqli
            }
            setPending(nil)
            verificationOutcome = .failed(apiError.message)
            return true
        }
    }

    // MARK: Chiqish va hisobni o'chirish

    /// Hisobdan chiqish: server kalitni bekor qiladi, telefondan kalit va profil o'chadi.
    /// Internet bo'lmasa ham telefonda chiqiladi.
    func signOut() async {
        if session.token != nil {
            try? await api.logout()
        }
        cancelVerification()
        verificationOutcome = nil
        session.clearAccount()
    }

    /// Hisobni butunlay o'chiradi. Tugallanmagan buyurtma bo'lsa server rad etadi (409
    /// `has_active_orders`): xato o'zbekcha xabari bilan chiqadi va telefonda hech narsa o'zgarmaydi.
    func deleteAccount() async throws {
        try await api.deleteAccount()
        cancelVerification()
        verificationOutcome = nil
        session.clearAccount()
    }

    // MARK: Kirish kaliti kerak bo'lgan so'rovlar

    /// Kirish kaliti kerak bo'lgan so'rovni bajaradi. Raqam tasdiqlanmagan yoki server kalitni
    /// tanimasa, mijozga raqamni tasdiqlashni aytadigan xato chiqadi.
    func withAuth<T>(_ block: () async throws -> T) async throws -> T {
        guard session.token != nil, session.profile?.verified == true else {
            throw ApiError(status: 403, code: Account.codeNotVerified, message: Account.notVerifiedMessage)
        }
        do {
            return try await block()
        } catch let apiError as ApiError {
            if apiError.isUnauthorized {
                // Hisobdan chiqarish `ApiClient.onUnauthorized` da bajarilgan
                throw ApiError(status: 401, code: Account.codeNotVerified, message: Account.notVerifiedMessage)
            }
            if apiError.code == Account.codeNotVerified {
                session.signOut()
            }
            throw apiError
        }
    }
}
