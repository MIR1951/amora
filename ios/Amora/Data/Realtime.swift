/// Live updates over Server-Sent Events, `GET /api/v1/events` (port of android data/Realtime.kt).
/// Protocol (backend/app/api/events.py): `event: ready|menu|shop|order|resync` + `data: {json}` + blank line;
/// lines starting with ":" are pings (every 20 s). Reconnects with backoff 1,2,5,10,20,30 s.
///
/// Surface:
/// - `struct OrderChange: Equatable, Hashable { var orderId: Int; var status: String; var statusLabel: String = ""; var rejectReason: String? = nil }`
/// - `enum LiveEvent: Equatable { case resync, menuChanged, shopChanged, orderChanged(OrderChange) }`
///   - `var orderChange: OrderChange?`   // non-nil only for `.orderChanged`
/// - `struct SseMessage: Equatable { var name: String; var data: String }`
/// - `struct SseParser { mutating func feed(_ line: String) -> SseMessage? }`
/// - `func parseLiveEvent(_ message: SseMessage) -> LiveEvent?`
/// - `@MainActor @Observable final class Realtime`
///   - `init(baseUrl: String, tokenProvider: @escaping @MainActor () -> String?)`
///   - `private(set) var connected: Bool`  // live stream is up (screens poll less often when true)
///   - `var isRunning: Bool`
///   - `func start()`, `func stop()`, `func restart()`
///   - `func events() -> AsyncStream<LiveEvent>`  // new subscriber stream each call; ends when the consuming task is cancelled
///     usage: `.task { for await event in container.realtime.events() { ... } }`

import Foundation
import Observation

/// Mijozning buyurtmasi boshqa holatga o'tdi.
struct OrderChange: Equatable, Hashable {
    var orderId: Int
    var status: String
    var statusLabel: String = ""
    var rejectReason: String? = nil
}

/// Serverdan kelgan jonli xabar: ilova shunga qarab kerakli ma'lumotni o'zi qayta o'qiydi.
enum LiveEvent: Equatable {
    /// Ulanish (qayta) o'rnatildi yoki ba'zi xabarlar o'tkazib yuborilgan bo'lishi mumkin.
    case resync
    /// Taom qo'shildi, o'zgardi, tugadi yoki o'chirildi.
    case menuChanged
    /// Kafe sozlamalari o'zgardi: ish vaqti, yetkazish narxi, buyurtma qabul qilish.
    case shopChanged
    /// Mijozning buyurtmasi boshqa holatga o'tdi.
    case orderChanged(OrderChange)

    var orderChange: OrderChange? {
        if case .orderChanged(let change) = self { return change }
        return nil
    }
}

/// Server-Sent Events oqimidagi bitta xabar: nomi va matni.
struct SseMessage: Equatable {
    var name: String
    var data: String
}

/// SSE oqimini satrma-satr o'qiydi. Xabar bo'sh satr bilan tugaydi; ":" bilan boshlangan
/// satr izoh (server aloqa tirikligini bildirish uchun yuboradigan "ping").
struct SseParser {
    private var name: String?
    private var data = ""
    private var hasData = false

    init() {}

    /// Satrni qabul qiladi. Shu satr bilan xabar tugagan bo'lsa, uni qaytaradi.
    mutating func feed(_ line: String) -> SseMessage? {
        if line.isEmpty {
            let message = hasData ? SseMessage(name: name ?? "message", data: data) : nil
            name = nil
            data = ""
            hasData = false
            return message
        }
        if line.hasPrefix(":") { return nil }
        let field: String
        var value: String
        if let colon = line.firstIndex(of: ":") {
            field = String(line[line.startIndex..<colon])
            value = String(line[line.index(after: colon)...])
            if value.hasPrefix(" ") { value.removeFirst() }
        } else {
            field = line
            value = ""
        }
        switch field {
        case "event":
            name = value
        case "data":
            if hasData { data.append("\n") }
            data.append(value)
            hasData = true
        default:
            break
        }
        return nil
    }
}

private struct OrderEventBody: Decodable {
    var orderId: Int
    var status: String
    var statusLabel: String
    var rejectReason: String?

    enum CodingKeys: String, CodingKey {
        case orderId = "order_id"
        case status
        case statusLabel = "status_label"
        case rejectReason = "reject_reason"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        orderId = try c.decode(Int.self, forKey: .orderId)
        status = try c.decode(String.self, forKey: .status)
        statusLabel = c.lenient(String.self, .statusLabel, "")
        rejectReason = c.lenientOptional(String.self, .rejectReason)
    }
}

/// Server xabarini ilova tushunadigan hodisaga aylantiradi. Notanish xabar bo'lsa nil.
func parseLiveEvent(_ message: SseMessage) -> LiveEvent? {
    switch message.name {
    case "ready", "resync":
        return .resync
    case "menu":
        return .menuChanged
    case "shop":
        return .shopChanged
    case "order":
        guard let body = try? JSONDecoder().decode(OrderEventBody.self, from: Data(message.data.utf8)) else {
            return nil
        }
        return .orderChanged(
            OrderChange(
                orderId: body.orderId,
                status: body.status,
                statusLabel: body.statusLabel,
                rejectReason: body.rejectReason
            )
        )
    default:
        return nil
    }
}

/// Server bilan doimiy ulanish (`GET /api/v1/events`). Ilova ochiq turganda ushlab turiladi.
/// Aloqa uzilsa, o'zi qayta ulanadi; server bu imkoniyatni bilmasa, ilova vaqti-vaqti bilan
/// so'rab turaveradi.
@MainActor
@Observable
final class Realtime {
    /// Ulanish hozir tirikmi. Tirik bo'lmasa, ekranlar serverdan tez-tez o'zi so'rab turadi.
    private(set) var connected = false

    private let url: URL?
    private let tokenProvider: @MainActor () -> String?
    private let session: URLSession

    @ObservationIgnored private var task: Task<Void, Never>?
    @ObservationIgnored private var subscribers: [UUID: AsyncStream<LiveEvent>.Continuation] = [:]
    @ObservationIgnored private var sawReady = false

    // Ketma-ket muvaffaqiyatsiz urinishlardan keyin kutish vaqti (ms)
    private static let retryDelaysMs: [UInt64] = [1_000, 2_000, 5_000, 10_000, 20_000, 30_000]

    init(baseUrl: String, tokenProvider: @escaping @MainActor () -> String?) {
        var base = baseUrl
        while base.hasSuffix("/") { base.removeLast() }
        self.url = URL(string: base + "/api/v1/events")
        self.tokenProvider = tokenProvider
        let config = URLSessionConfiguration.default
        // Server har 20 soniyada "ping" yuboradi: 45 soniya jimlik ulanish o'lganini bildiradi
        config.timeoutIntervalForRequest = 45
        config.timeoutIntervalForResource = 7 * 24 * 3600
        config.requestCachePolicy = .reloadIgnoringLocalCacheData
        config.urlCache = nil
        config.waitsForConnectivity = false
        self.session = URLSession(configuration: config)
    }

    var isRunning: Bool { task != nil }

    /// Jonli xabarlar oqimi. Har bir chaqiruv alohida obunachi; iste'molchi vazifa bekor
    /// qilinganda obuna o'zi tugaydi.
    func events() -> AsyncStream<LiveEvent> {
        let id = UUID()
        let pair = AsyncStream<LiveEvent>.makeStream(of: LiveEvent.self, bufferingPolicy: .bufferingNewest(64))
        subscribers[id] = pair.continuation
        pair.continuation.onTermination = { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.removeSubscriber(id)
            }
        }
        return pair.stream
    }

    private func removeSubscriber(_ id: UUID) {
        subscribers[id] = nil
    }

    func start() {
        if isRunning { return }
        task = Task { [weak self] in
            await self?.runForever()
        }
    }

    func stop() {
        task?.cancel()
        task = nil
        connected = false
    }

    /// Kirish kaliti o'zgarganda: buyurtma xabarlari yangi kalit egasiga kelishi kerak.
    func restart() {
        if !isRunning { return }
        stop()
        start()
    }

    private func broadcast(_ event: LiveEvent) {
        for continuation in subscribers.values {
            continuation.yield(event)
        }
    }

    private func runForever() async {
        var failures = 0
        while !Task.isCancelled {
            let wasConnected = await connectOnce()
            if Task.isCancelled { break }
            connected = false
            failures = wasConnected ? 0 : failures + 1
            let delays = Realtime.retryDelaysMs
            let delay = delays[min(failures, delays.count - 1)]
            do {
                try await Task.sleep(nanoseconds: delay * 1_000_000)
            } catch {
                break
            }
        }
    }

    /// Bir marta ulanadi va uzilguncha xabarlarni o'qiydi. Ulanish o'rnatilgan bo'lsa true.
    private func connectOnce() async -> Bool {
        guard let url else { return false }
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = 45
        request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
        request.setValue("no-cache", forHTTPHeaderField: "Cache-Control")
        if let token = tokenProvider(), !token.isEmpty {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        sawReady = false
        await Realtime.readStream(request: request, session: session) { [weak self] message in
            self?.handle(message)
        }
        return sawReady
    }

    private func handle(_ message: SseMessage) {
        if Task.isCancelled { return }
        if message.name == "ready" {
            sawReady = true
            connected = true
        }
        if let event = parseLiveEvent(message) {
            broadcast(event)
        }
    }

    /// Oqimni baytma-bayt o'qib, satrlarga ajratadi (`AsyncBytes.lines` bo'sh satrlarni tashlab
    /// yuboradi, SSE esa xabar oxirini aynan bo'sh satr bilan bildiradi). Asosiy oqimdan tashqarida ishlaydi.
    nonisolated private static func readStream(
        request: URLRequest,
        session: URLSession,
        onMessage: @escaping @MainActor (SseMessage) -> Void
    ) async {
        do {
            let (bytes, response) = try await session.bytes(for: request)
            guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
                return
            }
            var parser = SseParser()
            var buffer: [UInt8] = []
            var lastWasCR = false
            for try await byte in bytes {
                if byte == 0x0A || byte == 0x0D {
                    if byte == 0x0A && lastWasCR {
                        lastWasCR = false
                        continue
                    }
                    lastWasCR = byte == 0x0D
                    let line = String(decoding: buffer, as: UTF8.self)
                    buffer.removeAll(keepingCapacity: true)
                    if let message = parser.feed(line) {
                        await onMessage(message)
                    }
                } else {
                    lastWasCR = false
                    buffer.append(byte)
                }
            }
        } catch {
            // Aloqa uzildi yoki ulanish bekor qilindi: tashqaridagi sikl qayta ulanadi
        }
    }
}
