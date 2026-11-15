package uz.amora.app.ui.address

import android.Manifest
import android.content.Context
import android.content.Intent
import android.graphics.Color as AndroidColor
import android.location.Location
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Place
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.launch
import org.osmdroid.events.MapListener
import org.osmdroid.events.ScrollEvent
import org.osmdroid.events.ZoomEvent
import org.osmdroid.tileprovider.tilesource.TileSourceFactory
import org.osmdroid.util.GeoPoint
import org.osmdroid.views.CustomZoomButtonsController
import org.osmdroid.views.MapView
import org.osmdroid.views.overlay.Marker
import org.osmdroid.views.overlay.Polygon
import uz.amora.app.AppContainer
import uz.amora.app.R
import uz.amora.app.data.Address
import uz.amora.app.ui.components.BackTopBar
import uz.amora.app.ui.components.BigButton
import uz.amora.app.util.distanceKm

// Manzil hali tanlanmagan va kafe joylashuvi ham kiritilmagan bo'lsa, xarita shu yerdan ochiladi
private const val DEFAULT_LATITUDE = 41.3775
private const val DEFAULT_LONGITUDE = 64.5853
private const val COUNTRY_ZOOM = 6.0
private const val CITY_ZOOM = 14.0
private const val STREET_ZOOM = 17.0

// Bundan uzoqroq ko'rinishda nuqta juda noaniq bo'ladi: tasdiqlashga ruxsat berilmaydi
private const val MIN_CONFIRM_ZOOM = 14.0
private const val MAX_NOTE_LENGTH = 255

/**
 * Yetkazish manzilini tanlash. Xarita suriladi, o'rtadagi belgi turgan joy manzil bo'ladi.
 * Xarita: OpenStreetMap (kalit yoki to'lov talab qilmaydi).
 */
@Composable
fun AddressScreen(container: AppContainer, onBack: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val saved = container.session.address.collectAsStateWithLifecycle().value
    val shop = container.catalog.state.collectAsStateWithLifecycle().value.shop
    val finder = remember { LocationFinder(context) }

    val cafeLatitude = shop?.cafeLatitude
    val cafeLongitude = shop?.cafeLongitude
    val maxDeliveryKm = shop?.maxDeliveryKm
    val cafePoint = remember(cafeLatitude, cafeLongitude) {
        if (cafeLatitude != null && cafeLongitude != null) GeoPoint(cafeLatitude, cafeLongitude) else null
    }

    val mapView = remember {
        createMapView(
            context = context,
            start = when {
                saved != null -> GeoPoint(saved.latitude, saved.longitude)
                cafePoint != null -> cafePoint
                else -> GeoPoint(DEFAULT_LATITUDE, DEFAULT_LONGITUDE)
            },
            zoom = when {
                saved != null -> STREET_ZOOM
                cafePoint != null -> CITY_ZOOM
                else -> COUNTRY_ZOOM
            },
        )
    }
    val myLocationMarker = remember { createMyLocationMarker(context, mapView) }

    var center by remember {
        mutableStateOf(GeoPoint(mapView.mapCenter.latitude, mapView.mapCenter.longitude))
    }
    var note by rememberSaveable { mutableStateOf(saved?.note ?: "") }
    var locating by remember { mutableStateOf(false) }
    var notice by remember { mutableStateOf<String?>(null) }
    var locationOff by remember { mutableStateOf(false) }

    val outOfZone by remember(cafePoint, maxDeliveryKm) {
        derivedStateOf {
            cafePoint != null && maxDeliveryKm != null &&
                distanceKm(cafePoint.latitude, cafePoint.longitude, center.latitude, center.longitude) > maxDeliveryKm
        }
    }

    // Xarita surilganda o'rtadagi nuqtani kuzatib boramiz
    DisposableEffect(mapView) {
        val listener = object : MapListener {
            override fun onScroll(event: ScrollEvent?): Boolean {
                center = GeoPoint(mapView.mapCenter.latitude, mapView.mapCenter.longitude)
                return false
            }

            override fun onZoom(event: ZoomEvent?): Boolean {
                center = GeoPoint(mapView.mapCenter.latitude, mapView.mapCenter.longitude)
                return false
            }
        }
        mapView.addMapListener(listener)
        onDispose { mapView.removeMapListener(listener) }
    }

    // Yetkazish hududi chegarasi (kafe atrofidagi doira)
    DisposableEffect(mapView, cafePoint, maxDeliveryKm) {
        val zone = if (cafePoint != null && maxDeliveryKm != null) {
            createZoneCircle(cafePoint, maxDeliveryKm)
        } else {
            null
        }
        if (zone != null) {
            mapView.overlays.add(0, zone)
            mapView.invalidate()
        }
        onDispose {
            if (zone != null) mapView.overlays.remove(zone)
        }
    }

    // Xarita ekran bilan birga "uyg'onadi" va "uxlaydi", ekran yopilganda tozalanadi
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner, mapView) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_RESUME -> mapView.onResume()
                Lifecycle.Event.ON_PAUSE -> mapView.onPause()
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            mapView.onDetach()
        }
    }

    val showLocation: (Location) -> Unit = { location ->
        val point = GeoPoint(location.latitude, location.longitude)
        myLocationMarker.position = point
        if (!mapView.overlays.contains(myLocationMarker)) mapView.overlays.add(myLocationMarker)
        mapView.controller.animateTo(point, STREET_ZOOM, 700L)
        mapView.invalidate()
    }

    val locate: () -> Unit = {
        if (!finder.isEnabled()) {
            locationOff = true
            notice = "Telefonda joylashuv (GPS) o'chirilgan. Uni yoqing yoki manzilni xaritadan qo'lda tanlang."
        } else if (!locating) {
            locationOff = false
            notice = null
            locating = true
            scope.launch {
                try {
                    val lastKnown = finder.lastKnown()
                    if (lastKnown != null) showLocation(lastKnown)
                    val current = finder.current()
                    if (current != null) {
                        showLocation(current)
                    } else if (lastKnown == null) {
                        notice = "Joylashuvni aniqlab bo'lmadi. Manzilni xaritadan qo'lda tanlang."
                    }
                } finally {
                    locating = false
                }
            }
        }
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) { result ->
        if (result.values.any { it }) {
            locate()
        } else {
            notice = "Joylashuvga ruxsat berilmadi. Manzilni xaritadan qo'lda tanlang."
        }
    }

    val onMyLocation: () -> Unit = {
        if (finder.hasPermission()) {
            locate()
        } else {
            permissionLauncher.launch(
                arrayOf(
                    Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION,
                ),
            )
        }
    }

    // Manzil birinchi marta tanlanayotgan bo'lsa, xaritani darhol mijoz turgan joyga olib boramiz
    LaunchedEffect(Unit) {
        if (saved == null) onMyLocation()
    }

    val confirm: () -> Unit = {
        if (mapView.zoomLevelDouble < MIN_CONFIRM_ZOOM) {
            locationOff = false
            notice = "Xaritani yaqinlashtirib, yetkazish joyini aniqroq belgilang."
        } else {
            val point = mapView.mapCenter
            container.session.saveAddress(Address(point.latitude, point.longitude, note.trim()))
            onBack()
        }
    }

    Scaffold(
        modifier = Modifier.imePadding(),
        containerColor = MaterialTheme.colorScheme.background,
        topBar = { BackTopBar(title = "Yetkazish manzili", onBack = onBack) },
        bottomBar = {
            Surface(
                color = MaterialTheme.colorScheme.surface,
                shadowElevation = 12.dp,
                shape = RoundedCornerShape(topStart = 24.dp, topEnd = 24.dp),
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .navigationBarsPadding()
                        .padding(16.dp),
                ) {
                    val currentNotice = notice
                    if (outOfZone) {
                        Text(
                            text = "Bu joy yetkazish hududidan tashqarida. Belgini doira ichiga suring.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.error,
                        )
                        Spacer(Modifier.height(8.dp))
                    } else if (currentNotice != null) {
                        Text(
                            text = currentNotice,
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.error,
                        )
                        if (locationOff) {
                            TextButton(onClick = { openLocationSettings(context) }) {
                                Text("Joylashuv sozlamalarini ochish")
                            }
                        } else {
                            Spacer(Modifier.height(8.dp))
                        }
                    }
                    OutlinedTextField(
                        value = note,
                        onValueChange = { note = it.take(MAX_NOTE_LENGTH) },
                        label = { Text("Mo'ljal, uy, xonadon") },
                        placeholder = { Text("Masalan: 12-uy, 3-podyezd, 45-xonadon") },
                        modifier = Modifier.fillMaxWidth(),
                        maxLines = 2,
                        shape = MaterialTheme.shapes.medium,
                        keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences),
                    )
                    Spacer(Modifier.height(12.dp))
                    BigButton(
                        text = "Shu manzilga yetkazish",
                        onClick = confirm,
                        enabled = !outOfZone,
                    )
                }
            }
        },
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            AndroidView(factory = { mapView }, modifier = Modifier.fillMaxSize())

            // O'rtadagi belgi: uchi aynan xarita markazini ko'rsatadi
            Icon(
                imageVector = Icons.Default.Place,
                contentDescription = "Tanlangan joy",
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier
                    .align(Alignment.Center)
                    .size(48.dp)
                    .offset(y = (-20).dp),
            )

            Text(
                text = "Xaritani surib, belgini yetkazish joyiga qo'ying",
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.onSurface,
                textAlign = TextAlign.Center,
                modifier = Modifier
                    .align(Alignment.TopCenter)
                    .padding(12.dp)
                    .clip(RoundedCornerShape(50))
                    .background(MaterialTheme.colorScheme.surface.copy(alpha = 0.92f))
                    .padding(horizontal = 14.dp, vertical = 8.dp),
            )

            // OpenStreetMap shartiga ko'ra xarita manbasi ko'rsatilishi kerak
            Text(
                text = "© OpenStreetMap",
                style = MaterialTheme.typography.labelSmall,
                color = Color(0xFF333333),
                modifier = Modifier
                    .align(Alignment.BottomStart)
                    .padding(6.dp)
                    .clip(RoundedCornerShape(4.dp))
                    .background(Color(0xCCFFFFFF))
                    .padding(horizontal = 6.dp, vertical = 2.dp),
            )

            FloatingActionButton(
                onClick = onMyLocation,
                modifier = Modifier
                    .align(Alignment.BottomEnd)
                    .padding(16.dp),
                containerColor = MaterialTheme.colorScheme.surface,
                contentColor = MaterialTheme.colorScheme.primary,
            ) {
                if (locating) {
                    CircularProgressIndicator(modifier = Modifier.size(24.dp), strokeWidth = 2.dp)
                } else {
                    Icon(
                        painter = painterResource(R.drawable.ic_gps),
                        contentDescription = "Mening joylashuvim",
                    )
                }
            }
        }
    }
}

private fun createMapView(context: Context, start: GeoPoint, zoom: Double): MapView {
    val mapView = MapView(context)
    mapView.setTileSource(TileSourceFactory.MAPNIK)
    mapView.setMultiTouchControls(true)
    mapView.zoomController.setVisibility(CustomZoomButtonsController.Visibility.NEVER)
    mapView.setTilesScaledToDpi(true)
    mapView.setMinZoomLevel(5.0)
    mapView.setMaxZoomLevel(19.0)
    mapView.setVerticalMapRepetitionEnabled(false)
    mapView.controller.setZoom(zoom)
    mapView.controller.setCenter(start)
    return mapView
}

/** Kafe atrofidagi yetkazish hududi doirasi. */
@Suppress("DEPRECATION")
private fun createZoneCircle(center: GeoPoint, radiusKm: Double): Polygon {
    val circle = Polygon()
    circle.setPoints(Polygon.pointsAsCircle(center, radiusKm * 1000.0))
    circle.setFillColor(AndroidColor.argb(22, 217, 68, 43))
    circle.setStrokeColor(AndroidColor.argb(150, 217, 68, 43))
    circle.setStrokeWidth(4f)
    return circle
}

/** Mijoz turgan joyni ko'rsatuvchi ko'k nuqta. */
private fun createMyLocationMarker(context: Context, mapView: MapView): Marker {
    val marker = Marker(mapView)
    marker.icon = ContextCompat.getDrawable(context, R.drawable.ic_my_location)
    marker.setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_CENTER)
    marker.setOnMarkerClickListener { _, _ -> true }
    return marker
}

private fun openLocationSettings(context: Context) {
    try {
        context.startActivity(Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS))
    } catch (e: Exception) {
        // Bunday sozlama oynasi yo'q telefonlar juda kam: hech narsa qilmaymiz
    }
}
