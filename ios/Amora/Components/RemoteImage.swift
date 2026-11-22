/// Remote images: in-memory cache + downsampling to the displayed size (replaces AsyncImage for food photos).
///
/// Surface:
/// - `enum RemoteImagePhase { case loading, success(UIImage), failure }`
/// - `struct RemoteImage<Content: View>: View` - `RemoteImage(url: URL) { phase in ... }`; fills the space it is
///   given and loads the picture downsampled to that size (in pixels)
/// - `@MainActor final class ImageStore` (`static let shared`)
///   - `func cached(_ url: URL, maxPixel: Int) -> UIImage?`
///   - `func load(_ url: URL, maxPixel: Int) async -> UIImage?`
///   - `static func pixelBucket(_ size: CGSize, scale: CGFloat) -> Int`
///   - `nonisolated static func downsample(_ data: Data, maxPixel: Int) -> UIImage?`

import ImageIO
import SwiftUI
import UIKit

enum RemoteImagePhase {
    case loading
    case success(UIImage)
    case failure
}

/// Rasmlar ombori. Serverdagi rasm katta (yuzlab kilobayt, minglab piksel), ekranda esa kichik katakda
/// turadi: rasm ko'rsatiladigan o'lchamgacha kichraytirib ochiladi va xotirada shu holda saqlanadi.
/// Ro'yxat surilganda rasm qayta yuklanmaydi va qayta ochilmaydi. Fayllarning o'zi diskda
/// `URLCache.shared` da turadi (AmoraApp.configureUrlCache).
@MainActor
final class ImageStore {
    static let shared = ImageStore()

    private let cache = NSCache<NSString, UIImage>()
    private var inFlight: [String: Task<UIImage?, Never>] = [:]

    // Kichraytirilgan rasmlar bir necha o'lchamda saqlanadi: turli ekranlar bitta nusxadan foydalanadi
    private static let buckets = [160, 320, 480, 720, 1080, 1620]

    init() {
        // Xotira chegarasi (baytlarda): tizim xotira tanqisligida NSCache'ni o'zi ham tozalaydi
        cache.totalCostLimit = 64 * 1024 * 1024
    }

    /// Ko'rsatiladigan o'lcham (nuqtalarda) uchun rasmning uzun tomoni necha piksel bo'lishi kerak.
    /// Rasm katakni to'ldirib turadi (scaledToFill), tomonlar nisbati boshqacha bo'lishi mumkin: zaxira bilan.
    static func pixelBucket(_ size: CGSize, scale: CGFloat) -> Int {
        let wanted = Int((max(size.width, size.height) * max(scale, 1) * 1.5).rounded(.up))
        return buckets.first(where: { $0 >= wanted }) ?? buckets[buckets.count - 1]
    }

    private static func key(_ url: URL, _ maxPixel: Int) -> String {
        "\(maxPixel)|\(url.absoluteString)"
    }

    func cached(_ url: URL, maxPixel: Int) -> UIImage? {
        cache.object(forKey: ImageStore.key(url, maxPixel) as NSString)
    }

    /// Rasmni yuklaydi (yoki keshdan oladi). Yuklanmasa yoki rasm bo'lmasa nil.
    func load(_ url: URL, maxPixel: Int) async -> UIImage? {
        let key = ImageStore.key(url, maxPixel)
        if let image = cache.object(forKey: key as NSString) {
            return image
        }
        // Bir xil rasmni bir vaqtda bir nechta katak so'rasa, bitta yuklash yetadi
        if let running = inFlight[key] {
            return await running.value
        }
        let task = Task<UIImage?, Never>.detached(priority: .userInitiated) {
            guard let (data, response) = try? await URLSession.shared.data(from: url) else { return nil }
            if let http = response as? HTTPURLResponse, !(200...299).contains(http.statusCode) {
                return nil
            }
            return ImageStore.downsample(data, maxPixel: maxPixel)
        }
        inFlight[key] = task
        let image = await task.value
        inFlight[key] = nil
        if let image {
            let cost = Int(image.size.width * image.scale * image.size.height * image.scale * 4)
            cache.setObject(image, forKey: key as NSString, cost: cost)
        }
        return image
    }

    /// Rasmni to'liq ochmasdan, uzun tomoni `maxPixel` dan oshmaydigan nusxasini yaratadi.
    nonisolated static func downsample(_ data: Data, maxPixel: Int) -> UIImage? {
        let sourceOptions = [kCGImageSourceShouldCache: false] as CFDictionary
        guard let source = CGImageSourceCreateWithData(data as CFData, sourceOptions) else { return nil }
        let options = [
            kCGImageSourceCreateThumbnailFromImageAlways: true,
            kCGImageSourceShouldCacheImmediately: true,
            kCGImageSourceCreateThumbnailWithTransform: true,
            kCGImageSourceThumbnailMaxPixelSize: max(maxPixel, 1),
        ] as CFDictionary
        guard let image = CGImageSourceCreateThumbnailAtIndex(source, 0, options) else { return nil }
        return UIImage(cgImage: image)
    }
}

/// Internetdagi rasm: berilgan joyni egallaydi va rasmni shu o'lchamga mos kichraytirib yuklaydi.
/// Ko'rinishni (rasm, kutish, xato) chaqiruvchi chizadi.
struct RemoteImage<Content: View>: View {
    let url: URL
    @ViewBuilder let content: (RemoteImagePhase) -> Content

    @Environment(\.displayScale) private var displayScale
    @State private var loaded: UIImage?
    @State private var loadedKey: String?
    @State private var failedKey: String?

    init(url: URL, @ViewBuilder content: @escaping (RemoteImagePhase) -> Content) {
        self.url = url
        self.content = content
    }

    var body: some View {
        GeometryReader { geo in
            let maxPixel = ImageStore.pixelBucket(geo.size, scale: displayScale)
            let key = "\(maxPixel)|\(url.absoluteString)"
            content(phase(key: key, maxPixel: maxPixel))
                .frame(width: geo.size.width, height: geo.size.height)
                // O'lcham ma'lum bo'lgach (yoki o'zgargach) qayta ishga tushadi
                .task(id: "\(key)|\(geo.size.width > 0 && geo.size.height > 0)") {
                    await load(key: key, maxPixel: maxPixel, size: geo.size)
                }
        }
    }

    private func phase(key: String, maxPixel: Int) -> RemoteImagePhase {
        // Keshda bo'lsa darhol ko'rsatiladi: ro'yxat surilganda kutish to'lqini lip etib o'tmaydi
        if let image = ImageStore.shared.cached(url, maxPixel: maxPixel) {
            return .success(image)
        }
        if loadedKey == key, let loaded {
            return .success(loaded)
        }
        return failedKey == key ? .failure : .loading
    }

    private func load(key: String, maxPixel: Int, size: CGSize) async {
        // Joy hali o'lchanmagan: o'lcham ma'lum bo'lgach qayta chaqiriladi
        guard size.width > 0, size.height > 0 else { return }
        if ImageStore.shared.cached(url, maxPixel: maxPixel) != nil { return }
        let image = await ImageStore.shared.load(url, maxPixel: maxPixel)
        if Task.isCancelled { return }
        withAnimation(.easeInOut(duration: 0.25)) {
            if let image {
                loaded = image
                loadedKey = key
                failedKey = nil
            } else {
                failedKey = key
            }
        }
    }
}
