/// Formatting helpers (port of android util/Format.kt). Pure Foundation, no UI.
///
/// Surface:
/// - `let localPhoneLength: Int`                                  // 9
/// - `func formatSum(_ amount: Int) -> String`                    // 25000 -> "25 000 so'm"
/// - `func formatNumber(_ amount: Int) -> String`                 // 1250000 -> "1 250 000"
/// - `func localPhoneDigits(_ input: String) -> String`           // "+998 90 123 45 67" -> "901234567"
/// - `func fullPhone(_ localDigits: String) -> String?`           // "901234567" -> "+998901234567"
/// - `func formatPhone(_ phone: String) -> String`                // "+998901234567" -> "+998 90 123 45 67"
/// - `func parseIsoDate(_ text: String) -> Date?`                 // server ISO time -> Date
/// - `func parseIsoMillis(_ text: String) -> Int64?`              // server ISO time -> epoch millis
/// - `func formatTime(_ iso: String) -> String`                   // -> "19:03" (Asia/Tashkent)
/// - `func formatDateTime(_ iso: String) -> String`               // -> "15-noyabr, 19:03" (Asia/Tashkent)
/// - `func distanceKm(_ lat1: Double, _ lon1: Double, _ lat2: Double, _ lon2: Double) -> Double`

import Foundation

private let countryCode = "+998"
let localPhoneLength = 9

/// 25000 -> "25 000 so'm". Bo'shliqlar uzilmaydigan (NBSP): summa ikki qatorga bo'linib qolmaydi.
func formatSum(_ amount: Int) -> String {
    formatNumber(amount) + "\u{00A0}so'm"
}

/// 1250000 -> "1 250 000"
func formatNumber(_ amount: Int) -> String {
    let digits = Array(String(Int64(amount).magnitude))
    var grouped = ""
    for (index, char) in digits.enumerated() {
        if index > 0 && (digits.count - index) % 3 == 0 {
            grouped.append("\u{00A0}")
        }
        grouped.append(char)
    }
    return amount < 0 ? "-" + grouped : grouped
}

private func asciiDigits(_ text: String) -> String {
    String(text.filter { $0 >= "0" && $0 <= "9" })
}

/// Telefon raqamning mahalliy qismi (kodsiz 9 ta raqam): "+998 90 123 45 67" -> "901234567".
func localPhoneDigits(_ input: String) -> String {
    let digits = asciiDigits(input)
    let local: String
    if digits.count > localPhoneLength && digits.hasPrefix("998") {
        local = String(digits.dropFirst(3))
    } else {
        local = digits
    }
    return String(local.prefix(localPhoneLength))
}

/// "901234567" -> "+998901234567". To'liq bo'lmasa nil.
func fullPhone(_ localDigits: String) -> String? {
    guard localDigits.count == localPhoneLength,
          asciiDigits(localDigits).count == localPhoneLength else { return nil }
    return countryCode + localDigits
}

/// "+998901234567" -> "+998 90 123 45 67". Boshqa ko'rinishdagi raqam o'zgarishsiz qaytadi.
func formatPhone(_ phone: String) -> String {
    let digits = Array(asciiDigits(phone))
    guard digits.count == 12, String(digits[0..<3]) == "998" else { return phone }
    return "+998 " + String(digits[3..<5]) + " " + String(digits[5..<8]) + " " +
        String(digits[8..<10]) + " " + String(digits[10..<12])
}

private let isoRegex: NSRegularExpression? = try? NSRegularExpression(
    pattern: "^(\\d{4})-(\\d{2})-(\\d{2})[T ](\\d{2}):(\\d{2}):(\\d{2})(?:\\.\\d+)?(Z|[+-]\\d{2}:?\\d{2})?$",
    options: []
)

private func utcCalendar() -> Calendar {
    var calendar = Calendar(identifier: .gregorian)
    calendar.timeZone = TimeZone(identifier: "UTC") ?? TimeZone(secondsFromGMT: 0)!
    return calendar
}

private func cafeCalendar() -> Calendar {
    var calendar = Calendar(identifier: .gregorian)
    calendar.timeZone = TimeZone(identifier: "Asia/Tashkent") ?? TimeZone(secondsFromGMT: 5 * 3600)!
    return calendar
}

private func offsetSeconds(_ zone: String) -> Int {
    if zone.isEmpty || zone == "Z" { return 0 }
    let sign = zone.hasPrefix("-") ? -1 : 1
    let digits = Array(zone.dropFirst().replacingOccurrences(of: ":", with: ""))
    guard digits.count >= 4,
          let hours = Int(String(digits[0..<2])),
          let minutes = Int(String(digits[2..<4])) else { return 0 }
    return sign * (hours * 60 + minutes) * 60
}

/// Server yuborgan vaqt ("2026-11-15T14:03:22.123456Z") -> Date.
func parseIsoDate(_ text: String) -> Date? {
    let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
    guard let regex = isoRegex else { return nil }
    let nsRange = NSRange(trimmed.startIndex..<trimmed.endIndex, in: trimmed)
    guard let match = regex.firstMatch(in: trimmed, options: [], range: nsRange) else { return nil }

    func group(_ index: Int) -> String {
        let range = match.range(at: index)
        guard range.location != NSNotFound, let swiftRange = Range(range, in: trimmed) else { return "" }
        return String(trimmed[swiftRange])
    }

    guard let year = Int(group(1)), let month = Int(group(2)), let day = Int(group(3)),
          let hour = Int(group(4)), let minute = Int(group(5)), let second = Int(group(6)) else {
        return nil
    }
    var components = DateComponents()
    components.year = year
    components.month = month
    components.day = day
    components.hour = hour
    components.minute = minute
    components.second = second
    guard let date = utcCalendar().date(from: components) else { return nil }
    return date.addingTimeInterval(TimeInterval(-offsetSeconds(group(7))))
}

/// Server yuborgan vaqtni millisekundga aylantiradi.
func parseIsoMillis(_ text: String) -> Int64? {
    guard let date = parseIsoDate(text) else { return nil }
    return Int64((date.timeIntervalSince1970 * 1000).rounded())
}

private let uzMonths = [
    "yanvar", "fevral", "mart", "aprel", "may", "iyun",
    "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr",
]

private func twoDigits(_ value: Int) -> String {
    value < 10 ? "0\(value)" : "\(value)"
}

/// "2026-11-15T14:03:22Z" -> "19:03" (kafe vaqti bilan).
func formatTime(_ iso: String) -> String {
    guard let date = parseIsoDate(iso) else { return "" }
    let parts = cafeCalendar().dateComponents([.hour, .minute], from: date)
    return twoDigits(parts.hour ?? 0) + ":" + twoDigits(parts.minute ?? 0)
}

/// "2026-11-15T14:03:22Z" -> "15-noyabr, 19:03" (kafe vaqti bilan).
func formatDateTime(_ iso: String) -> String {
    guard let date = parseIsoDate(iso) else { return "" }
    let parts = cafeCalendar().dateComponents([.day, .month, .hour, .minute], from: date)
    let monthIndex = max(0, min(11, (parts.month ?? 1) - 1))
    return "\(parts.day ?? 1)-\(uzMonths[monthIndex]), " +
        twoDigits(parts.hour ?? 0) + ":" + twoDigits(parts.minute ?? 0)
}

/// Ikki nuqta orasidagi masofa (km). Serverdagi hisob bilan bir xil formula.
func distanceKm(_ lat1: Double, _ lon1: Double, _ lat2: Double, _ lon2: Double) -> Double {
    let earthRadiusKm = 6371.0088
    let toRadians = Double.pi / 180
    let dLat = (lat2 - lat1) * toRadians
    let dLon = (lon2 - lon1) * toRadians
    let a = pow(sin(dLat / 2), 2) +
        cos(lat1 * toRadians) * cos(lat2 * toRadians) * pow(sin(dLon / 2), 2)
    return 2 * earthRadiusKm * asin(sqrt(a))
}
