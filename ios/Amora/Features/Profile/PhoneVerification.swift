/// Telegram phone verification (port of android ui/profile/PhoneVerification.kt).
///
/// Surface:
/// - `enum PhoneVerifyStep { case idle, starting, waiting, done }`           (Kotlin `VerifyStep`)
/// - `@MainActor @Observable final class PhoneVerificationModel`             (Kotlin `PhoneVerificationViewModel`)
/// - `struct PhoneVerificationSection: View`
///     `PhoneVerificationSection(profile: Profile?, name: String, toast: ToastCenter, onVerified: @escaping () -> Void)`
///   Needs `AppContainer` in the environment. `name`: the cleaned name the customer typed
///   (a new account is created with it).

import Observation
import SwiftUI
import UIKit

/// Tasdiqlash bosqichi.
enum PhoneVerifyStep: Equatable {
    case idle
    case starting
    case waiting
    case done
}

/// Raqamni Telegram orqali tasdiqlash: serverdan kod olinadi, bot ochiladi, mijoz u yerda
/// "📱 Raqamni yuborish" ni bosadi. Ilova shu orada natijani bir necha soniyada bir so'rab turadi
/// va mijoz ilovaga qaytganda darhol tekshiradi.
@MainActor
@Observable
final class PhoneVerificationModel {
    private(set) var step: PhoneVerifyStep = .idle
    private(set) var appUrl: String?
    private(set) var botUrl: String?
    private(set) var error: String?
    // Telegram ochilishi kerak (bir martalik hodisa: ochilgach telegramOpened() bilan o'chadi)
    private(set) var pendingOpen = false

    @ObservationIgnored private var account: Account?
    @ObservationIgnored private var code: String?
    @ObservationIgnored private var pollTask: Task<Void, Never>?
    // Bir vaqtda faqat bitta tekshiruv so'rovi (Kotlin Mutex o'rnida)
    @ObservationIgnored private var checking = false

    private static let pollNanos: UInt64 = 2_000_000_000

    init() {}

    func start(name: String?, account: Account) {
        if step == .starting || step == .waiting {
            return
        }
        self.account = account
        step = .starting
        error = nil
        let sentName: String?
        if let name, !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            sentName = name
        } else {
            sentName = nil
        }
        Task { [weak self] in
            do {
                let started = try await account.startVerification(name: sentName)
                guard let self else { return }
                self.code = started.code
                self.appUrl = started.appUrl
                self.botUrl = started.botUrl
                self.step = .waiting
                self.pendingOpen = true
                self.poll(expiresInSeconds: started.expiresIn)
            } catch {
                guard let self else { return }
                self.step = .idle
                if let apiError = ApiError.from(error) {
                    self.error = apiError.message
                }
            }
        }
    }

    private func poll(expiresInSeconds: Int) {
        pollTask?.cancel()
        let deadline = Date().addingTimeInterval(TimeInterval(max(expiresInSeconds, 0)))
        pollTask = Task { [weak self] in
            while !Task.isCancelled && Date() < deadline {
                try? await Task.sleep(nanoseconds: PhoneVerificationModel.pollNanos)
                if Task.isCancelled {
                    return
                }
                guard let self else { return }
                if await self.checkOnce() {
                    return
                }
            }
            if Task.isCancelled {
                return
            }
            guard let self else { return }
            if self.step == .waiting {
                self.step = .idle
                self.error = "Vaqt tugadi. Qaytadan urinib ko'ring"
            }
        }
    }

    /// Natijani bir marta so'raydi. Kutish tugagan bo'lsa (tasdiqlandi yoki eskirdi) true.
    private func checkOnce() async -> Bool {
        guard step == .waiting, let current = code, let account else {
            return true
        }
        if checking {
            // Boshqa tekshiruv hozir ketmoqda: uning natijasini kutamiz
            return false
        }
        checking = true
        defer { checking = false }
        do {
            let result = try await account.checkVerification(code: current)
            switch result {
            case .verified:
                step = .done
                error = nil
                return true
            case .pending:
                return false
            }
        } catch {
            guard let apiError = ApiError.from(error) else {
                // So'rov bekor qilindi (mijoz "Bekor qilish"ni bosdi yoki ekran yopildi)
                return true
            }
            if apiError.isNetwork {
                return false // internet qaytgach yana so'raladi
            }
            step = .idle
            self.error = apiError.message
            return true
        }
    }

    /// Mijoz Telegram'dan qaytdi: kutmasdan tekshiramiz.
    func checkNow() {
        if step != .waiting {
            return
        }
        Task { [weak self] in
            guard let self else { return }
            if await self.checkOnce() {
                self.pollTask?.cancel()
            }
        }
    }

    func reopenTelegram() {
        pendingOpen = true
    }

    func telegramOpened() {
        pendingOpen = false
    }

    func cancel() {
        pollTask?.cancel()
        pollTask = nil
        code = nil
        step = .idle
        pendingOpen = false
    }

    func clearError() {
        error = nil
    }

    func consumeDone() {
        step = .idle
    }
}

/// Profil ekranidagi raqam bo'limi: tasdiqlangan raqam yoki "Telegram orqali tasdiqlash" tugmasi.
/// `name`: mijoz yozgan ism (yangi hisob shu ism bilan ochiladi).
struct PhoneVerificationSection: View {
    let profile: Profile?
    let name: String
    let toast: ToastCenter
    let onVerified: () -> Void

    @Environment(AppContainer.self) private var container
    @Environment(\.amoraColors) private var colors
    @Environment(\.scenePhase) private var scenePhase
    @State private var vm = PhoneVerificationModel()

    init(profile: Profile?, name: String, toast: ToastCenter, onVerified: @escaping () -> Void) {
        self.profile = profile
        self.name = name
        self.toast = toast
        self.onVerified = onVerified
    }

    var body: some View {
        content
            .onChange(of: vm.pendingOpen) { _, pending in
                if pending {
                    // Avval o'chiramiz: ekran qayta chizilsa Telegram ikkinchi marta ochilmaydi
                    vm.telegramOpened()
                    openTelegram(appUrl: vm.appUrl, botUrl: vm.botUrl)
                }
            }
            .onChange(of: vm.error) { _, message in
                if let message {
                    toast.show(message)
                    vm.clearError()
                }
            }
            .onChange(of: vm.step) { _, step in
                if step == .done {
                    vm.consumeDone()
                    onVerified()
                }
            }
            // Telegram'dan qaytganda natija darhol tekshiriladi
            .onChange(of: scenePhase) { _, phase in
                if phase == .active {
                    vm.checkNow()
                }
            }
            .onAppear {
                vm.checkNow()
            }
    }

    @ViewBuilder
    private var content: some View {
        if vm.step == .waiting {
            waitingCard
        } else if let profile, profile.verified {
            verifiedCard(profile)
        } else {
            unverifiedCard
        }
    }

    private var waitingCard: some View {
        SectionCard {
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 0) {
                    VerifySpinner()
                    Spacer().frame(width: 14)
                    Text("Telegram'da «📱 Raqamni yuborish» tugmasini bosing, so'ng shu yerga qayting")
                        .amoraText(.bodyMedium)
                        .foregroundColor(colors.onSurface)
                        .fixedSize(horizontal: false, vertical: true)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                HStack(spacing: 10) {
                    SoftButton(
                        text: "Telegramni ochish",
                        onClick: { vm.reopenTelegram() },
                        icon: .send,
                        accent: true
                    )
                    SoftButton(text: "Bekor qilish", onClick: { vm.cancel() })
                }
            }
        }
    }

    private func verifiedCard(_ profile: Profile) -> some View {
        SectionCard {
            HStack(spacing: 0) {
                IconTile(icon: .check, container: colors.successContainer, tint: colors.success)
                Spacer().frame(width: 14)
                VStack(alignment: .leading, spacing: 0) {
                    Text(formatPhone(profile.phone))
                        .amoraText(.titleMedium)
                        .foregroundColor(colors.onSurface)
                        .lineLimit(1)
                        .minimumScaleFactor(0.85)
                    Text("Telegram orqali tasdiqlangan")
                        .amoraText(.bodySmall)
                        .foregroundColor(colors.success)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                Spacer().frame(width: 10)
                // SoftButton o'zi butun kenglikni egallaydi: qatorda raqamga joy qolishi uchun eni belgilanadi
                SoftButton(
                    text: "Almashtirish",
                    onClick: { vm.start(name: name, account: container.account) },
                    enabled: vm.step == .idle
                )
                .frame(width: 136)
            }
        }
    }

    private var unverifiedCard: some View {
        SectionCard {
            VStack(alignment: .leading, spacing: 12) {
                Text(
                    "Raqamingizni Telegram orqali tasdiqlang: kuryer shu raqamga qo'ng'iroq qiladi. " +
                        "Boshqa telefondan kirsangiz ham buyurtmalaringiz saqlanib qoladi."
                )
                .amoraText(.bodyMedium)
                .foregroundColor(colors.onSurfaceVariant)
                .fixedSize(horizontal: false, vertical: true)
                .frame(maxWidth: .infinity, alignment: .leading)
                BigButton(
                    text: "Telegram orqali tasdiqlash",
                    onClick: { vm.start(name: name, account: container.account) },
                    enabled: !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
                    loading: vm.step == .starting
                )
            }
        }
    }

    /// Telegram ilovasini bot bilan ochadi; o'rnatilmagan bo'lsa brauzerda t.me sahifasini.
    private func openTelegram(appUrl: String?, botUrl: String?) {
        let urls = [appUrl, botUrl].compactMap { $0 }.compactMap { URL(string: $0) }
        let toast = self.toast
        Task { @MainActor in
            for url in urls {
                let scheme = url.scheme?.lowercased() ?? ""
                let isWeb = scheme == "https" || scheme == "http"
                // tg:// faqat Telegram o'rnatilgan bo'lsa ochiladi (LSApplicationQueriesSchemes: tg)
                if !isWeb && !UIApplication.shared.canOpenURL(url) {
                    continue
                }
                let opened = await UIApplication.shared.open(url, options: [:])
                if opened {
                    return
                }
                // keyingi havolani sinaymiz
            }
            toast.show("Telegram topilmadi. Uni o'rnatib, qaytadan urinib ko'ring")
        }
    }
}

/// Kutish paytidagi aylanuvchi halqa (Material CircularProgressIndicator, 26 pt, chiziq 3).
private struct VerifySpinner: View {
    @Environment(\.amoraColors) private var colors

    init() {}

    var body: some View {
        TimelineView(.animation) { context in
            let seconds = context.date.timeIntervalSinceReferenceDate
            let angle = seconds.truncatingRemainder(dividingBy: 1.1) / 1.1 * 360
            Circle()
                .trim(from: 0, to: 0.72)
                .stroke(colors.primary, style: StrokeStyle(lineWidth: 3, lineCap: .round))
                .rotationEffect(.degrees(angle))
                .padding(1.5)
        }
        .frame(width: 26, height: 26)
        .accessibilityHidden(true)
    }
}
