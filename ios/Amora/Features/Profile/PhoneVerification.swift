/// Telegram phone verification (port of android ui/profile/PhoneVerification.kt).
///
/// Surface:
/// - `@MainActor @Observable final class PhoneVerificationModel`             (Kotlin `PhoneVerificationViewModel`)
/// - `struct PhoneVerificationSection: View`
///     `PhoneVerificationSection(profile: Profile?, name: String, toast: ToastCenter, onVerified: @escaping () -> Void)`
///   Needs `AppContainer` in the environment. `name`: the cleaned name the customer typed
///   (a new account is created with it).
///
/// The pending verification itself (code, expiry, result polling) lives in `Account`, not in this view:
/// it is persisted and checked whenever the app is in the foreground, so a verification that finishes
/// after the customer left this screen (or after the app was killed) is still picked up.

import Observation
import SwiftUI
import UIKit

/// Raqamni Telegram orqali tasdiqlash: serverdan kod olinadi, bot ochiladi, mijoz u yerda
/// "📱 Raqamni yuborish" ni bosadi. Natijani `Account` so'rab turadi (ilova ekranda turgan paytda va
/// mijoz ilovaga qaytishi bilan); bu yerda faqat shu ekranning o'z holati.
@MainActor
@Observable
final class PhoneVerificationModel {
    // Serverdan kod so'ralmoqda
    private(set) var starting = false
    private(set) var error: String?
    // Telegram ochilishi kerak (bir martalik hodisa: ochilgach telegramOpened() bilan o'chadi)
    private(set) var pendingOpen = false

    init() {}

    func start(name: String?, account: Account) {
        if starting || account.pendingVerification != nil {
            return
        }
        starting = true
        error = nil
        let sentName: String?
        if let name, !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            sentName = name
        } else {
            sentName = nil
        }
        Task { [weak self] in
            do {
                try await account.startVerification(name: sentName)
                guard let self else { return }
                self.starting = false
                self.pendingOpen = true
            } catch {
                guard let self else { return }
                self.starting = false
                if let apiError = ApiError.from(error) {
                    self.error = apiError.message
                }
            }
        }
    }

    func reopenTelegram() {
        pendingOpen = true
    }

    func telegramOpened() {
        pendingOpen = false
    }

    func clearError() {
        error = nil
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
    @State private var vm = PhoneVerificationModel()

    init(profile: Profile?, name: String, toast: ToastCenter, onVerified: @escaping () -> Void) {
        self.profile = profile
        self.name = name
        self.toast = toast
        self.onVerified = onVerified
    }

    /// Tasdiqlash boshlangan va natija kutilmoqda (ilova yopilib ochilgan bo'lsa ham).
    private var pending: PendingVerification? {
        container.account.pendingVerification
    }

    var body: some View {
        content
            .onChange(of: vm.pendingOpen) { _, open in
                if open {
                    // Avval o'chiramiz: ekran qayta chizilsa Telegram ikkinchi marta ochilmaydi
                    vm.telegramOpened()
                    openTelegram(appUrl: pending?.appUrl, botUrl: pending?.botUrl)
                }
            }
            .onChange(of: vm.error) { _, message in
                if let message {
                    toast.show(message)
                    vm.clearError()
                }
            }
            // Tasdiqlash tugadi (shu ekran ochiq paytda): natija bir marta ko'rsatiladi
            .onChange(of: container.account.verificationOutcome) { _, outcome in
                guard let outcome else { return }
                container.account.consumeVerificationOutcome()
                switch outcome {
                case .verified:
                    onVerified()
                case .expired:
                    toast.show(Account.verificationExpiredMessage)
                case .failed(let message):
                    toast.show(message)
                }
            }
            .onAppear {
                // Ekran yopiq paytda tugagan tasdiqlash natijasi profilning o'zida ko'rinadi:
                // eskirgan xabar keyinroq chiqib qolmasin
                container.account.consumeVerificationOutcome()
            }
    }

    @ViewBuilder
    private var content: some View {
        if pending != nil {
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
                    SoftButton(text: "Bekor qilish", onClick: { container.account.cancelVerification() })
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
                    enabled: !vm.starting
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
                    loading: vm.starting
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
