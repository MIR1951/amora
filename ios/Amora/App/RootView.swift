/// Root of the UI (port of android ui/AmoraNavHost.kt): NavigationStack rooted at the menu.
///
/// Surface:
/// - `struct RootView: View` - `RootView()`; needs `.environment(container)` and `.environment(router)`.
///   Installs the theme (`.amoraTheme()`), hides the system navigation bar on every screen (each screen
///   draws its own GlassTopBar), keeps the swipe-back gesture, opens orders tapped in notifications.
/// - `@MainActor @Observable final class NotificationInbox` - `static let shared`, `var pendingOrderId: Int?`,
///   `func open(orderId: Int)` (filled by the notification delegate in AmoraApp.swift)

import Observation
import SwiftUI
import UIKit

struct RootView: View {
    @Environment(Router.self) private var router
    @Environment(\.colorScheme) private var colorScheme

    init() {}

    var body: some View {
        @Bindable var router = router
        let colors = AmoraColors.resolve(colorScheme)
        NavigationStack(path: $router.path) {
            MenuScreen()
                .screenChrome(colors)
                .navigationDestination(for: Route.self) { route in
                    destination(route)
                        .screenChrome(colors)
                }
        }
        .amoraTheme()
        .background(colors.background.ignoresSafeArea())
        .onChange(of: NotificationInbox.shared.pendingOrderId, initial: true) { _, orderId in
            guard let orderId else { return }
            NotificationInbox.shared.pendingOrderId = nil
            router.openOrderFromNotification(id: orderId)
        }
    }

    @ViewBuilder
    private func destination(_ route: Route) -> some View {
        switch route {
        case .orders:
            OrdersScreen()
        case .profile:
            ProfileScreen(quickEdit: false)
        case .cart:
            CartScreen()
        case .address:
            AddressScreen()
        case .profileEdit:
            ProfileScreen(quickEdit: true)
        case .order(let id):
            OrderScreen(orderId: id)
        }
    }
}

private extension View {
    /// Har ekran: tizim navigatsiya satri yashirin (ekran o'z GlassTopBar'ini chizadi), fon shaffof emas
    /// (o'tish animatsiyasida ostidagi ekran ko'rinib qolmaydi).
    func screenChrome(_ colors: AmoraColors) -> some View {
        self
            .toolbar(.hidden, for: .navigationBar)
            .background(colors.background.ignoresSafeArea())
    }
}

/// Bildirishnoma bosilganda ochilishi kerak bo'lgan buyurtma (Android MainActivity.openOrderId).
@MainActor
@Observable
final class NotificationInbox {
    static let shared = NotificationInbox()

    var pendingOrderId: Int?

    init() {}

    func open(orderId: Int) {
        if orderId > 0 {
            pendingOrderId = orderId
        }
    }
}

// Tizim navigatsiya satri yashirilganda ham chetdan surib "orqaga" qaytish ishlasin.
// (SwiftUI satrni yashirganda UINavigationController bu imo-ishorani o'chirib qo'yadi.)
extension UINavigationController: UIGestureRecognizerDelegate {
    override open func viewDidLoad() {
        super.viewDidLoad()
        interactivePopGestureRecognizer?.delegate = self
    }

    public func gestureRecognizerShouldBegin(_ gestureRecognizer: UIGestureRecognizer) -> Bool {
        // Menyuda (ildiz ekranda) orqaga qaytadigan joy yo'q
        viewControllers.count > 1
    }
}
