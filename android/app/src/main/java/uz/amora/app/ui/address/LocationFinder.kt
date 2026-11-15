package uz.amora.app.ui.address

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Bundle
import android.os.Looper
import androidx.core.content.ContextCompat
import kotlin.coroutines.resume
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull

/**
 * Telefonning joylashuvini aniqlaydi. Google xizmatlariga bog'liq emas:
 * Androidning o'z LocationManager'i ishlatiladi (GPS va tarmoq).
 */
class LocationFinder(context: Context) {
    private val appContext = context.applicationContext
    private val manager = appContext.getSystemService(Context.LOCATION_SERVICE) as LocationManager

    fun hasPermission(): Boolean =
        isGranted(Manifest.permission.ACCESS_FINE_LOCATION) ||
            isGranted(Manifest.permission.ACCESS_COARSE_LOCATION)

    private fun isGranted(permission: String): Boolean =
        ContextCompat.checkSelfPermission(appContext, permission) == PackageManager.PERMISSION_GRANTED

    /** Telefonda joylashuv xizmati (GPS yoki tarmoq orqali) yoqilganmi. */
    fun isEnabled(): Boolean = enabledProviders().isNotEmpty()

    private fun enabledProviders(): List<String> {
        val candidates = ArrayList<String>()
        // Aniq joylashuvga ruxsat bo'lmasa GPS'dan foydalanib bo'lmaydi
        if (isGranted(Manifest.permission.ACCESS_FINE_LOCATION)) candidates.add(LocationManager.GPS_PROVIDER)
        candidates.add(LocationManager.NETWORK_PROVIDER)
        return candidates.filter { provider ->
            try {
                manager.isProviderEnabled(provider)
            } catch (e: Exception) {
                false
            }
        }
    }

    /** Oxirgi ma'lum joylashuv: darhol qaytadi, lekin eskirgan bo'lishi mumkin. */
    @SuppressLint("MissingPermission")
    fun lastKnown(): Location? {
        var best: Location? = null
        for (provider in enabledProviders()) {
            val location = try {
                manager.getLastKnownLocation(provider)
            } catch (e: Exception) {
                null
            }
            if (location != null && (best == null || location.time > best.time)) best = location
        }
        return best
    }

    /** Hozirgi joylashuv. Belgilangan vaqt ichida aniqlanmasa null. */
    @SuppressLint("MissingPermission")
    suspend fun current(timeoutMillis: Long = 15_000L): Location? {
        val providers = enabledProviders()
        if (providers.isEmpty()) return null
        return withTimeoutOrNull(timeoutMillis) {
            suspendCancellableCoroutine<Location?> { continuation ->
                val listener = object : LocationListener {
                    override fun onLocationChanged(location: Location) {
                        manager.removeUpdates(this)
                        if (continuation.isActive) continuation.resume(location)
                    }

                    // Eski Android versiyalarida bu funksiyalar majburiy
                    @Deprecated("Deprecated in Java")
                    override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) = Unit

                    override fun onProviderEnabled(provider: String) = Unit

                    override fun onProviderDisabled(provider: String) = Unit
                }
                continuation.invokeOnCancellation { manager.removeUpdates(listener) }
                try {
                    for (provider in providers) {
                        manager.requestLocationUpdates(provider, 0L, 0f, listener, Looper.getMainLooper())
                    }
                } catch (e: Exception) {
                    manager.removeUpdates(listener)
                    if (continuation.isActive) continuation.resume(null)
                }
            }
        }
    }
}
