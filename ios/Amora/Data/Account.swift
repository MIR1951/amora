/// Account and Telegram phone verification (port of `Account` in android data/Stores.kt).
///
/// Surface:
/// - `enum VerificationResult: Equatable { case pending; case verified(Profile) }`
/// - `@MainActor final class Account`
///   - `init(api: ApiClient, session: SessionStore)`
///   - `static let codeNotVerified = "phone_not_verified"`
///   - `static let notVerifiedMessage = "Buyurtma berish uchun raqamingizni Telegram orqali tasdiqlang"`
///   - `func saveName(_ name: String)`                       // local save + PATCH /me in background
///   - `func refreshInBackground()`
///   - `func refresh() async`                                // sync profile with GET /me, 401 -> signOut
///   - `func startVerification(name: String?) async throws -> TelegramStart`
///   - `func checkVerification(code: String) async throws -> VerificationResult`
///   - `func withAuth<T>(_ block: () async throws -> T) async throws -> T`
///     (throws ApiError(code: "phone_not_verified") when not verified / token rejected)

import Foundation

/// Telegram orqali tasdiqlash natijasi.
enum VerificationResult: Equatable {
    case pending
    case verified(Profile)
}

/// Hisob va profil. Mijoz raqamini Telegram orqali tasdiqlaydi: ilova botni ochadi, mijoz u yerda
/// "📱 Raqamni yuborish" ni bosadi, ilova natijani so'rab turadi.
@MainActor
final class Account {
    static let codeNotVerified = "phone_not_verified"
    static let notVerifiedMessage = "Buyurtma berish uchun raqamingizni Telegram orqali tasdiqlang"

    private let api: ApiClient
    private let session: SessionStore

    init(api: ApiClient, session: SessionStore) {
        self.api = api
        self.session = session
    }

    /// Ismni o'zgartiradi (raqam faqat Telegram orqali almashadi).
    func saveName(_ name: String) {
        guard var profile = session.profile else { return }
        profile.name = name
        session.saveProfile(profile)
        guard let sent = session.token else { return }
        Task { [weak self] in
            guard let self else { return }
            do {
                _ = try await self.api.updateName(name)
            } catch {
                // Muhim emas: ism har bir buyurtma bilan birga ham yuboriladi. Shu orada yangi
                // kalit olingan bo'lsa, eski kalitning xatosi uni o'chirmaydi
                if let apiError = error as? ApiError, apiError.isUnauthorized, self.session.token == sent {
                    self.session.signOut()
                }
            }
        }
    }

    func refreshInBackground() {
        Task { [weak self] in
            await self?.refresh()
        }
    }

    func startVerification(name: String?) async throws -> TelegramStart {
        try await api.startTelegramVerification(name: name)
    }

    /// Mijoz botda raqamini yubordimi. Yuborgan bo'lsa, kalit va profil saqlanadi.
    func checkVerification(code: String) async throws -> VerificationResult {
        let result = try await api.checkTelegramVerification(code: code)
        guard result.status == "verified", let token = result.token, let customer = result.customer else {
            return .pending
        }
        let profile = Profile(name: customer.name, phone: customer.phone, verified: customer.phoneVerified)
        session.saveProfile(profile)
        session.saveToken(token)
        return .verified(profile)
    }

    /// Serverdagi profil bilan solishtiradi: boshqa telefonda ism o'zgargan bo'lishi yoki bu
    /// telefon hisobdan chiqarilgan bo'lishi mumkin.
    func refresh() async {
        guard let sent = session.token else { return }
        do {
            let customer = try await api.me()
            // Javob kelguncha raqam tasdiqlanib, yangi kalit va profil saqlangan bo'lishi mumkin
            if session.token != sent { return }
            session.saveProfile(Profile(name: customer.name, phone: customer.phone, verified: customer.phoneVerified))
        } catch {
            if let apiError = error as? ApiError, apiError.isUnauthorized, session.token == sent {
                session.signOut()
            }
        }
    }

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
                session.signOut()
                throw ApiError(status: 401, code: Account.codeNotVerified, message: Account.notVerifiedMessage)
            }
            if apiError.code == Account.codeNotVerified {
                session.signOut()
            }
            throw apiError
        }
    }
}
