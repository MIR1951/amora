package uz.amora.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import uz.amora.app.R

// Amora dizayn asosi ("Issiq tandir" maketi). To'rtta rang, har biri o'z ma'nosiga ega:
//   pomidor qizil  - faqat harakat uchun: tugma, "+", narx tanlagich
//   ko'mir         - kuchli bloklar: banner, savat paneli, buyurtma holati
//   non oq         - iliq fon, ustida oq kartochkalar
//   rayhon yashil  - faqat ijobiy holat: "Ochiq", "Bepul", "Yetkazildi"
// Kafe o'z logotipi va ranglarini bersa, faqat shu fayl o'zgaradi.

private val Ink = Color(0xFF17130F)
private val Cream = Color(0xFFF6F2EC)

private val LightColors = lightColorScheme(
    primary = Color(0xFFE5432A),
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFFFDECE7),
    onPrimaryContainer = Color(0xFFC7321C),
    secondary = Ink,
    onSecondary = Color(0xFFFFFFFF),
    secondaryContainer = Cream,
    onSecondaryContainer = Ink,
    tertiary = Color(0xFFF2A33A),
    onTertiary = Ink,
    tertiaryContainer = Color(0xFFFDF1DD),
    onTertiaryContainer = Color(0xFF6B4410),
    background = Cream,
    onBackground = Ink,
    surface = Color(0xFFFFFFFF),
    onSurface = Ink,
    surfaceVariant = Cream,
    onSurfaceVariant = Color(0xFF5E564F),
    outline = Color(0xFFD8D0C5),
    outlineVariant = Color(0xFFECE6DE),
    error = Color(0xFFC7321C),
    onError = Color(0xFFFFFFFF),
    errorContainer = Color(0xFFFDECE7),
    onErrorContainer = Color(0xFFC7321C),
    surfaceContainerLowest = Color(0xFFFFFFFF),
    surfaceContainerLow = Color(0xFFFFFFFF),
    surfaceContainer = Color(0xFFFFFFFF),
    surfaceContainerHigh = Color(0xFFFFFFFF),
    surfaceContainerHighest = Cream,
    surfaceTint = Color(0xFFFFFFFF),
    scrim = Color(0xFF000000),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFFF0563C),
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFF3D1B13),
    onPrimaryContainer = Color(0xFFFFB4A3),
    secondary = Color(0xFFF4EFE8),
    onSecondary = Ink,
    secondaryContainer = Color(0xFF28241F),
    onSecondaryContainer = Color(0xFFF4EFE8),
    tertiary = Color(0xFFF2A33A),
    onTertiary = Ink,
    tertiaryContainer = Color(0xFF443008),
    onTertiaryContainer = Color(0xFFFFDFA8),
    background = Color(0xFF12100E),
    onBackground = Color(0xFFF4EFE8),
    surface = Color(0xFF1D1A17),
    onSurface = Color(0xFFF4EFE8),
    surfaceVariant = Color(0xFF28241F),
    onSurfaceVariant = Color(0xFFB9B0A6),
    outline = Color(0xFF4A443E),
    outlineVariant = Color(0xFF2F2A25),
    error = Color(0xFFFF8A75),
    onError = Color(0xFF4A0F05),
    errorContainer = Color(0xFF3D1B13),
    onErrorContainer = Color(0xFFFFB4A3),
    surfaceContainerLowest = Color(0xFF12100E),
    surfaceContainerLow = Color(0xFF1D1A17),
    surfaceContainer = Color(0xFF1D1A17),
    surfaceContainerHigh = Color(0xFF24201C),
    surfaceContainerHighest = Color(0xFF28241F),
    surfaceTint = Color(0xFF1D1A17),
    scrim = Color(0xFF000000),
)

// Sarlavha va narxlar: Bricolage Grotesque (xarakterli, zich). Matn: Instrument Sans (toza, o'qilishi oson).
// Ikkalasi ham ochiq litsenziyali (OFL), matni android/licenses papkasida.
val HeadingFont = FontFamily(
    Font(R.font.bricolage_regular, FontWeight.Normal),
    Font(R.font.bricolage_bold, FontWeight.Bold),
)

val BodyFont = FontFamily(
    Font(R.font.instrument_regular, FontWeight.Normal),
    Font(R.font.instrument_bold, FontWeight.Bold),
)

private fun heading(size: Int, line: Int, spacing: Double) = TextStyle(
    fontFamily = HeadingFont,
    fontWeight = FontWeight.Bold,
    fontSize = size.sp,
    lineHeight = line.sp,
    letterSpacing = spacing.sp,
)

private fun body(size: Double, line: Int, weight: FontWeight, spacing: Double = 0.0) = TextStyle(
    fontFamily = BodyFont,
    fontWeight = weight,
    fontSize = size.sp,
    lineHeight = line.sp,
    letterSpacing = spacing.sp,
)

private val AmoraTypography = Typography(
    displayLarge = heading(40, 42, -1.4),
    displayMedium = heading(36, 38, -1.2),
    displaySmall = heading(32, 33, -1.1),
    headlineLarge = heading(30, 32, -0.9),
    headlineMedium = heading(26, 30, -0.6),
    headlineSmall = heading(24, 28, -0.5),
    titleLarge = heading(20, 24, -0.4),
    titleMedium = body(16.0, 22, FontWeight.Bold),
    titleSmall = body(15.0, 20, FontWeight.Bold),
    bodyLarge = body(15.0, 22, FontWeight.Normal),
    bodyMedium = body(14.0, 20, FontWeight.Normal),
    bodySmall = body(12.5, 17, FontWeight.Normal),
    labelLarge = body(15.0, 20, FontWeight.Bold),
    labelMedium = body(13.0, 18, FontWeight.Bold),
    labelSmall = body(12.0, 16, FontWeight.Bold, 0.7),
)

/** Narx: raqam sarlavha shriftida, katta va zich. Ko'z avval raqamni ko'radi. */
val PriceStyle = TextStyle(
    fontFamily = HeadingFont,
    fontWeight = FontWeight.Bold,
    fontSize = 15.5.sp,
    lineHeight = 20.sp,
    letterSpacing = (-0.3).sp,
)

/** Jami summa kabi asosiy narxlar. */
val PriceLargeStyle = PriceStyle.copy(fontSize = 22.sp, lineHeight = 26.sp, letterSpacing = (-0.4).sp)

private val AmoraShapes = Shapes(
    extraSmall = RoundedCornerShape(10.dp),
    small = RoundedCornerShape(13.dp),
    medium = RoundedCornerShape(18.dp),
    large = RoundedCornerShape(24.dp),
    extraLarge = RoundedCornerShape(30.dp),
)

@Composable
fun AmoraTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) DarkColors else LightColors,
        typography = AmoraTypography,
        shapes = AmoraShapes,
        content = content,
    )
}

val ColorScheme.isDark: Boolean
    get() = background.luminance() < 0.5f

// Material sxemasida yo'q, lekin maketda bor ranglar.

/** Ikkinchi darajali yozuvlar: belgilar ostidagi izoh, sana, maydon nomi. */
val ColorScheme.hint: Color
    get() = if (isDark) Color(0xFF8A8178) else Color(0xFF9C938A)

/** "Ko'mir" bloklar foni: banner, savat paneli, buyurtma holati. Ustidagi yozuv har doim oq. */
val ColorScheme.ink: Color
    get() = if (isDark) Color(0xFF26221E) else Ink

/** Ko'mir blok ustidagi ikkinchi darajali yozuv. */
val ColorScheme.onInkMuted: Color
    get() = Color(0xFFBDB3A9)

val ColorScheme.success: Color
    get() = if (isDark) Color(0xFF4CCB8C) else Color(0xFF1E9E61)

val ColorScheme.successContainer: Color
    get() = if (isDark) Color(0xFF123624) else Color(0xFFE3F5EB)

/** Sariq urg'u: "jonli holat" nuqtasi, chaqmoq belgisi. */
val ColorScheme.amber: Color
    get() = Color(0xFFF2A33A)

/** Qabul qiluvchi qatoridagi ko'k belgi. */
val ColorScheme.info: Color
    get() = if (isDark) Color(0xFFA9B6F0) else Color(0xFF3B4A8C)

val ColorScheme.infoContainer: Color
    get() = if (isDark) Color(0xFF232838) else Color(0xFFEEF0F6)
