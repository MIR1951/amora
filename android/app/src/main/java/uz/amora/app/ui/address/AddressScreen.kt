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
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TextField
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
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardCapitalization
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
import uz.amora.app.ui.components.BigButton
import uz.amora.app.ui.components.CircleIconButton
import uz.amora.app.ui.components.fieldColors
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

// Pastki panel burchagi: xarita shu qadar panel ostiga kirib turadi
private val PANEL_CORNER = 26.dp
private val PIN_HEAD = 38.dp
private val PIN_STEM = 16.dp

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

    val scheme = MaterialTheme.colorScheme

    Scaffold(
        modifier = Modifier.imePadding(),
        containerColor = scheme.background,
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        bottomBar = {
            Surface(
                color = scheme.surface,
                shadowElevation = 16.dp,
                shape = RoundedCornerShape(topStart = PANEL_CORNER, topEnd = PANEL_CORNER),
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .navigationBarsPadding()
                        .padding(start = 16.dp, end = 16.dp, top = 20.dp, bottom = 12.dp),
                ) {
                    Text("Yetkazish manzili", style = MaterialTheme.typography.titleLarge)
                    Spacer(Modifier.height(2.dp))
                    Text(
                        text = "Xaritani surib, belgini yetkazish joyiga qo'ying",
                        style = MaterialTheme.typography.bodyMedium,
                        color = scheme.onSurfaceVariant,
                    )
                    Spacer(Modifier.height(14.dp))

                    val currentNotice = notice
                    val warning = when {
                        outOfZone -> "Bu joy yetkazish hududidan tashqarida. Belgini doira ichiga suring."
                        else -> currentNotice
                    }
                    if (warning != null) {
                        Surface(
                            modifier = Modifier.fillMaxWidth(),
                            shape = MaterialTheme.shapes.medium,
                            color = scheme.errorContainer,
                            contentColor = scheme.onErrorContainer,
                        ) {
                            Column(modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp)) {
                                Text(warning, style = MaterialTheme.typography.bodyMedium)
                                if (!outOfZone && locationOff) {
                                    TextButton(
                                        onClick = { openLocationSettings(context) },
                                        contentPadding = PaddingValues(0.dp),
                                    ) {
                                        Text(
                                            text = "Joylashuv sozlamalarini ochish",
                                            style = MaterialTheme.typography.labelLarge,
                                        )
                                    }
                                }
                            }
                        }
                        Spacer(Modifier.height(12.dp))
                    }

                    TextField(
                        value = note,
                        onValueChange = { note = it.take(MAX_NOTE_LENGTH) },
                        label = { Text("Mo'ljal, uy, xonadon") },
                        placeholder = { Text("Masalan: 12-uy, 3-podyezd, 45-xonadon") },
                        modifier = Modifier.fillMaxWidth(),
                        maxLines = 2,
                        shape = MaterialTheme.shapes.medium,
                        colors = fieldColors(container = scheme.surfaceVariant),
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
        // Xarita panelning yumaloq burchaklari ostiga ham kirib turadi
        val mapBottom = (padding.calculateBottomPadding() - PANEL_CORNER).coerceAtLeast(0.dp)
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(bottom = mapBottom),
        ) {
            AndroidView(factory = { mapView }, modifier = Modifier.fillMaxSize())

            // O'rtadagi belgi: uchi aynan xarita markazini ko'rsatadi
            Box(
                modifier = Modifier
                    .align(Alignment.Center)
                    .size(width = 10.dp, height = 5.dp)
                    .clip(RoundedCornerShape(50))
                    .background(Color.Black.copy(alpha = 0.28f)),
            )
            Column(
                modifier = Modifier
                    .align(Alignment.Center)
                    .offset(y = -(PIN_HEAD + PIN_STEM) / 2)
                    .semantics { contentDescription = "Tanlangan joy" },
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Box(
                    modifier = Modifier
                        .size(PIN_HEAD)
                        .shadow(elevation = 6.dp, shape = CircleShape)
                        .clip(CircleShape)
                        .background(scheme.primary),
                    contentAlignment = Alignment.Center,
                ) {
                    Box(
                        modifier = Modifier
                            .size(14.dp)
                            .clip(CircleShape)
                            .background(Color.White),
                    )
                }
                Box(
                    modifier = Modifier
                        .size(width = 4.dp, height = PIN_STEM)
                        .clip(RoundedCornerShape(bottomStart = 2.dp, bottomEnd = 2.dp))
                        .background(scheme.primary),
                )
            }

            // Holat satri ostidagi yumshoq parda: soat va belgilar xarita ustida ham o'qiladi
            Box(
                modifier = Modifier
                    .align(Alignment.TopCenter)
                    .fillMaxWidth()
                    .height(96.dp)
                    .background(
                        Brush.verticalGradient(
                            listOf(scheme.background.copy(alpha = 0.85f), scheme.background.copy(alpha = 0f)),
                        ),
                    ),
            )

            CircleIconButton(
                icon = Icons.AutoMirrored.Filled.ArrowBack,
                label = "Orqaga",
                onClick = onBack,
                modifier = Modifier
                    .align(Alignment.TopStart)
                    .statusBarsPadding()
                    .padding(start = 16.dp, top = 8.dp),
                elevation = 6.dp,
            )

            // OpenStreetMap shartiga ko'ra xarita manbasi ko'rsatilishi kerak
            Text(
                text = "© OpenStreetMap",
                style = MaterialTheme.typography.labelSmall,
                color = Color(0xFF333333),
                modifier = Modifier
                    .align(Alignment.BottomStart)
                    .padding(start = 8.dp, bottom = PANEL_CORNER + 6.dp)
                    .clip(RoundedCornerShape(6.dp))
                    .background(Color(0xCCFFFFFF))
                    .padding(horizontal = 6.dp, vertical = 2.dp),
            )

            Surface(
                onClick = onMyLocation,
                modifier = Modifier
                    .align(Alignment.BottomEnd)
                    .padding(end = 16.dp, bottom = PANEL_CORNER + 16.dp)
                    .size(52.dp),
                shape = CircleShape,
                color = scheme.surface,
                contentColor = scheme.primary,
                shadowElevation = 6.dp,
            ) {
                Box(contentAlignment = Alignment.Center) {
                    if (locating) {
                        CircularProgressIndicator(modifier = Modifier.size(24.dp), strokeWidth = 2.5.dp)
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
