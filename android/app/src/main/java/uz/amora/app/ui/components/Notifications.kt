package uz.amora.app.ui.components

import android.Manifest
import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.ContextWrapper
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LifecycleResumeEffect
import uz.amora.app.AppContainer
import uz.amora.app.notify.OrderNotifier

private fun hasNotificationPermission(context: Context): Boolean =
    Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
        ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) ==
        PackageManager.PERMISSION_GRANTED

internal tailrec fun Context.findActivity(): Activity? = when (this) {
    is Activity -> this
    is ContextWrapper -> baseContext.findActivity()
    else -> null
}

/**
 * Bildirishnomaga ruxsatni bir marta so'raydi (Android 13+). Mijoz faol buyurtma ekraniga
 * kelganda chaqiriladi: nega kerakligi shu yerda tushunarli. Rad etilsa, qayta so'ralmaydi;
 * keyin profil sahifasidagi "Bildirishnomalar" qatoridan yoqish mumkin.
 */
@Composable
fun AskNotificationPermissionOnce(container: AppContainer) {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
    val context = LocalContext.current
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { }
    LaunchedEffect(Unit) {
        if (!hasNotificationPermission(context) && !container.session.notificationsAsked) {
            container.session.notificationsAsked = true
            launcher.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }
}

/** Bildirishnomalar yoqilganmi va ularni yoqish (yoki sozlamalarini ochish) amali. */
class NotificationSwitch(val enabled: Boolean, val toggle: () -> Unit)

/**
 * Profil sahifasidagi "Bildirishnomalar" qatori uchun. O'chiq bo'lsa, bosilganda avval tizim
 * ruxsat oynasi chiqadi; tizim uni endi ko'rsatmasa (mijoz ikki marta rad etgan), telefon
 * sozlamalaridagi shu ilova sahifasi ochiladi.
 */
@Composable
fun rememberNotificationSwitch(container: AppContainer): NotificationSwitch {
    val context = LocalContext.current
    var enabled by remember { mutableStateOf(container.notifier.isEnabled()) }
    // Mijoz sozlamalardan qaytganda holat qayta o'qiladi
    LifecycleResumeEffect(Unit) {
        enabled = container.notifier.isEnabled()
        onPauseOrDispose { }
    }
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {
        enabled = container.notifier.isEnabled()
    }
    val toggle: () -> Unit = {
        val activity = context.findActivity()
        val canAsk = Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            !hasNotificationPermission(context) &&
            (
                !container.session.notificationsAsked ||
                    (
                        activity != null && ActivityCompat.shouldShowRequestPermissionRationale(
                            activity,
                            Manifest.permission.POST_NOTIFICATIONS,
                        )
                        )
                )
        if (canAsk) {
            container.session.notificationsAsked = true
            launcher.launch(Manifest.permission.POST_NOTIFICATIONS)
        } else {
            try {
                context.startActivity(OrderNotifier.settingsIntent(context))
            } catch (e: ActivityNotFoundException) {
                // Bunday sahifasi yo'q telefon: hech narsa ochilmaydi
            }
        }
    }
    return NotificationSwitch(enabled, toggle)
}
