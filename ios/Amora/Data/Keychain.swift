/// Minimal Keychain wrapper (Security framework, kSecClassGenericPassword, service "uz.amora.app").
/// Used by `SessionStore` for the device (auth) token.
///
/// Surface:
/// - `enum Keychain`
///   - `static let service: String`
///   - `static func read(_ account: String) -> String?`
///   - `static func write(_ account: String, _ value: String?)`   // nil deletes

import Foundation
import Security

enum Keychain {
    static let service = "uz.amora.app"

    private static func baseQuery(_ account: String) -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
    }

    static func read(_ account: String) -> String? {
        var query = baseQuery(account)
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        guard status == errSecSuccess, let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    static func write(_ account: String, _ value: String?) {
        let query = baseQuery(account)
        SecItemDelete(query as CFDictionary)
        guard let value, let data = value.data(using: .utf8) else { return }
        var attributes = query
        attributes[kSecValueData as String] = data
        // Orqa fonda ham o'qilsin (jonli ulanish, bildirishnomalar)
        attributes[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        SecItemAdd(attributes as CFDictionary, nil)
    }
}
