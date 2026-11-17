/// Delivery address picker (port of android ui/address/AddressScreen.kt).
///
/// The map fills the whole screen and moves under a pin that stays fixed in the middle of the visible
/// part of the map (between the top controls and the bottom glass panel). The point under the pin's tip
/// is the address. Buttons and the bottom panel float over the map as glass.
///
/// How the pin and the camera agree: the SwiftUI `Map` is given a frame whose centre is exactly the
/// pin's tip (the frame reaches above the screen when needed) and equal top/bottom safe-area padding,
/// so the camera's centre coordinate is always the coordinate under the pin, whether or not MapKit
/// centres the camera inside its safe area.
///
/// Surface:
/// - `struct AddressScreen: View` - `AddressScreen()`; needs `AppContainer` and `Router` in the environment.
///   "Shu manzilga yetkazish" saves `container.session.saveAddress(...)` and calls `router.back()`.
/// - `@MainActor @Observable final class AddressScreenModel` - the screen's state (used only here).

import CoreLocation
import Foundation
import MapKit
import Observation
import SwiftUI

// MARK: - Constants

private enum AddressConst {
    // Manzil hali tanlanmagan va kafe joylashuvi ham kiritilmagan bo'lsa, xarita shu yerdan ochiladi
    static let defaultLatitude = 41.3775
    static let defaultLongitude = 64.5853
    // Android (osmdroid) xarita yaqinlik darajalari
    static let countryZoom = 6.0
    static let cityZoom = 14.0
    static let streetZoom = 17.0

    // Bundan uzoqroq ko'rinishda nuqta juda noaniq bo'ladi: tasdiqlashga ruxsat berilmaydi
    static let minConfirmZoom = 14.0
    static let maxNoteLength = 255

    // Xarita ustidagi yuqori tugmalar egallaydigan joy (holat satridan tashqari)
    static let topControls: CGFloat = 60
    static let sheetCorner: CGFloat = 32
    static let pinHead: CGFloat = 46
    static let pinStem: CGFloat = 18
    static let pinGround: CGFloat = 6

    // Xarita surilishi shuncha vaqt to'xtab tursa, belgi joyiga "qo'nadi"
    static let pinSettleNanos: UInt64 = 220_000_000

    static let zoomNotice = "Xaritani yaqinlashtirib, yetkazish joyini aniqroq belgilang."
    static let locationOffNotice =
        "Telefonda joylashuv (GPS) o'chirilgan. Uni yoqing yoki manzilni xaritadan qo'lda tanlang."
    static let locateFailedNotice = "Joylashuvni aniqlab bo'lmadi. Manzilni xaritadan qo'lda tanlang."
    static let deniedNotice = "Joylashuvga ruxsat berilmadi. Manzilni xaritadan qo'lda tanlang."
    static let outOfZoneWarning = "Bu joy yetkazish hududidan tashqarida. Belgini doira ichiga suring."
    static let settingsAction = "Joylashuv sozlamalarini ochish"
    static let defaultHint = "Xaritani surib, belgini yetkazish joyiga qo'ying"

    // Yetkazish hududi doirasi (Android: argb(22, 229, 67, 42) va argb(150, 229, 67, 42))
    static let zoneFill: UInt32 = 0x16E5432A
    static let zoneStroke: UInt32 = 0x96E5432A
}

/// Kafe atrofidagi yetkazish hududi.
private struct AddressZone {
    let center: CLLocationCoordinate2D
    let radiusKm: Double

    init?(shop: Shop?) {
        guard let shop,
              let latitude = shop.cafeLatitude,
              let longitude = shop.cafeLongitude,
              let radiusKm = shop.maxDeliveryKm else {
            return nil
        }
        self.center = CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
        self.radiusKm = radiusKm
    }

    func contains(_ point: CLLocationCoordinate2D) -> Bool {
        distanceKm(center.latitude, center.longitude, point.latitude, point.longitude) <= radiusKm
    }
}

// MARK: - State

/// Ekran holati: xarita kamerasi, belgi ko'rsatayotgan nuqta, mo'ljal, joylashuvni aniqlash.
@MainActor
@Observable
final class AddressScreenModel {
    var started: Bool = false
    var position: MapCameraPosition = .automatic
    // Belgi ko'rsatib turgan nuqta
    var center: CLLocationCoordinate2D = CLLocationCoordinate2D(latitude: AddressConst.defaultLatitude, longitude: AddressConst.defaultLongitude)
    var moving: Bool = false
    var note: String = ""
    var locating: Bool = false
    var notice: String? = nil
    var locationOff: Bool = false
    // Ruxsat avvalroq rad etilgan: iOS qayta so'ramaydi, faqat Sozlamalardan yoqiladi
    var permissionDenied: Bool = false
    var myLocation: CLLocationCoordinate2D? = nil
    // Pastki panel balandligi (uy tugmasi chizig'isiz)
    var sheetHeight: CGFloat = 0

    @ObservationIgnored var zoom: Double = AddressConst.countryZoom
    @ObservationIgnored var mapWidth: CGFloat = 0
    @ObservationIgnored private var requesting: Bool = false
    @ObservationIgnored private var autoLocated: Bool = false
    @ObservationIgnored private var liftAfter: Date = .distantFuture
    @ObservationIgnored private var settleTask: Task<Void, Never>? = nil

    init() {}

    /// Xarita qayerdan ochilishi: saqlangan manzil, kafe yoki mamlakat markazi.
    func start(saved: Address?, shop: Shop?, width: CGFloat) {
        if width > 0 {
            mapWidth = width
        }
        if started {
            return
        }
        let point: CLLocationCoordinate2D
        let startZoom: Double
        if let saved {
            point = CLLocationCoordinate2D(latitude: saved.latitude, longitude: saved.longitude)
            startZoom = AddressConst.streetZoom
        } else if let latitude = shop?.cafeLatitude, let longitude = shop?.cafeLongitude {
            point = CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
            startZoom = AddressConst.cityZoom
        } else {
            point = CLLocationCoordinate2D(latitude: AddressConst.defaultLatitude, longitude: AddressConst.defaultLongitude)
            startZoom = AddressConst.countryZoom
        }
        center = point
        zoom = startZoom
        note = saved?.note ?? ""
        position = .region(region(point, zoom: startZoom))
        // Xarita joylashib olguncha belgi sakramaydi
        liftAfter = Date().addingTimeInterval(0.8)
        started = true
    }

    /// Android osmdroid yaqinlik darajasiga mos hudud (256 nuqtali kataklar, kenglik bo'yicha).
    func region(_ point: CLLocationCoordinate2D, zoom level: Double) -> MKCoordinateRegion {
        let width = Double(effectiveWidth)
        let longitudeDelta = min(300, width * 360 / (256 * pow(2, level)))
        // Balandlik bo'yicha kichikroq: xarita kenglik bo'yicha moslanadi
        let latitudeDelta = max(0.000_01, longitudeDelta * cos(point.latitude * Double.pi / 180) * 0.3)
        return MKCoordinateRegion(
            center: point,
            span: MKCoordinateSpan(latitudeDelta: min(80, latitudeDelta), longitudeDelta: longitudeDelta)
        )
    }

    private var effectiveWidth: CGFloat {
        if mapWidth > 0 {
            return mapWidth
        }
        let window = AmoraWindow.width
        return window > 0 ? window : 390
    }

    private func zoomLevel(_ region: MKCoordinateRegion) -> Double {
        let delta = region.span.longitudeDelta
        guard delta > 0 else { return zoom }
        return log2(Double(effectiveWidth) * 360 / (256 * delta))
    }

    /// Xarita surilganda belgi ko'rsatayotgan nuqtani kuzatib boramiz.
    func cameraChanged(_ context: MapCameraUpdateContext, ended: Bool) {
        center = context.camera.centerCoordinate
        zoom = zoomLevel(context.region)
        // Xarita yetarlicha yaqinlashtirilgach, shu haqdagi ogohlantirish o'chadi
        if notice == AddressConst.zoomNotice && zoom >= AddressConst.minConfirmZoom {
            notice = nil
        }
        if !ended && Date() >= liftAfter {
            if !moving {
                moving = true
            }
            settle()
        }
    }

    /// Xarita to'xtagach belgi joyiga qo'nadi.
    private func settle() {
        settleTask?.cancel()
        settleTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: AddressConst.pinSettleNanos)
            if Task.isCancelled {
                return
            }
            self?.moving = false
        }
    }

    /// Manzil birinchi marta tanlanayotgan bo'lsa, xaritani darhol mijoz turgan joyga olib boramiz.
    func autoLocateOnce(_ finder: LocationFinder) {
        if autoLocated {
            return
        }
        autoLocated = true
        onMyLocation(finder)
    }

    /// "Mening joylashuvim" tugmasi.
    func onMyLocation(_ finder: LocationFinder) {
        if locating || requesting {
            return
        }
        Task {
            await self.findMe(finder)
        }
    }

    private func findMe(_ finder: LocationFinder) async {
        if !finder.hasPermission() {
            // Joylashuv xizmati o'chiq bo'lsa iOS ruxsatni ham "rad etilgan" deb ko'rsatadi
            if !(await finder.isEnabled()) {
                showLocationOff()
                return
            }
            let askedBefore = finder.permission != .notDetermined
            requesting = true
            let granted = await finder.requestPermission()
            requesting = false
            if !granted {
                locationOff = false
                permissionDenied = askedBefore
                notice = AddressConst.deniedNotice
                return
            }
        }
        await locate(finder)
    }

    private func showLocationOff() {
        locationOff = true
        permissionDenied = false
        notice = AddressConst.locationOffNotice
    }

    private func locate(_ finder: LocationFinder) async {
        if !(await finder.isEnabled()) {
            showLocationOff()
            return
        }
        if locating {
            return
        }
        locationOff = false
        permissionDenied = false
        notice = nil
        locating = true
        defer { locating = false }
        let lastKnown = finder.lastKnown()
        if let lastKnown {
            show(lastKnown)
        }
        let current = await finder.current()
        if let current {
            show(current)
        } else if lastKnown == nil {
            notice = AddressConst.locateFailedNotice
        }
    }

    private func show(_ location: CLLocation) {
        let point = location.coordinate
        myLocation = point
        let target = region(point, zoom: AddressConst.streetZoom)
        withAnimation(.easeInOut(duration: 0.7)) {
            position = .region(target)
        }
    }

    /// Sozlamalardan GPS yoki ruxsat yoqib qaytilgan bo'lsa, ogohlantirish yo'qoladi.
    func onResume(_ finder: LocationFinder) async {
        if locationOff, await finder.isEnabled() {
            locationOff = false
            if notice == AddressConst.locationOffNotice {
                notice = nil
            }
        }
        if permissionDenied && finder.hasPermission() {
            permissionDenied = false
            if notice == AddressConst.deniedNotice {
                notice = nil
            }
        }
    }

    func setNote(_ text: String) {
        note = String(text.prefix(AddressConst.maxNoteLength))
    }

    /// Tasdiqlash: xarita yetarlicha yaqin bo'lsa manzil saqlanadi va true qaytadi.
    func confirm(_ session: SessionStore) -> Bool {
        if zoom < AddressConst.minConfirmZoom {
            locationOff = false
            permissionDenied = false
            notice = AddressConst.zoomNotice
            return false
        }
        let trimmed = note.trimmingCharacters(in: .whitespacesAndNewlines)
        session.saveAddress(Address(latitude: center.latitude, longitude: center.longitude, note: trimmed))
        return true
    }
}

// MARK: - Screen

/// Yetkazish manzilini tanlash. Xarita butun ekranni egallaydi va suriladi; belgi turgan joy manzil bo'ladi.
/// Tugmalar va pastki panel xarita ustida shisha bo'lib turadi.
struct AddressScreen: View {
    @Environment(AppContainer.self) private var container
    @Environment(Router.self) private var router
    @Environment(\.amoraColors) private var colors
    @Environment(\.scenePhase) private var scenePhase
    @State private var model = AddressScreenModel()
    @FocusState private var noteFocused: Bool

    init() {}

    var body: some View {
        let zone = AddressZone(shop: container.catalog.shop)
        let outOfZone = zone.map { !$0.contains(model.center) } ?? false
        let warning: String? = outOfZone ? AddressConst.outOfZoneWarning : model.notice
        let actionLabel: String? = !outOfZone && (model.locationOff || model.permissionDenied)
            ? AddressConst.settingsAction
            : nil
        ZStack {
            GeometryReader { geo in
                mapLayer(geo: geo, zone: zone, warning: warning, actionLabel: actionLabel)
            }
            .ignoresSafeArea()

            bottomPanel(outOfZone: outOfZone)
        }
        .background(colors.background.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
        .task {
            if container.session.address == nil {
                model.autoLocateOnce(container.location)
            }
        }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active {
                let finder = container.location
                Task {
                    await model.onResume(finder)
                }
            }
        }
    }

    // MARK: Map, pin and top controls (full screen, keyboard does not move them)

    @ViewBuilder
    private func mapLayer(geo: GeometryProxy, zone: AddressZone?, warning: String?, actionLabel: String?) -> some View {
        let width = geo.size.width
        let height = geo.size.height
        let topInset = max(geo.safeAreaInsets.top, AmoraWindow.keyWindow?.safeAreaInsets.top ?? 0)
        let bottomInset = AmoraWindow.bottomInset
        // Belgi xaritaning ko'rinib turgan qismi (yuqori tugmalar va pastki panel orasi) o'rtasida turadi
        let visibleTop = topInset + AddressConst.topControls
        let sheetTop = height - bottomInset - model.sheetHeight
        let pinY = model.sheetHeight > 0 ? (visibleTop + sheetTop) / 2 : height / 2
        // Xarita ramkasining markazi aynan belgining uchida: kamera markazi = tanlangan nuqta
        let mapHeight = 2 * max(pinY, height - pinY)
        let frameTop = pinY - mapHeight / 2
        let insetPadding = model.sheetHeight > 0 ? max(0, visibleTop - frameTop + 6) : 0

        ZStack(alignment: .topLeading) {
            if model.started {
                mapView(zone: zone, padding: insetPadding)
                    .frame(width: width, height: mapHeight)
                    .position(x: width / 2, y: pinY)
            }

            // Belgining uchi (pastki nuqtasi) aynan tanlangan joyni ko'rsatadi
            AddressMapPin(moving: model.moving)
                .frame(width: width, height: max(0, pinY + AddressConst.pinGround), alignment: .bottom)
                .allowsHitTesting(false)

            // Holat satri ostidagi yumshoq parda: soat va belgilar xarita ustida ham o'qiladi
            LinearGradient(
                colors: [colors.background.opacity(0.75), colors.background.opacity(0)],
                startPoint: .top,
                endPoint: .bottom
            )
            .frame(width: width, height: topInset + 56)
            .allowsHitTesting(false)

            HStack(alignment: .top, spacing: 10) {
                RoundButton(icon: .back, label: "Orqaga", onClick: { router.back() }, glass: true)
                AddressMapHint(
                    warning: warning,
                    actionLabel: actionLabel,
                    onAction: { container.location.openSettings() }
                )
                .layoutPriority(1)
                Spacer(minLength: 0)
            }
            .padding(.top, topInset + 8)
            .padding(.horizontal, 16)
            .frame(width: width, alignment: .leading)
        }
        .frame(width: width, height: height, alignment: .topLeading)
        .onAppear {
            model.start(saved: container.session.address, shop: container.catalog.shop, width: width)
        }
        .onChange(of: width) { _, newWidth in
            if newWidth > 0 {
                model.mapWidth = newWidth
            }
        }
    }

    private func mapView(zone: AddressZone?, padding: CGFloat) -> some View {
        let position = Binding<MapCameraPosition>(
            get: { model.position },
            set: { model.position = $0 }
        )
        let myLocation = model.myLocation
        return Map(position: position, interactionModes: [.pan, .zoom]) {
            // Yetkazish hududi chegarasi (kafe atrofidagi doira)
            if let zone {
                MapCircle(center: zone.center, radius: zone.radiusKm * 1000)
                    .foregroundStyle(Color(argb: AddressConst.zoneFill))
                    .stroke(Color(argb: AddressConst.zoneStroke), lineWidth: 1.5)
            }
            // Mijoz turgan joyni ko'rsatuvchi ko'k nuqta
            if let myLocation {
                Annotation("", coordinate: myLocation, anchor: .center) {
                    IconImage(.myLocation, size: 28)
                        .allowsHitTesting(false)
                }
            }
        }
        .onMapCameraChange(frequency: .continuous) { context in
            MainActor.assumeIsolated {
                model.cameraChanged(context, ended: false)
            }
        }
        .onMapCameraChange(frequency: .onEnd) { context in
            MainActor.assumeIsolated {
                model.cameraChanged(context, ended: true)
            }
        }
        // Teng yuqori/pastki chekka: kamera markazi o'zgarmaydi, xarita yozuvlari panel ustida ko'rinadi
        .safeAreaPadding(.top, padding)
        .safeAreaPadding(.bottom, padding)
        .ignoresSafeArea()
    }

    // MARK: Bottom: my-location button and the glass sheet (rises with the keyboard)

    private func bottomPanel(outOfZone: Bool) -> some View {
        VStack(spacing: 0) {
            Spacer(minLength: 0)
            HStack(alignment: .bottom, spacing: 0) {
                Spacer(minLength: 0)
                myLocationButton
            }
            .padding(.leading, 10)
            .padding(.trailing, 16)
            .padding(.bottom, 12)

            sheet(outOfZone: outOfZone)
        }
    }

    @ViewBuilder
    private var myLocationButton: some View {
        let onClick: () -> Void = { model.onMyLocation(container.location) }
        if model.locating {
            RoundButton(
                icon: .gps,
                label: "Mening joylashuvim",
                onClick: onClick,
                size: 52,
                cornerRadius: 18,
                tint: colors.primary,
                glass: true
            ) {
                ProgressView()
                    .progressViewStyle(.circular)
                    .tint(colors.primary)
                    .frame(width: 22, height: 22)
            }
        } else {
            RoundButton(
                icon: .gps,
                label: "Mening joylashuvim",
                onClick: onClick,
                size: 52,
                cornerRadius: 18,
                tint: colors.primary,
                glass: true
            )
        }
    }

    /// Pastki shisha panel: sarlavha, mo'ljal maydoni va tasdiqlash tugmasi.
    private func sheet(outOfZone: Bool) -> some View {
        let shape = UnevenRoundedRectangle(
            topLeadingRadius: AddressConst.sheetCorner,
            bottomLeadingRadius: 0,
            bottomTrailingRadius: 0,
            topTrailingRadius: AddressConst.sheetCorner,
            style: .continuous
        )
        return VStack(alignment: .leading, spacing: 0) {
            Capsule()
                .fill(colors.outline)
                .frame(width: 38, height: 4)
                .frame(maxWidth: .infinity)
            Spacer().frame(height: 16)
            HStack(alignment: .center, spacing: 12) {
                IconTile(
                    icon: .pin,
                    container: outOfZone ? colors.errorContainer : colors.primaryContainer
                )
                VStack(alignment: .leading, spacing: 0) {
                    Text("Yetkazish manzili")
                        .amoraText(.titleLarge)
                        .foregroundColor(colors.onSurface)
                    Text(outOfZone ? "Yetkazish hududidan tashqarida" : "Xaritada belgilangan joy")
                        .amoraText(.bodySmall)
                        .foregroundColor(outOfZone ? colors.error : colors.onSurfaceVariant)
                        .lineLimit(1)
                }
                Spacer(minLength: 0)
            }
            Spacer().frame(height: 16)
            noteField
            Spacer().frame(height: 14)
            BigButton(text: "Shu manzilga yetkazish", onClick: confirm, enabled: !outOfZone)
        }
        .padding(.horizontal, 16)
        .padding(.top, 10)
        .padding(.bottom, 14)
        .background(
            GeometryReader { proxy in
                Color.clear
                    .onAppear { model.sheetHeight = proxy.size.height }
                    .onChange(of: proxy.size.height) { _, newHeight in
                        model.sheetHeight = newHeight
                    }
            }
        )
        .frame(maxWidth: .infinity)
        .background(
            GlassBackground(shape: shape, tone: .light, elevation: 20)
                .ignoresSafeArea(edges: .bottom)
        )
        // Panelning bo'sh joyiga bosilganda ostidagi xarita surilib ketmaydi
        .contentShape(Rectangle())
    }

    private var noteField: some View {
        let text = Binding<String>(
            get: { model.note },
            set: { model.setNote($0) }
        )
        return HStack(spacing: 12) {
            IconImage(.home, size: 20, tint: colors.onSurfaceVariant)
            TextField("", text: text, prompt: fieldPrompt("Mo'ljal, uy, xonadon", colors))
                .textInputAutocapitalization(.sentences)
                .submitLabel(.done)
                .focused($noteFocused)
                .onSubmit { noteFocused = false }
        }
        .fieldStyle()
        .onTapGesture { noteFocused = true }
    }

    private func confirm() {
        if model.confirm(container.session) {
            noteFocused = false
            router.back()
        }
    }
}

// MARK: - Pin

/// Xarita o'rtasidagi belgi: ustida yozuv, qizil bosh va ingichka oyoq. Xarita surilayotganda biroz ko'tariladi.
/// Ko'rinishning pastki chetidan `pinGround` yuqorida oyoqning uchi turadi.
private struct AddressMapPin: View {
    let moving: Bool
    @Environment(\.amoraColors) private var colors

    init(moving: Bool) {
        self.moving = moving
    }

    var body: some View {
        let ink = AmoraColors.inkBlack
        VStack(spacing: 0) {
            VStack(spacing: 0) {
                Text("Yetkazish shu yerga")
                    .amoraText(AmoraTextStyle.labelSmall.with(size: 12, tracking: 0))
                    .foregroundColor(.white)
                    .lineLimit(1)
                    .fixedSize()
                    .padding(.horizontal, 11)
                    .padding(.vertical, 7)
                    .background(
                        RoundedRectangle(cornerRadius: 11, style: .continuous)
                            .fill(ink)
                            .shadow(color: AmoraColors.shadow.opacity(0.28), radius: 4, x: 0, y: 2)
                    )
                Spacer().frame(height: 6)
                ZStack {
                    Circle()
                        .fill(Color.white)
                        .shadow(color: AmoraColors.shadow.opacity(0.30), radius: 6, x: 0, y: 3)
                    Circle()
                        .fill(colors.primary)
                        .padding(4)
                    Circle()
                        .fill(Color.white)
                        .frame(width: 12, height: 12)
                }
                .frame(width: AddressConst.pinHead, height: AddressConst.pinHead)
                UnevenRoundedRectangle(
                    topLeadingRadius: 0,
                    bottomLeadingRadius: 2,
                    bottomTrailingRadius: 2,
                    topTrailingRadius: 0,
                    style: .continuous
                )
                .fill(ink)
                .frame(width: 3, height: AddressConst.pinStem)
            }
            .offset(y: moving ? -10 : 0)
            .animation(.spring(response: 0.28, dampingFraction: 0.5), value: moving)

            // Belgi ko'tarilganda ham aynan qaysi nuqta tanlanayotgani ko'rinib turadi.
            // Soya oyoqning uchi bilan bir nuqtada turadi: oyoq uchi tanlangan joyning o'zi.
            Capsule()
                .fill(Color.black.opacity(0.26))
                .frame(width: 12, height: AddressConst.pinGround)
                .offset(y: -AddressConst.pinGround / 2)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Tanlangan joy")
    }
}

// MARK: - Hint

/// Xarita ustidagi to'q shisha yozuv: odatda yo'riqnoma, muammo bo'lsa ogohlantirish.
private struct AddressMapHint: View {
    let warning: String?
    let actionLabel: String?
    let onAction: () -> Void
    @Environment(\.amoraColors) private var colors

    init(warning: String?, actionLabel: String?, onAction: @escaping () -> Void) {
        self.warning = warning
        self.actionLabel = actionLabel
        self.onAction = onAction
    }

    var body: some View {
        GlassBox(cornerRadius: 16, tone: .dark, elevation: 8) {
            content
                .id(warning ?? "")
                .transition(.opacity)
        }
        .animation(.easeInOut(duration: 0.2), value: warning)
    }

    private var content: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .center, spacing: 8) {
                if warning != nil {
                    IconImage(.info, size: 16, tint: colors.amber)
                }
                Text(warning ?? AddressConst.defaultHint)
                    .amoraText(.bodySmall)
                    .foregroundColor(.white)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if warning != nil, let actionLabel {
                Button(action: onAction) {
                    Text(actionLabel)
                        .amoraText(.labelMedium)
                        .foregroundColor(colors.amber)
                        .padding(.vertical, 4)
                        .contentShape(Rectangle())
                }
                .buttonStyle(PressScaleStyle())
                .padding(.top, 6)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
    }
}
