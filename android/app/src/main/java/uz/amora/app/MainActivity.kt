package uz.amora.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import uz.amora.app.ui.AmoraNavHost
import uz.amora.app.ui.theme.AmoraTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        val container = (application as AmoraApp).container
        setContent {
            AmoraTheme {
                AmoraNavHost(container)
            }
        }
    }
}
