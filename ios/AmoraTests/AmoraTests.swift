//
//  AmoraTests.swift
//  AmoraTests
//
//  Server kerak bo'lmagan tez sinovlar: SSE oqimini o'qish, buyurtma holatlari tartibi,
//  ro'yxatlarni ehtiyotkor o'qish (bitta buzuq element butun ro'yxatni bo'shatmaydi),
//  qidiruv matnini bir xil ko'rinishga keltirish.
//

import XCTest
@testable import Amora

final class SseParserTests: XCTestCase {
    private func feed(_ lines: [String]) -> [SseMessage] {
        var parser = SseParser()
        return lines.compactMap { parser.feed($0) }
    }

    func testEventWithData() {
        let messages = feed(["event: order", "data: {\"order_id\": 7}", ""])
        XCTAssertEqual(messages, [SseMessage(name: "order", data: "{\"order_id\": 7}")])
    }

    func testCommentAndEmptyMessageAreIgnored() {
        XCTAssertEqual(feed([": ping", "", "event: menu", ""]), [])
    }

    func testDefaultNameAndMultilineData() {
        let messages = feed(["data: a", "data:b", "", "event: shop", "data", ""])
        XCTAssertEqual(messages, [
            SseMessage(name: "message", data: "a\nb"),
            SseMessage(name: "shop", data: ""),
        ])
    }

    func testStateResetsBetweenMessages() {
        let messages = feed(["event: order", "data: 1", "", "data: 2", ""])
        XCTAssertEqual(messages.map { $0.name }, ["order", "message"])
    }

    func testParseLiveEvent() {
        XCTAssertEqual(parseLiveEvent(SseMessage(name: "ready", data: "{}")), .resync)
        XCTAssertEqual(parseLiveEvent(SseMessage(name: "menu", data: "{}")), .menuChanged)
        XCTAssertEqual(parseLiveEvent(SseMessage(name: "shop", data: "{}")), .shopChanged)
        XCTAssertNil(parseLiveEvent(SseMessage(name: "unknown", data: "{}")))
        XCTAssertNil(parseLiveEvent(SseMessage(name: "order", data: "not json")))
        let order = SseMessage(
            name: "order",
            data: "{\"order_id\": 12, \"status\": \"rejected\", \"reject_reason\": \"Taom tugadi\"}"
        )
        XCTAssertEqual(
            parseLiveEvent(order),
            .orderChanged(OrderChange(orderId: 12, status: "rejected", statusLabel: "", rejectReason: "Taom tugadi"))
        )
    }
}

final class StatusOrderTests: XCTestCase {
    func testFirstStatusIsAlwaysNew() {
        XCTAssertTrue(isNewerStatus(nil, OrderStatus.new))
        XCTAssertTrue(isNewerStatus(nil, OrderStatus.delivered))
    }

    func testOnlyForward() {
        XCTAssertTrue(isNewerStatus(OrderStatus.new, OrderStatus.accepted))
        XCTAssertTrue(isNewerStatus(OrderStatus.accepted, OrderStatus.delivering))
        XCTAssertTrue(isNewerStatus(OrderStatus.delivering, OrderStatus.delivered))
        XCTAssertTrue(isNewerStatus(OrderStatus.new, OrderStatus.rejected))
        XCTAssertFalse(isNewerStatus(OrderStatus.accepted, OrderStatus.accepted))
        XCTAssertFalse(isNewerStatus(OrderStatus.delivering, OrderStatus.accepted))
        XCTAssertFalse(isNewerStatus(OrderStatus.delivered, OrderStatus.delivering))
    }

    func testFinalStatusesDoNotReplaceEachOther() {
        XCTAssertFalse(isNewerStatus(OrderStatus.delivered, OrderStatus.cancelled))
        XCTAssertFalse(isNewerStatus(OrderStatus.rejected, OrderStatus.delivered))
    }

    func testOrderChangeFromPushPayload() {
        let change = OrderNotifier.orderChange(from: [
            "type": "order", "order_id": 31, "status": "delivering",
        ])
        XCTAssertEqual(change, OrderChange(orderId: 31, status: "delivering"))
        // FCM uslubidagi satr ko'rinishidagi raqam ham qabul qilinadi
        XCTAssertEqual(
            OrderNotifier.orderChange(from: ["order_id": "32", "status": "rejected", "reject_reason": "Yopiq"]),
            OrderChange(orderId: 32, status: "rejected", statusLabel: "", rejectReason: "Yopiq")
        )
        XCTAssertNil(OrderNotifier.orderChange(from: ["order_id": 31]))
        XCTAssertNil(OrderNotifier.orderChange(from: ["status": "accepted"]))
    }
}

final class LenientDecodingTests: XCTestCase {
    private func decode<T: Decodable>(_ type: T.Type, _ json: String) throws -> T {
        try JSONDecoder().decode(type, from: Data(json.utf8))
    }

    func testBadProductIsDroppedOthersSurvive() throws {
        let menu = try decode(MenuData.self, """
        {"categories": [{"id": 1, "name": "Taomlar"}, {"name": "id yo'q"}, 5],
         "products": [
            {"id": 1, "name": "Osh", "price": 30000},
            {"id": "buzuq", "name": "Xato"},
            null,
            {"id": 2, "name": "Lag'mon", "price": "narx emas", "is_available": false}
         ]}
        """)
        XCTAssertEqual(menu.categories.map { $0.id }, [1])
        XCTAssertEqual(menu.products.map { $0.id }, [1, 2])
        XCTAssertEqual(menu.products[1].price, 0)
        XCTAssertFalse(menu.products[1].isAvailable)
    }

    func testMissingOrMistypedListIsEmpty() throws {
        XCTAssertEqual(try decode(MenuData.self, "{}"), MenuData())
        XCTAssertEqual(try decode(MenuData.self, "{\"products\": \"yo'q\", \"categories\": null}"), MenuData())
    }

    func testBadOrderIsDroppedFromList() throws {
        let list = try decode(OrderList.self, """
        {"orders": [
            {"id": 10, "status": "new", "items": [{"name": "Osh", "quantity": 2}, "buzuq"], "history": [1]},
            {"status": "id yo'q"},
            {"id": 11, "status": "delivered"}
         ], "has_more": true}
        """)
        XCTAssertEqual(list.orders.map { $0.id }, [10, 11])
        XCTAssertEqual(list.orders[0].items.count, 1)
        XCTAssertEqual(list.orders[0].items[0].quantity, 2)
        XCTAssertEqual(list.orders[0].history, [])
        XCTAssertTrue(list.hasMore)
    }

    func testQuoteLines() throws {
        let quote = try decode(Quote.self, """
        {"lines": [{"product_id": 1, "name": "Osh", "quantity": 1}, {"name": "raqamsiz"}],
         "problems": [{"code": "x", "message": "y"}, 3], "total": 5}
        """)
        XCTAssertEqual(quote.lines.map { $0.productId }, [1])
        XCTAssertEqual(quote.problems.count, 1)
        XCTAssertEqual(quote.total, 5)
    }
}

final class SearchNormalizerTests: XCTestCase {
    func testApostropheVariantsBecomePlain() {
        for variant in ["\u{2019}", "\u{2018}", "\u{02BB}", "\u{02BC}", "`"] {
            XCTAssertEqual(normalizeSearchText("Qo\(variant)y go\(variant)shti"), "qo'y go'shti")
        }
    }

    func testCaseDiacriticsAndWhitespace() {
        XCTAssertEqual(normalizeSearchText("  LAG'MON \n"), "lag'mon")
        XCTAssertEqual(normalizeSearchText("Café Crème"), "cafe creme")
    }

    func testSearchFindsEitherSpelling() {
        let menu = MenuData(
            categories: [],
            products: [
                Product(id: 1, name: "Qo\u{02BB}y go\u{02BB}shti", price: 1),
                Product(id: 2, name: "Somsa", description: "Mol go'shtli", price: 1),
                Product(id: 3, name: "Choy", price: 1),
            ]
        )
        // iPhone klaviaturasi "’" yozadi
        XCTAssertEqual(searchMenuProducts(menu, "GO\u{2019}SHT").map { $0.id }, [1, 2])
        XCTAssertEqual(searchMenuProducts(menu, " choy ").map { $0.id }, [3])
        XCTAssertEqual(searchMenuProducts(menu, "palov"), [])
    }
}

final class HashTests: XCTestCase {
    func testSha256Hex() {
        XCTAssertEqual(
            sha256Hex("abc"),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        )
        XCTAssertTrue(isSha256Hex(sha256Hex("kalit|manzil")))
        XCTAssertFalse(isSha256Hex("token-123|abcdef"))
        XCTAssertFalse(isSha256Hex(String(repeating: "G", count: 64)))
    }
}
