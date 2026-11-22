package uz.amora.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import uz.amora.app.data.Address
import uz.amora.app.data.PendingOrder
import uz.amora.app.data.STABLE_CONNECTION_MS
import uz.amora.app.data.isDefinitiveRejection
import uz.amora.app.data.nextFailures
import uz.amora.app.data.orderFingerprint
import uz.amora.app.data.orderKeyFor
import uz.amora.app.data.retryDelayMs
import uz.amora.app.data.sha256Hex
import uz.amora.app.ui.address.isMoreAccurate

class ReliabilityTest {
    // ---------- Buyurtma kaliti ----------

    @Test
    fun sameOrderKeepsItsKeyAcrossRetries() {
        val first = orderKeyFor(null, "savat-1") { "id-1" }
        assertEquals(PendingOrder("id-1", "savat-1"), first)
        // Javobi yo'qolgan buyurtma qayta yuborilmoqda (ilova qayta ochilgan bo'lsa ham): kalit o'sha
        val retry = orderKeyFor(first, "savat-1") { "id-2" }
        assertEquals(first, retry)
    }

    @Test
    fun changedOrderGetsNewKey() {
        val first = PendingOrder("id-1", "savat-1")
        val changed = orderKeyFor(first, "savat-2") { "id-2" }
        assertEquals(PendingOrder("id-2", "savat-2"), changed)
    }

    @Test
    fun fingerprintIgnoresCartOrderButNotContent() {
        val address = Address(41.3, 69.2, "2-qavat")
        val a = orderFingerprint(linkedMapOf(5 to 1, 2 to 3), address, "", "+998901234567", null)
        // Savat telefondan boshqa tartibda o'qilgan: o'sha buyurtma, kalit ham o'sha qolishi kerak
        val b = orderFingerprint(linkedMapOf(2 to 3, 5 to 1), address, "", "+998901234567", null)
        assertEquals(a, b)
        // Soni, izoh yoki promokod o'zgarsa, bu boshqa buyurtma
        assertNotEquals(a, orderFingerprint(mapOf(5 to 2, 2 to 3), address, "", "+998901234567", null))
        assertNotEquals(a, orderFingerprint(mapOf(5 to 1, 2 to 3), address, "achchiq", "+998901234567", null))
        assertNotEquals(a, orderFingerprint(mapOf(5 to 1, 2 to 3), address, "", "+998901234567", "AMORA10"))
    }

    @Test
    fun keyIsDroppedOnlyAfterDefinitiveRejection() {
        // Server aniq rad etdi: buyurtma yaratilmagan
        for (status in listOf(400, 401, 403, 404, 409, 422, 429)) assertTrue(isDefinitiveRejection(status))
        // Tarmoq xatosi (0), tushunarsiz javob (200), kutish vaqti tugadi (408), server xatosi (5xx):
        // buyurtma yaratilgan bo'lishi mumkin, kalit saqlanadi
        for (status in listOf(0, 200, 408, 500, 502, 503, 504)) assertFalse(isDefinitiveRejection(status))
    }

    // ---------- Jonli ulanish: qayta ulanish ----------

    @Test
    fun retryDelayStaysWithinJitterBounds() {
        val bases = longArrayOf(1_000, 2_000, 5_000, 10_000, 20_000, 30_000)
        for ((failures, base) in bases.withIndex()) {
            assertEquals(base * 7 / 10, retryDelayMs(failures, 0.0))
            assertEquals(base * 13 / 10, retryDelayMs(failures, 1.0))
            assertEquals(base, retryDelayMs(failures, 0.5))
            for (step in 0..20) {
                val delay = retryDelayMs(failures, step / 20.0)
                assertTrue(delay >= base * 7 / 10 && delay <= base * 13 / 10)
            }
        }
    }

    @Test
    fun retryDelayIsCappedAndToleratesBadInput() {
        // Urinishlar soni jadvaldan oshsa, oxirgi (eng uzun) vaqt olinadi
        assertEquals(30_000L, retryDelayMs(99, 0.5))
        assertEquals(1_000L, retryDelayMs(-3, 0.5))
        // Tasodifiy son chegaradan chiqsa ham kutish ±30% ichida qoladi
        assertEquals(700L, retryDelayMs(0, -5.0))
        assertEquals(1_300L, retryDelayMs(0, 5.0))
    }

    @Test
    fun failuresResetOnlyAfterStableConnection() {
        // Ulanmadi
        assertEquals(3, nextFailures(2, null))
        // Ulandi, lekin darhol uzildi: hisob nolga tushmaydi
        assertEquals(3, nextFailures(2, 0L))
        assertEquals(3, nextFailures(2, STABLE_CONNECTION_MS - 1))
        // Bir necha soniya yashadi: barqaror ulanish
        assertEquals(0, nextFailures(2, STABLE_CONNECTION_MS))
        assertEquals(0, nextFailures(7, 60_000L))
    }

    // ---------- Joylashuv aniqligi ----------

    @Test
    fun bestLocationIsTheMostAccurateSeen() {
        // Birinchi o'lchov har doim olinadi (aniqligi noma'lum bo'lsa ham)
        assertTrue(isMoreAccurate(null, null, hasBest = false))
        assertTrue(isMoreAccurate(800f, null, hasBest = false))
        // Aniqroq o'lchov avvalgisining o'rnini oladi, noaniqrog'i olmaydi
        assertTrue(isMoreAccurate(30f, 800f, hasBest = true))
        assertFalse(isMoreAccurate(900f, 800f, hasBest = true))
        assertFalse(isMoreAccurate(800f, 800f, hasBest = true))
        // Aniqligi noma'lum o'lchov ma'lumining o'rnini olmaydi, aksincha oladi
        assertFalse(isMoreAccurate(null, 800f, hasBest = true))
        assertTrue(isMoreAccurate(800f, null, hasBest = true))
    }

    // ---------- Iz (hash) ----------

    @Test
    fun sha256HexIsStableAndHidesInput() {
        assertEquals(
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            sha256Hex("abc"),
        )
        assertNotEquals(sha256Hex("kalit-1|manzil"), sha256Hex("kalit-2|manzil"))
        assertFalse(sha256Hex("kalit-1|manzil").contains("kalit-1"))
    }
}
