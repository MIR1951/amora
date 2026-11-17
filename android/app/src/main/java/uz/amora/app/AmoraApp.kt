package uz.amora.app

import android.app.Application
import android.content.Context
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.ProcessLifecycleOwner
import java.io.File
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import org.osmdroid.config.Configuration
import uz.amora.app.data.Account
import uz.amora.app.data.ActiveOrders
import uz.amora.app.data.ApiClient
import uz.amora.app.data.CartStore
import uz.amora.app.data.Catalog
import uz.amora.app.data.LiveUpdates
import uz.amora.app.data.PushTokens
import uz.amora.app.data.Realtime
import uz.amora.app.data.SessionStore
import uz.amora.app.notify.OrderNotifier

/** Ilova davomida bitta nusxada yashaydigan qismlar. Ekranlar shu yerdan oladi. */
class AppContainer(context: Context) {
    private val appScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    val baseUrl: String = BuildConfig.API_BASE_URL
    val session = SessionStore(context)
    val cart = CartStore(context)
    val api = ApiClient(baseUrl) { session.token }
    val catalog = Catalog(api)
    val account = Account(api, session, appScope)

    // Jonli yangilanishlar: server bilan doimiy ulanish va unga tayanadigan qismlar
    val realtime = Realtime(baseUrl, { session.token }, appScope)
    val activeOrders = ActiveOrders(api, session)
    val notifier = OrderNotifier(context)
    val live = LiveUpdates(realtime, catalog, activeOrders, notifier, session, appScope)

    // Firebase: ilova yopiq bo'lsa ham bildirishnoma
    val push = PushTokens(api, session, appScope)
}

class AmoraApp : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
        container.notifier.createChannel()
        container.push.start()
        configureMap()
        // Ilova ekranda turganda server bilan jonli ulanish ushlab turiladi
        ProcessLifecycleOwner.get().lifecycle.addObserver(
            object : DefaultLifecycleObserver {
                override fun onStart(owner: LifecycleOwner) {
                    container.live.onForeground()
                    container.push.retry()
                    container.account.refreshInBackground()
                }

                override fun onStop(owner: LifecycleOwner) = container.live.onBackground()
            },
        )
    }

    /** Xarita (OpenStreetMap) sozlamalari: ilovani tanituvchi nom va kesh joyi. */
    private fun configureMap() {
        val basePath = File(filesDir, "osmdroid")
        val tileCache = File(cacheDir, "osmdroid-tiles")
        basePath.mkdirs()
        tileCache.mkdirs()
        val config = Configuration.getInstance()
        config.userAgentValue = BuildConfig.APPLICATION_ID
        config.osmdroidBasePath = basePath
        config.osmdroidTileCache = tileCache
        config.tileFileSystemCacheMaxBytes = 100L * 1024 * 1024
        config.tileFileSystemCacheTrimBytes = 80L * 1024 * 1024
    }
}
