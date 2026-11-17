/// Loading / empty / error states, pull-to-refresh and the confirm dialog
/// (port of LoadingBox, MessageBox, RefreshBox, ConfirmDialog from android ui/components/Components.kt).
///
/// Surface:
/// - `LoadingBox()`                                                  // centered spinner, fills the space
/// - `MessageBox(icon: AppIcon, title: String, text: String? = nil, actionLabel: String? = nil, onAction: (() -> Void)? = nil)`
///   fills the space, scrollable (so `.refreshable` on it works), content centered
/// - `View.amoraRefreshable(onRefresh: @escaping () -> Void, isRefreshing: @escaping () -> Bool)`
///   native pull-to-refresh for a ScrollView/List; the spinner stays until `isRefreshing()` is false
/// - `View.amoraRefreshable(action: @escaping () async -> Void)`     // same, for an async refresh
/// - `ConfirmDialog(title:text:confirmLabel:dismissLabel:onConfirm:onDismiss:)` view (centered card)
/// - `View.confirmDialog(isPresented: Binding<Bool>, title: String, text: String, confirmLabel: String,
///    dismissLabel: String, onConfirm: @escaping () -> Void, onDismiss: (() -> Void)? = nil)`
///   apply to the OUTERMOST view of a screen (after .safeAreaInset) so the dim/blur covers the bars.

import SwiftUI
import UIKit

// MARK: - Yuklanish, bo'sh holat, xato

/// Bor joyning o'rtasidagi aylanuvchi yuklanish belgisi.
struct LoadingBox: View {
    @Environment(\.amoraColors) private var colors

    init() {}

    var body: some View {
        ProgressView()
            .progressViewStyle(.circular)
            .tint(colors.primary)
            .controlSize(.large)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

/// Bo'sh holat yoki xato: katta belgi, sarlavha, izoh va ixtiyoriy tugma.
struct MessageBox: View {
    let icon: AppIcon
    let title: String
    var text: String? = nil
    var actionLabel: String? = nil
    var onAction: (() -> Void)? = nil
    @Environment(\.amoraColors) private var colors

    init(
        icon: AppIcon,
        title: String,
        text: String? = nil,
        actionLabel: String? = nil,
        onAction: (() -> Void)? = nil
    ) {
        self.icon = icon
        self.title = title
        self.text = text
        self.actionLabel = actionLabel
        self.onAction = onAction
    }

    var body: some View {
        GeometryReader { geo in
            ScrollView {
                VStack(spacing: 0) {
                    IconTile(icon: icon, size: 92, iconSize: 40)
                    Spacer().frame(height: 20)
                    Text(title)
                        .amoraText(.headlineSmall)
                        .foregroundColor(colors.onBackground)
                        .multilineTextAlignment(.center)
                    if let text {
                        Spacer().frame(height: 6)
                        Text(text)
                            .amoraText(.bodyLarge)
                            .foregroundColor(colors.onSurfaceVariant)
                            .multilineTextAlignment(.center)
                    }
                    if let actionLabel, let onAction {
                        Spacer().frame(height: 24)
                        PillButton(text: actionLabel, onClick: onAction)
                    }
                }
                .padding(32)
                .frame(maxWidth: .infinity)
                .frame(minHeight: geo.size.height)
            }
        }
    }
}

// MARK: - Pastga tortib yangilash

extension View {
    /// Pastga tortib yangilash (Android RefreshBox). `onRefresh` yangilashni boshlaydi; aylanuvchi belgi
    /// `isRefreshing()` false bo'lguncha (ko'pi bilan 30 s) turadi. ScrollView yoki List'ga qo'llanadi.
    func amoraRefreshable(onRefresh: @escaping () -> Void, isRefreshing: @escaping () -> Bool) -> some View {
        refreshable {
            await MainActor.run {
                onRefresh()
            }
            // Holat yangilanishiga ulgursin
            try? await Task.sleep(nanoseconds: 250_000_000)
            var waited = 0
            while waited < 300 {
                let busy = await MainActor.run { isRefreshing() }
                if !busy {
                    break
                }
                try? await Task.sleep(nanoseconds: 100_000_000)
                waited += 1
            }
        }
    }

    /// Pastga tortib yangilash: `action` tugaguncha aylanuvchi belgi turadi.
    func amoraRefreshable(action: @escaping () async -> Void) -> some View {
        refreshable {
            await action()
        }
    }
}

// MARK: - Tasdiqlash oynasi

/// Ha yoki yo'q deb so'raydigan oyna (kartochka). Odatda `.confirmDialog(isPresented:...)` orqali ko'rsatiladi.
struct ConfirmDialog: View {
    let title: String
    let text: String
    let confirmLabel: String
    let dismissLabel: String
    let onConfirm: () -> Void
    let onDismiss: () -> Void
    @Environment(\.amoraColors) private var colors

    init(
        title: String,
        text: String,
        confirmLabel: String,
        dismissLabel: String,
        onConfirm: @escaping () -> Void,
        onDismiss: @escaping () -> Void
    ) {
        self.title = title
        self.text = text
        self.confirmLabel = confirmLabel
        self.dismissLabel = dismissLabel
        self.onConfirm = onConfirm
        self.onDismiss = onDismiss
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(title)
                .amoraText(.titleLarge)
                .foregroundColor(colors.onSurface)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityAddTraits(.isHeader)
            Spacer().frame(height: 16)
            Text(text)
                .amoraText(.bodyLarge)
                .foregroundColor(colors.onSurfaceVariant)
                .fixedSize(horizontal: false, vertical: true)
            Spacer().frame(height: 24)
            HStack(spacing: 8) {
                Spacer(minLength: 0)
                Button(action: onDismiss) {
                    Text(dismissLabel)
                        .amoraText(.labelLarge)
                        .foregroundColor(colors.onSurfaceVariant)
                        .lineLimit(1)
                        .padding(.horizontal, 12)
                        .frame(minHeight: 40)
                        .contentShape(Rectangle())
                }
                .buttonStyle(PressScaleStyle(scale: 0.95))
                Button(action: onConfirm) {
                    Text(confirmLabel)
                        .amoraText(.labelLarge)
                        .foregroundColor(colors.onPrimary)
                        .lineLimit(1)
                        .padding(.horizontal, 24)
                        .frame(minHeight: 40)
                        .background(RoundedRectangle(cornerRadius: 14, style: .continuous).fill(colors.primary))
                        .contentShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                }
                .buttonStyle(PressScaleStyle(scale: 0.95))
            }
        }
        .padding(24)
        .frame(maxWidth: 340)
        .background(
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .fill(colors.surface)
                .shadow(color: AmoraColors.shadow.opacity(0.25), radius: 24, x: 0, y: 10)
        )
        .padding(.horizontal, 24)
        .accessibilityAddTraits(.isModal)
    }
}

/// `.confirmDialog(...)` ning ichki qismi: xiralashgan fon va o'rtadagi oyna.
struct ConfirmDialogModifier: ViewModifier {
    @Binding var isPresented: Bool
    let title: String
    let text: String
    let confirmLabel: String
    let dismissLabel: String
    let onConfirm: () -> Void
    let onDismiss: (() -> Void)?
    @Environment(\.amoraColors) private var colors

    init(
        isPresented: Binding<Bool>,
        title: String,
        text: String,
        confirmLabel: String,
        dismissLabel: String,
        onConfirm: @escaping () -> Void,
        onDismiss: (() -> Void)?
    ) {
        self._isPresented = isPresented
        self.title = title
        self.text = text
        self.confirmLabel = confirmLabel
        self.dismissLabel = dismissLabel
        self.onConfirm = onConfirm
        self.onDismiss = onDismiss
    }

    func body(content: Content) -> some View {
        content
            .accessibilityHidden(isPresented)
            .overlay {
                ZStack {
                    if isPresented {
                        // Ochilganda ortidagi ekran xiralashadi
                        ZStack {
                            Rectangle().fill(Material.ultraThinMaterial).opacity(0.85)
                            Color.black.opacity(colors.isDark ? 0.45 : 0.28)
                        }
                        .ignoresSafeArea()
                        .onTapGesture { dismiss() }
                        .transition(.opacity)
                        .accessibilityHidden(true)

                        ConfirmDialog(
                            title: title,
                            text: text,
                            confirmLabel: confirmLabel,
                            dismissLabel: dismissLabel,
                            onConfirm: { confirm() },
                            onDismiss: { dismiss() }
                        )
                        .transition(.scale(scale: 0.92).combined(with: .opacity))
                    }
                }
                .animation(.easeOut(duration: 0.2), value: isPresented)
            }
    }

    private func confirm() {
        isPresented = false
        onConfirm()
    }

    private func dismiss() {
        isPresented = false
        onDismiss?()
    }
}

extension View {
    /// Tasdiqlash oynasi (Android ConfirmDialog). Ekranning eng tashqi ko'rinishiga qo'llang.
    /// Tugma bosilganda oyna o'zi yopiladi (`isPresented = false`), keyin `onConfirm`/`onDismiss` chaqiriladi.
    func confirmDialog(
        isPresented: Binding<Bool>,
        title: String,
        text: String,
        confirmLabel: String,
        dismissLabel: String,
        onConfirm: @escaping () -> Void,
        onDismiss: (() -> Void)? = nil
    ) -> some View {
        modifier(
            ConfirmDialogModifier(
                isPresented: isPresented,
                title: title,
                text: text,
                confirmLabel: confirmLabel,
                dismissLabel: dismissLabel,
                onConfirm: onConfirm,
                onDismiss: onDismiss
            )
        )
    }
}
