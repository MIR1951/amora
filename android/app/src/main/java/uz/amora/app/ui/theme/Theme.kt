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

// Amora dizayn asosi: och kulrang fon ustida oq kartochkalar, bitta yorqin asosiy rang
// (pomidor qizili) faqat asosiy tugmalar va urg'ular uchun, qolgan hamma narsa neytral.
// Kafe o'z logotipi va ranglarini bersa, faqat shu fayl o'zgaradi.

private val LightColors = lightColorScheme(
    primary = Color(0xFFE8442A),
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFFFFEAE5),
    onPrimaryContainer = Color(0xFF8C1F0D),
    secondary = Color(0xFF1C1A19),
    onSecondary = Color(0xFFFFFFFF),
    secondaryContainer = Color(0xFFF0EEEB),
    onSecondaryContainer = Color(0xFF1C1A19),
    tertiary = Color(0xFFB26A00),
    onTertiary = Color(0xFFFFFFFF),
    tertiaryContainer = Color(0xFFFFF1D6),
    onTertiaryContainer = Color(0xFF5C3A00),
    background = Color(0xFFF6F5F3),
    onBackground = Color(0xFF1C1A19),
    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF1C1A19),
    surfaceVariant = Color(0xFFF0EEEB),
    onSurfaceVariant = Color(0xFF77726E),
    outline = Color(0xFFCFCAC5),
    outlineVariant = Color(0xFFE9E6E2),
    error = Color(0xFFD92D20),
    onError = Color(0xFFFFFFFF),
    errorContainer = Color(0xFFFEE4E2),
    onErrorContainer = Color(0xFF7A271A),
    surfaceContainerLowest = Color(0xFFFFFFFF),
    surfaceContainerLow = Color(0xFFFFFFFF),
    surfaceContainer = Color(0xFFFFFFFF),
    surfaceContainerHigh = Color(0xFFFFFFFF),
    surfaceContainerHighest = Color(0xFFF0EEEB),
    surfaceTint = Color(0xFFFFFFFF),
    scrim = Color(0xFF000000),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFFF2573D),
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFF4A1C12),
    onPrimaryContainer = Color(0xFFFFD9D1),
    secondary = Color(0xFFF3F1EE),
    onSecondary = Color(0xFF1C1A19),
    secondaryContainer = Color(0xFF2A2826),
    onSecondaryContainer = Color(0xFFF3F1EE),
    tertiary = Color(0xFFF5BF56),
    onTertiary = Color(0xFF412D00),
    tertiaryContainer = Color(0xFF4A3600),
    onTertiaryContainer = Color(0xFFFFE2A8),
    background = Color(0xFF111010),
    onBackground = Color(0xFFF3F1EE),
    surface = Color(0xFF1C1B1A),
    onSurface = Color(0xFFF3F1EE),
    surfaceVariant = Color(0xFF2A2826),
    onSurfaceVariant = Color(0xFFA8A39E),
    outline = Color(0xFF55504C),
    outlineVariant = Color(0xFF33302E),
    error = Color(0xFFFF8A80),
    onError = Color(0xFF4A0A05),
    errorContainer = Color(0xFF5C1A14),
    onErrorContainer = Color(0xFFFFDAD6),
    surfaceContainerLowest = Color(0xFF111010),
    surfaceContainerLow = Color(0xFF1C1B1A),
    surfaceContainer = Color(0xFF1C1B1A),
    surfaceContainerHigh = Color(0xFF242321),
    surfaceContainerHighest = Color(0xFF2A2826),
    surfaceTint = Color(0xFF1C1B1A),
    scrim = Color(0xFF000000),
)

// Manrope: zamonaviy, o'qilishi oson shrift (lotin va kirill harflari bor). Litsenziyasi: android/licenses.
private val Manrope = FontFamily(
    Font(R.font.manrope_medium, FontWeight.Normal),
    Font(R.font.manrope_medium, FontWeight.Medium),
    Font(R.font.manrope_semibold, FontWeight.SemiBold),
    Font(R.font.manrope_bold, FontWeight.Bold),
    Font(R.font.manrope_extrabold, FontWeight.ExtraBold),
)

private fun style(size: Int, line: Int, weight: FontWeight, spacing: Double = 0.0) = TextStyle(
    fontFamily = Manrope,
    fontWeight = weight,
    fontSize = size.sp,
    lineHeight = line.sp,
    letterSpacing = spacing.sp,
)

private val AmoraTypography = Typography(
    displayLarge = style(40, 46, FontWeight.ExtraBold, -0.8),
    displayMedium = style(34, 40, FontWeight.ExtraBold, -0.6),
    displaySmall = style(30, 36, FontWeight.ExtraBold, -0.5),
    headlineLarge = style(28, 34, FontWeight.ExtraBold, -0.4),
    headlineMedium = style(26, 32, FontWeight.ExtraBold, -0.4),
    headlineSmall = style(22, 28, FontWeight.ExtraBold, -0.3),
    titleLarge = style(20, 26, FontWeight.Bold, -0.2),
    titleMedium = style(16, 22, FontWeight.Bold, -0.1),
    titleSmall = style(14, 20, FontWeight.Bold),
    bodyLarge = style(16, 24, FontWeight.Medium),
    bodyMedium = style(14, 20, FontWeight.Medium),
    bodySmall = style(12, 16, FontWeight.Medium),
    labelLarge = style(15, 20, FontWeight.Bold),
    labelMedium = style(13, 18, FontWeight.SemiBold),
    labelSmall = style(11, 14, FontWeight.SemiBold, 0.1),
)

private val AmoraShapes = Shapes(
    extraSmall = RoundedCornerShape(8.dp),
    small = RoundedCornerShape(12.dp),
    medium = RoundedCornerShape(16.dp),
    large = RoundedCornerShape(22.dp),
    extraLarge = RoundedCornerShape(28.dp),
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

// "Muvaffaqiyat" ranglari (ochiq, yetkazildi, bepul): Material sxemasida bunday rang yo'q.

val ColorScheme.success: Color
    get() = if (isDark) Color(0xFF5BD79A) else Color(0xFF14935A)

val ColorScheme.successContainer: Color
    get() = if (isDark) Color(0xFF0F3D29) else Color(0xFFE0F5EA)

val ColorScheme.onSuccessContainer: Color
    get() = if (isDark) Color(0xFFA6F3C9) else Color(0xFF0B4A2D)

/** Kafe kartochkasi va shunga o'xshash urg'uli bloklar uchun gradient ranglari. */
val ColorScheme.brandGradient: List<Color>
    get() = if (isDark) {
        listOf(Color(0xFFE8442A), Color(0xFFB02A14))
    } else {
        listOf(Color(0xFFF2603F), Color(0xFFDD3A21))
    }
