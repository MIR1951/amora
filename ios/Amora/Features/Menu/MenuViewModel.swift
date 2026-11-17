/// Menu screen state (port of android ui/menu/MenuViewModel.kt).
///
/// Surface (used only inside Features/Menu):
/// - `@MainActor @Observable final class MenuViewModel`
///   - `init(container: AppContainer)`
///   - `var activeOrders: [Order]`            // container.activeOrders.orders (live)
///   - `private(set) var refreshing: Bool`    // pull-to-refresh running
///   - `func refreshCatalog()`                // screen visible / back to the app (skips if one is running)
///   - `func retry()`                         // "Qayta urinish" after an error (shows loading)
///   - `func pullToRefresh() async`           // catalog + active orders
///   - `func refreshActiveOrders()`
///   - `var liveConnected: Bool`              // live stream is up: poll less often

import Foundation
import Observation

@MainActor
@Observable
final class MenuViewModel {
    private let container: AppContainer
    @ObservationIgnored private var catalogRunning = false

    private(set) var refreshing = false

    init(container: AppContainer) {
        self.container = container
    }

    // Faol buyurtmalar butun ilova uchun bitta joyda turadi: jonli xabar kelganda ham yangilanadi
    var activeOrders: [Order] {
        container.activeOrders.orders
    }

    /// Ekran ochilganda yoki ilovaga qaytilganda menyuni yangilaydi.
    func refreshCatalog() {
        if catalogRunning {
            return
        }
        catalogRunning = true
        let catalog = container.catalog
        Task { [weak self] in
            await catalog.refresh()
            self?.catalogRunning = false
        }
    }

    /// Xatodan keyin "Qayta urinish": yuklanish belgisi ko'rsatiladi.
    func retry() {
        let catalog = container.catalog
        Task {
            await catalog.refresh(showLoading: true)
        }
    }

    /// Ekranni pastga tortib yangilash.
    func pullToRefresh() async {
        if refreshing {
            return
        }
        refreshing = true
        await container.catalog.refresh()
        await container.activeOrders.refresh()
        refreshing = false
    }

    func refreshActiveOrders() {
        let activeOrders = container.activeOrders
        Task {
            await activeOrders.refresh()
        }
    }

    /// Jonli ulanish ishlab turibdimi: ishlasa, serverdan tez-tez so'rab turish shart emas.
    var liveConnected: Bool {
        container.realtime.connected
    }
}
