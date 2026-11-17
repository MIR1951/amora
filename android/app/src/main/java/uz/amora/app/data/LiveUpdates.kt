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

    // Har bir buyurtma bo'yicha mijozga oxirgi bildirilgan (yoki ekranda ko'rsatilgan) holat
    private val notified = mutableMapOf<Int, String>()

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
                        notify(event)
                        launch { refreshActiveOrders() }
                    }
                }
            }
        }
        // Ulanish uzilib turganda o'tkazib yuborilgan o'zgarish: qayta o'qishda aniqlanadi va
        // xuddi jonli xabar kelgandek bildiriladi
        scope.launch {
            activeOrders.statusChanges.collect { order ->
                notify(
                    LiveEvent.OrderChanged(order.id, order.status, order.statusLabel, order.rejectReason),
                )
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

    /**
     * Mijoz shu buyurtma ekraniga qarab turibdi: u haqidagi bildirishnoma kerak emas.
     * [status] ekranda ko'rinib turgan holat: u haqida keyin ham alohida bildirilmaydi.
     */
    fun setVisibleOrder(orderId: Int, status: String? = null) {
        visibleOrderId = orderId
        if (status != null) notified[orderId] = status
        notifier.dismiss(orderId)
    }

    /** Buyurtma ekrani yopildi. Shu orada boshqa buyurtma ochilgan bo'lsa, unga tegilmaydi. */
    fun clearVisibleOrder(orderId: Int) {
        if (visibleOrderId == orderId) visibleOrderId = null
    }

    /**
     * Firebase orqali kelgan holat (ilova yopiq yoki orqa fonda bo'lsa ham keladi). Jonli ulanish
     * orqali kelgan xuddi shu xabar bilan ikkilanmaydi: ikkalasi bir joydan o'tadi.
     */
    fun onPush(event: LiveEvent.OrderChanged) {
        scope.launch {
            notify(event)
            refreshActiveOrders()
        }
    }

    /** Mijoz hozirgina buyurtma berdi: u darhol faol buyurtmalar qatoriga qo'shiladi. */
    fun orderPlaced() {
        scope.launch { refreshActiveOrders() }
    }

    /**
     * Holat o'zgarishi haqida bildiradi. Bitta o'zgarish ikki yo'ldan kelishi mumkin (jonli xabar
     * va qayta o'qish): ikkinchisi va kechikib kelgan eski holat e'tiborsiz qoldiriladi.
     */
    private fun notify(event: LiveEvent.OrderChanged) {
        if (!isNewerStatus(notified[event.orderId], event.status)) return
        notified[event.orderId] = event.status
        // Mijoz aynan shu buyurtma ekraniga qarab turgan bo'lsa, o'zgarishni ekranda ko'radi
        if (foreground && visibleOrderId == event.orderId) return
        notifier.show(event)
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

// Buyurtma faqat oldinga yuradi: yangi, tayyorlanmoqda, yo'lda, tugadi (yetkazildi yoki bekor bo'ldi)
private fun statusStep(status: String): Int = when (status) {
    "new" -> 0
    "accepted" -> 1
    "delivering" -> 2
    else -> 3
}

/** [status] mijozga oxirgi bildirilgan [last] holatdan keyingi bosqichmi. */
fun isNewerStatus(last: String?, status: String): Boolean =
    last == null || statusStep(status) > statusStep(last)
