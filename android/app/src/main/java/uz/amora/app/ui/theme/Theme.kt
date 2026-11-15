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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

// Amora ranglari: iliq qizil asosiy rang, och krem fon.
// Kafe o'z logotipi va ranglarini bersa, faqat shu fayl o'zgaradi.

private val LightColors = lightColorScheme(
    primary = Color(0xFFD9442B),
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFFFFE2DB),
    onPrimaryContainer = Color(0xFF4A0E04),
    secondary = Color(0xFF77574F),
    onSecondary = Color(0xFFFFFFFF),
    secondaryContainer = Color(0xFFFBE7E1),
    onSecondaryContainer = Color(0xFF2C1510),
    tertiary = Color(0xFF8A5A00),
    onTertiary = Color(0xFFFFFFFF),
    tertiaryContainer = Color(0xFFFFE9C2),
    onTertiaryContainer = Color(0xFF2C1A00),
    background = Color(0xFFFAF7F5),
    onBackground = Color(0xFF1F1B1A),
    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF1F1B1A),
    surfaceVariant = Color(0xFFF3ECE9),
    onSurfaceVariant = Color(0xFF6B5F5B),
    outline = Color(0xFFBDB0AB),
    outlineVariant = Color(0xFFE9E0DC),
    error = Color(0xFFBA1A1A),
    onError = Color(0xFFFFFFFF),
    errorContainer = Color(0xFFFFDAD6),
    onErrorContainer = Color(0xFF410002),
    surfaceContainerLowest = Color(0xFFFFFFFF),
    surfaceContainerLow = Color(0xFFFFFFFF),
    surfaceContainer = Color(0xFFF7F1EE),
    surfaceContainerHigh = Color(0xFFF3ECE9),
    surfaceContainerHighest = Color(0xFFEEE6E2),
    surfaceTint = Color(0xFFD9442B),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFFFF8A73),
    onPrimary = Color(0xFF4A0E04),
    primaryContainer = Color(0xFF7A2415),
    onPrimaryContainer = Color(0xFFFFDAD3),
    secondary = Color(0xFFE7BDB3),
    onSecondary = Color(0xFF442A23),
    secondaryContainer = Color(0xFF5D3F38),
    onSecondaryContainer = Color(0xFFFFDAD3),
    tertiary = Color(0xFFF5BF56),
    onTertiary = Color(0xFF412D00),
    tertiaryContainer = Color(0xFF5D4200),
    onTertiaryContainer = Color(0xFFFFDEA6),
    background = Color(0xFF181210),
    onBackground = Color(0xFFEDE0DC),
    surface = Color(0xFF231B19),
    onSurface = Color(0xFFEDE0DC),
    surfaceVariant = Color(0xFF3A2F2C),
    onSurfaceVariant = Color(0xFFD8C2BC),
    outline = Color(0xFFA08C87),
    outlineVariant = Color(0xFF53433F),
    error = Color(0xFFFFB4AB),
    onError = Color(0xFF690005),
    errorContainer = Color(0xFF93000A),
    onErrorContainer = Color(0xFFFFDAD6),
    surfaceContainerLowest = Color(0xFF130D0C),
    surfaceContainerLow = Color(0xFF231B19),
    surfaceContainer = Color(0xFF2A211F),
    surfaceContainerHigh = Color(0xFF342B28),
    surfaceContainerHighest = Color(0xFF3F3532),
    surfaceTint = Color(0xFFFF8A73),
)

private val BaseTypography = Typography()

private val AmoraTypography = Typography(
    headlineSmall = BaseTypography.headlineSmall.copy(fontWeight = FontWeight.Bold),
    titleLarge = BaseTypography.titleLarge.copy(fontWeight = FontWeight.Bold),
    titleMedium = BaseTypography.titleMedium.copy(fontWeight = FontWeight.SemiBold),
    titleSmall = BaseTypography.titleSmall.copy(fontWeight = FontWeight.SemiBold),
    labelLarge = BaseTypography.labelLarge.copy(fontWeight = FontWeight.SemiBold),
)

private val AmoraShapes = Shapes(
    extraSmall = RoundedCornerShape(8.dp),
    small = RoundedCornerShape(12.dp),
    medium = RoundedCornerShape(16.dp),
    large = RoundedCornerShape(20.dp),
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

// "Muvaffaqiyat" ranglari (ochiq, yetkazildi): Material sxemasida bunday rang yo'q.

private val ColorScheme.isDark: Boolean
    get() = background.luminance() < 0.5f

val ColorScheme.success: Color
    get() = if (isDark) Color(0xFF8AD6AE) else Color(0xFF2E7D5B)

val ColorScheme.successContainer: Color
    get() = if (isDark) Color(0xFF0F5236) else Color(0xFFD8F3E4)

val ColorScheme.onSuccessContainer: Color
    get() = if (isDark) Color(0xFFA6F3C9) else Color(0xFF07301F)
