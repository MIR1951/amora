package uz.amora.app

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import uz.amora.app.notify.OrderNotifier
import uz.amora.app.ui.AmoraNavHost
import uz.amora.app.ui.theme.AmoraTheme

class MainActivity : ComponentActivity() {
    // Bildirishnoma bosilganda ochilishi kerak bo'lgan buyurtma
    private var openOrderId by mutableStateOf<Int?>(null)

    @OptIn(ExperimentalComposeUiApi::class)
    override fun onCreate(savedInstanceState: Bundle?) {
        // Ilova ochilayotganda logotipli ekran ko'rinadi (Theme.Amora.Launch), keyin oddiy mavzuga o'tiladi
        setTheme(R.style.Theme_Amora)
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        val container = (application as AmoraApp).container
        // Ekran aylantirilganda yoki ilova "oxirgi ilovalar" ro'yxatidan qayta ochilganda
        // (tizim eski intentni qayta beradi) avvalgi bildirishnoma qayta ochilib ketmasin
        val fromRecents = (intent.flags and Intent.FLAG_ACTIVITY_LAUNCHED_FROM_HISTORY) != 0
        if (savedInstanceState == null && !fromRecents) openOrderId = orderIdFrom(intent)
        setContent {
            AmoraTheme {
                // testTagsAsResourceId: avtomatik sinov (android/ci/smoke_test.py) elementlarni belgisi orqali topadi
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .semantics { testTagsAsResourceId = true },
                ) {
                    AmoraNavHost(
                        container = container,
                        openOrderId = openOrderId,
                        onOrderOpened = { openOrderId = null },
                    )
                }
            }
        }
    }

    /** Ilova ochiq turganda bildirishnoma bosildi. */
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        orderIdFrom(intent)?.let { openOrderId = it }
    }

    private fun orderIdFrom(intent: Intent?): Int? =
        intent?.getIntExtra(OrderNotifier.EXTRA_ORDER_ID, 0)?.takeIf { it > 0 }
}
