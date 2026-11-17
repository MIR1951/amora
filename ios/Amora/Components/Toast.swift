/// Toast / snackbar (Android `SnackbarHost` + `snackbar.showSnackbar(...)`): a short message at the
/// bottom of the screen that hides itself after a few seconds (tap hides it at once).
///
/// Two ways to use it:
///
/// 1. A ToastCenter object (like Android SnackbarHostState):
///        @State private var toast = ToastCenter()
///        ...
///        content
///            .toastHost(toast)                 // apply BEFORE .safeAreaInset(edge: .bottom) -> sits above the dock
///        toast.show("Telegram topilmadi. Uni o'rnatib, qaytadan urinib ko'ring")
///
/// 2. A String? binding (set it to show; it is set back to nil when the toast hides):
///        @State private var message: String?
///        content.toast(message: $message)
///
/// Surface:
/// - `struct ToastMessage: Identifiable, Equatable { let id: UUID; let text: String }`
/// - `@MainActor @Observable final class ToastCenter`
///     `init()`, `private(set) var current: ToastMessage?`,
///     `func show(_ text: String, duration: TimeInterval = ToastCenter.defaultDuration)`, `func dismiss()`
///     `static let defaultDuration: TimeInterval = 4`
/// - `struct ToastHost: View` - `ToastHost(center: ToastCenter, bottomPadding: CGFloat = 12)` (bottom-aligned overlay)
/// - `struct ToastView: View` - `ToastView(text: String, onTap: (() -> Void)? = nil)` (the dark pill itself)
/// - `View.toastHost(_ center: ToastCenter, bottomPadding: CGFloat = 12)`
/// - `View.toast(message: Binding<String?>, duration: TimeInterval = 4, bottomPadding: CGFloat = 12)`

import Observation
import SwiftUI
import UIKit

struct ToastMessage: Identifiable, Equatable {
    let id: UUID
    let text: String

    init(text: String) {
        self.id = UUID()
        self.text = text
    }
}

/// Ekran pastidagi qisqa xabarlar navbati (bir vaqtda bittasi ko'rinadi, yangisi eskisini almashtiradi).
@MainActor
@Observable
final class ToastCenter {
    nonisolated static let defaultDuration: TimeInterval = 4

    private(set) var current: ToastMessage?
    @ObservationIgnored private var hideTask: Task<Void, Never>?

    init() {}

    /// Xabarni ko'rsatadi; `duration` soniyadan keyin o'zi yopiladi.
    func show(_ text: String, duration: TimeInterval = ToastCenter.defaultDuration) {
        let message = ToastMessage(text: text)
        current = message
        UIAccessibility.post(notification: .announcement, argument: text)
        hideTask?.cancel()
        let nanos = UInt64(max(duration, 0.5) * 1_000_000_000)
        hideTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: nanos)
            if Task.isCancelled {
                return
            }
            guard let self else { return }
            if self.current?.id == message.id {
                self.current = nil
            }
        }
    }

    func dismiss() {
        hideTask?.cancel()
        hideTask = nil
        current = nil
    }
}

/// Xabarning o'zi: ko'mir rangli yumaloq panel, oq yozuv.
struct ToastView: View {
    let text: String
    var onTap: (() -> Void)? = nil
    @Environment(\.amoraColors) private var colors

    init(text: String, onTap: (() -> Void)? = nil) {
        self.text = text
        self.onTap = onTap
    }

    var body: some View {
        Text(text)
            .amoraText(.bodyMedium)
            .foregroundColor(colors.onInk)
            .multilineTextAlignment(.leading)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 16)
            .padding(.vertical, 14)
            .background(
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .fill(colors.isDark ? Color(argb: 0xFF332E29) : AmoraColors.inkBlack)
                    .shadow(color: AmoraColors.shadow.opacity(0.25), radius: 14, x: 0, y: 6)
            )
            .padding(.horizontal, 16)
            .contentShape(Rectangle())
            .onTapGesture {
                onTap?()
            }
            .accessibilityAddTraits(.isStaticText)
    }
}

/// Ekran pastida `ToastCenter` xabarini ko'rsatadigan qatlam.
struct ToastHost: View {
    let center: ToastCenter
    var bottomPadding: CGFloat = 12

    init(center: ToastCenter, bottomPadding: CGFloat = 12) {
        self.center = center
        self.bottomPadding = bottomPadding
    }

    var body: some View {
        VStack(spacing: 0) {
            Spacer(minLength: 0)
            if let message = center.current {
                ToastView(text: message.text, onTap: { center.dismiss() })
                    .id(message.id)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            }
        }
        .padding(.bottom, bottomPadding)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottom)
        .animation(.spring(response: 0.35, dampingFraction: 0.85), value: center.current)
    }
}

/// `toast(message:)` ning ichki qismi.
struct ToastBindingModifier: ViewModifier {
    @Binding var message: String?
    let duration: TimeInterval
    let bottomPadding: CGFloat

    init(message: Binding<String?>, duration: TimeInterval, bottomPadding: CGFloat) {
        self._message = message
        self.duration = duration
        self.bottomPadding = bottomPadding
    }

    func body(content: Content) -> some View {
        content.overlay(alignment: .bottom) {
            VStack(spacing: 0) {
                if let text = message {
                    ToastView(text: text, onTap: { message = nil })
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                }
            }
            .padding(.bottom, bottomPadding)
            .animation(.spring(response: 0.35, dampingFraction: 0.85), value: message)
            .task(id: message) {
                await hideLater()
            }
        }
    }

    @MainActor
    private func hideLater() async {
        guard let text = message else { return }
        UIAccessibility.post(notification: .announcement, argument: text)
        try? await Task.sleep(nanoseconds: UInt64(max(duration, 0.5) * 1_000_000_000))
        if Task.isCancelled {
            return
        }
        if message == text {
            message = nil
        }
    }
}

extension View {
    /// `ToastCenter` xabarlarini shu ko'rinishning pastida ko'rsatadi.
    func toastHost(_ center: ToastCenter, bottomPadding: CGFloat = 12) -> some View {
        overlay(alignment: .bottom) {
            ToastHost(center: center, bottomPadding: bottomPadding)
        }
    }

    /// `message` ga matn berilsa ko'rsatiladi va `duration` soniyadan keyin nil qilinadi.
    func toast(message: Binding<String?>, duration: TimeInterval = ToastCenter.defaultDuration, bottomPadding: CGFloat = 12) -> some View {
        modifier(ToastBindingModifier(message: message, duration: duration, bottomPadding: bottomPadding))
    }
}
