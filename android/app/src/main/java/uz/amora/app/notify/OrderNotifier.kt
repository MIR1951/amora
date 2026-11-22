package uz.amora.app.notify

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import uz.amora.app.MainActivity
import uz.amora.app.R
import uz.amora.app.data.LiveEvent
import uz.amora.app.data.OrderStatus

/** Bildirishnomada ko'rinadigan matn. */
data class OrderNotice(val title: String, val text: String)

/**
 * Buyurtma holati uchun bildirishnoma matni. Mijozning o'zi qilgan ishlar (yubordi, bekor qildi)
 * uchun bildirishnoma kerak emas: null qaytadi.
 */
fun orderNotice(event: LiveEvent.OrderChanged): OrderNotice? = when (event.status) {
    OrderStatus.ACCEPTED -> OrderNotice(
        "Buyurtma №${event.orderId} qabul qilindi",
        "Kafe buyurtmangizni tayyorlamoqda.",
    )

    OrderStatus.DELIVERING -> OrderNotice(
        "Kuryer yo'lda",
        "Buyurtma №${event.orderId} ni kuryer olib yo'lga chiqdi.",
    )

    OrderStatus.DELIVERED -> OrderNotice(
        "Buyurtma yetkazildi",
        "Buyurtma №${event.orderId} yetkazildi. Yoqimli ishtaha!",
    )

    OrderStatus.REJECTED -> OrderNotice(
        "Buyurtma №${event.orderId} rad etildi",
        event.rejectReason?.takeIf { it.isNotBlank() }?.let { "Sabab: $it" }
            ?: "Afsuski, kafe buyurtmani qabul qila olmadi.",
    )

    else -> null
}

/** Buyurtma holati haqidagi tizim bildirishnomalari. */
class OrderNotifier(context: Context) {
    private val context = context.applicationContext
    private val manager = NotificationManagerCompat.from(this.context)

    /** Android 8+ da bildirishnomalar "kanal"ga bo'linadi: mijoz uni sozlamalardan boshqaradi. */
    fun createChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val channel = NotificationChannel(
            CHANNEL_ORDERS,
            "Buyurtma holati",
            NotificationManager.IMPORTANCE_HIGH,
        ).apply {
            description = "Buyurtma qabul qilingani, kuryer yo'lga chiqqani va yetkazilgani haqida"
        }
        val promo = NotificationChannel(
            CHANNEL_PROMO,
            "Aksiyalar va yangiliklar",
            NotificationManager.IMPORTANCE_DEFAULT,
        ).apply {
            description = "Kafedan chegirmalar va yangi taomlar haqida xabarlar"
        }
        context.getSystemService(NotificationManager::class.java)?.let { manager ->
            manager.createNotificationChannel(channel)
            manager.createNotificationChannel(promo)
        }
    }

    /** Kafedan aksiya xabari (ilova ochiq paytda keldi: tizim o'zi ko'rsatmaydi). */
    fun showPromo(title: String, text: String) {
        if (!isEnabled()) return
        val open = Intent(context, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        val pending = PendingIntent.getActivity(
            context,
            PROMO_REQUEST,
            open,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(context, CHANNEL_PROMO)
            .setSmallIcon(R.drawable.ic_bell)
            .setColor(ContextCompat.getColor(context, R.color.brand))
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setContentIntent(pending)
            .setAutoCancel(true)
            .build()
        try {
            manager.notify(PROMO_NOTIFICATION_ID, notification)
        } catch (e: SecurityException) {
            // Ruxsat shu lahzada qaytarib olingan
        }
    }

    /** Telefon hozir bildirishnoma ko'rsatishga ruxsat beradimi. */
    fun isEnabled(): Boolean {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            val granted = ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS)
            if (granted != PackageManager.PERMISSION_GRANTED) return false
        }
        return manager.areNotificationsEnabled()
    }

    fun show(event: LiveEvent.OrderChanged) {
        val notice = orderNotice(event) ?: return
        if (!isEnabled()) return
        val open = Intent(context, MainActivity::class.java)
            .putExtra(EXTRA_ORDER_ID, event.orderId)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        val pending = PendingIntent.getActivity(
            context,
            event.orderId,
            open,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(context, CHANNEL_ORDERS)
            .setSmallIcon(R.drawable.ic_bell)
            .setColor(ContextCompat.getColor(context, R.color.brand))
            .setContentTitle(notice.title)
            .setContentText(notice.text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(notice.text))
            .setContentIntent(pending)
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            // Android 7 da kanal yo'q: ovoz va tebranish shu yerda so'ralmasa, xabar jim keladi
            .setDefaults(NotificationCompat.DEFAULT_ALL)
            .setCategory(NotificationCompat.CATEGORY_STATUS)
            .build()
        try {
            manager.notify(event.orderId, notification)
        } catch (e: SecurityException) {
            // Ruxsat shu lahzada qaytarib olingan: bildirishnoma ko'rsatilmaydi
        }
    }

    /** Mijoz buyurtma ekranini ochgan: shu buyurtma haqidagi bildirishnoma endi kerak emas. */
    fun dismiss(orderId: Int) {
        manager.cancel(orderId)
    }

    /** Hisobdan chiqildi: avvalgi hisobning bildirishnomalari ekranda qolmaydi. */
    fun dismissAll() {
        manager.cancelAll()
    }

    companion object {
        const val CHANNEL_ORDERS = "orders"
        const val CHANNEL_PROMO = "promo"
        // Buyurtma bildirishnomalari buyurtma raqamini ishlatadi: aksiya manfiy raqamda turadi
        private const val PROMO_NOTIFICATION_ID = -1
        private const val PROMO_REQUEST = -1
        const val EXTRA_ORDER_ID = "order_id"

        /** Telefon sozlamalaridagi shu ilovaning bildirishnomalar sahifasi. */
        fun settingsIntent(context: Context): Intent {
            val intent = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                    .putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName)
            } else {
                Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS)
                    .setData(Uri.fromParts("package", context.packageName, null))
            }
            return intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
    }
}
