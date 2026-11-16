package uz.amora.app.ui.components

import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.RectangleShape
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import dev.chrisbanes.haze.HazeChildScope
import dev.chrisbanes.haze.HazeState
import dev.chrisbanes.haze.HazeStyle
import dev.chrisbanes.haze.HazeTint
import dev.chrisbanes.haze.haze
import dev.chrisbanes.haze.hazeChild
import uz.amora.app.ui.theme.ink
import uz.amora.app.ui.theme.isDark

// "Suyuq shisha" (liquid glass) qatlami. Ekran kontenti ustida suzib turadigan panellar
// (yuqori satr, savat paneli, xarita ustidagi tugmalar) ortidagi kontentni xira shisha
// orqali ko'rsatadi. Ishlash tartibi:
//   1. Ekran `rememberGlassState()` bilan holat yaratadi.
//   2. Suriladigan kontentga `Modifier.glassSource(holat)` qo'yiladi.
//   3. Ustidagi panellar `GlassBox(holat)` yoki `GlassStrip(holat)` ichida chiziladi.
// Panel kontentning ICHIDA emas, YONIDA (ustida) turishi shart.
// Haqiqiy xiralashtirish Android 12L va undan yangi telefonlarda ishlaydi; eskilarida
// o'rniga deyarli shaffof bo'lmagan rang chiziladi, ko'rinish buzilmaydi.

/** Shisha turi: och (oq), to'q (ko'mir) yoki tuman (fon rangida, satrlar uchun). */
enum class GlassTone { Light, Dark, Fog }

/** `GlassStrip` qaysi chetida asta yo'qolib boradi. */
enum class GlassFade { Top, Bottom }

@Composable
fun rememberGlassState(): HazeState = remember { HazeState() }

/** Shisha ortida ko'rinadigan kontent. */
fun Modifier.glassSource(state: HazeState): Modifier = haze(state)

@Composable
private fun glassStyle(tone: GlassTone): HazeStyle {
    val scheme = MaterialTheme.colorScheme
    return remember(scheme, tone) {
        val tint: Color
        val fallback: Color
        when (tone) {
            GlassTone.Light -> {
                tint = if (scheme.isDark) scheme.surface.copy(alpha = 0.62f) else Color.White.copy(alpha = 0.60f)
                fallback = scheme.surface.copy(alpha = 0.95f)
            }

            GlassTone.Dark -> {
                tint = scheme.ink.copy(alpha = 0.74f)
                fallback = scheme.ink.copy(alpha = 0.96f)
            }

            GlassTone.Fog -> {
                tint = scheme.background.copy(alpha = 0.68f)
                fallback = scheme.background.copy(alpha = 0.95f)
            }
        }
        HazeStyle(
            backgroundColor = scheme.background,
            tints = listOf(HazeTint(tint)),
            blurRadius = 22.dp,
            noiseFactor = 0.04f,
            fallbackTint = HazeTint(fallback),
        )
    }
}

/**
 * Shisha panel: ortidagi kontent xira ko'rinadi, chetida yorug'lik aks etgandek ingichka hoshiya bor.
 * `elevation`: panel ostidagi soya (suzib turgan panellar uchun).
 */
@Composable
fun GlassBox(
    glass: HazeState,
    modifier: Modifier = Modifier,
    shape: Shape = RectangleShape,
    tone: GlassTone = GlassTone.Light,
    elevation: Dp = 0.dp,
    contentAlignment: Alignment = Alignment.TopStart,
    content: @Composable BoxScope.() -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    val rim = remember(scheme, tone) {
        val top = when {
            tone == GlassTone.Dark -> 0.30f
            scheme.isDark -> 0.20f
            else -> 0.95f
        }
        val bottom = when {
            tone == GlassTone.Dark -> 0.06f
            scheme.isDark -> 0.04f
            else -> 0.30f
        }
        Brush.verticalGradient(listOf(Color.White.copy(alpha = top), Color.White.copy(alpha = bottom)))
    }
    val shadowColor = Color(0xFF17130F)
    val lifted = if (elevation > 0.dp) {
        Modifier.shadow(
            elevation = elevation,
            shape = shape,
            clip = false,
            ambientColor = shadowColor.copy(alpha = 0.20f),
            spotColor = shadowColor.copy(alpha = 0.35f),
        )
    } else {
        Modifier
    }
    Box(
        modifier = modifier
            .then(lifted)
            .clip(shape)
            .hazeChild(glass, glassStyle(tone))
            .border(1.dp, rim, shape),
        contentAlignment = contentAlignment,
        content = content,
    )
}

/**
 * Yuqori yoki pastki satr ortidagi "tuman": kontent uning ostiga xiralashib kirib ketadi,
 * bir chetida esa asta yo'qoladi (keskin chegara ko'rinmaydi).
 */
@Composable
fun GlassStrip(glass: HazeState, modifier: Modifier = Modifier, fade: GlassFade = GlassFade.Bottom) {
    val block: HazeChildScope.() -> Unit = remember(fade) {
        val mask = when (fade) {
            GlassFade.Bottom -> Brush.verticalGradient(
                0f to Color.Black,
                0.70f to Color.Black,
                1f to Color.Transparent,
            )

            GlassFade.Top -> Brush.verticalGradient(
                0f to Color.Transparent,
                0.34f to Color.Black,
                1f to Color.Black,
            )
        }
        val configure: HazeChildScope.() -> Unit = { this.mask = mask }
        configure
    }
    Box(modifier = modifier.hazeChild(glass, glassStyle(GlassTone.Fog), block))
}
