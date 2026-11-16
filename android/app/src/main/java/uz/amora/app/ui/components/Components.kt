package uz.amora.app.ui.components

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextFieldColors
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.input.OffsetMapping
import androidx.compose.ui.text.input.TransformedText
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import coil.request.ImageRequest
import uz.amora.app.R
import uz.amora.app.data.OrderStatus
import uz.amora.app.ui.theme.onSuccessContainer
import uz.amora.app.ui.theme.successContainer

/** Taom rasmi. Rasm yo'q yoki yuklanmagan bo'lsa, o'rnida yumshoq fon va likopcha belgisi turadi. */
@Composable
fun ProductImage(url: String?, modifier: Modifier = Modifier, iconSize: Dp = 44.dp) {
    val scheme = MaterialTheme.colorScheme
    Box(
        modifier = modifier.background(
            Brush.linearGradient(listOf(scheme.surfaceVariant, scheme.primaryContainer)),
        ),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            painter = painterResource(R.drawable.ic_dish),
            contentDescription = null,
            tint = scheme.primary.copy(alpha = 0.26f),
            modifier = Modifier.size(iconSize),
        )
        if (url != null) {
            AsyncImage(
                model = ImageRequest.Builder(LocalContext.current)
                    .data(url)
                    .crossfade(true)
                    .build(),
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.matchParentSize(),
            )
        }
    }
}

/**
 * "−  2  +" ko'rinishidagi son tanlagich.
 * `tonal`: neytral kulrang ko'rinish (savat qatorlarida), aks holda asosiy rangda.
 * `label`: son o'rniga ko'rsatiladigan matn, masalan "2 ta · 70 000 so'm".
 */
@Composable
fun QuantityStepper(
    quantity: Int,
    onMinus: () -> Unit,
    onPlus: () -> Unit,
    modifier: Modifier = Modifier,
    height: Dp = 44.dp,
    corner: Dp = 14.dp,
    tonal: Boolean = false,
    label: String? = null,
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
        StepperButton(minus = true, label = "Kamaytirish", size = height, tint = content, onClick = onMinus)
        Box(modifier = Modifier.weight(1f), contentAlignment = Alignment.Center) {
            AnimatedContent(targetState = label ?: quantity.toString(), label = "quantity") { value ->
                Text(
                    text = value,
                    color = content,
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 1,
                )
            }
        }
        StepperButton(minus = false, label = "Ko'paytirish", size = height, tint = content, onClick = onPlus)
    }
}

@Composable
private fun StepperButton(minus: Boolean, label: String, size: Dp, tint: Color, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .size(size)
            .clickable(onClickLabel = label, role = Role.Button, onClick = onClick)
            .semantics { contentDescription = label },
        contentAlignment = Alignment.Center,
    ) {
        if (minus) {
            Box(
                modifier = Modifier
                    .size(width = 14.dp, height = 2.5.dp)
                    .clip(RoundedCornerShape(50))
                    .background(tint),
            )
        } else {
            Icon(Icons.Default.Add, contentDescription = null, tint = tint, modifier = Modifier.size(20.dp))
        }
    }
}

/** Taom kartochkasidagi tugma: ustida narx yozilgan, bosilganda taom savatga tushadi. */
@Composable
fun PriceAddButton(price: String, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val scheme = MaterialTheme.colorScheme
    Row(
        modifier = modifier
            .height(44.dp)
            .clip(RoundedCornerShape(14.dp))
            .background(scheme.surfaceVariant)
            .clickable(onClickLabel = "Qo'shish", role = Role.Button, onClick = onClick)
            .semantics { contentDescription = "Qo'shish: $price" }
            .padding(start = 12.dp, end = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = price,
            modifier = Modifier.weight(1f),
            style = MaterialTheme.typography.titleSmall,
            color = scheme.onSurface,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Box(
            modifier = Modifier
                .size(28.dp)
                .clip(CircleShape)
                .background(scheme.surface),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                imageVector = Icons.Default.Add,
                contentDescription = null,
                tint = scheme.primary,
                modifier = Modifier.size(18.dp),
            )
        }
    }
}

/** Yumaloq belgili tugma: orqaga, qo'ng'iroq, joylashuv va h.k. */
@Composable
fun CircleIconButton(
    icon: ImageVector,
    label: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    container: Color = MaterialTheme.colorScheme.surface,
    tint: Color = MaterialTheme.colorScheme.onSurface,
    elevation: Dp = 0.dp,
) {
    Surface(
        onClick = onClick,
        modifier = modifier.size(44.dp),
        shape = CircleShape,
        color = container,
        contentColor = tint,
        shadowElevation = elevation,
    ) {
        Box(contentAlignment = Alignment.Center) {
            Icon(icon, contentDescription = label, modifier = Modifier.size(22.dp))
        }
    }
}

/** Belgi turadigan rangli doira (ro'yxat qatorlari va holat kartochkalarida). */
@Composable
fun IconBadge(
    modifier: Modifier = Modifier,
    size: Dp = 44.dp,
    container: Color = MaterialTheme.colorScheme.primaryContainer,
    content: @Composable () -> Unit,
) {
    Box(
        modifier = modifier
            .size(size)
            .clip(CircleShape)
            .background(container),
        contentAlignment = Alignment.Center,
    ) {
        content()
    }
}

@Composable
fun LoadingBox(modifier: Modifier = Modifier) {
    Box(modifier = modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        CircularProgressIndicator(strokeWidth = 3.dp)
    }
}

/** Yuklanayotgan kontent o'rnida turadigan, ohista "nafas oladigan" blok. */
@Composable
fun SkeletonBox(modifier: Modifier = Modifier, shape: Shape = MaterialTheme.shapes.medium) {
    val transition = rememberInfiniteTransition(label = "skeleton")
    val alpha by transition.animateFloat(
        initialValue = 0.45f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(750), RepeatMode.Reverse),
        label = "skeleton-alpha",
    )
    Box(
        modifier = modifier
            .clip(shape)
            .background(MaterialTheme.colorScheme.outlineVariant.copy(alpha = alpha)),
    )
}

/** Bo'sh holat yoki xato: doira ichidagi belgi, sarlavha, izoh va ixtiyoriy tugma. */
@Composable
fun MessageBox(
    icon: ImageVector,
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
        IconBadge(size = 96.dp) {
            Icon(icon, contentDescription = null, tint = scheme.primary, modifier = Modifier.size(42.dp))
        }
        Spacer(Modifier.height(20.dp))
        Text(title, style = MaterialTheme.typography.titleLarge, textAlign = TextAlign.Center)
        if (text != null) {
            Spacer(Modifier.height(6.dp))
            Text(
                text = text,
                style = MaterialTheme.typography.bodyMedium,
                color = scheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )
        }
        if (actionLabel != null && onAction != null) {
            Spacer(Modifier.height(24.dp))
            Button(
                onClick = onAction,
                modifier = Modifier.height(50.dp),
                shape = MaterialTheme.shapes.medium,
                contentPadding = PaddingValues(horizontal = 28.dp),
            ) {
                Text(actionLabel, style = MaterialTheme.typography.labelLarge)
            }
        }
    }
}

/** Oq fonli, burchaklari yumaloq blok. */
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
        Surface(onClick = onClick, modifier = modifier.fillMaxWidth(), shape = shape, color = color) {
            Column(modifier = Modifier.padding(padding), content = content)
        }
    } else {
        Surface(modifier = modifier.fillMaxWidth(), shape = shape, color = color) {
            Column(modifier = Modifier.padding(padding), content = content)
        }
    }
}

/**
 * Bosiladigan qator: chapda doiradagi belgi, o'rtada sarlavha va qiymat, o'ngda strelka.
 * `highlighted`: hali to'ldirilmagan narsa (masalan, manzil tanlanmagan) rang bilan ajratiladi.
 */
@Composable
fun LinkRow(
    icon: ImageVector,
    label: String,
    value: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    highlighted: Boolean = false,
) {
    val scheme = MaterialTheme.colorScheme
    Row(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(18.dp))
            .clickable(role = Role.Button, onClick = onClick)
            .padding(horizontal = 12.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconBadge(
            size = 40.dp,
            container = if (highlighted) scheme.primaryContainer else scheme.surfaceVariant,
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = if (highlighted) scheme.primary else scheme.onSurface,
                modifier = Modifier.size(20.dp),
            )
        }
        Spacer(Modifier.width(12.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(label, style = MaterialTheme.typography.labelMedium, color = scheme.onSurfaceVariant)
            Text(
                text = value,
                style = MaterialTheme.typography.titleSmall,
                color = if (highlighted) scheme.primary else scheme.onSurface,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
        }
        Spacer(Modifier.width(8.dp))
        Icon(
            imageVector = Icons.AutoMirrored.Filled.KeyboardArrowRight,
            contentDescription = null,
            tint = scheme.onSurfaceVariant,
        )
    }
}

@Composable
fun SummaryRow(label: String, value: String, strong: Boolean = false, valueColor: Color = Color.Unspecified) {
    val style = if (strong) MaterialTheme.typography.titleLarge else MaterialTheme.typography.bodyLarge
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 5.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = label,
            modifier = Modifier.weight(1f),
            style = style,
            color = if (strong) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            text = value,
            style = if (strong) style else MaterialTheme.typography.titleMedium,
            color = valueColor,
        )
    }
}

/** Buyurtma holatiga mos fon rangi: yashil (yetkazildi), qizil (rad etildi), kulrang (bekor), asosiy (faol). */
@Composable
fun statusContainerColor(status: String): Color {
    val scheme = MaterialTheme.colorScheme
    return when (status) {
        OrderStatus.DELIVERED -> scheme.successContainer
        OrderStatus.REJECTED -> scheme.errorContainer
        OrderStatus.CANCELLED -> scheme.surfaceVariant
        else -> scheme.primaryContainer
    }
}

/** `statusContainerColor` ustidagi belgi va yozuv rangi. */
@Composable
fun statusContentColor(status: String): Color {
    val scheme = MaterialTheme.colorScheme
    return when (status) {
        OrderStatus.DELIVERED -> scheme.onSuccessContainer
        OrderStatus.REJECTED -> scheme.onErrorContainer
        OrderStatus.CANCELLED -> scheme.onSurfaceVariant
        else -> scheme.onPrimaryContainer
    }
}

/** Buyurtma holati yozilgan rangli belgi. */
@Composable
fun StatusBadge(status: String, label: String, modifier: Modifier = Modifier) {
    val content = statusContentColor(status)
    Row(
        modifier = modifier
            .clip(RoundedCornerShape(50))
            .background(statusContainerColor(status))
            .padding(start = 8.dp, end = 11.dp, top = 5.dp, bottom = 5.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        OrderStatusIcon(status = status, modifier = Modifier.size(15.dp), tint = content)
        Spacer(Modifier.width(5.dp))
        Text(
            text = label,
            color = content,
            style = MaterialTheme.typography.labelMedium,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

/** Buyurtma holatiga mos belgi: soat, qozon, skuter, tasdiq yoki xoch. */
@Composable
fun OrderStatusIcon(
    status: String,
    modifier: Modifier = Modifier,
    tint: Color = LocalContentColor.current,
) {
    val drawable = when (status) {
        OrderStatus.NEW -> R.drawable.ic_clock
        OrderStatus.ACCEPTED -> R.drawable.ic_pot
        OrderStatus.DELIVERING -> R.drawable.ic_scooter
        else -> null
    }
    if (drawable != null) {
        Icon(painterResource(drawable), contentDescription = null, modifier = modifier, tint = tint)
    } else {
        Icon(
            imageVector = if (status == OrderStatus.DELIVERED) Icons.Default.Check else Icons.Default.Close,
            contentDescription = null,
            modifier = modifier,
            tint = tint,
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

/** To'rt bo'lakli chiziq: buyurtma qaysi bosqichga yetgani bir qarashda ko'rinadi. */
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
            Box(
                modifier = Modifier
                    .weight(1f)
                    .height(5.dp)
                    .clip(RoundedCornerShape(50))
                    .background(if (index < step) color else track),
            )
        }
    }
}

/** Orqaga tugmasi bor yuqori panel. */
@Composable
fun BackTopBar(
    title: String,
    onBack: () -> Unit,
    actions: @Composable RowScope.() -> Unit = {},
) {
    TopAppBar(
        title = {
            Text(
                text = title,
                style = MaterialTheme.typography.titleLarge,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        },
        navigationIcon = {
            CircleIconButton(
                icon = Icons.AutoMirrored.Filled.ArrowBack,
                label = "Orqaga",
                onClick = onBack,
                modifier = Modifier.padding(start = 12.dp, end = 8.dp),
            )
        },
        actions = actions,
        colors = TopAppBarDefaults.topAppBarColors(
            containerColor = MaterialTheme.colorScheme.background,
            scrolledContainerColor = MaterialTheme.colorScheme.background,
        ),
    )
}

/** Pastki menyudagi bo'limlar (Buyurtmalar, Profil) uchun katta sarlavhali yuqori panel. */
@Composable
fun TitleTopBar(title: String) {
    TopAppBar(
        title = {
            Text(
                text = title,
                style = MaterialTheme.typography.headlineMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.padding(start = 4.dp),
            )
        },
        colors = TopAppBarDefaults.topAppBarColors(
            containerColor = MaterialTheme.colorScheme.background,
            scrolledContainerColor = MaterialTheme.colorScheme.background,
        ),
    )
}

/** Ekran pastidagi asosiy tugma turadigan panel. */
@Composable
fun BottomActionBar(content: @Composable ColumnScope.() -> Unit) {
    Surface(
        color = MaterialTheme.colorScheme.surface,
        shape = RoundedCornerShape(topStart = 24.dp, topEnd = 24.dp),
        shadowElevation = 16.dp,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .navigationBarsPadding()
                .padding(start = 16.dp, end = 16.dp, top = 14.dp, bottom = 12.dp),
            content = content,
        )
    }
}

/** Asosiy tugma. `trailing` berilsa, matn chapda, u (masalan narx) o'ngda turadi. */
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
    Button(
        onClick = onClick,
        enabled = enabled && !loading,
        modifier = modifier
            .fillMaxWidth()
            .height(56.dp),
        shape = RoundedCornerShape(18.dp),
        contentPadding = PaddingValues(horizontal = 20.dp),
        colors = ButtonDefaults.buttonColors(
            disabledContainerColor = if (loading) scheme.primary else scheme.surfaceVariant,
            disabledContentColor = if (loading) scheme.onPrimary else scheme.onSurfaceVariant,
        ),
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
                Spacer(Modifier.width(12.dp))
                Text(trailing, style = MaterialTheme.typography.titleMedium, maxLines = 1)
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

/** Ikkinchi darajali tugma: oq fonli, ixtiyoriy belgi bilan. `danger`: xavfli amal (bekor qilish). */
@Composable
fun SoftButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    icon: ImageVector? = null,
    enabled: Boolean = true,
    danger: Boolean = false,
) {
    val scheme = MaterialTheme.colorScheme
    Button(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier
            .fillMaxWidth()
            .height(52.dp),
        shape = MaterialTheme.shapes.medium,
        contentPadding = PaddingValues(horizontal = 16.dp),
        colors = ButtonDefaults.buttonColors(
            containerColor = scheme.surface,
            contentColor = if (danger) scheme.error else scheme.onSurface,
            disabledContainerColor = scheme.surface,
            disabledContentColor = scheme.onSurfaceVariant,
        ),
    ) {
        if (icon != null) {
            Icon(icon, contentDescription = null, modifier = Modifier.size(20.dp))
            Spacer(Modifier.width(8.dp))
        }
        Text(text, style = MaterialTheme.typography.labelLarge, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}

/**
 * Matn kiritish maydonlari uchun: chiziqsiz, yumaloq burchakli.
 * Fon odatda oq; oq panel ustida turadigan maydonga kulrang fon beriladi.
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
        unfocusedLabelColor = scheme.onSurfaceVariant,
    )
}

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
