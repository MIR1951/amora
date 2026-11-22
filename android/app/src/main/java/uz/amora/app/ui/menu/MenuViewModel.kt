package uz.amora.app.ui.menu

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import uz.amora.app.AppContainer
import uz.amora.app.data.Order

class MenuViewModel(private val container: AppContainer) : ViewModel() {
    // Faol buyurtmalar butun ilova uchun bitta joyda turadi: jonli xabar kelganda ham yangilanadi
    val activeOrders: StateFlow<List<Order>> = container.activeOrders.orders

    private val _refreshing = MutableStateFlow(false)
    val refreshing: StateFlow<Boolean> = _refreshing.asStateFlow()

    // Bir martalik xabar: menyu ekranda turganda yangilab bo'lmadi
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()

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
                // Avval yuklangan menyu ekranda qoladi: yangilanmaganini mijoz bilishi kerak
                val catalog = container.catalog.state.value
                if (catalog.menu != null && catalog.error != null) _message.value = catalog.error
                container.activeOrders.refresh()
            } finally {
                _refreshing.value = false
            }
        }
    }

    fun clearMessage() {
        _message.value = null
    }

    fun refreshActiveOrders() {
        viewModelScope.launch { container.activeOrders.refresh() }
    }

    /** Jonli ulanish ishlab turibdimi: ishlasa, serverdan tez-tez so'rab turish shart emas. */
    val liveConnected: Boolean get() = container.realtime.connected.value
}
