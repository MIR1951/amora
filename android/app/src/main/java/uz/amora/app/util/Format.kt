package uz.amora.app.util

import java.util.Calendar
import java.util.TimeZone
import kotlin.math.asin
import kotlin.math.cos
import kotlin.math.pow
import kotlin.math.sin
import kotlin.math.sqrt

// Bu fayldagi funksiyalar Android'ga bog'liq emas: ular oddiy testlar bilan tekshiriladi.

private const val COUNTRY_CODE = "+998"
const val LOCAL_PHONE_LENGTH = 9

/** 25000 -> "25 000 so'm" */
fun formatSum(amount: Int): String = formatNumber(amount) + " so'm"

/** 1250000 -> "1 250 000" */
fun formatNumber(amount: Int): String {
    val digits = kotlin.math.abs(amount.toLong()).toString()
    val grouped = StringBuilder()
    for ((index, char) in digits.withIndex()) {
        if (index > 0 && (digits.length - index) % 3 == 0) grouped.append(' ')
        grouped.append(char)
    }
    return if (amount < 0) "-$grouped" else grouped.toString()
}

/**
 * Foydalanuvchi yozgan yoki joylashtirgan matndan telefon raqamning mahalliy qismini
 * (kodsiz 9 ta raqam) ajratib oladi: "+998 90 123 45 67" -> "901234567".
 */
fun localPhoneDigits(input: String): String {
    val digits = input.filter { it in '0'..'9' }
    val local = if (digits.length > LOCAL_PHONE_LENGTH && digits.startsWith("998")) digits.drop(3) else digits
    return local.take(LOCAL_PHONE_LENGTH)
}

/** "901234567" -> "+998901234567". To'liq bo'lmasa null. */
fun fullPhone(localDigits: String): String? =
    if (localDigits.length == LOCAL_PHONE_LENGTH && localDigits.all { it in '0'..'9' }) {
        COUNTRY_CODE + localDigits
    } else {
        null
    }

/** "+998901234567" -> "+998 90 123 45 67". Boshqa ko'rinishdagi raqam o'zgarishsiz qaytadi. */
fun formatPhone(phone: String): String {
    val digits = phone.filter { it in '0'..'9' }
    if (digits.length != 12 || !digits.startsWith("998")) return phone
    return "+998 ${digits.substring(3, 5)} ${digits.substring(5, 8)} ${digits.substring(8, 10)} ${digits.substring(10, 12)}"
}

private val ISO_PATTERN =
    Regex("""^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(Z|[+-]\d{2}:?\d{2})?$""")

/** Server yuborgan vaqtni ("2026-11-15T14:03:22.123456Z") millisekundga aylantiradi. */
fun parseIsoMillis(text: String): Long? {
    val match = ISO_PATTERN.matchEntire(text.trim()) ?: return null
    val groups = match.groupValues
    val calendar = Calendar.getInstance(TimeZone.getTimeZone("UTC"))
    calendar.clear()
    calendar.set(
        groups[1].toInt(),
        groups[2].toInt() - 1,
        groups[3].toInt(),
        groups[4].toInt(),
        groups[5].toInt(),
        groups[6].toInt(),
    )
    return calendar.timeInMillis - offsetMillis(groups[7])
}

private fun offsetMillis(zone: String): Long {
    if (zone.isEmpty() || zone == "Z") return 0
    val sign = if (zone[0] == '-') -1 else 1
    val digits = zone.drop(1).replace(":", "")
    val hours = digits.substring(0, 2).toInt()
    val minutes = digits.substring(2, 4).toInt()
    return sign * (hours * 60L + minutes) * 60_000L
}

private val MONTHS = listOf(
    "yanvar", "fevral", "mart", "aprel", "may", "iyun",
    "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr",
)

private val CAFE_TIME_ZONE: TimeZone = TimeZone.getTimeZone("Asia/Tashkent")

private fun cafeCalendar(millis: Long): Calendar {
    val calendar = Calendar.getInstance(CAFE_TIME_ZONE)
    calendar.timeInMillis = millis
    return calendar
}

private fun twoDigits(value: Int): String = if (value < 10) "0$value" else value.toString()

/** "2026-11-15T14:03:22Z" -> "19:03" (kafe vaqti bilan). */
fun formatTime(iso: String): String {
    val millis = parseIsoMillis(iso) ?: return ""
    val calendar = cafeCalendar(millis)
    return twoDigits(calendar.get(Calendar.HOUR_OF_DAY)) + ":" + twoDigits(calendar.get(Calendar.MINUTE))
}

/** "2026-11-15T14:03:22Z" -> "15-noyabr, 19:03" (kafe vaqti bilan). */
fun formatDateTime(iso: String): String {
    val millis = parseIsoMillis(iso) ?: return ""
    val calendar = cafeCalendar(millis)
    val day = calendar.get(Calendar.DAY_OF_MONTH)
    val month = MONTHS[calendar.get(Calendar.MONTH)]
    return "$day-$month, " + twoDigits(calendar.get(Calendar.HOUR_OF_DAY)) + ":" +
        twoDigits(calendar.get(Calendar.MINUTE))
}

/** Ikki nuqta orasidagi masofa (km). Serverdagi hisob bilan bir xil formula. */
fun distanceKm(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
    val earthRadiusKm = 6371.0088
    val dLat = Math.toRadians(lat2 - lat1)
    val dLon = Math.toRadians(lon2 - lon1)
    val a = sin(dLat / 2).pow(2) +
        cos(Math.toRadians(lat1)) * cos(Math.toRadians(lat2)) * sin(dLon / 2).pow(2)
    return 2 * earthRadiusKm * asin(sqrt(a))
}
