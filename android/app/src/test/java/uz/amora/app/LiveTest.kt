package uz.amora.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import uz.amora.app.data.LiveEvent
import uz.amora.app.data.SseMessage
import uz.amora.app.data.SseParser
import uz.amora.app.data.parseLiveEvent
import uz.amora.app.notify.orderNotice

class LiveTest {
    private fun feedAll(parser: SseParser, text: String): List<SseMessage> =
        text.split("\n").mapNotNull { parser.feed(it) }

    @Test
    fun parserSplitsStreamIntoMessages() {
        val stream = "event: ready\ndata: {}\n\n: ping\n\nevent: menu\ndata: {}\n\nevent: order\n" +
            "data: {\"order_id\":7,\"status\":\"accepted\"}\n\n"
        val messages = feedAll(SseParser(), stream)
        assertEquals(
            listOf(
                SseMessage("ready", "{}"),
                SseMessage("menu", "{}"),
                SseMessage("order", "{\"order_id\":7,\"status\":\"accepted\"}"),
            ),
            messages,
        )
    }

    @Test
    fun parserHandlesCommentsMultilineDataAndMissingNames() {
        val parser = SseParser()
        // Faqat izoh (ping): xabar emas
        assertEquals(emptyList<SseMessage>(), feedAll(parser, ": ping\n\n"))
        // Bir nechta "data" satri bitta xabarga birlashadi, nomsiz xabar "message" deb ataladi
        assertEquals(listOf(SseMessage("message", "a\nb")), feedAll(parser, "data: a\ndata:b\n\n"))
        // Ma'lumotsiz "event" satri xabar hisoblanmaydi va keyingi xabarga aralashmaydi
        assertEquals(listOf(SseMessage("shop", "{}")), feedAll(parser, "event: menu\n\nevent: shop\ndata: {}\n\n"))
        // Notanish maydonlar e'tiborga olinmaydi
        assertEquals(listOf(SseMessage("menu", "{}")), feedAll(parser, "id: 5\nretry: 1000\nevent: menu\ndata: {}\n\n"))
    }

    @Test
    fun serverMessagesBecomeLiveEvents() {
        assertEquals(LiveEvent.Resync, parseLiveEvent(SseMessage("ready", "{}")))
        assertEquals(LiveEvent.Resync, parseLiveEvent(SseMessage("resync", "{}")))
        assertEquals(LiveEvent.MenuChanged, parseLiveEvent(SseMessage("menu", "{}")))
        assertEquals(LiveEvent.ShopChanged, parseLiveEvent(SseMessage("shop", "{}")))
        assertEquals(
            LiveEvent.OrderChanged(7, "rejected", "Rad etildi", "Mahsulot tugadi"),
            parseLiveEvent(
                SseMessage(
                    "order",
                    "{\"order_id\":7,\"status\":\"rejected\",\"status_label\":\"Rad etildi\"," +
                        "\"reject_reason\":\"Mahsulot tugadi\",\"yangi_maydon\":1}",
                ),
            ),
        )
        assertEquals(
            LiveEvent.OrderChanged(8, "accepted"),
            parseLiveEvent(SseMessage("order", "{\"order_id\":8,\"status\":\"accepted\"}")),
        )
    }

    @Test
    fun brokenOrUnknownMessagesAreIgnored() {
        assertNull(parseLiveEvent(SseMessage("order", "{}")))
        assertNull(parseLiveEvent(SseMessage("order", "buzilgan")))
        assertNull(parseLiveEvent(SseMessage("kelajakdagi-xabar", "{}")))
    }

    @Test
    fun notificationTextDependsOnStatus() {
        assertEquals(
            "Buyurtma №7 qabul qilindi",
            orderNotice(LiveEvent.OrderChanged(7, "accepted"))?.title,
        )
        assertEquals("Kuryer yo'lda", orderNotice(LiveEvent.OrderChanged(7, "delivering"))?.title)
        assertEquals(
            "Buyurtma №7 yetkazildi. Yoqimli ishtaha!",
            orderNotice(LiveEvent.OrderChanged(7, "delivered"))?.text,
        )
        assertEquals(
            "Sabab: Mahsulot tugadi",
            orderNotice(LiveEvent.OrderChanged(7, "rejected", rejectReason = "Mahsulot tugadi"))?.text,
        )
        assertEquals(
            "Afsuski, kafe buyurtmani qabul qila olmadi.",
            orderNotice(LiveEvent.OrderChanged(7, "rejected", rejectReason = " "))?.text,
        )
        // Mijozning o'zi qilgan ishlar uchun bildirishnoma kerak emas
        assertNull(orderNotice(LiveEvent.OrderChanged(7, "new")))
        assertNull(orderNotice(LiveEvent.OrderChanged(7, "cancelled")))
    }
}
