package uz.amora.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import uz.amora.app.data.decodeCart
import uz.amora.app.data.encodeCart
import uz.amora.app.data.resolveImageUrl
import uz.amora.app.util.distanceKm
import uz.amora.app.util.formatDateTime
import uz.amora.app.util.formatNumber
import uz.amora.app.util.formatPhone
import uz.amora.app.util.formatSum
import uz.amora.app.util.formatTime
import uz.amora.app.util.fullPhone
import uz.amora.app.util.localPhoneDigits
import uz.amora.app.util.parseIsoMillis

class FormatTest {
    @Test
    fun sumIsGroupedByThousands() {
        assertEquals("0 so'm", formatSum(0))
        assertEquals("900 so'm", formatSum(900))
        assertEquals("25 000 so'm", formatSum(25000))
        assertEquals("1 250 000 so'm", formatSum(1250000))
        assertEquals("-5 000", formatNumber(-5000))
    }

    @Test
    fun phoneDigitsAreTakenFromAnyInput() {
        assertEquals("901234567", localPhoneDigits("90 123 45 67"))
        assertEquals("901234567", localPhoneDigits("+998 (90) 123-45-67"))
        assertEquals("901234567", localPhoneDigits("998901234567"))
        assertEquals("9012", localPhoneDigits("9012"))
        assertEquals("901234567", localPhoneDigits("9012345678888"))
        assertEquals("", localPhoneDigits("abc"))
    }

    @Test
    fun fullPhoneNeedsNineDigits() {
        assertEquals("+998901234567", fullPhone("901234567"))
        assertNull(fullPhone("90123456"))
        assertNull(fullPhone(""))
    }

    @Test
    fun phoneIsFormattedForDisplay() {
        assertEquals("+998 90 123 45 67", formatPhone("+998901234567"))
        assertEquals("12345", formatPhone("12345"))
    }

    @Test
    fun isoTimeIsParsed() {
        val expected = 1794751402000L // 2026-11-15T14:03:22Z
        assertEquals(expected, parseIsoMillis("2026-11-15T14:03:22Z"))
        assertEquals(expected, parseIsoMillis("2026-11-15T14:03:22.123456Z"))
        assertEquals(expected, parseIsoMillis("2026-11-15T14:03:22+00:00"))
        assertEquals(expected, parseIsoMillis("2026-11-15T19:03:22.5+05:00"))
        assertEquals(expected, parseIsoMillis("2026-11-15T14:03:22"))
        assertNull(parseIsoMillis("kecha"))
        assertNull(parseIsoMillis(""))
    }

    @Test
    fun timeIsShownInCafeTimeZone() {
        assertEquals("19:03", formatTime("2026-11-15T14:03:22Z"))
        assertEquals("15-noyabr, 19:03", formatDateTime("2026-11-15T14:03:22.123456Z"))
        // Yarim tundan o'tganda sana ham o'zgaradi
        assertEquals("1-yanvar, 00:30", formatDateTime("2026-12-31T19:30:00Z"))
        assertEquals("", formatDateTime("noto'g'ri"))
    }

    @Test
    fun distanceMatchesKnownValue() {
        // Samarqand Registon -> Toshkent markazi: taxminan 265 km
        val km = distanceKm(39.6547, 66.9758, 41.3111, 69.2797)
        assertTrue("masofa: $km", km > 255 && km < 275)
        assertEquals(0.0, distanceKm(41.0, 69.0, 41.0, 69.0), 1e-9)
    }

    @Test
    fun cartSurvivesSaveAndLoad() {
        val cart = linkedMapOf(3 to 2, 1 to 1, 7 to 5)
        assertEquals(cart, decodeCart(encodeCart(cart)))
        assertEquals(listOf(3, 1, 7), decodeCart(encodeCart(cart)).keys.toList())
        assertEquals(emptyMap<Int, Int>(), decodeCart(null))
        assertEquals(emptyMap<Int, Int>(), decodeCart(""))
        assertEquals(mapOf(2 to 1), decodeCart("x:1;2:1;3:0;4;5:-2"))
        assertEquals(mapOf(1 to 50), decodeCart("1:999"))
    }

    @Test
    fun imageUrlFollowsAppServerAddress() {
        val base = "https://amora.example.uz"
        assertEquals(
            "https://amora.example.uz/media/products/a.jpg",
            resolveImageUrl(base, "http://10.0.0.5:8000/media/products/a.jpg"),
        )
        assertEquals(
            "https://amora.example.uz/media/products/a.jpg",
            resolveImageUrl("$base/", "https://amora.example.uz/media/products/a.jpg"),
        )
        assertEquals("https://cdn.example.com/a.jpg", resolveImageUrl(base, "https://cdn.example.com/a.jpg"))
        assertNull(resolveImageUrl(base, null))
        assertNull(resolveImageUrl(base, ""))
    }
}
