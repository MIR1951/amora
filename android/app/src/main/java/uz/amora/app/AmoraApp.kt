package uz.amora.app

import android.app.Application
import android.content.Context
import java.io.File
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import org.osmdroid.config.Configuration
import uz.amora.app.data.Account
import uz.amora.app.data.ApiClient
import uz.amora.app.data.CartStore
import uz.amora.app.data.Catalog
import uz.amora.app.data.SessionStore

/** Ilova davomida bitta nusxada yashaydigan qismlar. Ekranlar shu yerdan oladi. */
class AppContainer(context: Context) {
    private val appScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    val baseUrl: String = BuildConfig.API_BASE_URL
    val session = SessionStore(context)
    val cart = CartStore(context)
    val api = ApiClient(baseUrl) { session.token }
    val catalog = Catalog(api)
    val account = Account(api, session, appScope)
}

class AmoraApp : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
        configureMap()
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
