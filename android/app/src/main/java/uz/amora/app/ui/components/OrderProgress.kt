package uz.amora.app.ui.components

import android.database.ContentObserver
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.keyframes
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.State
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalInspectionMode
import androidx.compose.ui.unit.dp
import uz.amora.app.data.OrderStatus

/** Hozirgi bosqichdagi to'lqinning bir aylanishi (ms). */
private const val SWEEP_MS = 1_800

/** Animatsiyalar o'chirilgan telefonda hozirgi bosqich shuncha to'lgan holda turadi. */
private const val STATIC_ACTIVE_FILL = 0.55f

/**
 * To'rt bo'lakli chiziq: 1 yuborildi, 2 kafe qabul qildi, 3 kuryer yo'lda, 4 yetkazildi.
 *
 * O'tilgan bosqichlar to'la. Hozirgi bosqich och rangda bo'lib, uning ichida chapdan o'ngga
 * to'lqin oqib turadi: bo'lak to'lib boradi, so'ng o'ngga oqib chiqib ketadi va yana boshlanadi.
 * Holat o'zgarganda tugagan bosqich ohista to'ladi va to'lqin keyingi bo'lakka o'tadi.
 * Telefonda animatsiyalar o'chirilgan bo'lsa (Maxsus imkoniyatlar), hozirgi bo'lak yarim to'lgan
 * holda jim turadi.
 *
 * Animatsiya faqat chizish bosqichida o'qiladi: ekran qayta tuzilmaydi, faqat chiziq qayta chiziladi.
 */
@Composable
fun OrderProgressBar(
    status: String,
    modifier: Modifier = Modifier,
    color: Color = MaterialTheme.colorScheme.primary,
    track: Color = MaterialTheme.colorScheme.outlineVariant,
) {
    val step = orderStep(status)
    val delivered = status == OrderStatus.DELIVERED
    val animate = rememberAnimationsEnabled()
    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        repeat(4) { index ->
            val active = !delivered && step > 0 && index == step - 1
            val target = when {
                delivered || index < step - 1 -> 1f
                active && !animate -> STATIC_ACTIVE_FILL
                else -> 0f
            }
            val fill = animateFloatAsState(
                targetValue = target,
                animationSpec = tween(600, easing = FastOutSlowInEasing),
                label = "order-progress-fill",
            )
            val sweep = if (active && animate) rememberSweep() else null
            val activeTint = color.copy(alpha = 0.22f)
            Box(
                modifier = Modifier
                    .weight(1f)
                    .height(6.dp)
                    .clip(RoundedCornerShape(50))
                    .drawBehind {
                        drawRect(track)
                        if (active) drawRect(activeTint)
                        val filled = size.width * fill.value
                        if (filled > 0f) drawRect(color, size = Size(filled, size.height))
                        if (sweep != null) {
                            val (tail, head) = sweep.value
                            val left = size.width * tail
                            val width = size.width * head - left
                            if (width > 0.5f) {
                                drawRoundRect(
                                    brush = Brush.horizontalGradient(
                                        colors = listOf(color.copy(alpha = 0.45f), color),
                                        startX = left,
                                        endX = left + width,
                                    ),
                                    topLeft = Offset(left, 0f),
                                    size = Size(width, size.height),
                                    cornerRadius = CornerRadius(size.height / 2, size.height / 2),
                                )
                            }
                        }
                    },
            )
        }
    }
}

/**
 * To'lqinning ikki uchi (0..1): oldingi uchi tez yugurib bo'lakni to'ldiradi, orqa uchi biroz
 * kechikib ergashadi. Aylanish oxirida ikkalasi ham o'ng chetda uchrashadi, shuning uchun
 * qayta boshlanganda sakrash ko'rinmaydi.
 */
@Composable
private fun rememberSweep(): State<Pair<Float, Float>> {
    val transition = rememberInfiniteTransition(label = "order-progress-sweep")
    val head = transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            keyframes {
                durationMillis = SWEEP_MS
                0f at 0 using FastOutSlowInEasing
                1f at 1_150
            },
        ),
        label = "order-progress-head",
    )
    val tail = transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            keyframes {
                durationMillis = SWEEP_MS
                0f at 550 using FastOutSlowInEasing
                1f at SWEEP_MS
            },
        ),
        label = "order-progress-tail",
    )
    return remember(head, tail) {
        object : State<Pair<Float, Float>> {
            override val value: Pair<Float, Float> get() = tail.value to head.value
        }
    }
}

/**
 * Telefonda animatsiyalar yoqilganmi (Sozlamalar → Maxsus imkoniyatlar → "Animatsiyalarni olib
 * tashlash" yoki dasturchi sozlamalaridagi animatsiya tezligi). O'zgarsa, darhol hisobga olinadi.
 */
@Composable
fun rememberAnimationsEnabled(): Boolean {
    if (LocalInspectionMode.current) return true
    val resolver = LocalContext.current.contentResolver
    var enabled by remember(resolver) { mutableStateOf(animatorScale(resolver) > 0f) }
    DisposableEffect(resolver) {
        val observer = object : ContentObserver(Handler(Looper.getMainLooper())) {
            override fun onChange(selfChange: Boolean) {
                enabled = animatorScale(resolver) > 0f
            }
        }
        resolver.registerContentObserver(
            Settings.Global.getUriFor(Settings.Global.ANIMATOR_DURATION_SCALE),
            false,
            observer,
        )
        onDispose { resolver.unregisterContentObserver(observer) }
    }
    return enabled
}

private fun animatorScale(resolver: android.content.ContentResolver): Float =
    Settings.Global.getFloat(resolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f)
