/// Hashing helper.
///
/// Surface:
/// - `func sha256Hex(_ text: String) -> String`   // 64 lowercase hex characters
/// - `func isSha256Hex(_ text: String) -> Bool`

import CryptoKit
import Foundation

/// Matnning SHA-256 xeshi (64 belgili hex). Maxfiy qiymatlarni (kirish kaliti) telefonda ochiq
/// saqlamaslik uchun: solishtirishga xeshning o'zi yetadi.
func sha256Hex(_ text: String) -> String {
    SHA256.hash(data: Data(text.utf8)).map { String(format: "%02x", $0) }.joined()
}

/// `sha256Hex` natijasiga o'xshaydimi (64 ta kichik hex belgi).
func isSha256Hex(_ text: String) -> Bool {
    text.count == 64 && text.allSatisfy { ("0"..."9").contains($0) || ("a"..."f").contains($0) }
}
