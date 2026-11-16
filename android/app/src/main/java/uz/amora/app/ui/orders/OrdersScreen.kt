package uz.amora.app.ui.orders

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
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
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import uz.amora.app.AppContainer
import uz.amora.app.R
import uz.amora.app.data.ApiException
import uz.amora.app.data.LiveEvent
import uz.amora.app.data.Order
import uz.amora.app.data.OrderStatus
import uz.amora.app.data.resolveImageUrl
import uz.amora.app.ui.components.GlassTopBar
import uz.amora.app.ui.components.MessageBox
import uz.amora.app.ui.components.OrderProgressBar
import uz.amora.app.ui.components.PriceText
import uz.amora.app.ui.components.ProductImage
import uz.amora.app.ui.components.RefreshBox
import uz.amora.app.ui.components.SectionCard
import uz.amora.app.ui.components.SkeletonBox
import uz.amora.app.ui.components.StatusChip
import uz.amora.app.ui.components.TabChip
import uz.amora.app.ui.components.glassSource
import uz.amora.app.ui.components.pressScale
import uz.amora.app.ui.components.rememberGlassState
import uz.amora.app.ui.components.softShadow
import uz.amora.app.ui.order.REPEAT_UNAVAILABLE
import uz.amora.app.ui.order.repeatOrder
import uz.amora.app.ui.theme.PriceStyle
import uz.amora.app.ui.theme.hint
import uz.amora.app.util.formatDateTime

private const val PAGE_SIZE = 20
private const val COMPACT_WIDTH_DP = 380

data class OrdersUiState(
    val loading: Boolean = true,
    val refreshing: Boolean = false,
    val loadingMore: Boolean = false,
    val error: String? = null,
    val orders: List<Order> = emptyList(),
    val hasMore: Boolean = false,
)

class OrdersViewModel(private val container: AppContainer) : ViewModel() {
    private val _state = MutableStateFlow(OrdersUiState())
    val state: StateFlow<OrdersUiState> = _state.asStateFlow()

    init {
        // Buyurtma holati o'zgargani haqida jonli xabar kelsa, ro'yxat o'zi yangilanadi
        viewModelScope.launch {
            container.realtime.events.collect { event ->
                if (event is LiveEvent.OrderChanged || event == LiveEvent.Resync) reload()
            }
        }
    }

    /** Birinchi sahifani qayta yuklaydi. `byUser`: mijoz ekranni pastga tortdi. */
    fun reload(byUser: Boolean = false) {
        if (container.session.token == null) {
            // Hali birorta buyurtma berilmagan: serverga murojaat qilishning hojati yo'q
            _state.value = OrdersUiState(loading = false)
            return
        }
        _state.update { it.copy(refreshing = byUser, loading = it.orders.isEmpty() && !byUser, error = null) }
        viewModelScope.launch {
            try {
                val page = container.api.orders(limit = PAGE_SIZE, offset = 0)
                // "Yana ko'rsatish" bilan yuklangan eski buyurtmalar ro'yxatda qoladi:
                // buyurtmani ochib qaytgan mijoz ro'yxatni yana boshidan varaqlamaydi
                _state.update { old ->
                    val freshIds = page.orders.mapTo(HashSet()) { it.id }
                    val tail = old.orders.filter { it.id !in freshIds }
                    OrdersUiState(
                        loading = false,
                        orders = page.orders + tail,
                        hasMore = if (tail.isEmpty()) page.hasMore else old.hasMore,
                    )
                }
            } catch (e: ApiException) {
                if (e.isUnauthorized) {
                    _state.value = OrdersUiState(loading = false)
                } else {
                    _state.update { it.copy(loading = false, refreshing = false, error = e.message) }
                }
            }
        }
    }

    fun loadMore() {
        val current = _state.value
        if (current.loadingMore || !current.hasMore) return
        _state.update { it.copy(loadingMore = true) }
        viewModelScope.launch {
            try {
                val page = container.api.orders(limit = PAGE_SIZE, offset = current.orders.size)
                _state.update { state ->
                    val known = state.orders.map { it.id }.toSet()
                    state.copy(
                        loadingMore = false,
                        orders = state.orders + page.orders.filter { it.id !in known },
                        hasMore = page.hasMore,
                    )
                }
            } catch (e: ApiException) {
                _state.update { it.copy(loadingMore = false, error = e.message) }
            }
        }
    }
}

private val FILTERS = listOf("Hammasi", "Faol", "Yakunlangan")

/** Mijozning barcha buyurtmalari, eng yangisi tepada. Bosh sahifadagi "Buyurtmalarim" tugmasidan ochiladi. */
@Composable
fun OrdersScreen(
    container: AppContainer,
    onBack: () -> Unit,
    onOpenOrder: (Int) -> Unit,
    onOpenCart: () -> Unit,
) {
    val vm: OrdersViewModel = viewModel(
        factory = viewModelFactory { initializer { OrdersViewModel(container) } },
    )
    val state = vm.state.collectAsStateWithLifecycle().value
    val menu = container.catalog.state.collectAsStateWithLifecycle().value.menu
    val glass = rememberGlassState()
    val scope = rememberCoroutineScope()
    val snackbar = remember { SnackbarHostState() }
    var filter by rememberSaveable { mutableIntStateOf(0) }

    // Ekranga har qaytilganda ro'yxat yangilanadi (masalan, buyurtma holati o'zgargan bo'lishi mumkin)
    val lifecycleOwner = LocalLifecycleOwner.current
    LaunchedEffect(lifecycleOwner) {
        lifecycleOwner.repeatOnLifecycle(Lifecycle.State.RESUMED) {
            vm.reload()
        }
    }

    // Kartochkadagi kichik rasm: buyurtmadagi birinchi taomning menyudagi rasmi
    val imagesByProduct = remember(menu) {
        (menu?.products ?: emptyList()).associate { it.id to it.imageUrl }
    }
    val shown = remember(state.orders, filter) {
        when (filter) {
            1 -> state.orders.filter { it.isActive }
            2 -> state.orders.filter { !it.isActive }
            else -> state.orders
        }
    }
    val navigationBar = with(LocalDensity.current) { WindowInsets.navigationBars.getBottom(this).toDp() }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        topBar = {
            GlassTopBar(
                glass = glass,
                title = "Buyurtmalarim",
                onBack = onBack,
                below = if (state.orders.isEmpty()) {
                    null
                } else {
                    {
                        Row(
                            modifier = Modifier
                                .horizontalScroll(rememberScrollState())
                                .padding(horizontal = 16.dp),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            FILTERS.forEachIndexed { index, title ->
                                TabChip(text = title, selected = filter == index, onClick = { filter = index })
                            }
                        }
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbar, modifier = Modifier.navigationBarsPadding()) },
    ) { padding ->
        val top = padding.calculateTopPadding()
        RefreshBox(
            refreshing = state.refreshing,
            onRefresh = { vm.reload(byUser = true) },
            modifier = Modifier
                .fillMaxSize()
                .glassSource(glass),
            indicatorTop = top,
        ) {
            when {
                state.loading -> OrdersSkeleton(top = top)

                state.orders.isEmpty() && state.error != null -> MessageBox(
                    icon = R.drawable.ic_refresh,
                    title = "Buyurtmalar yuklanmadi",
                    text = state.error,
                    actionLabel = "Qayta urinish",
                    onAction = { vm.reload() },
                    modifier = Modifier.padding(top = top, bottom = navigationBar),
                )

                state.orders.isEmpty() -> MessageBox(
                    icon = R.drawable.ic_receipt,
                    title = "Hali buyurtma yo'q",
                    text = "Birinchi buyurtmangiz shu yerda ko'rinadi",
                    actionLabel = "Menyuga o'tish",
                    onAction = onBack,
                    modifier = Modifier.padding(top = top, bottom = navigationBar),
                )

                else -> LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(
                        start = 16.dp,
                        end = 16.dp,
                        top = top,
                        bottom = navigationBar + 20.dp,
                    ),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    if (shown.isEmpty()) {
                        item(key = "empty-filter") {
                            Text(
                                text = if (filter == 1) "Hozir faol buyurtma yo'q" else "Yakunlangan buyurtma yo'q",
                                style = MaterialTheme.typography.bodyLarge,
                                color = MaterialTheme.colorScheme.hint,
                                textAlign = TextAlign.Center,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 48.dp),
                            )
                        }
                    }
                    items(items = shown, key = { it.id }) { order ->
                        val firstProductId = order.items.firstOrNull()?.productId
                        OrderCard(
                            order = order,
                            imageUrl = resolveImageUrl(container.baseUrl, imagesByProduct[firstProductId]),
                            imageSeed = firstProductId ?: order.id,
                            onClick = { onOpenOrder(order.id) },
                            onRepeat = {
                                if (repeatOrder(container, order) > 0) {
                                    onOpenCart()
                                } else {
                                    scope.launch { snackbar.showSnackbar(REPEAT_UNAVAILABLE) }
                                }
                            },
                            modifier = Modifier.animateItem(),
                        )
                    }
                    if (state.hasMore) {
                        item(key = "more") {
                            Box(modifier = Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                                if (state.loadingMore) {
                                    CircularProgressIndicator(strokeWidth = 3.dp)
                                } else {
                                    SmallPill(text = "Yana ko'rsatish", icon = null, onClick = { vm.loadMore() })
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun OrderCard(
    order: Order,
    imageUrl: String?,
    imageSeed: Int,
    onClick: () -> Unit,
    onRepeat: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val scheme = MaterialTheme.colorScheme
    // Tor ekranda holat belgisi sarlavha ostiga tushadi, aks holda u sarlavhani siqib qo'yadi
    val compact = LocalConfiguration.current.screenWidthDp < COMPACT_WIDTH_DP
    SectionCard(onClick = onClick, padding = 14.dp, modifier = modifier) {
        Row(verticalAlignment = Alignment.Top) {
            ProductImage(
                url = imageUrl,
                modifier = Modifier
                    .size(52.dp)
                    .clip(RoundedCornerShape(16.dp)),
                iconSize = 26.dp,
                seed = imageSeed,
            )
            Spacer(Modifier.width(12.dp))
            Column(
                modifier = Modifier
                    .weight(1f)
                    .padding(top = 4.dp),
            ) {
                Text(
                    text = "Buyurtma №${order.id}",
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                if (compact) {
                    StatusChip(
                        status = order.status,
                        label = order.statusLabel,
                        modifier = Modifier.padding(top = 4.dp, bottom = 6.dp),
                    )
                }
                Text(
                    text = order.items.joinToString(", ") { "${it.quantity}× ${it.name}" },
                    style = MaterialTheme.typography.bodySmall,
                    color = scheme.hint,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            if (!compact) {
                Spacer(Modifier.width(8.dp))
                StatusChip(
                    status = order.status,
                    label = order.statusLabel,
                    modifier = Modifier.widthIn(max = 136.dp),
                )
            }
        }

        val reason = order.rejectReason
        if (order.status == OrderStatus.REJECTED && !reason.isNullOrBlank()) {
            Spacer(Modifier.height(12.dp))
            Text(
                text = "Sabab: $reason",
                style = MaterialTheme.typography.bodySmall,
                color = scheme.onErrorContainer,
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(12.dp))
                    .background(scheme.errorContainer)
                    .padding(horizontal = 12.dp, vertical = 9.dp),
            )
        }
        if (order.isActive) {
            Spacer(Modifier.height(14.dp))
            OrderProgressBar(status = order.status)
        }

        Spacer(Modifier.height(12.dp))
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(1.dp)
                .background(scheme.outlineVariant),
        )
        Spacer(Modifier.height(12.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = formatDateTime(order.createdAt),
                    style = MaterialTheme.typography.bodySmall,
                    color = scheme.hint,
                    maxLines = 1,
                )
                PriceText(
                    amount = order.total,
                    style = PriceStyle.copy(fontSize = PriceStyle.fontSize * 1.1f),
                    unitColor = scheme.onSurface,
                )
            }
            if (order.isActive) {
                SmallPill(text = "Kuzatish", icon = R.drawable.ic_clock, onClick = onClick)
            } else {
                SmallPill(text = "Yana shunday", icon = R.drawable.ic_repeat, onClick = onRepeat)
            }
        }
    }
}

/** Kartochka ichidagi kichik och-qizil tugma. */
@Composable
private fun SmallPill(text: String, icon: Int?, onClick: () -> Unit) {
    val scheme = MaterialTheme.colorScheme
    val source = remember { MutableInteractionSource() }
    Row(
        modifier = Modifier
            .pressScale(source, 0.94f)
            .clip(RoundedCornerShape(13.dp))
            .background(scheme.primaryContainer)
            .clickable(
                interactionSource = source,
                indication = androidx.compose.foundation.LocalIndication.current,
                role = Role.Button,
                onClick = onClick,
            )
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (icon != null) {
            Icon(
                painter = painterResource(icon),
                contentDescription = null,
                tint = scheme.onPrimaryContainer,
                modifier = Modifier.size(16.dp),
            )
            Spacer(Modifier.width(6.dp))
        }
        Text(
            text = text,
            style = MaterialTheme.typography.labelMedium,
            color = scheme.onPrimaryContainer,
            maxLines = 1,
        )
    }
}

/** Ro'yxat birinchi marta yuklanayotganda: buyurtma kartochkalari shaklidagi skelet. */
@Composable
private fun OrdersSkeleton(top: Dp) {
    val scheme = MaterialTheme.colorScheme
    val shape = MaterialTheme.shapes.large
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(start = 16.dp, end = 16.dp, top = top),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        repeat(3) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .softShadow(shape)
                    .clip(shape)
                    .background(scheme.surface)
                    .padding(14.dp),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    SkeletonBox(modifier = Modifier.size(52.dp), shape = RoundedCornerShape(16.dp))
                    Spacer(Modifier.width(12.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        SkeletonBox(modifier = Modifier.size(width = 120.dp, height = 16.dp))
                        Spacer(Modifier.height(8.dp))
                        SkeletonBox(modifier = Modifier.size(width = 90.dp, height = 12.dp))
                    }
                    SkeletonBox(modifier = Modifier.size(width = 74.dp, height = 26.dp), shape = RoundedCornerShape(10.dp))
                }
                Spacer(Modifier.height(26.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(modifier = Modifier.weight(1f)) {
                        SkeletonBox(modifier = Modifier.size(width = 96.dp, height = 12.dp))
                        Spacer(Modifier.height(8.dp))
                        SkeletonBox(modifier = Modifier.size(width = 110.dp, height = 18.dp))
                    }
                    SkeletonBox(modifier = Modifier.size(width = 118.dp, height = 38.dp))
                }
            }
        }
    }
}
