package uz.amora.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import uz.amora.app.ui.AmoraNavHost
import uz.amora.app.ui.theme.AmoraTheme

class MainActivity : ComponentActivity() {
    @OptIn(ExperimentalComposeUiApi::class)
    override fun onCreate(savedInstanceState: Bundle?) {
        // Ilova ochilayotganda logotipli ekran ko'rinadi (Theme.Amora.Launch), keyin oddiy mavzuga o'tiladi
        setTheme(R.style.Theme_Amora)
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        val container = (application as AmoraApp).container
        setContent {
            AmoraTheme {
                // testTagsAsResourceId: avtomatik sinov (android/ci/smoke_test.py) elementlarni belgisi orqali topadi
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .semantics { testTagsAsResourceId = true },
                ) {
                    AmoraNavHost(container)
                }
            }
        }
    }
}
