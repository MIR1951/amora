/// Minimal Keychain wrapper (Security framework, kSecClassGenericPassword, service "uz.amora.app").
/// Used by `SessionStore` for the device (auth) token.
///
/// Surface:
/// - `enum Keychain`
///   - `static let service: String`
///   - `static func read(_ account: String) -> String?`
///   - `@discardableResult static func write(_ account: String, _ value: String?) -> Bool`   // nil deletes; false = failed

import Foundation
import Security
import os

enum Keychain {
    static let service = "uz.amora.app"

    private static let log = Logger(subsystem: "uz.amora.app", category: "keychain")

    private static func baseQuery(_ account: String) -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
    }

    /// Qidiruvda himoya darajasi ko'rsatilmaydi: eski daraja bilan saqlangan qiymat ham o'qiladi.
    static func read(_ account: String) -> String? {
        var query = baseQuery(account)
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        if status != errSecSuccess && status != errSecItemNotFound {
            log.error("Keychain o'qilmadi: \(status)")
        }
        guard status == errSecSuccess, let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    /// Qiymatni yozadi (nil bo'lsa o'chiradi). Yozilmasa false qaytadi: xato e'tiborsiz qolmaydi.
    @discardableResult
    static func write(_ account: String, _ value: String?) -> Bool {
        let query = baseQuery(account)
        guard let value else {
            let status = SecItemDelete(query as CFDictionary)
            return check(status, "o'chirish", allowMissing: true)
        }
        let attributes: [String: Any] = [
            kSecValueData as String: Data(value.utf8),
            // Orqa fonda ham o'qilsin (jonli ulanish, bildirishnomalar), lekin faqat shu qurilmada:
            // zaxira nusxa yoki boshqa qurilmaga ko'chmaydi. Eski daraja bilan saqlangan qiymat
            // shu yangilashda yangi darajaga o'tadi
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly,
        ]
        var status = SecItemUpdate(query as CFDictionary, attributes as CFDictionary)
        if status == errSecItemNotFound {
            status = SecItemAdd(query.merging(attributes) { _, new in new } as CFDictionary, nil)
        } else if status != errSecSuccess {
            // Yangilab bo'lmadi (masalan, eski yozuv buzilgan): o'chirib, qaytadan qo'shamiz
            log.error("Keychain yangilanmadi: \(status)")
            SecItemDelete(query as CFDictionary)
            status = SecItemAdd(query.merging(attributes) { _, new in new } as CFDictionary, nil)
        }
        return check(status, "yozish", allowMissing: false)
    }

    private static func check(_ status: OSStatus, _ action: String, allowMissing: Bool) -> Bool {
        if status == errSecSuccess || (allowMissing && status == errSecItemNotFound) {
            return true
        }
        log.error("Keychain: \(action, privacy: .public) bajarilmadi: \(status)")
        return false
    }
}
