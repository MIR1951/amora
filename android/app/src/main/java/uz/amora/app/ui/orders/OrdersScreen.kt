package uz.amora.app.ui.orders

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
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
import uz.amora.app.data.ApiException
import uz.amora.app.data.Order
import uz.amora.app.ui.components.BackTopBar
import uz.amora.app.ui.components.LoadingBox
import uz.amora.app.ui.components.MessageBox
import uz.amora.app.ui.components.SectionCard
import uz.amora.app.ui.components.StatusBadge
import uz.amora.app.util.formatDateTime
import uz.amora.app.util.formatSum

private const val PAGE_SIZE = 20

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
                _state.value = OrdersUiState(loading = false, orders = page.orders, hasMore = page.hasMore)
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

/** Mijozning barcha buyurtmalari, eng yangisi tepada. */
@Composable
fun OrdersScreen(container: AppContainer, onBack: () -> Unit, onOpenOrder: (Int) -> Unit) {
    val vm: OrdersViewModel = viewModel(
        factory = viewModelFactory { initializer { OrdersViewModel(container) } },
    )
    val state = vm.state.collectAsStateWithLifecycle().value

    // Ekranga har qaytilganda ro'yxat yangilanadi (masalan, buyurtma holati o'zgargan bo'lishi mumkin)
    val lifecycleOwner = LocalLifecycleOwner.current
    LaunchedEffect(lifecycleOwner) {
        lifecycleOwner.repeatOnLifecycle(Lifecycle.State.RESUMED) {
            vm.reload()
        }
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = { BackTopBar(title = "Buyurtmalarim", onBack = onBack) },
    ) { padding ->
        PullToRefreshBox(
            isRefreshing = state.refreshing,
            onRefresh = { vm.reload(byUser = true) },
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            when {
                state.loading -> LoadingBox()

                state.orders.isEmpty() && state.error != null -> MessageBox(
                    emoji = "📡",
                    title = "Buyurtmalar yuklanmadi",
                    text = state.error,
                    actionLabel = "Qayta urinish",
                    onAction = { vm.reload() },
                )

                state.orders.isEmpty() -> MessageBox(
                    emoji = "🧾",
                    title = "Hali buyurtma yo'q",
                    text = "Birinchi buyurtmangiz shu yerda ko'rinadi",
                    actionLabel = "Menyuga o'tish",
                    onAction = onBack,
                )

                else -> LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    items(items = state.orders, key = { it.id }) { order ->
                        OrderCard(order = order, onClick = { onOpenOrder(order.id) })
                    }
                    if (state.hasMore) {
                        item(key = "more") {
                            Box(modifier = Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                                if (state.loadingMore) {
                                    CircularProgressIndicator()
                                } else {
                                    TextButton(onClick = { vm.loadMore() }) { Text("Yana ko'rsatish") }
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
private fun OrderCard(order: Order, onClick: () -> Unit) {
    SectionCard(onClick = onClick) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                text = "Buyurtma №${order.id}",
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.weight(1f),
            )
            StatusBadge(status = order.status, label = order.statusLabel)
        }
        Spacer(Modifier.height(6.dp))
        Text(
            text = order.items.joinToString(", ") { "${it.quantity} × ${it.name}" },
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
        Spacer(Modifier.height(8.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                text = formatDateTime(order.createdAt),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.weight(1f),
            )
            Text(text = formatSum(order.total), style = MaterialTheme.typography.titleSmall)
        }
    }
}
