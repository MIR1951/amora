/// Profile screen (port of android ui/profile/ProfileScreen.kt).
///
/// Surface:
/// - `struct ProfileScreen: View` - `ProfileScreen(quickEdit: Bool)`
///   `quickEdit == false` (Route.profile): header, name, phone verification, delivery address, cafe phone,
///   notifications, sign out / delete account (signed-in customers only, each behind a confirmation dialog),
///   version. `quickEdit == true` (Route.profileEdit, from the cart): only name + phone,
///   bottom "Saqlash", goes back by itself once the phone is verified.

import SwiftUI
import UIKit

private let profileMaxNameLength = 60

/// Mijozning ismi va telefoni. Kuryer shu raqamga qo'ng'iroq qiladi. Raqam qo'lda yozilmaydi:
/// u Telegram orqali tasdiqlanadi (soxta yoki birovning raqamini yozib bo'lmaydi).
///
/// Ikki xil ochiladi: bosh sahifadagi "Profil" tugmasidan (manzil va kafe telefoni ham ko'rinadi)
/// yoki savatdan (`quickEdit`: ism va raqam, tasdiqlangach orqaga qaytadi).
struct ProfileScreen: View {
    let quickEdit: Bool

    @Environment(AppContainer.self) private var container
    @Environment(Router.self) private var router
    @Environment(\.amoraColors) private var colors
    @State private var toast = ToastCenter()
    @State private var name = ""
    @State private var nameLoaded = false
    @State private var savingName = false
    @State private var confirmSignOut = false
    @State private var confirmDelete = false
    // Chiqish yoki o'chirish so'rovi ketmoqda
    @State private var accountBusy = false
    @FocusState private var nameFocused: Bool

    init(quickEdit: Bool = false) {
        self.quickEdit = quickEdit
    }

    // MARK: - Holat

    private var cleanName: String {
        name.split(whereSeparator: { $0.isWhitespace }).joined(separator: " ")
    }

    private var verified: Bool {
        container.session.profile?.verified == true
    }

    /// Ism faqat tasdiqlangan hisobda alohida saqlanadi; yangi mijozning ismi tasdiqlash bilan ketadi.
    private var canSaveName: Bool {
        let clean = cleanName
        return verified && !clean.isEmpty && clean != container.session.profile?.name
    }

    private var nameBinding: Binding<String> {
        Binding(
            get: { name },
            set: { name = limitText($0, profileMaxNameLength) }
        )
    }

    private func save() {
        guard canSaveName, !savingName else { return }
        let account = container.account
        let clean = cleanName
        let toast = self.toast
        nameFocused = false
        if quickEdit {
            // Savatdan ochilgan: kutmasdan qaytamiz. Ism buyurtma bilan birga ham yuboriladi, serverga
            // yetmagan bo'lsa keyinroq o'zi qayta yuboriladi (`Account.refresh`)
            Task {
                _ = await account.saveName(clean)
            }
            router.back()
            return
        }
        savingName = true
        Task {
            // "Saqlandi" faqat server qabul qilgach aytiladi; aks holda nima bo'lgani ko'rsatiladi
            let problem = await account.saveName(clean)
            savingName = false
            toast.show(problem ?? "Saqlandi")
        }
    }

    /// Hisobga kirilgan (kirish kaliti bor): chiqish va hisobni o'chirish shundagina ko'rinadi.
    private var signedIn: Bool {
        container.session.token != nil
    }

    private func signOut() {
        if accountBusy { return }
        accountBusy = true
        nameFocused = false
        let container = self.container
        let toast = self.toast
        Task {
            await container.signOut()
            accountBusy = false
            toast.show("Hisobdan chiqdingiz")
        }
    }

    private func deleteAccount() {
        if accountBusy { return }
        accountBusy = true
        nameFocused = false
        let container = self.container
        let toast = self.toast
        Task {
            do {
                try await container.deleteAccount()
                accountBusy = false
                toast.show("Hisobingiz o'chirildi")
            } catch {
                accountBusy = false
                // Masalan, tugallanmagan buyurtma bor (409 has_active_orders): server xabari o'zicha ko'rsatiladi
                if let apiError = ApiError.from(error) {
                    toast.show(apiError.message)
                }
            }
        }
    }

    private func onVerified() {
        nameFocused = false
        if quickEdit {
            router.back()
        } else {
            toast.show("Raqam tasdiqlandi")
        }
    }

    // MARK: - Ekran

    var body: some View {
        let canSave = canSaveName
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                if quickEdit {
                    Text("Buyurtmani yetkazishda kuryer shu ism va raqam orqali siz bilan bog'lanadi.")
                        .amoraText(.bodyMedium)
                        .foregroundColor(colors.onSurfaceVariant)
                        .fixedSize(horizontal: false, vertical: true)
                        .padding(.horizontal, 4)
                } else {
                    ProfileHeaderCard(profile: container.session.profile)
                    SectionLabel("Shaxsiy ma'lumotlar")
                }

                nameField

                PhoneVerificationSection(
                    profile: container.session.profile,
                    name: cleanName,
                    toast: toast,
                    onVerified: { onVerified() }
                )

                if !quickEdit {
                    // Tugma faqat biror narsa o'zgarganda chiqadi: o'zgarish bo'lmasa saqlaydigan narsa yo'q
                    if canSave || savingName {
                        BigButton(text: "Saqlash", onClick: { save() }, loading: savingName)
                            .transition(.opacity)
                    }

                    SectionLabel("Yetkazish va aloqa")
                    linksCard

                    if signedIn {
                        SectionLabel("Hisob")
                        accountButtons
                    }

                    Text(versionText)
                        .amoraText(.bodySmall)
                        .foregroundColor(colors.hint)
                        .multilineTextAlignment(.center)
                        .frame(maxWidth: .infinity)
                        .padding(.top, 8)
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 20)
            .animation(.easeInOut(duration: 0.25), value: canSave)
        }
        .scrollDismissesKeyboard(.interactively)
        .toastHost(toast)
        .safeAreaInset(edge: .top, spacing: 0) {
            GlassTopBar(title: quickEdit ? "Ma'lumotlarim" : "Profil", onBack: { router.back() })
        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            if quickEdit && verified {
                BottomDock {
                    BigButton(text: "Saqlash", onClick: { save() }, enabled: canSave)
                }
            }
        }
        .background(colors.background.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
        .confirmDialog(
            isPresented: $confirmSignOut,
            title: "Hisobdan chiqasizmi?",
            text: "Buyurtma berish uchun raqamingizni Telegram orqali qayta tasdiqlashingiz kerak bo'ladi.",
            confirmLabel: "Chiqish",
            dismissLabel: "Bekor qilish",
            onConfirm: { signOut() }
        )
        .confirmDialog(
            isPresented: $confirmDelete,
            title: "Hisobni o'chirasizmi?",
            text: "Hisobingiz va shaxsiy ma'lumotlaringiz (ism, telefon raqam, manzil) o'chiriladi. "
                + "Bu amalni ortga qaytarib bo'lmaydi.",
            confirmLabel: "O'chirish",
            dismissLabel: "Bekor qilish",
            onConfirm: { deleteAccount() }
        )
        // Saqlangan profil o'zgarsa (masalan, boshqa telefonda ism o'zgargan bo'lsa), maydon ham yangilanadi
        // Ekran qayta ko'ringanda (masalan, xaritadan qaytganda) yozilayotgan ism o'chib ketmasin:
        // maydon faqat birinchi marta va saqlangan ism haqiqatan o'zgarganda to'ldiriladi
        .onAppear {
            if !nameLoaded {
                nameLoaded = true
                name = container.session.profile?.name ?? ""
            }
        }
        .onChange(of: container.session.profile?.name) { _, newName in
            name = newName ?? ""
        }
        .task {
            await container.notifications.refreshEnabled()
        }
    }

    // MARK: - Ism maydoni

    /// Material TextField: "Ismingiz" yozuvi maydon ichida, yozila boshlaganda tepaga ko'tariladi.
    private var nameField: some View {
        let floating = nameFocused || !name.isEmpty
        let shape = RoundedRectangle(cornerRadius: 18, style: .continuous)
        return ZStack(alignment: .topLeading) {
            Text("Ismingiz")
                .font(floating ? AmoraFont.body(12) : AmoraTextStyle.bodyLarge.font)
                .foregroundColor(nameFocused ? colors.primary : colors.hint)
                .lineLimit(1)
                .padding(.top, floating ? 8 : 18)
                .allowsHitTesting(false)
                .accessibilityHidden(true)
            TextField("", text: nameBinding)
                .font(AmoraTextStyle.bodyLarge.font)
                .foregroundColor(colors.onSurface)
                .tint(colors.primary)
                .textInputAutocapitalization(.words)
                .submitLabel(.done)
                .focused($nameFocused)
                .onSubmit { save() }
                .padding(.top, 25)
                .padding(.bottom, 9)
                .accessibilityLabel("Ismingiz")
        }
        .padding(.horizontal, 16)
        .frame(maxWidth: .infinity, minHeight: 56, alignment: .topLeading)
        .background(shape.fill(colors.surface))
        .overlay(shape.strokeBorder(colors.outlineVariant, lineWidth: 1))
        .contentShape(shape)
        .onTapGesture {
            nameFocused = true
        }
        .animation(.easeOut(duration: 0.15), value: floating)
    }

    // MARK: - Yetkazish va aloqa

    private var addressValue: String {
        guard let address = container.session.address else {
            return "Xaritadan tanlang"
        }
        if address.note.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return "Xaritada belgilangan joy"
        }
        return address.note
    }

    private var cafePhone: String? {
        guard let phone = container.catalog.shop?.phone,
              !phone.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return nil
        }
        return phone
    }

    private var linksCard: some View {
        let notificationsOn = container.notifications.enabled
        return SectionCard(padding: 0) {
            LinkRow(
                icon: .pin,
                label: "Yetkazish manzili",
                value: addressValue,
                onClick: { router.open(.address) },
                highlighted: container.session.address == nil
            )
            if let phone = cafePhone {
                RowDivider()
                LinkRow(
                    icon: .phone,
                    label: "Kafe bilan bog'lanish",
                    value: formatPhone(phone),
                    onClick: { profileDialPhone(phone) },
                    tileContainer: colors.successContainer,
                    tileTint: colors.success
                )
            }
            // Buyurtma holati haqidagi xabarlar: o'chiq bo'lsa, shu yerdan yoqiladi
            RowDivider()
            LinkRow(
                icon: .bell,
                label: "Bildirishnomalar",
                value: notificationsOn ? "Yoqilgan" : "O'chirilgan. Yoqish uchun bosing",
                onClick: { toggleNotifications() },
                highlighted: !notificationsOn,
                tileContainer: colors.infoContainer,
                tileTint: colors.info
            )
        }
    }

    // MARK: - Hisob

    /// Hisobdan chiqish va hisobni o'chirish (App Store talabi: hisob ochiladigan ilovada uni
    /// o'chirish ham mumkin bo'lishi kerak). Har biri tasdiqlash oynasidan keyin bajariladi.
    private var accountButtons: some View {
        VStack(spacing: 10) {
            SoftButton(
                text: "Chiqish",
                onClick: {
                    nameFocused = false
                    confirmSignOut = true
                },
                enabled: !accountBusy
            )
            SoftButton(
                text: accountBusy ? "Kutib turing…" : "Hisobni o'chirish",
                onClick: {
                    nameFocused = false
                    confirmDelete = true
                },
                enabled: !accountBusy,
                danger: true
            )
        }
    }

    /// Hali so'ralmagan bo'lsa tizim oynasi chiqadi, aks holda telefon sozlamalaridagi shu ilova sahifasi.
    private func toggleNotifications() {
        let notifications = container.notifications
        Task {
            await notifications.toggle()
        }
    }

    private var versionText: String {
        let info = Bundle.main.infoDictionary
        let version = info?["CFBundleShortVersionString"] as? String ?? ""
        let build = info?["CFBundleVersion"] as? String ?? ""
        return "Amora · \(version) (\(build))"
    }
}

/// Profil boshidagi kartochka: ismning bosh harfi, ism va telefon.
private struct ProfileHeaderCard: View {
    let profile: Profile?
    @Environment(\.amoraColors) private var colors

    init(profile: Profile?) {
        self.profile = profile
    }

    var body: some View {
        SectionCard {
            HStack(spacing: 0) {
                ZStack {
                    RoundedRectangle(cornerRadius: 19, style: .continuous)
                        .fill(colors.ink)
                    if let profile {
                        Text(String(profile.name.prefix(1)).uppercased())
                            .amoraText(.headlineMedium)
                            .foregroundColor(.white)
                    } else {
                        IconImage(.user, size: 26, tint: .white)
                    }
                }
                .frame(width: 58, height: 58)
                .accessibilityHidden(true)
                Spacer().frame(width: 14)
                VStack(alignment: .leading, spacing: 0) {
                    Text(profile?.name ?? "Xush kelibsiz!")
                        .amoraText(.titleLarge)
                        .foregroundColor(colors.onSurface)
                        .lineLimit(1)
                        .truncationMode(.tail)
                    Text(subtitle)
                        .amoraText(.bodyMedium)
                        .foregroundColor(colors.onSurfaceVariant)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }

    private var subtitle: String {
        guard let profile else {
            return "Buyurtma berish uchun ismingizni yozing va raqamingizni tasdiqlang"
        }
        if !profile.verified {
            return "Raqamingizni Telegram orqali tasdiqlang"
        }
        return formatPhone(profile.phone)
    }
}

/// Telefon ilovasini raqam terilgan holda ochadi (qo'ng'iroqni mijoz o'zi tasdiqlaydi).
@MainActor
private func profileDialPhone(_ phone: String) {
    let digits = phone.filter { ($0.isASCII && $0.isNumber) || $0 == "+" }
    guard !digits.isEmpty, let url = URL(string: "tel:\(digits)") else { return }
    // Qo'ng'iroq ilovasi yo'q qurilma (masalan iPad): hech narsa qilmaymiz
    UIApplication.shared.open(url, options: [:], completionHandler: nil)
}
