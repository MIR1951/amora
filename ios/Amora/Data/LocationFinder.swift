/// Current device location with CoreLocation (port of android ui/address/LocationFinder.kt).
///
/// Surface:
/// - `enum LocationPermission: Equatable { case notDetermined, denied, restricted, granted }`
/// - `@MainActor @Observable final class LocationFinder`
///   - `init()`
///   - `private(set) var permission: LocationPermission`     // observable, kept in sync with the system
///   - `func hasPermission() -> Bool`
///   - `func requestPermission() async -> Bool`               // shows the system prompt if not determined yet; true if granted
///   - `func isEnabled() async -> Bool`                       // location services switched on (checked off the main thread)
///   - `var isReducedAccuracy: Bool`                          // customer allowed only the approximate location
///   - `func isApproximate(_ location: CLLocation) -> Bool`   // reduced accuracy or error radius > 100 m
///   - `func lastKnown(maxAge: TimeInterval = 180) -> CLLocation?`   // instant; nil if older than `maxAge`
///   - `func current(timeout: TimeInterval = 15) async -> CLLocation?`   // nil on timeout/failure/no permission
///   - `func openSettings()`                                  // app page in Settings

import CoreLocation
import Foundation
import Observation
import UIKit

enum LocationPermission: Equatable {
    case notDetermined
    case denied
    case restricted
    case granted
}

/// CLLocationManager delegate: forwards callbacks to the main-actor `LocationFinder`.
private final class LocationDelegate: NSObject, CLLocationManagerDelegate {
    weak var owner: LocationFinder?

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        let status = manager.authorizationStatus
        let target = owner
        Task { @MainActor in
            target?.didChangeAuthorization(status)
        }
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let location = locations.last else { return }
        let target = owner
        Task { @MainActor in
            target?.finishAll(location)
        }
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        let target = owner
        Task { @MainActor in
            target?.finishAll(nil)
        }
    }
}

/// Telefonning joylashuvini aniqlaydi.
@MainActor
@Observable
final class LocationFinder {
    private(set) var permission: LocationPermission = .notDetermined

    private let manager: CLLocationManager
    private let delegate: LocationDelegate
    @ObservationIgnored private var waiters: [UUID: CheckedContinuation<CLLocation?, Never>] = [:]
    @ObservationIgnored private var permissionWaiters: [CheckedContinuation<Bool, Never>] = []

    init() {
        manager = CLLocationManager()
        delegate = LocationDelegate()
        manager.desiredAccuracy = kCLLocationAccuracyBest
        delegate.owner = self
        manager.delegate = delegate
        permission = LocationFinder.map(manager.authorizationStatus)
    }

    private static func map(_ status: CLAuthorizationStatus) -> LocationPermission {
        switch status {
        case .notDetermined: return .notDetermined
        case .denied: return .denied
        case .restricted: return .restricted
        case .authorizedAlways, .authorizedWhenInUse: return .granted
        @unknown default: return .denied
        }
    }

    fileprivate func didChangeAuthorization(_ status: CLAuthorizationStatus) {
        let mapped = LocationFinder.map(status)
        if permission != mapped { permission = mapped }
        if permission != .notDetermined && !permissionWaiters.isEmpty {
            let granted = permission == .granted
            let pending = permissionWaiters
            permissionWaiters = []
            for waiter in pending { waiter.resume(returning: granted) }
        }
    }

    fileprivate func finishAll(_ location: CLLocation?) {
        let pending = waiters
        waiters = [:]
        for waiter in pending.values { waiter.resume(returning: location) }
    }

    private func finish(_ id: UUID, _ location: CLLocation?) {
        guard let waiter = waiters.removeValue(forKey: id) else { return }
        waiter.resume(returning: location)
    }

    func hasPermission() -> Bool {
        LocationFinder.map(manager.authorizationStatus) == .granted
    }

    /// Ruxsat so'raydi (hali so'ralmagan bo'lsa tizim oynasi chiqadi). Ruxsat berilsa true.
    func requestPermission() async -> Bool {
        let status = LocationFinder.map(manager.authorizationStatus)
        if permission != status { permission = status }
        if status != .notDetermined { return status == .granted }
        return await withCheckedContinuation { (continuation: CheckedContinuation<Bool, Never>) in
            permissionWaiters.append(continuation)
            manager.requestWhenInUseAuthorization()
        }
    }

    /// Telefonda joylashuv xizmati yoqilganmi.
    func isEnabled() async -> Bool {
        // Asosiy oqimda chaqirilsa tizim ogohlantiradi: alohida oqimda tekshiriladi
        await Task.detached(priority: .userInitiated) {
            CLLocationManager.locationServicesEnabled()
        }.value
    }

    /// Mijoz faqat taxminiy joylashuvga ruxsat bergan ("Aniq joylashuv" o'chiq): nuqta bir necha
    /// kilometrga adashishi mumkin.
    var isReducedAccuracy: Bool {
        manager.accuracyAuthorization == .reducedAccuracy
    }

    /// Bu joylashuvni aniq manzil deb bo'lmaydi: taxminiy ruxsat yoki xatolik doirasi katta.
    func isApproximate(_ location: CLLocation) -> Bool {
        isReducedAccuracy
            || location.horizontalAccuracy < 0
            || location.horizontalAccuracy > LocationFinder.preciseAccuracyMeters
    }

    static let preciseAccuracyMeters: CLLocationAccuracy = 100

    /// Oxirgi ma'lum joylashuv: darhol qaytadi. `maxAge` soniyadan eski bo'lsa nil: mijoz shu orada
    /// boshqa joyga ketgan bo'lishi mumkin, eski nuqta uni chalg'itadi.
    func lastKnown(maxAge: TimeInterval = 180) -> CLLocation? {
        guard hasPermission(), let location = manager.location else { return nil }
        if Date().timeIntervalSince(location.timestamp) > maxAge { return nil }
        return location
    }

    /// Hozirgi joylashuv. Belgilangan vaqt ichida aniqlanmasa nil.
    func current(timeout: TimeInterval = 15) async -> CLLocation? {
        guard hasPermission() else { return nil }
        let id = UUID()
        let nanos = UInt64(max(0, timeout) * 1_000_000_000)
        return await withCheckedContinuation { (continuation: CheckedContinuation<CLLocation?, Never>) in
            waiters[id] = continuation
            manager.requestLocation()
            Task { @MainActor [weak self] in
                try? await Task.sleep(nanoseconds: nanos)
                self?.finish(id, nil)
            }
        }
    }

    func openSettings() {
        if let url = URL(string: UIApplication.openSettingsURLString) {
            UIApplication.shared.open(url, options: [:], completionHandler: nil)
        }
    }
}
