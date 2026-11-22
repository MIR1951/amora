package uz.amora.app.data

import android.util.Log
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/**
 * Firebase qurilma manzilini (token) serverga yetkazadi: server buyurtma holati o'zgarganda
 * shu manzilga xabar yuboradi. Mijoz hali ro'yxatdan o'tmagan bo'lsa, ro'yxatdan o'tgach yuboriladi.
 * Hamma telefon "all" mavzusiga yoziladi: kafe botdan aksiya xabarini shu orqali yuboradi.
 */
class PushTokens(
    private val api: ApiClient,
    private val session: SessionStore,
    private val scope: CoroutineScope,
) {
    private val mutex = Mutex()

    fun start() {
        try {
            val messaging = FirebaseMessaging.getInstance()
            messaging.token.addOnSuccessListener { token -> onNewToken(token) }
            messaging.subscribeToTopic(BROADCAST_TOPIC)
        } catch (e: IllegalStateException) {
            // Firebase sozlanmagan (google-services.json yo'q): bildirishnoma jonli ulanish bilan ishlaydi
            Log.w(TAG, "Firebase ishlamayapti", e)
            return
        }
        // Mijoz ro'yxatdan o'tdi yoki qayta ro'yxatdan o'tdi: manzil yangi kalit bilan yuboriladi
        scope.launch { session.tokenFlow.collect { sync() } }
    }

    fun onNewToken(token: String) {
        if (token == session.pushToken) return
        session.pushToken = token
        session.pushTokenSentWith = null
        scope.launch { sync() }
    }

    /** Ilova ekranga qaytdi: oldin yuborilmay qolgan bo'lsa, yana urinadi. */
    fun retry() {
        scope.launch { sync() }
    }

    private suspend fun sync() = mutex.withLock {
        val pushToken = session.pushToken ?: return@withLock
        val authToken = session.token ?: return@withLock
        // Qaysi manzil qaysi kalit bilan yuborilgani: yuborish paytida manzil yangilansa,
        // yangisi ham yuboriladi. Kirish kalitining o'zi emas, izi saqlanadi (xotirada ochiq turmasin)
        val sent = sha256Hex("$authToken|$pushToken")
        if (session.pushTokenSentWith == sent) return@withLock
        try {
            api.updatePushToken(pushToken)
            session.pushTokenSentWith = sent
        } catch (e: ApiException) {
            // Keyingi safar (ilova qayta ochilganda yoki kalit yangilanganda) yana urinamiz
            Log.w(TAG, "Push manzili serverga yuborilmadi: ${e.message}")
        }
    }

    private companion object {
        const val TAG = "AmoraPush"
        const val BROADCAST_TOPIC = "all"
    }
}
