package uz.amora.app.notify

import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import uz.amora.app.AmoraApp
import uz.amora.app.data.LiveEvent

/**
 * Firebase xabarlari. Buyurtma holati faqat ma'lumot bo'lib keladi va bildirishnomani ilova
 * o'zi ko'rsatadi (jonli ulanish bilan bir xil yo'ldan, ikkilanmaydi). Aksiya xabarini ilova
 * yopiq paytda tizim o'zi ko'rsatadi, ochiq paytda esa shu yerga keladi.
 */
class PushService : FirebaseMessagingService() {
    private val container get() = (application as AmoraApp).container

    override fun onNewToken(token: String) {
        container.push.onNewToken(token)
    }

    override fun onMessageReceived(message: RemoteMessage) {
        val data = message.data
        when (data["type"]) {
            "order" -> {
                val orderId = data["order_id"]?.toIntOrNull() ?: return
                val status = data["status"] ?: return
                container.live.onPush(
                    LiveEvent.OrderChanged(
                        orderId = orderId,
                        status = status,
                        statusLabel = data["status_label"].orEmpty(),
                        rejectReason = data["reject_reason"],
                    ),
                )
            }

            "promo" -> {
                val title = message.notification?.title ?: data["title"] ?: return
                val body = message.notification?.body ?: data["body"].orEmpty()
                container.notifier.showPromo(title, body)
            }
        }
    }
}
