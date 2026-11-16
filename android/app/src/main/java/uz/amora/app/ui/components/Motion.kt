package uz.amora.app.ui.components

import android.os.Build
import android.view.WindowManager
import androidx.compose.animation.AnimatedContentTransitionScope
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.foundation.interaction.InteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Box
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.findRootCoordinates
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.layout.positionInRoot
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.DialogWindowProvider
import androidx.navigation.NavBackStackEntry
import uz.amora.app.ui.theme.isDark

// Harakat: ekranlar orasidagi o'tishlar, bosilgandagi "yumshoq" siqilish va
// ma'lumot yuklanayotganda ko'rinadigan skelet bloklar.

// ---------- Ekranlar orasidagi o'tish ----------

private const val SCREEN_MS = 420

// Tez boshlanib, ohista to'xtaydi: ekran "sirpanib" kirgandek ko'rinadi
private val ScreenEasing = CubicBezierEasing(0.22f, 1f, 0.36f, 1f)

/** Yangi ekran o'ngdan to'liq sirpanib kiradi. */
val screenEnter: AnimatedContentTransitionScope<NavBackStackEntry>.() -> EnterTransition = {
    slideInHorizontally(tween(SCREEN_MS, easing = ScreenEasing)) { it } +
        fadeIn(tween(SCREEN_MS / 2))
}

/** Ostida qolayotgan ekran biroz chapga surilib, xiralashadi (chuqurlik hissi). */
val screenExit: AnimatedContentTransitionScope<NavBackStackEntry>.() -> ExitTransition = {
    slideOutHorizontally(tween(SCREEN_MS, easing = ScreenEasing)) { -it / 4 } +
        fadeOut(tween(SCREEN_MS, easing = ScreenEasing), targetAlpha = 0.35f)
}

/** Orqaga qaytilganda ostidagi ekran chapdan joyiga qaytadi. */
val screenPopEnter: AnimatedContentTransitionScope<NavBackStackEntry>.() -> EnterTransition = {
    slideInHorizontally(tween(SCREEN_MS, easing = ScreenEasing)) { -it / 4 } +
        fadeIn(tween(SCREEN_MS, easing = ScreenEasing), initialAlpha = 0.35f)
}

/** Orqaga qaytilganda ustki ekran o'ngga sirpanib chiqib ketadi. */
val screenPopExit: AnimatedContentTransitionScope<NavBackStackEntry>.() -> ExitTransition = {
    slideOutHorizontally(tween(SCREEN_MS, easing = ScreenEasing)) { it } +
        fadeOut(tween(SCREEN_MS / 2, delayMillis = SCREEN_MS / 2))
}

// ---------- Bosilgandagi siqilish ----------

/** Element bosib turilganda biroz kichrayadi va qo'yib yuborilganda prujinadek joyiga qaytadi. */
fun Modifier.pressScale(source: InteractionSource, pressedScale: Float = 0.97f): Modifier = composed {
    val pressed by source.collectIsPressedAsState()
    val scale by animateFloatAsState(
        targetValue = if (pressed) pressedScale else 1f,
        animationSpec = spring(dampingRatio = 0.55f, stiffness = Spring.StiffnessMedium),
        label = "press-scale",
    )
    graphicsLayer {
        scaleX = scale
        scaleY = scale
    }
}

// ---------- Skelet ----------

/**
 * Yuklanayotgan kontent o'rnidagi kulrang blok ustidan yorug'lik to'lqini o'tib turadi.
 * To'lqin butun ekran bo'ylab bitta bo'lib yuradi: bloklar alohida-alohida miltillamaydi.
 */
fun Modifier.shimmer(shape: Shape): Modifier = composed {
    val scheme = MaterialTheme.colorScheme
    val base = scheme.outlineVariant
    val highlight = if (scheme.isDark) Color.White.copy(alpha = 0.09f) else Color.White.copy(alpha = 0.80f)
    val transition = rememberInfiniteTransition(label = "shimmer")
    val progress by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(1300, easing = LinearEasing), RepeatMode.Restart),
        label = "shimmer-progress",
    )
    var left by remember { mutableFloatStateOf(0f) }
    var rootWidth by remember { mutableFloatStateOf(0f) }
    this
        .onGloballyPositioned { coordinates ->
            left = coordinates.positionInRoot().x
            rootWidth = coordinates.findRootCoordinates().size.width.toFloat()
        }
        .clip(shape)
        .drawBehind {
            drawRect(base)
            val total = if (rootWidth > 0f) rootWidth else size.width
            val band = total * 0.6f
            val start = -band + (total + band) * progress - left
            drawRect(
                brush = Brush.horizontalGradient(
                    colors = listOf(Color.Transparent, highlight, Color.Transparent),
                    startX = start,
                    endX = start + band,
                ),
            )
        }
}

/** Yuklanayotgan kontent o'rnida turadigan blok. */
@Composable
fun SkeletonBox(modifier: Modifier = Modifier, shape: Shape = MaterialTheme.shapes.small) {
    Box(modifier = modifier.shimmer(shape))
}

// ---------- Oyna ortini xiralashtirish ----------

/**
 * Pastdan chiqadigan oyna yoki tasdiqlash oynasi ichida chaqiriladi: oyna ortidagi ekran xiralashadi.
 * Android 12 va undan yangi, buni qo'llaydigan telefonlarda ishlaydi; qolganlarida hech narsa o'zgarmaydi.
 */
@Composable
fun BlurBehindEffect(radius: Dp = 16.dp) {
    val view = LocalView.current
    val radiusPx = with(LocalDensity.current) { radius.roundToPx() }
    DisposableEffect(view, radiusPx) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val window = (view.parent as? DialogWindowProvider)?.window
            if (window != null) {
                window.addFlags(WindowManager.LayoutParams.FLAG_BLUR_BEHIND)
                val attributes = window.attributes
                attributes.blurBehindRadius = radiusPx
                window.attributes = attributes
            }
        }
        onDispose { }
    }
}
