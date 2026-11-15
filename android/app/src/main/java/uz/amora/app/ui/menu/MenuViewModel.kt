package uz.amora.app.ui.menu

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import uz.amora.app.AppContainer
import uz.amora.app.data.ApiException
import uz.amora.app.data.Order

class MenuViewModel(private val container: AppContainer) : ViewModel() {
    private val _activeOrders = MutableStateFlow<List<Order>>(emptyList())
    val activeOrders: StateFlow<List<Order>> = _activeOrders.asStateFlow()

    private val _refreshing = MutableStateFlow(false)
    val refreshing: StateFlow<Boolean> = _refreshing.asStateFlow()

    private var catalogJob: Job? = null

    /** Ekran ochilganda yoki ilovaga qaytilganda menyuni yangilaydi. */
    fun refreshCatalog() {
        if (catalogJob?.isActive == true) return
        catalogJob = viewModelScope.launch { container.catalog.refresh() }
    }

    /** Xatodan keyin "Qayta urinish": yuklanish belgisi ko'rsatiladi. */
    fun retry() {
        viewModelScope.launch { container.catalog.refresh(showLoading = true) }
    }

    /** Ekranni pastga tortib yangilash. */
    fun pullToRefresh() {
        if (_refreshing.value) return
        viewModelScope.launch {
            _refreshing.value = true
            try {
                container.catalog.refresh()
                loadActiveOrders()
            } finally {
                _refreshing.value = false
            }
        }
    }

    fun refreshActiveOrders() {
        viewModelScope.launch { loadActiveOrders() }
    }

    private suspend fun loadActiveOrders() {
        if (container.session.token == null) {
            _activeOrders.value = emptyList()
            return
        }
        try {
            _activeOrders.value = container.api.orders(limit = 5).orders.filter { it.isActive }
        } catch (e: ApiException) {
            if (e.isUnauthorized) _activeOrders.value = emptyList()
        }
    }
}
