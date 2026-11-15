package uz.amora.app.ui.order

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Phone
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
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
import uz.amora.app.data.ApiException
import uz.amora.app.data.Order
import uz.amora.app.data.OrderStatus
import uz.amora.app.ui.components.BackTopBar
import uz.amora.app.ui.components.BigButton
import uz.amora.app.ui.components.BottomActionBar
import uz.amora.app.ui.components.IconBadge
import uz.amora.app.ui.components.LoadingBox
import uz.amora.app.ui.components.MessageBox
import uz.amora.app.ui.components.OrderProgressBar
import uz.amora.app.ui.components.OrderStatusIcon
import uz.amora.app.ui.components.SectionCard
import uz.amora.app.ui.components.SoftButton
import uz.amora.app.ui.components.SummaryRow
import uz.amora.app.ui.components.statusContainerColor
import uz.amora.app.ui.components.statusContentColor
import uz.amora.app.ui.profile.dialPhone
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
        val menuProducts = container.catalog.state.value.menu?.products
        val items = LinkedHashMap<Int, Int>()
        for (item in order.items) {
            val productId = item.productId ?: continue
            // Menyu yuklangan bo'lsa, faqat hozir sotuvda bor taomlar olinadi
            if (menuProducts != null && menuProducts.none { it.id == productId && it.isAvailable }) continue
            items[productId] = (items[productId] ?: 0) + item.quantity
        }
        if (items.isNotEmpty()) {
            container.cart.replace(items)
        } else {
            _state.update { it.copy(message = "Bu taomlar hozir menyuda yo'q") }
        }
        return items.size
    }
}

/** Bitta buyurtma: holati, tarkibi va summasi. Faol buyurtma o'zi yangilanib turadi. */
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

    Scaffold(
        containerColor = scheme.background,
        topBar = { BackTopBar(title = "Buyurtma №$orderId", onBack = onBack) },
        snackbarHost = { SnackbarHost(snackbar) },
        bottomBar = {
            // Tugagan buyurtmani bir bosishda takrorlash mumkin
            if (order != null && !order.isActive) {
                BottomActionBar {
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
        PullToRefreshBox(
            isRefreshing = state.refreshing,
            onRefresh = { vm.pullToRefresh() },
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            when {
                order == null && state.loading -> LoadingBox()

                order == null -> MessageBox(
                    icon = Icons.Default.Refresh,
                    title = "Buyurtma yuklanmadi",
                    text = state.error,
                    actionLabel = "Qayta urinish",
                    onAction = { vm.retry() },
                )

                else -> Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .verticalScroll(rememberScrollState())
                        .padding(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 24.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    StatusCard(order)

                    if (order.canCancel) {
                        SoftButton(
                            text = if (state.cancelling) "Bekor qilinmoqda…" else "Buyurtmani bekor qilish",
                            onClick = { confirmCancel = true },
                            icon = Icons.Default.Close,
                            enabled = !state.cancelling,
                            danger = true,
                        )
                    }

                    val cafePhone = shop?.phone
                    if (order.isActive && !cafePhone.isNullOrBlank()) {
                        SoftButton(
                            text = "Kafega qo'ng'iroq qilish: ${formatPhone(cafePhone)}",
                            onClick = { dialPhone(context, cafePhone) },
                            icon = Icons.Default.Phone,
                        )
                    }

                    ItemsCard(order)
                    DetailsCard(order)
                }
            }
        }
    }

    if (confirmCancel) {
        AlertDialog(
            onDismissRequest = { confirmCancel = false },
            containerColor = scheme.surface,
            title = { Text("Buyurtmani bekor qilasizmi?", style = MaterialTheme.typography.titleLarge) },
            text = {
                Text(
                    text = "Kafe buyurtmani hali qabul qilmagan. Bekor qilsangiz, u kafega yuborilmaydi.",
                    style = MaterialTheme.typography.bodyLarge,
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        confirmCancel = false
                        vm.cancel()
                    },
                    shape = MaterialTheme.shapes.medium,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = scheme.error,
                        contentColor = scheme.onError,
                    ),
                ) { Text("Bekor qilish", style = MaterialTheme.typography.labelLarge) }
            },
            dismissButton = {
                TextButton(onClick = { confirmCancel = false }) {
                    Text(
                        text = "Yo'q, qolsin",
                        style = MaterialTheme.typography.labelLarge,
                        color = scheme.onSurfaceVariant,
                    )
                }
            },
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

private val STEPS = listOf(
    OrderStatus.NEW to "Buyurtma yuborildi",
    OrderStatus.ACCEPTED to "Kafe qabul qildi",
    OrderStatus.DELIVERING to "Kuryer yo'lga chiqdi",
    OrderStatus.DELIVERED to "Yetkazildi",
)

/** Buyurtma holati: katta belgi, sarlavha, izoh va bosqichlar. */
@Composable
private fun StatusCard(order: Order) {
    val scheme = MaterialTheme.colorScheme
    val stopped = order.status == OrderStatus.REJECTED || order.status == OrderStatus.CANCELLED
    val accent = when (order.status) {
        OrderStatus.DELIVERED -> scheme.success
        else -> scheme.primary
    }
    SectionCard(padding = 18.dp) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconBadge(size = 60.dp, container = statusContainerColor(order.status)) {
                OrderStatusIcon(
                    status = order.status,
                    modifier = Modifier.size(30.dp),
                    tint = statusContentColor(order.status),
                )
            }
            Spacer(Modifier.width(14.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(order.statusLabel, style = MaterialTheme.typography.headlineSmall)
                Spacer(Modifier.height(2.dp))
                Text(
                    text = statusDescription(order),
                    style = MaterialTheme.typography.bodyMedium,
                    color = scheme.onSurfaceVariant,
                )
            }
        }

        if (!stopped) {
            Spacer(Modifier.height(18.dp))
            OrderProgressBar(status = order.status, color = accent)
            Spacer(Modifier.height(18.dp))

            val currentIndex = STEPS.indexOfFirst { it.first == order.status }
            STEPS.forEachIndexed { index, step ->
                val done = index <= currentIndex
                val time = order.history.lastOrNull { it.status == step.first }?.createdAt
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(24.dp)
                            .clip(CircleShape)
                            .background(if (done) accent else scheme.surfaceVariant),
                        contentAlignment = Alignment.Center,
                    ) {
                        if (done) {
                            Icon(
                                imageVector = Icons.Default.Check,
                                contentDescription = null,
                                tint = Color.White,
                                modifier = Modifier.size(15.dp),
                            )
                        } else {
                            Box(
                                modifier = Modifier
                                    .size(8.dp)
                                    .clip(CircleShape)
                                    .background(scheme.outline),
                            )
                        }
                    }
                    Spacer(Modifier.width(12.dp))
                    Text(
                        text = step.second,
                        style = if (index == currentIndex) {
                            MaterialTheme.typography.titleSmall
                        } else {
                            MaterialTheme.typography.bodyMedium
                        },
                        color = if (done) scheme.onSurface else scheme.onSurfaceVariant,
                        modifier = Modifier.weight(1f),
                    )
                    if (done && time != null) {
                        Text(
                            text = formatTime(time),
                            style = MaterialTheme.typography.labelMedium,
                            color = scheme.onSurfaceVariant,
                        )
                    }
                }
                if (index < STEPS.lastIndex) {
                    Box(
                        modifier = Modifier
                            .padding(start = 11.dp, top = 3.dp, bottom = 3.dp)
                            .width(2.dp)
                            .height(14.dp)
                            .clip(RoundedCornerShape(50))
                            .background(if (index < currentIndex) accent else scheme.outlineVariant),
                    )
                }
            }
        }
    }
}

@Composable
private fun ItemsCard(order: Order) {
    val scheme = MaterialTheme.colorScheme
    SectionCard {
        Text("Buyurtma tarkibi", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(10.dp))
        for (item in order.items) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 5.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = "${item.quantity} ×",
                    style = MaterialTheme.typography.labelMedium,
                    color = scheme.onSurface,
                    maxLines = 1,
                    modifier = Modifier
                        .clip(RoundedCornerShape(9.dp))
                        .background(scheme.surfaceVariant)
                        .padding(horizontal = 8.dp, vertical = 5.dp),
                )
                Spacer(Modifier.width(10.dp))
                Text(
                    text = item.name,
                    style = MaterialTheme.typography.bodyLarge,
                    modifier = Modifier.weight(1f),
                )
                Spacer(Modifier.width(12.dp))
                Text(formatSum(item.lineTotal), style = MaterialTheme.typography.titleSmall, maxLines = 1)
            }
        }
        HorizontalDivider(
            modifier = Modifier.padding(vertical = 10.dp),
            color = scheme.outlineVariant,
        )
        SummaryRow("Taomlar", formatSum(order.itemsTotal))
        SummaryRow(
            label = "Yetkazish",
            value = if (order.deliveryFee == 0) "Bepul" else formatSum(order.deliveryFee),
            valueColor = if (order.deliveryFee == 0) scheme.success else scheme.onSurface,
        )
        SummaryRow("Jami", formatSum(order.total), strong = true)
        Spacer(Modifier.height(10.dp))
        Text(
            text = "To'lov: kuryerga naqd pul bilan",
            style = MaterialTheme.typography.labelMedium,
            color = scheme.onSurfaceVariant,
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(12.dp))
                .background(scheme.surfaceVariant)
                .padding(horizontal = 12.dp, vertical = 10.dp),
        )
    }
}

@Composable
private fun DetailsCard(order: Order) {
    SectionCard {
        Text("Yetkazish ma'lumotlari", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(6.dp))
        DetailRow("Berilgan vaqti", formatDateTime(order.createdAt))
        DetailRow("Manzil", order.addressNote.ifBlank { "Xaritada belgilangan joy" })
        DetailRow("Qabul qiluvchi", "${order.customerName}, ${formatPhone(order.phone)}")
        if (order.comment.isNotBlank()) DetailRow("Izoh", order.comment)
    }
}

@Composable
private fun DetailRow(label: String, value: String) {
    Column(modifier = Modifier.padding(vertical = 5.dp)) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(text = value, style = MaterialTheme.typography.bodyLarge)
    }
}
