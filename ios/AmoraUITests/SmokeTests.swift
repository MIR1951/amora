//
//  SmokeTests.swift
//  AmoraUITests
//
//  Ilovani simulyatorda ochib, buyurtmaning butun yo'lini bosib chiqadi va har qadamni rasmga oladi.
//  android/ci/smoke_test.py dagi "full" ssenariyning iOS'dagi o'xshashi.
//
//  FAQAT CI ichida ko'tarilgan SINOV serveriga qaratilgan ilova bilan ishlaydi
//  (AMORA_API_BASE_URL=http://127.0.0.1:8000). Sinov boshida kafe nomi "Amora sinov serveri"
//  ekanligi tekshiriladi: aks holda buyurtma haqiqiy kafega ketib qolmasligi uchun sinov to'xtaydi.
//
//  Kafe xodimi va mijozning Telegram'dagi harakatlari ios/ci/control_server.py orqali bajariladi
//  (simulyatordan kompyuterdagi skriptni ishga tushirib bo'lmaydi, lekin HTTP so'rov yuborsa bo'ladi).
//
//  Muhit o'zgaruvchilari (xcodebuild'ga TEST_RUNNER_ prefiksi bilan beriladi, prefiks olib tashlanadi):
//    SCREENSHOT_DIR  rasmlar shu papkaga <NN-nom>.png bo'lib yoziladi (yo'q bo'lsa faqat XCTAttachment)
//    CONTROL_URL     boshqaruv serveri, standart holatda http://127.0.0.1:8099
//

import Foundation
import XCTest

/// Sinov xatosi: qaysi qadamda nima topilmadi.
struct SmokeFailure: Error, CustomStringConvertible {
    let message: String
    init(_ message: String) { self.message = message }
    var description: String { message }
}

/// Tizimning ruxsat oynasidagi "ruxsat berish" tugmalari (inglizcha va o'zbekcha simulyator).
let allowButtonTitles = [
    "Allow While Using App", "Allow Once", "Allow", "OK",
    "Ilova ishlatilayotganda ruxsat berish", "Bir marta ruxsat berish", "Ruxsat berish",
]

/// HTTP javobini yopiq blokdan olib chiqish uchun (URLSession natijasi boshqa oqimda keladi).
final class ControlReply {
    var status: Int = 0
    var text: String = ""
}

final class SmokeTests: XCTestCase {

    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    @MainActor
    func testFullOrderFlow() throws {
        let app = XCUIApplication()
        let driver = SmokeDriver(test: self, app: app)

        // Tizimning ruxsat oynalari (joylashuv, bildirishnoma): oldindan ruxsat berilgan bo'lsa ham,
        // oyna chiqib qolsa sinovni to'sib qo'ymasin
        _ = addUIInterruptionMonitor(withDescription: "Tizim ruxsat oynasi") { alert -> Bool in
            for title in allowButtonTitles {
                let button = alert.buttons[title]
                if button.exists {
                    button.tap()
                    return true
                }
            }
            return false
        }

        app.launch()
        do {
            try driver.scenarioFull()
            print("Sinov muvaffaqiyatli o'tdi (full)")
        } catch {
            print("[XATO] \(error)")
            driver.shot("failure")
            print("Ekranda: \(driver.visibleTexts())")
            print(app.debugDescription)
            XCTFail("\(error)")
        }
    }
}

/// Ekranni bosib chiqadigan yordamchi: matn bo'yicha izlash, kutish, bosish, rasmga olish.
@MainActor
final class SmokeDriver {
    /// android/ci/backend_ctl.py sinov serverida kafe nomini shunga o'zgartiradi (TEST_CAFE_NAME)
    static let testCafeName = "Amora sinov serveri"
    static let testPhone = "+998901234567"

    let test: XCTestCase
    let app: XCUIApplication
    let springboard: XCUIApplication
    let screenshotDir: URL?
    let controlURL: String

    init(test: XCTestCase, app: XCUIApplication) {
        self.test = test
        self.app = app
        self.springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        let env = ProcessInfo.processInfo.environment
        if let dir = env["SCREENSHOT_DIR"], !dir.isEmpty {
            let url = URL(fileURLWithPath: dir, isDirectory: true)
            try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
            screenshotDir = url
        } else {
            screenshotDir = nil
        }
        let control = env["CONTROL_URL"] ?? ""
        controlURL = control.isEmpty ? "http://127.0.0.1:8099" : control
    }

    // MARK: - Ssenariy

    func scenarioFull() throws {
        // Boshqaruv serveri ishlamasa, buyurtma holatini o'zgartirib bo'lmaydi: darhol to'xtaymiz
        _ = try control("/health", [:])

        // Himoya: ilova sinov serveriga ulangan bo'lsagina davom etamiz
        do {
            _ = try waitFor(SmokeDriver.testCafeName, timeout: 90)
        } catch {
            throw SmokeFailure("Ilova sinov serveriga ulanmagan: buyurtma berilmaydi")
        }
        _ = try waitFor("so'm", timeout: 90)
        // Jonli menyu tekshiruvi (smoke_test.py check_live_menu) bu yerda yo'q: macOS'da sinov
        // serveri SQLite'da ishlaydi va boshqa jarayondagi o'zgarishlar jonli kanalga tushmaydi.

        try fillCart()

        // Birinchi buyurtma chegirmasi kod kiritmasdan qo'llanadi
        if findScrolling("Birinchi buyurtma", attempts: 4) != nil {
            shot("08a-cart-first-order-discount")
        } else {
            print("[ogohlantirish] birinchi buyurtma chegirmasi ko'rinmadi")
        }

        // 1-buyurtma: kafe qabul qiladi, kuryer yo'lga chiqadi, yetkazadi
        try placeOrder()
        shot("09-order-new")
        print("Buyurtma: \(visibleTexts())")

        // Holat jonli kanal orqali emas (SQLite), buyurtma ekranining o'z so'rovi bilan keladi:
        // u har 7-30 soniyada serverdan so'raydi, shuning uchun kutish uzun
        try staff("accepted")
        _ = try waitFor("Tayyorlanmoqda", timeout: 90)
        shot("10-order-accepted")

        // Menyudagi "faol buyurtma" belgisi
        try goBack()
        _ = try waitFor("Buyurtma №", timeout: 40)
        shot("11-menu-active-order")

        try staff("delivering")
        Thread.sleep(forTimeInterval: 2)
        shot("11a-menu-after-delivering")
        if (try? waitFor("Kuryer yo'lda", timeout: 40)) != nil {
            print("Bosh sahifadagi buyurtma belgisi o'zi yangilandi")
        } else {
            print("[ogohlantirish] bosh sahifadagi belgi 40 soniyada yangilanmadi")
        }
        try tap("Buyurtma №")
        _ = try waitFor("Kuryer buyurtmangizni olib", timeout: 90)
        shot("12-order-delivering")

        try staff("delivered")
        _ = try waitFor("Yoqimli ishtaha", timeout: 90)
        shot("13-order-delivered")
        print("Yetkazilgan buyurtma: \(visibleTexts())")

        // Buyurtmalar tarixi
        try goBack()
        try tap("Buyurtmalarim", exact: true)
        _ = try waitFor("Buyurtma №")
        _ = try waitFor("Yetkazildi")
        shot("14-orders")
        print("Buyurtmalar: \(visibleTexts())")
        try tap("Buyurtma №")
        _ = try waitFor("Yoqimli ishtaha", timeout: 60)
        shot("15-order-from-history")
        try goBack()
        _ = try waitFor("Buyurtmalarim", timeout: 20)
        try goBack()

        // Profil
        _ = try waitFor(SmokeDriver.testCafeName, timeout: 30)
        try tap("Profil", exact: true)
        _ = try waitFor("Yetkazish manzili")
        if (try? waitFor("Telegram orqali tasdiqlangan", timeout: 10)) == nil {
            print("[ogohlantirish] profilda tasdiqlangan raqam ko'rinmadi")
        }
        shot("16-profile")
        try goBack()
        _ = try waitFor(SmokeDriver.testCafeName, timeout: 30)
    }

    /// Menyudan savatgacha: taom qo'shish, manzil va profil. Oxirida buyurtma berishga tayyor savat.
    func fillCart() throws {
        Thread.sleep(forTimeInterval: 6) // taom rasmlari yuklanib ulgursin
        shot("01-menu")
        print("Menyu: \(visibleTexts())")

        // Taom haqida ma'lumot oynasi: taom nomi bosilganda ochiladi (ochilmasa, sinov davom etaveradi)
        do {
            let name = app.descendants(matching: .any).matching(identifier: "product-name").firstMatch
            guard name.waitForExistence(timeout: 15) else {
                throw SmokeFailure("taom kartochkasi topilmadi")
            }
            tapElement(name)
            _ = try waitFor("Savatga qo'shish", timeout: 15)
            Thread.sleep(forTimeInterval: 1)
            shot("02-product")
            closeSheet()
            if find("Savatga qo'shish") != nil {
                app.swipeDown()
                Thread.sleep(forTimeInterval: 1.5)
            }
            try waitGone("Savatga qo'shish", timeout: 10)
        } catch {
            print("[ogohlantirish] taom oynasi: \(error)")
            shot("02-product-failed")
            closeSheet()
        }

        // Kartochkadagi "+" tugmasi (Android: contentDescription "Qo'shish")
        if let add = find("Qo'shish", exact: true) {
            tapElement(add)
        } else {
            try tap("Qo'shish", excluding: ["Savatga"])
        }
        _ = try waitFor("Savat")
        shot("03-added")

        try tap("Savat", excluding: ["Savatga qo'shish"])
        _ = try waitFor("Jami")
        Thread.sleep(forTimeInterval: 2)
        shot("04-cart")

        try tap("Manzilni tanlang")
        let confirm = try waitFor("Shu manzilga yetkazish", timeout: 60)
        Thread.sleep(forTimeInterval: 12) // joylashuv aniqlanib, xarita yuklansin
        shot("05-address")
        _ = waitEnabled(confirm, timeout: 20)
        try tap("Shu manzilga yetkazish")

        _ = try waitFor("Raqamni Telegram orqali tasdiqlang")
        shot("06-cart-address")
        try tap("Raqamni Telegram orqali tasdiqlang")

        let verifyButton = try waitFor("Telegram orqali tasdiqlash")
        try typeIntoFirstField("Sinov")
        shot("07-profile")
        _ = waitEnabled(verifyButton, timeout: 10)
        try verifyPhone(SmokeDriver.testPhone)

        // Tasdiqlangach tezkor profil o'zi yopiladi va savatga qaytadi
        do {
            _ = try waitFor("Buyurtma berish", timeout: 60)
        } catch {
            if find("Telegram orqali tasdiqlangan") != nil {
                print("[ogohlantirish] profil o'zi yopilmadi, orqaga qaytamiz")
                try goBack()
                _ = try waitFor("Buyurtma berish", timeout: 30)
            } else {
                throw error
            }
        }
        Thread.sleep(forTimeInterval: 3)
        shot("08-cart-ready")
        print("Savat: \(visibleTexts())")
    }

    /// Raqamni tasdiqlash: ilova botni ochadi (simulyatorda Telegram yo'q, Safari ochiladi),
    /// mijoz o'rnida boshqaruv serveri raqamni yuboradi, so'ng ilovaga qaytamiz.
    func verifyPhone(_ phone: String) throws {
        try tap("Telegram orqali tasdiqlash")
        Thread.sleep(forTimeInterval: 4)
        shot("07a-verify-opened")
        var lastError: Error?
        for _ in 0..<5 {
            do {
                _ = try control("/verify", ["phone": phone])
                lastError = nil
                break
            } catch {
                // Ilova tasdiqlash so'rovini hali yaratib ulgurmagan bo'lishi mumkin
                lastError = error
                Thread.sleep(forTimeInterval: 3)
            }
        }
        if let lastError = lastError {
            throw lastError
        }
        app.activate()
        _ = app.wait(for: .runningForeground, timeout: 20)
        Thread.sleep(forTimeInterval: 2)
    }

    /// Savatdagi buyurtmani yuboradi va buyurtma ekrani ochilishini kutadi.
    func placeOrder() throws {
        // Summa serverdan kelgach tugma yoqiladi (unda summa ham ko'rinadi)
        let deadline = Date().addingTimeInterval(60)
        var button: XCUIElement?
        while Date() < deadline {
            dismissSystemAlerts()
            if let candidate = find("Buyurtma berish", excluding: ["Buyurtmani tasdiqlaysizmi"]),
               candidate.isEnabled {
                button = candidate
                break
            }
            Thread.sleep(forTimeInterval: 1)
        }
        guard button != nil else {
            throw SmokeFailure("\"Buyurtma berish\" tugmasi yoqilmadi")
        }
        var dialogShown = false
        for _ in 0..<4 {
            Thread.sleep(forTimeInterval: 2)
            try tap("Buyurtma berish", excluding: ["Buyurtmani tasdiqlaysizmi"])
            if (try? waitFor("Buyurtmani tasdiqlaysizmi?", timeout: 6)) != nil {
                dialogShown = true
                break
            }
        }
        guard dialogShown else {
            throw SmokeFailure("Tasdiqlash oynasi ochilmadi")
        }
        shot("08b-confirm-dialog")
        let alertButton = app.alerts.buttons["Tasdiqlash"]
        if alertButton.exists {
            alertButton.tap()
        } else {
            try tap("Tasdiqlash", exact: true)
        }
        _ = try waitFor("Kafe javobi kutilmoqda", timeout: 60)
        Thread.sleep(forTimeInterval: 1)
    }

    // MARK: - Sinov serveri

    /// Sinov serverida oxirgi buyurtmaning holatini o'zgartiradi (kafe xodimi o'rnida).
    func staff(_ status: String, reason: String? = nil) throws {
        var query = ["order": "latest", "to": status]
        if let reason = reason {
            query["reason"] = reason
        }
        _ = try control("/status", query)
    }

    /// Boshqaruv serveriga GET so'rov. 200 bo'lmasa xato.
    func control(_ path: String, _ query: [String: String]) throws -> String {
        guard var components = URLComponents(string: controlURL + path) else {
            throw SmokeFailure("Noto'g'ri boshqaruv manzili: \(controlURL)\(path)")
        }
        if !query.isEmpty {
            components.queryItems = query.keys.sorted().map { URLQueryItem(name: $0, value: query[$0]) }
            // "+" so'rovda bo'sh joy deb o'qiladi: aniq kodlab yuboramiz
            components.percentEncodedQuery = components.percentEncodedQuery?
                .replacingOccurrences(of: "+", with: "%2B")
        }
        guard let url = components.url else {
            throw SmokeFailure("Noto'g'ri boshqaruv manzili: \(path)")
        }
        var request = URLRequest(url: url)
        request.timeoutInterval = 120
        let reply = ControlReply()
        let semaphore = DispatchSemaphore(value: 0)
        let task = URLSession.shared.dataTask(with: request) { data, response, error in
            if let http = response as? HTTPURLResponse {
                reply.status = http.statusCode
            }
            if let data = data {
                reply.text = String(decoding: data, as: UTF8.self)
            } else if let error = error {
                reply.text = error.localizedDescription
            }
            semaphore.signal()
        }
        task.resume()
        if semaphore.wait(timeout: .now() + 130) == .timedOut {
            task.cancel()
            throw SmokeFailure("Boshqaruv serveri javob bermadi: \(url.absoluteString)")
        }
        let text = reply.text.trimmingCharacters(in: .whitespacesAndNewlines)
        print("[kafe] \(path) \(query) -> \(reply.status): \(text)")
        guard reply.status == 200 else {
            throw SmokeFailure("Boshqaruv serveri \(path): \(reply.status) \(text)")
        }
        return text
    }

    // MARK: - Ekran bilan ishlash

    /// Yozuvi shu matnni o'z ichiga olgan birinchi element. Avval tugmalar, keyin matnlar, keyin qolgani.
    func find(_ text: String, exact: Bool = false, excluding: [String] = []) -> XCUIElement? {
        let predicate = exact
            ? NSPredicate(format: "label == %@", text)
            : NSPredicate(format: "label CONTAINS %@", text)
        let queries: [XCUIElementQuery] = [
            app.buttons, app.staticTexts, app.textFields, app.descendants(matching: .any),
        ]
        for query in queries {
            let matches = query.matching(predicate)
            let count = matches.count
            if count == 0 {
                continue
            }
            var fallback: XCUIElement?
            for index in 0..<min(count, 25) {
                let element = matches.element(boundBy: index)
                guard element.exists else { continue }
                if !excluding.isEmpty {
                    let label = element.label
                    if excluding.contains(where: { label.contains($0) }) {
                        continue
                    }
                }
                if element.isHittable {
                    return element
                }
                if fallback == nil {
                    fallback = element
                }
            }
            if let fallback = fallback {
                return fallback
            }
        }
        return nil
    }

    @discardableResult
    func waitFor(_ text: String, timeout: TimeInterval = 45, exact: Bool = false,
                 excluding: [String] = []) throws -> XCUIElement {
        let deadline = Date().addingTimeInterval(timeout)
        repeat {
            dismissSystemAlerts()
            if let element = find(text, exact: exact, excluding: excluding) {
                return element
            }
            Thread.sleep(forTimeInterval: 1)
        } while Date() < deadline
        throw SmokeFailure("Ekranda topilmadi: '\(text)'")
    }

    func waitGone(_ text: String, timeout: TimeInterval = 20) throws {
        let deadline = Date().addingTimeInterval(timeout)
        repeat {
            if find(text) == nil {
                return
            }
            Thread.sleep(forTimeInterval: 1)
        } while Date() < deadline
        throw SmokeFailure("Ekrandan yo'qolmadi: '\(text)'")
    }

    func waitEnabled(_ element: XCUIElement, timeout: TimeInterval) -> Bool {
        let deadline = Date().addingTimeInterval(timeout)
        repeat {
            if element.exists && element.isEnabled {
                return true
            }
            Thread.sleep(forTimeInterval: 0.5)
        } while Date() < deadline
        return false
    }

    func tap(_ text: String, timeout: TimeInterval = 45, exact: Bool = false,
             excluding: [String] = []) throws {
        let element = try waitFor(text, timeout: timeout, exact: exact, excluding: excluding)
        tapElement(element)
    }

    func tapElement(_ element: XCUIElement) {
        if element.isHittable {
            element.tap()
        } else {
            // Ba'zi SwiftUI elementlari "hittable" emas deb ko'rinadi: markaziga bosamiz
            element.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
        }
        Thread.sleep(forTimeInterval: 1.5)
    }

    /// Element ko'rinmasa, ekranni pastga surib izlaydi.
    func findScrolling(_ text: String, attempts: Int = 6) -> XCUIElement? {
        for _ in 0..<attempts {
            if let element = find(text) {
                return element
            }
            app.swipeUp()
            Thread.sleep(forTimeInterval: 1.5)
        }
        return nil
    }

    func typeIntoFirstField(_ text: String) throws {
        let field = app.textFields.firstMatch
        guard field.waitForExistence(timeout: 20) else {
            throw SmokeFailure("Matn maydoni topilmadi")
        }
        for _ in 0..<3 {
            field.tap()
            Thread.sleep(forTimeInterval: 1)
            field.typeText(text)
            Thread.sleep(forTimeInterval: 1)
            let value = (field.value as? String) ?? ""
            if value.contains(text) {
                break
            }
        }
        // Klaviaturani yopamiz: pastdagi tugmalarni to'sib qo'ymasin
        let returnKey = app.keyboards.buttons.matching(
            NSPredicate(format: "label IN %@", ["Return", "return", "Done", "done", "Go"] as NSArray)
        ).firstMatch
        if returnKey.exists {
            returnKey.tap()
        }
        Thread.sleep(forTimeInterval: 1)
    }

    /// Orqaga: ekrandagi "Orqaga" tugmasi, bo'lmasa chap chetdan surish (iOS swipe-back).
    func goBack() throws {
        dismissSystemAlerts()
        if let back = find("Orqaga", exact: true), back.isHittable {
            back.tap()
        } else {
            let start = app.coordinate(withNormalizedOffset: CGVector(dx: 0.01, dy: 0.5))
            let end = app.coordinate(withNormalizedOffset: CGVector(dx: 0.85, dy: 0.5))
            start.press(forDuration: 0.05, thenDragTo: end)
        }
        Thread.sleep(forTimeInterval: 2)
    }

    /// Pastdan chiqqan oynani (taom haqida) pastga surib yopadi.
    func closeSheet() {
        let top = app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.12))
        let bottom = app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.98))
        top.press(forDuration: 0.05, thenDragTo: bottom)
        Thread.sleep(forTimeInterval: 1.5)
    }

    /// Tizimning ruxsat oynasi (springboard) ochiq bo'lsa, ruxsat beradi.
    func dismissSystemAlerts() {
        let alert = springboard.alerts.firstMatch
        guard alert.exists else { return }
        for title in allowButtonTitles {
            let button = alert.buttons[title]
            if button.exists {
                print("[ogohlantirish] tizim oynasi: \(alert.label) -> \(title)")
                button.tap()
                Thread.sleep(forTimeInterval: 1)
                return
            }
        }
    }

    func visibleTexts() -> [String] {
        let texts = app.staticTexts.allElementsBoundByIndex.prefix(80)
        return texts.compactMap { element -> String? in
            let label = element.label.trimmingCharacters(in: .whitespacesAndNewlines)
            return label.isEmpty ? nil : label
        }
    }

    // MARK: - Rasmlar

    func shot(_ name: String) {
        let screenshot = XCUIScreen.main.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = name
        attachment.lifetime = .keepAlways
        test.add(attachment)
        if let dir = screenshotDir {
            let file = dir.appendingPathComponent("\(name).png")
            do {
                try screenshot.pngRepresentation.write(to: file)
                print("[rasm] \(name).png")
            } catch {
                print("[ogohlantirish] rasmni yozib bo'lmadi \(file.path): \(error)")
            }
        }
    }
}
