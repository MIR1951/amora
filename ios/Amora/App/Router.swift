/// Navigation state (port of the routes and helpers in android ui/AmoraNavHost.kt).
/// The start screen is the menu (NavigationStack root); every other screen is pushed on top of it
/// and closed with "back".
///
/// Surface:
/// - `enum Route: Hashable { case orders, profile, cart, address, profileEdit, order(id: Int) }`
/// - `@MainActor @Observable final class Router`
///   - `init()`, `var path: [Route]`
///   - `func open(_ route: Route)`               // push; ignored while a transition runs or if already on top
///   - `func back()`                             // pop one screen; never leaves the menu
///   - `func openCartFromOrders()`               // path = [.cart]  ("Yana shunday buyurtma": back -> menu)
///   - `func openOrderAfterCreate(id: Int)`      // path = [.order(id)] (cart removed from history)
///   - `func openOrderFromNotification(id: Int)` // path = [.order(id)] (back -> menu)
///   - `func popToRoot()`

import Foundation
import Observation

/// Ilova ekranlari (menyudan tashqari: u ildiz).
enum Route: Hashable {
    case orders
    case profile
    case cart
    case address
    case profileEdit
    case order(id: Int)
}

/// Ekranlar orasidagi o'tishlar. Ekranlar `@Environment(Router.self) private var router` orqali oladi.
@MainActor
@Observable
final class Router {
    var path: [Route] = []

    // O'tish animatsiyasi davomida (taxminan) ikkinchi bosish hisobga olinmaydi
    @ObservationIgnored private var lastChange: Date = .distantPast
    private static let transitionSeconds: TimeInterval = 0.45

    init() {}

    private var animating: Bool {
        Date().timeIntervalSince(lastChange) < Router.transitionSeconds
    }

    private func changed() {
        lastChange = Date()
    }

    /// Tugma bosilganda yangi ekran ochadi. O'tish animatsiyasi tugamaguncha ikkinchi bosish
    /// hisobga olinmaydi: bitta ekran ikki marta ochilib qolmaydi.
    func open(_ route: Route) {
        if path.last == route || animating {
            return
        }
        changed()
        path.append(route)
    }

    /// Bir ekran orqaga. Tugma ikki marta bosilsa ham boshlang'ich ekrandan (menyu) chiqib ketmaydi.
    func back() {
        if path.isEmpty || animating {
            return
        }
        changed()
        path.removeLast()
    }

    /// Menyuga qaytaradi.
    func popToRoot() {
        if path.isEmpty {
            return
        }
        changed()
        path = []
    }

    /// "Yana shunday buyurtma": savat ochiladi, undan "orqaga" bosilsa menyuga qaytiladi.
    func openCartFromOrders() {
        changed()
        path = [.cart]
    }

    /// Buyurtma yaratildi: savat ekrani tarixdan olib tashlanadi, "orqaga" menyuga qaytaradi.
    func openOrderAfterCreate(id: Int) {
        changed()
        path = [.order(id: id)]
    }

    /// Bildirishnoma bosildi: o'sha buyurtma ochiladi, undan "orqaga" menyuga qaytaradi.
    func openOrderFromNotification(id: Int) {
        if path == [.order(id: id)] {
            return
        }
        changed()
        path = [.order(id: id)]
    }
}
