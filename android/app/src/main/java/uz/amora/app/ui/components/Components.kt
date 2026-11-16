package uz.amora.app.ui.components

import android.os.Build
import androidx.annotation.DrawableRes
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.LocalIndication
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TextFieldColors
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.material3.pulltorefresh.PullToRefreshDefaults
import androidx.compose.material3.pulltorefresh.rememberPullToRefreshState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.RectangleShape
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.OffsetMapping
import androidx.compose.ui.text.input.TransformedText
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import coil.request.ImageRequest
import dev.chrisbanes.haze.HazeState
import uz.amora.app.R
import uz.amora.app.data.OrderStatus
import uz.amora.app.ui.theme.BodyFont
import uz.amora.app.ui.theme.PriceStyle
import uz.amora.app.ui.theme.hint
import uz.amora.app.ui.theme.isDark
import uz.amora.app.ui.theme.success
import uz.amora.app.ui.theme.successContainer
import uz.amora.app.util.formatNumber

// Ilovaning umumiy "g'ishtlari": kartochka, tugma, narx, belgi, yuqori va pastki satrlar.
// Yangi ekran shu yerdagi bo'laklardan yig'iladi, shunda hamma joyda bir xil chekinish (16),
// bir xil burchaklar va bir xil belgilar uslubi saqlanadi.

// ---------- Soya ----------

/** Juda yengil soya: kartochka fon ustida qog'ozdek "suzib" turadi. */
fun Modifier.softShadow(shape: Shape, elevation: Dp = 10.dp, alpha: Float = 0.10f): Modifier {
    // Android 9 dan eski telefonlarda soyaga rang berib bo'lmaydi: u yerda soya kichikroq olinadi
    val height = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) elevation else elevation / 4
    val color = Color(0xFF17130F)
    return shadow(
        elevation = height,
        shape = shape,
        clip = false,
        ambientColor = color.copy(alpha = alpha * 0.6f),
        spotColor = color.copy(alpha = alpha),
    )
}

// ---------- Taom rasmi va narx ----------

// Rasmi yo'q taomlar uchun yumshoq fon ranglari (har taomga o'ziniki, maketdagidek)
private val PLACEHOLDER_TINTS = listOf(
    Color(0xFFFBE7D3),
    Color(0xFFE3EEF6),
    Color(0xFFF9E3DA),
    Color(0xFFF1E6DB),
    Color(0xFFE2F0EA),
    Color(0xFFEEF3DF),
)

/**
 * Taom rasmi. Yuklanayotganda ustidan yorug'lik to'lqini o'tadi; rasm yo'q yoki yuklanmasa,
 * o'rnida rangli fon va likopcha belgisi turadi. `seed`: fon rangini tanlash uchun (taom raqami).
 */
@Composable
fun ProductImage(url: String?, modifier: Modifier = Modifier, iconSize: Dp = 44.dp, seed: Int = 0) {
    val scheme = MaterialTheme.colorScheme
    val tint = if (scheme.isDark) {
        scheme.surfaceVariant
    } else {
        PLACEHOLDER_TINTS[((seed % PLACEHOLDER_TINTS.size) + PLACEHOLDER_TINTS.size) % PLACEHOLDER_TINTS.size]
    }
    var loading by remember(url) { mutableStateOf(url != null) }
    var failed by remember(url) { mutableStateOf(false) }
    Box(modifier = modifier.background(tint), contentAlignment = Alignment.Center) {
        if (url == null || failed) {
            Icon(
                painter = painterResource(R.drawable.ic_dish),
                contentDescription = null,
                tint = scheme.onSurface.copy(alpha = 0.16f),
                modifier = Modifier.size(iconSize),
            )
        } else {
            if (loading) {
                Box(modifier = Modifier.matchParentSize().shimmer(RectangleShape))
            }
            AsyncImage(
                model = ImageRequest.Builder(LocalContext.current)
                    .data(url)
                    .crossfade(true)
                    .build(),
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.matchParentSize(),
                onSuccess = { loading = false },
                onError = {
                    loading = false
                    failed = true
                },
            )
        }
    }
}

/** Narx: "60 000" katta va zich, " so'm" kichik va xira. `unit = false`: faqat raqam. */
@Composable
fun PriceText(
    amount: Int,
    modifier: Modifier = Modifier,
    style: TextStyle = PriceStyle,
    color: Color = Color.Unspecified,
    unitColor: Color = MaterialTheme.colorScheme.hint,
    unit: Boolean = true,
) {
    val text = buildAnnotatedString {
        append(formatNumber(amount))
        if (unit) {
            withStyle(
                SpanStyle(
                    fontFamily = BodyFont,
                    fontWeight = FontWeight.Normal,
                    fontSize = style.fontSize * 0.72f,
                    letterSpacing = 0.sp,
                    color = unitColor,
                ),
            ) {
                append(" so'm")
            }
        }
    }
    Text(text = text, modifier = modifier, style = style, color = color, maxLines = 1, softWrap = false)
}

// ---------- Belgilar va kichik tugmalar ----------

/** Burchaklari yumaloq kvadrat ichidagi belgi (ro'yxat qatorlari, holat kartochkalari). */
@Composable
fun IconTile(
    @DrawableRes icon: Int,
    modifier: Modifier = Modifier,
    size: Dp = 42.dp,
    container: Color = MaterialTheme.colorScheme.primaryContainer,
    tint: Color = MaterialTheme.colorScheme.primary,
    iconSize: Dp = 22.dp,
) {
    Box(
        modifier = modifier
            .size(size)
            .clip(RoundedCornerShape(size / 3))
            .background(container),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            painter = painterResource(icon),
            contentDescription = null,
            tint = tint,
            modifier = Modifier.size(iconSize),
        )
    }
}

/** Kafe logotipi: qizil kvadrat ichida nomining bosh harfi. */
@Composable
fun LogoTile(letter: String, modifier: Modifier = Modifier, size: Dp = 46.dp) {
    val scheme = MaterialTheme.colorScheme
    val shape = RoundedCornerShape(size / 3)
    Box(
        modifier = modifier
            .size(size)
            .shadow(
                elevation = 8.dp,
                shape = shape,
                clip = false,
                ambientColor = scheme.primary.copy(alpha = 0.4f),
                spotColor = scheme.primary.copy(alpha = 0.7f),
            )
            .clip(shape)
            .background(scheme.primary),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = letter,
            style = MaterialTheme.typography.headlineMedium,
            color = Color.White,
        )
    }
}

/**
 * Yumaloq belgili tugma: orqaga, buyurtmalar, profil.
 * `glass` berilsa, tugma shishadan bo'ladi (xarita ustida), aks holda oq va ingichka hoshiyali.
 */
@Composable
fun RoundButton(
    @DrawableRes icon: Int,
    label: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    size: Dp = 44.dp,
    shape: Shape = CircleShape,
    tint: Color = MaterialTheme.colorScheme.onSurface,
    glass: HazeState? = null,
    content: (@Composable () -> Unit)? = null,
) {
    val scheme = MaterialTheme.colorScheme
    val source = remember { MutableInteractionSource() }
    val inner: @Composable () -> Unit = content ?: {
        Icon(
            painter = painterResource(icon),
            contentDescription = label,
            tint = tint,
            modifier = Modifier.size(22.dp),
        )
    }
    if (glass != null) {
        GlassBox(
            glass = glass,
            modifier = modifier
                .size(size)
                .pressScale(source, 0.92f),
            shape = shape,
            elevation = 8.dp,
        ) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .clickable(
                        interactionSource = source,
                        indication = LocalIndication.current,
                        role = Role.Button,
                        onClick = onClick,
                    ),
                contentAlignment = Alignment.Center,
            ) {
                inner()
            }
        }
    } else {
        Box(
            modifier = modifier
                .size(size)
                .pressScale(source, 0.92f)
                .clip(shape)
                .background(scheme.surface)
                .border(1.dp, scheme.outlineVariant, shape)
                .clickable(
                    interactionSource = source,
                    indication = LocalIndication.current,
                    role = Role.Button,
                    onClick = onClick,
                ),
            contentAlignment = Alignment.Center,
        ) {
            inner()
        }
    }
}

/** Taom kartochkasidagi "+" tugmasi: bosilganda taom savatga tushadi. */
@Composable
fun AddButton(onClick: () -> Unit, modifier: Modifier = Modifier) {
    val scheme = MaterialTheme.colorScheme
    val source = remember { MutableInteractionSource() }
    Box(
        modifier = modifier
            .size(38.dp)
            .pressScale(source, 0.88f)
            .clip(RoundedCornerShape(13.dp))
            .background(scheme.surfaceVariant)
            .clickable(
                interactionSource = source,
                indication = LocalIndication.current,
                onClickLabel = "Qo'shish",
                role = Role.Button,
                onClick = onClick,
            )
            .semantics { contentDescription = "Qo'shish" },
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            painter = painterResource(R.drawable.ic_plus),
            contentDescription = null,
            tint = scheme.onSurface,
            modifier = Modifier.size(22.dp),
        )
    }
}

/**
 * "−  2  +" ko'rinishidagi son tanlagich.
 * `tonal`: neytral ko'rinish (savat qatorlarida), aks holda qizil.
 * `label`: son o'rniga ko'rsatiladigan matn, masalan "2 ta · 70 000 so'm".
 * `expand`: bor kenglikni egallaydi (son o'rtada turadi).
 */
@Composable
fun QuantityStepper(
    quantity: Int,
    onMinus: () -> Unit,
    onPlus: () -> Unit,
    modifier: Modifier = Modifier,
    height: Dp = 38.dp,
    corner: Dp = 13.dp,
    buttonWidth: Dp = 28.dp,
    tonal: Boolean = false,
    label: String? = null,
    expand: Boolean = false,
) {
    val scheme = MaterialTheme.colorScheme
    val container = if (tonal) scheme.surfaceVariant else scheme.primary
    val content = if (tonal) scheme.onSurface else scheme.onPrimary
    Row(
        modifier = modifier
            .height(height)
            .clip(RoundedCornerShape(corner))
            .background(container),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        StepperButton(
            icon = R.drawable.ic_minus,
            label = "Kamaytirish",
            width = buttonWidth,
            tint = content,
            onClick = onMinus,
        )
        Box(
            modifier = if (expand) Modifier.weight(1f) else Modifier.widthIn(min = 16.dp),
            contentAlignment = Alignment.Center,
        ) {
            AnimatedContent(
                targetState = label ?: quantity.toString(),
                transitionSpec = {
                    (fadeIn(tween(160)) + slideInVertically(tween(200)) { it / 2 }) togetherWith
                        (fadeOut(tween(120)) + slideOutVertically(tween(200)) { -it / 2 })
                },
                label = "quantity",
            ) { value ->
                Text(
                    text = value,
                    color = content,
                    style = MaterialTheme.typography.titleSmall,
                    maxLines = 1,
                )
            }
        }
        StepperButton(
            icon = R.drawable.ic_plus,
            label = "Ko'paytirish",
            width = buttonWidth,
            tint = if (tonal) scheme.primary else content,
            onClick = onPlus,
        )
    }
}

@Composable
private fun StepperButton(@DrawableRes icon: Int, label: String, width: Dp, tint: Color, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .width(width)
            .fillMaxHeight()
            .clickable(onClickLabel = label, role = Role.Button, onClick = onClick)
            .semantics { contentDescription = label },
        contentAlignment = Alignment.Center,
    ) {
        Icon(painterResource(icon), contentDescription = null, tint = tint, modifier = Modifier.size(18.dp))
    }
}

// ---------- Holatlar: yuklanish, bo'sh, xato ----------

@Composable
fun LoadingBox(modifier: Modifier = Modifier) {
    Box(modifier = modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        CircularProgressIndicator(strokeWidth = 3.dp)
    }
}

/** Bo'sh holat yoki xato: katta belgi, sarlavha, izoh va ixtiyoriy tugma. */
@Composable
fun MessageBox(
    @DrawableRes icon: Int,
    title: String,
    modifier: Modifier = Modifier,
    text: String? = null,
    actionLabel: String? = null,
    onAction: (() -> Unit)? = null,
) {
    val scheme = MaterialTheme.colorScheme
    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(32.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        IconTile(icon = icon, size = 92.dp, iconSize = 40.dp)
        Spacer(Modifier.height(20.dp))
        Text(title, style = MaterialTheme.typography.headlineSmall, textAlign = TextAlign.Center)
        if (text != null) {
            Spacer(Modifier.height(6.dp))
            Text(
                text = text,
                style = MaterialTheme.typography.bodyLarge,
                color = scheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )
        }
        if (actionLabel != null && onAction != null) {
            Spacer(Modifier.height(24.dp))
            PillButton(text = actionLabel, onClick = onAction)
        }
    }
}

/** Matn kengligidagi asosiy tugma (bo'sh holatlarda). */
@Composable
fun PillButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val scheme = MaterialTheme.colorScheme
    val source = remember { MutableInteractionSource() }
    Surface(
        onClick = onClick,
        modifier = modifier.pressScale(source),
        shape = RoundedCornerShape(18.dp),
        color = scheme.primary,
        contentColor = scheme.onPrimary,
        interactionSource = source,
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.labelLarge,
            maxLines = 1,
            modifier = Modifier.padding(horizontal = 28.dp, vertical = 15.dp),
        )
    }
}

/** Pastga tortib yangilash. `indicatorTop`: aylanuvchi belgi yuqori satr ostidan chiqishi uchun chekinish. */
@Composable
fun RefreshBox(
    refreshing: Boolean,
    onRefresh: () -> Unit,
    modifier: Modifier = Modifier,
    indicatorTop: Dp = 0.dp,
    content: @Composable BoxScope.() -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    val state = rememberPullToRefreshState()
    PullToRefreshBox(
        isRefreshing = refreshing,
        onRefresh = onRefresh,
        modifier = modifier,
        state = state,
        indicator = {
            PullToRefreshDefaults.Indicator(
                state = state,
                isRefreshing = refreshing,
                modifier = Modifier
                    .align(Alignment.TopCenter)
                    .padding(top = indicatorTop),
                containerColor = scheme.surface,
                color = scheme.primary,
            )
        },
        content = content,
    )
}

/** Filtr yoki bo'lim tugmasi: tanlangani ko'mir rangda, qolganlari oq. */
@Composable
fun TabChip(text: String, selected: Boolean, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val scheme = MaterialTheme.colorScheme
    val shape = RoundedCornerShape(13.dp)
    Surface(
        onClick = onClick,
        modifier = modifier,
        shape = shape,
        color = if (selected) scheme.secondary else scheme.surface,
        contentColor = if (selected) scheme.onSecondary else scheme.onSurfaceVariant,
        border = if (selected) null else BorderStroke(1.dp, scheme.outlineVariant),
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.labelMedium,
            maxLines = 1,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp),
        )
    }
}

// ---------- Kartochka va qatorlar ----------

/** Oq fonli, burchaklari yumaloq, yengil soyali blok. */
@Composable
fun SectionCard(
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    padding: Dp = 16.dp,
    content: @Composable ColumnScope.() -> Unit,
) {
    val shape = MaterialTheme.shapes.large
    val color = MaterialTheme.colorScheme.surface
    if (onClick != null) {
        val source = remember { MutableInteractionSource() }
        Surface(
            onClick = onClick,
            modifier = modifier
                .fillMaxWidth()
                .pressScale(source, 0.98f)
                .softShadow(shape),
            shape = shape,
            color = color,
            interactionSource = source,
        ) {
            Column(modifier = Modifier.padding(padding), content = content)
        }
    } else {
        Surface(
            modifier = modifier
                .fillMaxWidth()
                .softShadow(shape),
            shape = shape,
            color = color,
        ) {
            Column(modifier = Modifier.padding(padding), content = content)
        }
    }
}

/** Bloklar ustidagi kichik bosh harfli sarlavha: "YETKAZISH". */
@Composable
fun SectionLabel(text: String, modifier: Modifier = Modifier) {
    Text(
        text = text.uppercase(),
        style = MaterialTheme.typography.labelSmall,
        color = MaterialTheme.colorScheme.hint,
        modifier = modifier.padding(start = 4.dp, top = 10.dp),
    )
}

/**
 * Bosiladigan qator: chapda belgi, o'rtada sarlavha va qiymat, o'ngda strelka.
 * `highlighted`: hali to'ldirilmagan narsa (masalan, manzil tanlanmagan) rang bilan ajratiladi.
 * `onClick` berilmasa, qator faqat ma'lumot ko'rsatadi.
 */
@Composable
fun LinkRow(
    @DrawableRes icon: Int,
    label: String,
    value: String,
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    highlighted: Boolean = false,
    tileContainer: Color = MaterialTheme.colorScheme.primaryContainer,
    tileTint: Color = MaterialTheme.colorScheme.primary,
) {
    val scheme = MaterialTheme.colorScheme
    val clickable = if (onClick != null) Modifier.clickable(role = Role.Button, onClick = onClick) else Modifier
    Row(
        modifier = modifier
            .fillMaxWidth()
            .then(clickable)
            .padding(horizontal = 16.dp, vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconTile(icon = icon, container = tileContainer, tint = tileTint)
        Spacer(Modifier.width(14.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(label, style = MaterialTheme.typography.bodySmall, color = scheme.hint)
            Spacer(Modifier.height(2.dp))
            Text(
                text = value,
                style = MaterialTheme.typography.titleSmall,
                color = if (highlighted) scheme.primary else scheme.onSurface,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
        }
        if (onClick != null) {
            Spacer(Modifier.width(8.dp))
            Icon(
                painter = painterResource(R.drawable.ic_chevron),
                contentDescription = null,
                tint = scheme.hint,
                modifier = Modifier.size(20.dp),
            )
        }
    }
}

/** Kartochka ichidagi qatorlar orasidagi ingichka chiziq (belgi ostidan boshlanmaydi). */
@Composable
fun RowDivider(modifier: Modifier = Modifier, inset: Dp = 72.dp) {
    Box(
        modifier = modifier
            .fillMaxWidth()
            .padding(start = inset, end = 16.dp)
            .height(1.dp)
            .background(MaterialTheme.colorScheme.outlineVariant),
    )
}

/** Punktir chiziq: chekdagidek, jami summa ustida. */
@Composable
fun DashedDivider(modifier: Modifier = Modifier) {
    val color = MaterialTheme.colorScheme.outline
    Canvas(
        modifier = modifier
            .fillMaxWidth()
            .height(1.dp),
    ) {
        drawLine(
            color = color,
            start = Offset(0f, size.height / 2),
            end = Offset(size.width, size.height / 2),
            strokeWidth = 1.dp.toPx(),
            pathEffect = PathEffect.dashPathEffect(floatArrayOf(4.dp.toPx(), 4.dp.toPx())),
        )
    }
}

/** "Taomlar ...... 35 000 so'm" qatori. `loading`: qiymat serverdan kutilmoqda (o'rnida skelet). */
@Composable
fun SummaryRow(
    label: String,
    value: String,
    valueColor: Color = Color.Unspecified,
    loading: Boolean = false,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 5.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = label,
            modifier = Modifier.weight(1f),
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        if (loading) {
            SkeletonBox(modifier = Modifier.size(width = 76.dp, height = 16.dp))
        } else {
            Text(
                text = value,
                style = if (valueColor == Color.Unspecified) {
                    MaterialTheme.typography.bodyLarge
                } else {
                    MaterialTheme.typography.titleSmall
                },
                color = valueColor,
            )
        }
    }
}

// ---------- Buyurtma holati ----------

/** Buyurtma holatiga mos fon rangi: yashil (yetkazildi), qizil (rad etildi), kulrang (bekor), sariq (faol). */
@Composable
fun statusContainerColor(status: String): Color {
    val scheme = MaterialTheme.colorScheme
    return when (status) {
        OrderStatus.DELIVERED -> scheme.successContainer
        OrderStatus.REJECTED -> scheme.errorContainer
        OrderStatus.CANCELLED -> if (scheme.isDark) scheme.surfaceVariant else Color(0xFFEFEAE3)
        else -> scheme.tertiaryContainer
    }
}

/** `statusContainerColor` ustidagi belgi va yozuv rangi. */
@Composable
fun statusContentColor(status: String): Color {
    val scheme = MaterialTheme.colorScheme
    return when (status) {
        OrderStatus.DELIVERED -> scheme.success
        OrderStatus.REJECTED -> scheme.onErrorContainer
        OrderStatus.CANCELLED -> if (scheme.isDark) scheme.onSurfaceVariant else Color(0xFF6F665E)
        else -> scheme.onTertiaryContainer
    }
}

/** Buyurtma holatiga mos belgi: soat, oshpaz qalpog'i, kuryer, tasdiq yoki xoch. */
@DrawableRes
fun statusIcon(status: String): Int = when (status) {
    OrderStatus.NEW -> R.drawable.ic_clock
    OrderStatus.ACCEPTED -> R.drawable.ic_chef
    OrderStatus.DELIVERING -> R.drawable.ic_bike
    OrderStatus.DELIVERED -> R.drawable.ic_check
    else -> R.drawable.ic_close
}

/** Buyurtma holati yozilgan rangli belgi: nuqta va yozuv. */
@Composable
fun StatusChip(status: String, label: String, modifier: Modifier = Modifier) {
    val content = statusContentColor(status)
    Row(
        modifier = modifier
            .clip(RoundedCornerShape(10.dp))
            .background(statusContainerColor(status))
            .padding(horizontal = 10.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier
                .size(6.dp)
                .clip(CircleShape)
                .background(content),
        )
        Spacer(Modifier.width(6.dp))
        Text(
            text = label,
            color = content,
            style = MaterialTheme.typography.labelSmall.copy(letterSpacing = 0.sp),
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

/** Buyurtma nechanchi bosqichda: 1 yuborildi, 2 qabul qilindi, 3 yo'lda, 4 yetkazildi, 0 bekor bo'lgan. */
fun orderStep(status: String): Int = when (status) {
    OrderStatus.NEW -> 1
    OrderStatus.ACCEPTED -> 2
    OrderStatus.DELIVERING -> 3
    OrderStatus.DELIVERED -> 4
    else -> 0
}

/**
 * To'rt bo'lakli chiziq: o'tilgan bosqichlar to'la, hozirgi bosqich yarim to'lgan.
 * Holat o'zgarganda bo'laklar ohista to'ladi.
 */
@Composable
fun OrderProgressBar(
    status: String,
    modifier: Modifier = Modifier,
    color: Color = MaterialTheme.colorScheme.primary,
    track: Color = MaterialTheme.colorScheme.outlineVariant,
) {
    val step = orderStep(status)
    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        repeat(4) { index ->
            val target = when {
                status == OrderStatus.DELIVERED -> 1f
                index < step - 1 -> 1f
                index == step - 1 -> 0.55f
                else -> 0f
            }
            val fraction by animateFloatAsState(
                targetValue = target,
                animationSpec = tween(600),
                label = "order-progress",
            )
            Box(
                modifier = Modifier
                    .weight(1f)
                    .height(6.dp)
                    .clip(RoundedCornerShape(50))
                    .background(track),
            ) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth(fraction)
                        .fillMaxHeight()
                        .background(color),
                )
            }
        }
    }
}

// ---------- Yuqori va pastki satrlar ----------

/**
 * Yuqori satr: orqaga tugmasi va sarlavha. Kontent uning ostiga xiralashib kirib ketadi.
 * `onBack` berilmasa, tugma chizilmaydi. `below`: sarlavha ostidagi qo'shimcha qator (masalan, filtrlar).
 */
@Composable
fun GlassTopBar(
    glass: HazeState,
    title: String,
    onBack: (() -> Unit)?,
    actions: @Composable RowScope.() -> Unit = {},
    below: (@Composable () -> Unit)? = null,
) {
    Box {
        GlassStrip(glass = glass, modifier = Modifier.matchParentSize(), fade = GlassFade.Bottom)
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .statusBarsPadding()
                .padding(top = 8.dp, bottom = 16.dp),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                if (onBack != null) {
                    RoundButton(icon = R.drawable.ic_back, label = "Orqaga", onClick = onBack)
                    Spacer(Modifier.width(12.dp))
                }
                Text(
                    text = title,
                    style = MaterialTheme.typography.headlineSmall,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f),
                )
                actions()
            }
            if (below != null) {
                Spacer(Modifier.height(12.dp))
                below()
            }
        }
    }
}

/** Ekran pastida suzib turadigan asosiy tugma joyi: ortidagi kontent xiralashib ko'rinadi. */
@Composable
fun BottomDock(glass: HazeState, content: @Composable ColumnScope.() -> Unit) {
    Box {
        GlassStrip(glass = glass, modifier = Modifier.matchParentSize(), fade = GlassFade.Top)
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .navigationBarsPadding()
                .padding(start = 16.dp, end = 16.dp, top = 26.dp, bottom = 14.dp),
            content = content,
        )
    }
}

// ---------- Tugmalar ----------

/**
 * Asosiy tugma: qizil, ostida o'z rangidagi yorug' soya.
 * `trailing` berilsa, matn chapda, u (masalan narx) o'ngdagi shaffof "tabletka" ichida turadi.
 */
@Composable
fun BigButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    loading: Boolean = false,
    trailing: String? = null,
) {
    val scheme = MaterialTheme.colorScheme
    val lit = enabled || loading
    val shape = RoundedCornerShape(20.dp)
    val source = remember { MutableInteractionSource() }
    val glow = if (lit) {
        Modifier.shadow(
            elevation = 14.dp,
            shape = shape,
            clip = false,
            ambientColor = scheme.primary.copy(alpha = 0.35f),
            spotColor = scheme.primary.copy(alpha = 0.60f),
        )
    } else {
        Modifier
    }
    // Avtomatik sinov tugmani "Buyurtma berish · 45 000 so'm" ko'rinishida izlaydi
    val described = if (trailing != null) {
        Modifier.semantics { contentDescription = "$text · $trailing" }
    } else {
        Modifier
    }
    Surface(
        onClick = onClick,
        enabled = enabled && !loading,
        modifier = modifier
            .fillMaxWidth()
            .height(58.dp)
            .pressScale(source)
            .then(glow)
            .then(described),
        shape = shape,
        color = if (lit) scheme.primary else scheme.outlineVariant,
        contentColor = if (lit) scheme.onPrimary else scheme.hint,
        interactionSource = source,
    ) {
        // Ustki qismdagi yengil yaltirash: tugma shishadek bo'rtib ko'rinadi
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(
                    Brush.verticalGradient(
                        listOf(Color.White.copy(alpha = if (lit) 0.16f else 0f), Color.Transparent),
                    ),
                ),
        )
        Row(
            modifier = Modifier
                .fillMaxSize()
                .padding(start = 22.dp, end = if (trailing != null && !loading) 9.dp else 22.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.Center,
        ) {
            when {
                loading -> CircularProgressIndicator(
                    modifier = Modifier.size(22.dp),
                    color = LocalContentColor.current,
                    strokeWidth = 2.5.dp,
                )

                trailing != null -> {
                    Text(
                        text = text,
                        style = MaterialTheme.typography.titleMedium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f),
                    )
                    Spacer(Modifier.width(10.dp))
                    Text(
                        text = trailing,
                        style = MaterialTheme.typography.titleSmall,
                        maxLines = 1,
                        modifier = Modifier
                            .clip(RoundedCornerShape(13.dp))
                            .background(Color.White.copy(alpha = if (lit) 0.18f else 0f))
                            .padding(horizontal = 14.dp, vertical = 10.dp),
                    )
                }

                else -> Text(
                    text = text,
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

/**
 * Ikkinchi darajali tugma: oq fonli, ingichka hoshiyali, ixtiyoriy belgi bilan.
 * `accent`: yozuvi qizil (qo'ng'iroq qilish). `danger`: xavfli amal (bekor qilish).
 */
@Composable
fun SoftButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    @DrawableRes icon: Int? = null,
    enabled: Boolean = true,
    accent: Boolean = false,
    danger: Boolean = false,
) {
    val scheme = MaterialTheme.colorScheme
    val source = remember { MutableInteractionSource() }
    val content = when {
        !enabled -> scheme.hint
        accent -> scheme.primary
        danger -> scheme.onSurfaceVariant
        else -> scheme.onSurface
    }
    Surface(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier
            .fillMaxWidth()
            .height(52.dp)
            .pressScale(source),
        shape = RoundedCornerShape(18.dp),
        color = scheme.surface,
        contentColor = content,
        border = BorderStroke(1.dp, scheme.outlineVariant),
        interactionSource = source,
    ) {
        Row(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.Center,
        ) {
            if (icon != null) {
                Icon(painterResource(icon), contentDescription = null, modifier = Modifier.size(19.dp))
                Spacer(Modifier.width(8.dp))
            }
            Text(
                text = text,
                style = MaterialTheme.typography.labelLarge,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

// ---------- Tasdiqlash oynasi ----------

/** Ha yoki yo'q deb so'raydigan oyna. Ochilganda ortidagi ekran xiralashadi. */
@Composable
fun ConfirmDialog(
    title: String,
    text: String,
    confirmLabel: String,
    dismissLabel: String,
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = scheme.surface,
        shape = RoundedCornerShape(28.dp),
        title = {
            BlurBehindEffect()
            Text(title, style = MaterialTheme.typography.titleLarge)
        },
        text = {
            Text(text, style = MaterialTheme.typography.bodyLarge, color = scheme.onSurfaceVariant)
        },
        confirmButton = {
            Button(
                onClick = onConfirm,
                shape = RoundedCornerShape(14.dp),
                colors = ButtonDefaults.buttonColors(containerColor = scheme.primary, contentColor = scheme.onPrimary),
            ) { Text(confirmLabel, style = MaterialTheme.typography.labelLarge) }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text(dismissLabel, style = MaterialTheme.typography.labelLarge, color = scheme.onSurfaceVariant)
            }
        },
    )
}

// ---------- Matn kiritish ----------

/**
 * Matn kiritish maydonlari uchun: chiziqsiz, yumaloq burchakli.
 * Fon odatda oq; kartochka ichidagi maydonga shaffof fon beriladi.
 */
@Composable
fun fieldColors(container: Color = MaterialTheme.colorScheme.surface): TextFieldColors {
    val scheme = MaterialTheme.colorScheme
    return TextFieldDefaults.colors(
        focusedContainerColor = container,
        unfocusedContainerColor = container,
        disabledContainerColor = container,
        errorContainerColor = container,
        focusedIndicatorColor = Color.Transparent,
        unfocusedIndicatorColor = Color.Transparent,
        disabledIndicatorColor = Color.Transparent,
        errorIndicatorColor = Color.Transparent,
        focusedLabelColor = scheme.primary,
        unfocusedLabelColor = scheme.hint,
        focusedPlaceholderColor = scheme.hint,
        unfocusedPlaceholderColor = scheme.hint,
        focusedLeadingIconColor = scheme.hint,
        unfocusedLeadingIconColor = scheme.hint,
    )
}

/** Oq maydon atrofidagi ingichka hoshiya (maketdagidek). */
@Composable
fun Modifier.fieldBorder(shape: Shape = RoundedCornerShape(18.dp)): Modifier =
    border(1.dp, MaterialTheme.colorScheme.outlineVariant, shape)

/** Telefon raqamni "90 123 45 67" ko'rinishida ko'rsatadi (maydonda faqat 9 ta raqam saqlanadi). */
object PhoneVisualTransformation : VisualTransformation {
    override fun filter(text: AnnotatedString): TransformedText {
        val raw = text.text
        val formatted = StringBuilder()
        raw.forEachIndexed { index, char ->
            if (index == 2 || index == 5 || index == 7) formatted.append(' ')
            formatted.append(char)
        }
        val formattedLength = formatted.length
        val rawLength = raw.length
        val mapping = object : OffsetMapping {
            override fun originalToTransformed(offset: Int): Int {
                var result = offset
                if (offset > 2) result++
                if (offset > 5) result++
                if (offset > 7) result++
                return result.coerceIn(0, formattedLength)
            }

            override fun transformedToOriginal(offset: Int): Int {
                var result = offset
                if (offset > 2) result--
                if (offset > 6) result--
                if (offset > 9) result--
                return result.coerceIn(0, rawLength)
            }
        }
        return TransformedText(AnnotatedString(formatted.toString()), mapping)
    }
}
