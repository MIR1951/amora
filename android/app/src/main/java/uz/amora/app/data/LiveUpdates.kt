package uz.amora.app.data

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.drop
import kotlinx.coroutines.launch
import uz.amora.app.notify.OrderNotifier

/**
 * Jonli xabarlarni ilova bo'ylab tarqatadi: menyu va kafe ma'lumotini yangilaydi, faol
 * buyurtmalarni kuzatadi va kerak bo'lsa bildirishnoma ko'rsatadi. Alohida ekranlar
 * (buyurtma, tarix, savat) o'zlariga tegishli xabarlarni `realtime.events` dan o'zlari oladi.
 */
class LiveUpdates(
    private val realtime: Realtime,
    private val catalog: Catalog,
    private val activeOrders: ActiveOrders,
    private val notifier: OrderNotifier,
    session: SessionStore,
    private val scope: CoroutineScope,
) {
    private var foreground = false
    private var visibleOrderId: Int? = null
    private var lingerJob: Job? = null

    init {
        scope.launch {
            realtime.events.collect { event ->
                when (event) {
                    LiveEvent.Resync -> {
                        launch { catalog.refresh() }
                        launch { refreshActiveOrders() }
                    }

                    LiveEvent.MenuChanged, LiveEvent.ShopChanged -> launch { catalog.refresh() }

                    is LiveEvent.OrderChanged -> {
                        // Mijoz aynan shu buyurtma ekraniga qarab turgan bo'lsa, o'zgarishni
                        // ekranda ko'radi: bildirishnoma ortiqcha
                        if (!(foreground && visibleOrderId == event.orderId)) notifier.show(event)
                        launch { refreshActiveOrders() }
                    }
                }
            }
        }
        // Mijoz ro'yxatdan o'tdi yoki kalit yangilandi: ulanish yangi kalit bilan qayta o'rnatiladi
        scope.launch {
            session.tokenFlow.drop(1).collect { realtime.restart() }
        }
    }

    /** Ilova ekranga chiqdi. */
    fun onForeground() {
        foreground = true
        lingerJob?.cancel()
        lingerJob = null
        realtime.start()
    }

    /**
     * Ilova orqa fonga o'tdi. Faol buyurtma bo'lsa, ulanish yana bir muddat ushlab turiladi:
     * tizim ilovani to'xtatib qo'ymaguncha holat o'zgarishi haqida bildirishnoma keladi.
     */
    fun onBackground() {
        foreground = false
        lingerJob?.cancel()
        lingerJob = scope.launch {
            if (activeOrders.orders.value.isNotEmpty()) delay(BACKGROUND_LINGER_MS)
            realtime.stop()
        }
    }

    /** Mijoz shu buyurtma ekraniga qarab turibdi: u haqidagi bildirishnoma kerak emas. */
    fun setVisibleOrder(orderId: Int) {
        visibleOrderId = orderId
        notifier.dismiss(orderId)
    }

    /** Buyurtma ekrani yopildi. Shu orada boshqa buyurtma ochilgan bo'lsa, unga tegilmaydi. */
    fun clearVisibleOrder(orderId: Int) {
        if (visibleOrderId == orderId) visibleOrderId = null
    }

    /** Mijoz hozirgina buyurtma berdi: u darhol faol buyurtmalar qatoriga qo'shiladi. */
    fun orderPlaced() {
        scope.launch { refreshActiveOrders() }
    }

    private suspend fun refreshActiveOrders() {
        activeOrders.refresh()
        // Orqa fonda kutilayotgan buyurtma qolmadi: ulanishni ushlab turishning hojati yo'q
        if (!foreground && activeOrders.orders.value.isEmpty()) realtime.stop()
    }

    private companion object {
        const val BACKGROUND_LINGER_MS = 20 * 60 * 1000L
    }
}
