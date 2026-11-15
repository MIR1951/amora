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
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
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
import uz.amora.app.ui.components.LoadingBox
import uz.amora.app.ui.components.MessageBox
import uz.amora.app.ui.components.SectionCard
import uz.amora.app.ui.components.SummaryRow
import uz.amora.app.ui.profile.dialPhone
import uz.amora.app.ui.theme.onSuccessContainer
import uz.amora.app.ui.theme.successContainer
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
        containerColor = MaterialTheme.colorScheme.background,
        topBar = { BackTopBar(title = "Buyurtma №$orderId", onBack = onBack) },
        snackbarHost = { SnackbarHost(snackbar) },
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
                    emoji = "📡",
                    title = "Buyurtma yuklanmadi",
                    text = state.error,
                    actionLabel = "Qayta urinish",
                    onAction = { vm.retry() },
                )

                else -> Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .verticalScroll(rememberScrollState())
                        .padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    StatusCard(order)

                    if (order.canCancel) {
                        OutlinedButton(
                            onClick = { confirmCancel = true },
                            enabled = !state.cancelling,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(if (state.cancelling) "Bekor qilinmoqda…" else "Buyurtmani bekor qilish")
                        }
                    }

                    val cafePhone = shop?.phone
                    if (order.isActive && !cafePhone.isNullOrBlank()) {
                        OutlinedButton(
                            onClick = { dialPhone(context, cafePhone) },
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text("Kafega qo'ng'iroq qilish: ${formatPhone(cafePhone)}")
                        }
                    }

                    ItemsCard(order)
                    DetailsCard(order)

                    if (!order.isActive) {
                        BigButton(
                            text = "Yana shunday buyurtma berish",
                            onClick = {
                                if (vm.repeatOrder() > 0) onOpenCart()
                            },
                        )
                    }
                }
            }
        }
    }

    if (confirmCancel) {
        AlertDialog(
            onDismissRequest = { confirmCancel = false },
            title = { Text("Buyurtmani bekor qilasizmi?") },
            text = { Text("Kafe buyurtmani hali qabul qilmagan. Bekor qilsangiz, u kafega yuborilmaydi.") },
            confirmButton = {
                TextButton(
                    onClick = {
                        confirmCancel = false
                        vm.cancel()
                    },
                ) { Text("Bekor qilish") }
            },
            dismissButton = {
                TextButton(onClick = { confirmCancel = false }) { Text("Yo'q, qolsin") }
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

@Composable
private fun StatusCard(order: Order) {
    val scheme = MaterialTheme.colorScheme
    val stopped = order.status == OrderStatus.REJECTED || order.status == OrderStatus.CANCELLED
    val container = when {
        order.status == OrderStatus.REJECTED -> scheme.errorContainer
        order.status == OrderStatus.CANCELLED -> scheme.surfaceVariant
        order.status == OrderStatus.DELIVERED -> scheme.successContainer
        else -> scheme.surface
    }
    val content = when {
        order.status == OrderStatus.REJECTED -> scheme.onErrorContainer
        order.status == OrderStatus.CANCELLED -> scheme.onSurfaceVariant
        order.status == OrderStatus.DELIVERED -> scheme.onSuccessContainer
        else -> scheme.onSurface
    }
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.large,
        color = container,
        contentColor = content,
        shadowElevation = if (container == scheme.surface) 1.dp else 0.dp,
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(order.statusLabel, style = MaterialTheme.typography.headlineSmall)
            Spacer(Modifier.height(4.dp))
            Text(statusDescription(order), style = MaterialTheme.typography.bodyMedium)

            if (!stopped) {
                Spacer(Modifier.height(16.dp))
                val currentIndex = STEPS.indexOfFirst { it.first == order.status }
                STEPS.forEachIndexed { index, step ->
                    val done = index <= currentIndex
                    val time = order.history.lastOrNull { it.status == step.first }?.createdAt
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            modifier = Modifier
                                .size(26.dp)
                                .clip(CircleShape)
                                .background(if (done) scheme.primary else scheme.outlineVariant),
                            contentAlignment = Alignment.Center,
                        ) {
                            if (done) {
                                Icon(
                                    imageVector = Icons.Default.Check,
                                    contentDescription = null,
                                    tint = scheme.onPrimary,
                                    modifier = Modifier.size(16.dp),
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
                            modifier = Modifier.weight(1f),
                        )
                        if (done && time != null) {
                            Text(formatTime(time), style = MaterialTheme.typography.labelMedium)
                        }
                    }
                    if (index < STEPS.lastIndex) {
                        Box(
                            modifier = Modifier
                                .padding(start = 12.dp)
                                .width(2.dp)
                                .height(16.dp)
                                .background(if (index < currentIndex) scheme.primary else scheme.outlineVariant),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun ItemsCard(order: Order) {
    SectionCard {
        for (item in order.items) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = "${item.quantity} × ${item.name}",
                    style = MaterialTheme.typography.bodyLarge,
                    modifier = Modifier.weight(1f),
                )
                Spacer(Modifier.width(12.dp))
                Text(formatSum(item.lineTotal), style = MaterialTheme.typography.bodyLarge)
            }
        }
        HorizontalDivider(
            modifier = Modifier.padding(vertical = 8.dp),
            color = MaterialTheme.colorScheme.outlineVariant,
        )
        SummaryRow("Taomlar", formatSum(order.itemsTotal))
        SummaryRow("Yetkazish", if (order.deliveryFee == 0) "Bepul" else formatSum(order.deliveryFee))
        SummaryRow("Jami", formatSum(order.total), strong = true)
        Spacer(Modifier.height(6.dp))
        Text(
            text = "To'lov: kuryerga naqd pul bilan",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun DetailsCard(order: Order) {
    SectionCard {
        DetailRow("Berilgan vaqti", formatDateTime(order.createdAt))
        DetailRow("Manzil", order.addressNote.ifBlank { "Xaritada belgilangan joy" })
        DetailRow("Qabul qiluvchi", "${order.customerName}, ${formatPhone(order.phone)}")
        if (order.comment.isNotBlank()) DetailRow("Izoh", order.comment)
    }
}

@Composable
private fun DetailRow(label: String, value: String) {
    Column(modifier = Modifier.padding(vertical = 4.dp)) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(text = value, style = MaterialTheme.typography.bodyLarge)
    }
}
