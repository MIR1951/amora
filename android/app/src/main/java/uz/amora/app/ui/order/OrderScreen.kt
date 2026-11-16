package uz.amora.app.ui.order

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
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
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import uz.amora.app.AppContainer
import uz.amora.app.R
import uz.amora.app.data.ApiException
import uz.amora.app.data.Order
import uz.amora.app.data.OrderStatus
import uz.amora.app.ui.components.BigButton
import uz.amora.app.ui.components.BottomDock
import uz.amora.app.ui.components.ConfirmDialog
import uz.amora.app.ui.components.GlassTopBar
import uz.amora.app.ui.components.LinkRow
import uz.amora.app.ui.components.MessageBox
import uz.amora.app.ui.components.OrderProgressBar
import uz.amora.app.ui.components.PriceText
import uz.amora.app.ui.components.RefreshBox
import uz.amora.app.ui.components.RowDivider
import uz.amora.app.ui.components.SectionCard
import uz.amora.app.ui.components.SkeletonBox
import uz.amora.app.ui.components.SoftButton
import uz.amora.app.ui.components.glassSource
import uz.amora.app.ui.components.rememberGlassState
import uz.amora.app.ui.components.softShadow
import uz.amora.app.ui.profile.dialPhone
import uz.amora.app.ui.theme.PriceLargeStyle
import uz.amora.app.ui.theme.amber
import uz.amora.app.ui.theme.hint
import uz.amora.app.ui.theme.info
import uz.amora.app.ui.theme.infoContainer
import uz.amora.app.ui.theme.ink
import uz.amora.app.ui.theme.onInkMuted
import uz.amora.app.ui.theme.success
import uz.amora.app.util.formatDateTime
import uz.amora.app.util.formatPhone
import uz.amora.app.util.formatSum
import uz.amora.app.util.formatTime

// Buyurtma tugallanmagan bo'lsa, holati shuncha vaqtda bir marta serverdan so'raladi
private const val POLL_INTERVAL_MS = 7_000L

data class OrderUiState(
    val loading: Boolean = true,
    val refreshing: Boolean = false,
    val order: Order? = null,
    val error: String? = null,
    val cancelling: Boolean = false,
    // Bir martalik xabar (masalan, bekor qilib bo'lmadi)
    val message: String? = null,
)

class OrderViewModel(private val container: AppContainer, private val orderId: Int) : ViewModel() {
    private val _state = MutableStateFlow(OrderUiState())
    val state: StateFlow<OrderUiState> = _state.asStateFlow()

    /** Buyurtmani serverdan qayta o'qiydi. Xato bo'lsa, avval yuklangan ma'lumot ekranda qoladi. */
    suspend fun refresh() {
        try {
            val order = container.api.order(orderId)
            _state.update { it.copy(loading = false, refreshing = false, order = order, error = null) }
        } catch (e: ApiException) {
            _state.update { it.copy(loading = false, refreshing = false, error = e.message) }
        }
    }

    fun retry() {
        _state.update { it.copy(loading = it.order == null, error = null) }
        viewModelScope.launch { refresh() }
    }

    fun pullToRefresh() {
        _state.update { it.copy(refreshing = true) }
        viewModelScope.launch { refresh() }
    }

    fun cancel() {
        if (_state.value.cancelling) return
        _state.update { it.copy(cancelling = true) }
        viewModelScope.launch {
            try {
                val order = container.api.cancelOrder(orderId)
                _state.update { it.copy(cancelling = false, order = order) }
            } catch (e: ApiException) {
                _state.update { it.copy(cancelling = false, message = e.message) }
                // Kafe allaqachon qabul qilgan bo'lishi mumkin: holatni yangilaymiz
                if (!e.isNetwork) refresh()
            }
        }
    }

    fun clearMessage() {
        _state.update { it.copy(message = null) }
    }

    /** Xuddi shu taomlarni savatga soladi. Savatga tushgan taomlar sonini qaytaradi. */
    fun repeatOrder(): Int {
        val order = _state.value.order ?: return 0
        val added = repeatOrder(container, order)
        if (added == 0) _state.update { it.copy(message = REPEAT_UNAVAILABLE) }
        return added
    }
}

const val REPEAT_UNAVAILABLE = "Bu taomlar hozir menyuda yo'q"

/**
 * Buyurtmadagi taomlarni savatga soladi (savatdagi eski taomlar o'rniga).
 * Savatga tushgan taomlar turini qaytaradi: 0 bo'lsa, hech biri hozir menyuda yo'q.
 */
fun repeatOrder(container: AppContainer, order: Order): Int {
    val menuProducts = container.catalog.state.value.menu?.products
    val items = LinkedHashMap<Int, Int>()
    for (item in order.items) {
        val productId = item.productId ?: continue
        // Menyu yuklangan bo'lsa, faqat hozir sotuvda bor taomlar olinadi
        if (menuProducts != null && menuProducts.none { it.id == productId && it.isAvailable }) continue
        items[productId] = (items[productId] ?: 0) + item.quantity
    }
    if (items.isNotEmpty()) container.cart.replace(items)
    return items.size
}

/** Bitta buyurtma: jonli holati, bosqichlari, tarkibi va summasi. Faol buyurtma o'zi yangilanib turadi. */
@Composable
fun OrderScreen(
    container: AppContainer,
    orderId: Int,
    onBack: () -> Unit,
    onOpenCart: () -> Unit,
) {
    val vm: OrderViewModel = viewModel(
        key = "order-$orderId",
        factory = viewModelFactory { initializer { OrderViewModel(container, orderId) } },
    )
    val state = vm.state.collectAsStateWithLifecycle().value
    val shop = container.catalog.state.collectAsStateWithLifecycle().value.shop
    val context = LocalContext.current
    val scheme = MaterialTheme.colorScheme
    val glass = rememberGlassState()
    val snackbar = remember { SnackbarHostState() }
    var confirmCancel by rememberSaveable { mutableStateOf(false) }

    // Ekran ko'rinib turganda holat yangilanib turadi; buyurtma tugagach so'rovlar to'xtaydi
    val lifecycleOwner = LocalLifecycleOwner.current
    LaunchedEffect(lifecycleOwner, orderId) {
        lifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
            while (true) {
                vm.refresh()
                val order = vm.state.value.order
                if (order != null && !order.isActive) break
                delay(POLL_INTERVAL_MS)
            }
        }
    }

    val message = state.message
    LaunchedEffect(message) {
        if (message != null) {
            snackbar.showSnackbar(message)
            vm.clearMessage()
        }
    }

    val order = state.order
    // Pastki panel bor paytda u tizim tugmalari uchun joyni o'zi qoldiradi
    val docked = order != null && !order.isActive
    val systemBarSpace = if (docked) Modifier else Modifier.navigationBarsPadding()

    Scaffold(
        containerColor = scheme.background,
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        topBar = { GlassTopBar(glass = glass, title = "Buyurtma №$orderId", onBack = onBack) },
        snackbarHost = { SnackbarHost(snackbar, modifier = systemBarSpace) },
        bottomBar = {
            // Tugagan buyurtmani bir bosishda takrorlash mumkin
            if (docked) {
                BottomDock(glass = glass) {
                    BigButton(
                        text = "Yana shunday buyurtma berish",
                        onClick = {
                            if (vm.repeatOrder() > 0) onOpenCart()
                        },
                    )
                }
            }
        },
    ) { padding ->
        val top = padding.calculateTopPadding()
        val bottom = padding.calculateBottomPadding()
        RefreshBox(
            refreshing = state.refreshing,
            onRefresh = { vm.pullToRefresh() },
            modifier = Modifier
                .fillMaxSize()
                .glassSource(glass),
            indicatorTop = top,
        ) {
            when {
                order == null && state.loading -> OrderSkeleton(top = top)

                order == null -> MessageBox(
                    icon = R.drawable.ic_refresh,
                    title = "Buyurtma yuklanmadi",
                    text = state.error,
                    actionLabel = "Qayta urinish",
                    onAction = { vm.retry() },
                    modifier = Modifier.padding(top = top),
                )

                else -> Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .verticalScroll(rememberScrollState())
                        .padding(start = 16.dp, end = 16.dp, top = top, bottom = bottom)
                        .then(systemBarSpace)
                        .padding(bottom = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    StatusHero(order)

                    val stopped = order.status == OrderStatus.REJECTED || order.status == OrderStatus.CANCELLED
                    if (!stopped) Timeline(order)

                    val cafePhone = shop?.phone
                    if (order.isActive && !cafePhone.isNullOrBlank()) {
                        SoftButton(
                            text = "Kafega qo'ng'iroq",
                            onClick = { dialPhone(context, cafePhone) },
                            icon = R.drawable.ic_phone,
                            accent = true,
                        )
                    }

                    if (order.canCancel) {
                        SoftButton(
                            text = if (state.cancelling) "Bekor qilinmoqda…" else "Buyurtmani bekor qilish",
                            onClick = { confirmCancel = true },
                            icon = R.drawable.ic_close,
                            enabled = !state.cancelling,
                            danger = true,
                        )
                    }

                    ItemsCard(order)
                    DetailsCard(order)
                }
            }
        }
    }

    if (confirmCancel) {
        ConfirmDialog(
            title = "Buyurtmani bekor qilasizmi?",
            text = "Kafe buyurtmani hali qabul qilmagan. Bekor qilsangiz, u kafega yuborilmaydi.",
            confirmLabel = "Bekor qilish",
            dismissLabel = "Yo'q, qolsin",
            onConfirm = {
                confirmCancel = false
                vm.cancel()
            },
            onDismiss = { confirmCancel = false },
        )
    }
}

private fun statusDescription(order: Order): String = when (order.status) {
    OrderStatus.NEW -> "Buyurtmangiz kafega yuborildi. Tasdiqlanishini kuting."
    OrderStatus.ACCEPTED -> "Kafe buyurtmani qabul qildi va tayyorlamoqda."
    OrderStatus.DELIVERING -> "Kuryer buyurtmangizni olib yo'lga chiqdi."
    OrderStatus.DELIVERED -> "Buyurtma yetkazildi. Yoqimli ishtaha!"
    OrderStatus.REJECTED -> {
        val reason = order.rejectReason
        if (reason.isNullOrBlank()) {
            "Afsuski, kafe buyurtmani qabul qila olmadi."
        } else {
            "Afsuski, kafe buyurtmani qabul qila olmadi. Sabab: $reason"
        }
    }
    OrderStatus.CANCELLED -> "Siz bu buyurtmani bekor qilgansiz."
    else -> ""
}

/** Holat vaqti ostidagi qisqa izoh: shu vaqtda nima bo'lgani. */
private fun statusTimeCaption(status: String): String = when (status) {
    OrderStatus.NEW -> "yuborildi"
    OrderStatus.ACCEPTED -> "qabul qilindi"
    OrderStatus.DELIVERING -> "yo'lga chiqdi"
    OrderStatus.DELIVERED -> "yetkazildi"
    OrderStatus.REJECTED -> "javob berildi"
    OrderStatus.CANCELLED -> "to'xtatildi"
    else -> ""
}

private data class Step(val status: String, val label: String, val icon: Int)

private val STEPS = listOf(
    Step(OrderStatus.NEW, "Buyurtma yuborildi", R.drawable.ic_send),
    Step(OrderStatus.ACCEPTED, "Kafe qabul qildi", R.drawable.ic_chef),
    Step(OrderStatus.DELIVERING, "Kuryer yo'lga chiqdi", R.drawable.ic_bike),
    Step(OrderStatus.DELIVERED, "Yetkazildi", R.drawable.ic_home),
)

/** Ko'mir rangli blok: buyurtma hozir qaysi holatda, qachondan beri va umumiy yo'lning qancha qismi o'tilgan. */
@Composable
private fun StatusHero(order: Order) {
    val scheme = MaterialTheme.colorScheme
    val stopped = order.status == OrderStatus.REJECTED || order.status == OrderStatus.CANCELLED
    val delivered = order.status == OrderStatus.DELIVERED
    val dotColor = when {
        order.isActive -> scheme.amber
        delivered -> Color(0xFF4CCB8C)
        else -> scheme.onInkMuted
    }
    val time = (order.history.lastOrNull { it.status == order.status }?.createdAt ?: order.updatedAt)
    val shape = RoundedCornerShape(30.dp)
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .softShadow(shape, elevation = 16.dp, alpha = 0.24f)
            .clip(shape)
            .background(scheme.ink)
            .padding(start = 18.dp, end = 18.dp, top = 16.dp, bottom = 18.dp),
    ) {
        Row(verticalAlignment = Alignment.Top) {
            Column(modifier = Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    LiveDot(color = dotColor, pulsing = order.isActive)
                    Spacer(Modifier.width(6.dp))
                    Text(
                        text = if (order.isActive) "Jonli holat" else "Yakunlangan",
                        style = MaterialTheme.typography.bodySmall,
                        color = scheme.onInkMuted,
                    )
                }
                Spacer(Modifier.height(8.dp))
                AnimatedContent(
                    targetState = order.statusLabel,
                    transitionSpec = {
                        (fadeIn(tween(260)) + slideInVertically(tween(320)) { it / 3 }) togetherWith
                            (fadeOut(tween(180)) + slideOutVertically(tween(260)) { -it / 3 })
                    },
                    label = "status-title",
                ) { label ->
                    Text(
                        text = label,
                        style = MaterialTheme.typography.headlineLarge,
                        color = Color.White,
                    )
                }
            }
            Spacer(Modifier.width(12.dp))
            Column(
                modifier = Modifier.padding(top = 2.dp),
                horizontalAlignment = Alignment.End,
            ) {
                Text(text = formatTime(time), style = PriceLargeStyle, color = Color.White, maxLines = 1)
                Text(
                    text = statusTimeCaption(order.status),
                    style = MaterialTheme.typography.bodySmall,
                    color = scheme.onInkMuted,
                    maxLines = 1,
                    textAlign = TextAlign.End,
                )
            }
        }
        Spacer(Modifier.height(8.dp))
        Text(
            text = statusDescription(order),
            style = MaterialTheme.typography.bodyMedium,
            color = scheme.onInkMuted,
        )
        if (!stopped) {
            Spacer(Modifier.height(16.dp))
            OrderProgressBar(
                status = order.status,
                color = if (delivered) Color(0xFF4CCB8C) else scheme.primary,
                track = Color.White.copy(alpha = 0.14f),
            )
        }
    }
}

/** Kichik nuqta. Buyurtma faol bo'lsa, atrofida to'lqin tarqalib turadi: holat jonli kuzatilmoqda. */
@Composable
private fun LiveDot(color: Color, pulsing: Boolean) {
    Box(modifier = Modifier.size(14.dp), contentAlignment = Alignment.Center) {
        if (pulsing) {
            val transition = rememberInfiniteTransition(label = "live-dot")
            val pulse by transition.animateFloat(
                initialValue = 0f,
                targetValue = 1f,
                animationSpec = infiniteRepeatable(tween(1500, easing = LinearEasing), RepeatMode.Restart),
                label = "live-dot-pulse",
            )
            Box(
                modifier = Modifier
                    .size(14.dp)
                    .graphicsLayer {
                        val scale = 0.45f + pulse * 0.55f
                        scaleX = scale
                        scaleY = scale
                        alpha = (1f - pulse) * 0.55f
                    }
                    .clip(CircleShape)
                    .background(color),
            )
        }
        Box(
            modifier = Modifier
                .size(7.dp)
                .clip(CircleShape)
                .background(color),
        )
    }
}

/** Buyurtma bosqichlari: o'tilgani belgilangan, hozirgisi ajratilgan, kelgusisi xira. */
@Composable
private fun Timeline(order: Order) {
    val scheme = MaterialTheme.colorScheme
    val currentIndex = STEPS.indexOfFirst { it.status == order.status }
    val finished = order.status == OrderStatus.DELIVERED
    SectionCard(padding = 16.dp) {
        STEPS.forEachIndexed { index, step ->
            val done = index < currentIndex || (finished && index == currentIndex)
            val now = !finished && index == currentIndex
            val time = order.history.lastOrNull { it.status == step.status }?.createdAt
            Row(verticalAlignment = Alignment.CenterVertically) {
                StepTile(icon = step.icon, done = done, now = now)
                Spacer(Modifier.width(14.dp))
                Text(
                    text = step.label,
                    style = if (done || now) {
                        MaterialTheme.typography.titleSmall
                    } else {
                        MaterialTheme.typography.bodyLarge
                    },
                    color = if (done || now) scheme.onSurface else scheme.hint,
                    modifier = Modifier.weight(1f),
                )
                if ((done || now) && time != null) {
                    Text(
                        text = formatTime(time),
                        style = MaterialTheme.typography.bodySmall,
                        color = scheme.hint,
                    )
                }
            }
            if (index < STEPS.lastIndex) {
                StepConnector(solid = index < currentIndex)
            }
        }
    }
}

@Composable
private fun StepTile(icon: Int, done: Boolean, now: Boolean) {
    val scheme = MaterialTheme.colorScheme
    val shape = RoundedCornerShape(12.dp)
    val base = Modifier
        .size(34.dp)
        .clip(shape)
    val styled = when {
        done -> base.background(scheme.primary)
        now -> base
            .background(scheme.primaryContainer)
            .border(1.5.dp, scheme.primary, shape)
        else -> base.background(scheme.surfaceVariant)
    }
    Box(modifier = styled, contentAlignment = Alignment.Center) {
        Icon(
            painter = painterResource(if (done) R.drawable.ic_check else icon),
            contentDescription = null,
            tint = when {
                done -> Color.White
                now -> scheme.primary
                else -> scheme.hint
            },
            modifier = Modifier.size(18.dp),
        )
    }
}

/** Ikki bosqich orasidagi chiziq: o'tilgan yo'l uzluksiz, kelgusi yo'l punktir. */
@Composable
private fun StepConnector(solid: Boolean) {
    val scheme = MaterialTheme.colorScheme
    val color = if (solid) scheme.primary else scheme.outline
    Canvas(
        modifier = Modifier
            .padding(start = 16.dp, top = 3.dp, bottom = 3.dp)
            .size(width = 2.dp, height = 14.dp),
    ) {
        drawLine(
            color = color,
            start = Offset(size.width / 2, 0f),
            end = Offset(size.width / 2, size.height),
            strokeWidth = size.width,
            cap = StrokeCap.Round,
            pathEffect = if (solid) null else PathEffect.dashPathEffect(floatArrayOf(3.dp.toPx(), 4.dp.toPx())),
        )
    }
}

/** Buyurtma tarkibi va summasi: chekdagidek qisqa qatorlar. */
@Composable
private fun ItemsCard(order: Order) {
    val scheme = MaterialTheme.colorScheme
    SectionCard(padding = 0.dp) {
        for (item in order.items) {
            MiniRow {
                Text(
                    text = buildAnnotatedString {
                        withStyle(SpanStyle(color = scheme.primary, fontWeight = FontWeight.Bold)) {
                            append("${item.quantity}×")
                        }
                        append("  ")
                        append(item.name)
                    },
                    style = MaterialTheme.typography.bodyLarge,
                    modifier = Modifier.weight(1f),
                )
                Spacer(Modifier.width(12.dp))
                Text(formatSum(item.lineTotal), style = MaterialTheme.typography.bodyLarge, maxLines = 1)
            }
            RowDivider(inset = 16.dp)
        }
        MiniRow {
            Text(
                text = "Yetkazish",
                style = MaterialTheme.typography.bodyLarge,
                color = scheme.onSurfaceVariant,
                modifier = Modifier.weight(1f),
            )
            if (order.deliveryFee == 0) {
                Text("Bepul", style = MaterialTheme.typography.titleSmall, color = scheme.success)
            } else {
                Text(formatSum(order.deliveryFee), style = MaterialTheme.typography.bodyLarge, maxLines = 1)
            }
        }
        RowDivider(inset = 16.dp)
        MiniRow(vertical = 15.dp) {
            Text(
                text = "Jami · naqd",
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.weight(1f),
            )
            PriceText(amount = order.total, style = PriceLargeStyle.copy(fontSize = PriceLargeStyle.fontSize * 0.86f), unitColor = scheme.onSurface)
        }
    }
}

@Composable
private fun MiniRow(vertical: Dp = 13.dp, content: @Composable androidx.compose.foundation.layout.RowScope.() -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = vertical),
        verticalAlignment = Alignment.CenterVertically,
        content = content,
    )
}

/** Qayerga, kimga va qachon: manzil, qabul qiluvchi, izoh. */
@Composable
private fun DetailsCard(order: Order) {
    val scheme = MaterialTheme.colorScheme
    SectionCard(padding = 0.dp) {
        LinkRow(
            icon = R.drawable.ic_pin,
            label = "Manzil · ${formatDateTime(order.createdAt)}",
            value = order.addressNote.ifBlank { "Xaritada belgilangan joy" },
        )
        RowDivider()
        LinkRow(
            icon = R.drawable.ic_user,
            label = "Qabul qiluvchi",
            value = "${order.customerName}, ${formatPhone(order.phone)}",
            tileContainer = scheme.infoContainer,
            tileTint = scheme.info,
        )
        if (order.comment.isNotBlank()) {
            RowDivider()
            LinkRow(
                icon = R.drawable.ic_message,
                label = "Izoh",
                value = order.comment,
                tileContainer = scheme.surfaceVariant,
                tileTint = scheme.onSurfaceVariant,
            )
        }
    }
}

/** Buyurtma birinchi marta yuklanayotganda: sahifa shaklini takrorlaydigan skelet. */
@Composable
private fun OrderSkeleton(top: Dp) {
    val scheme = MaterialTheme.colorScheme
    val shape = MaterialTheme.shapes.large
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(start = 16.dp, end = 16.dp, top = top),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        SkeletonBox(
            modifier = Modifier
                .fillMaxWidth()
                .height(178.dp),
            shape = RoundedCornerShape(30.dp),
        )
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .softShadow(shape)
                .clip(shape)
                .background(scheme.surface)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp),
        ) {
            repeat(4) { index ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    SkeletonBox(modifier = Modifier.size(34.dp), shape = RoundedCornerShape(12.dp))
                    Spacer(Modifier.width(14.dp))
                    SkeletonBox(modifier = Modifier.size(width = (150 - index * 14).dp, height = 14.dp))
                    Spacer(Modifier.weight(1f))
                    SkeletonBox(modifier = Modifier.size(width = 36.dp, height = 12.dp))
                }
            }
        }
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .softShadow(shape)
                .clip(shape)
                .background(scheme.surface)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp),
        ) {
            repeat(3) { index ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    SkeletonBox(modifier = Modifier.size(width = (130 - index * 22).dp, height = 14.dp))
                    Spacer(Modifier.weight(1f))
                    SkeletonBox(modifier = Modifier.size(width = 84.dp, height = 14.dp))
                }
            }
        }
    }
}
