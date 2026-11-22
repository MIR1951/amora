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
import kotlinx.coroutines.async
import org.osmdroid.config.Configuration
import uz.amora.app.data.Account
import uz.amora.app.data.ActiveOrders
import uz.amora.app.data.ApiClient
import uz.amora.app.data.ApiException
import uz.amora.app.data.CartStore
import uz.amora.app.data.Catalog
import uz.amora.app.data.LiveUpdates
import uz.amora.app.data.OrderSubmitter
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
    val api = ApiClient(
        baseUrl,
        tokenProvider = { session.token },
        // Server kalitni tanimadi: telefon hisobdan chiqadi. Shu orada yangi kalit olingan bo'lsa
        // (raqam qayta tasdiqlandi), eski kalitning xatosi uni o'chirmaydi
        onUnauthorized = { tokenUsed -> if (session.token == tokenUsed) session.signOut() },
    )
    val catalog = Catalog(api)
    val account = Account(api, session, appScope)

    // Jonli yangilanishlar: server bilan doimiy ulanish va unga tayanadigan qismlar
    val realtime = Realtime(baseUrl, { session.token }, appScope)
    val activeOrders = ActiveOrders(api, session)
    val notifier = OrderNotifier(context)
    val live = LiveUpdates(realtime, catalog, activeOrders, notifier, session, appScope)

    // Firebase: ilova yopiq bo'lsa ham bildirishnoma
    val push = PushTokens(api, session, appScope)

    // Buyurtma yuborish: savat ekrani yopilsa ham oxirigacha boradi
    val orders = OrderSubmitter(api, account, cart, activeOrders, live, appScope)

    /**
     * Hisobdan chiqish. Server shu telefonning kalitini bekor qiladi; unga yetib bo'lmasa ham
     * (internet yo'q) telefondagi kalit va profil o'chiriladi.
     */
    suspend fun logout() = appScope.async {
        if (session.token != null) {
            try {
                api.logout()
            } catch (e: ApiException) {
                // Mijoz chiqmoqchi: serverga yetib bo'lmasa ham telefondan chiqiladi
            }
        }
        session.clearAccount()
        live.forgetOrders()
    }.await()

    /**
     * Hisobni o'chirish. O'chirilmasa (masalan tugallanmagan buyurtma bor), mijozga ko'rsatiladigan
     * xato matni qaytadi; o'chirilsa null va telefondagi hamma ma'lumot tozalanadi.
     */
    suspend fun deleteAccount(): String? = appScope.async {
        try {
            api.deleteAccount()
        } catch (e: ApiException) {
            return@async if (e.isUnauthorized) Account.NOT_VERIFIED_AGAIN_MESSAGE else e.message
        }
        session.clearAccount()
        session.clearAddress()
        cart.clear()
        live.forgetOrders()
        null
    }.await()
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
                    container.account.checkPendingVerificationInBackground()
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
