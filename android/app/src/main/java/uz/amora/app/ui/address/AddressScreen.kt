package uz.amora.app.ui.address

import android.Manifest
import android.content.Context
import android.content.Intent
import android.graphics.Color as AndroidColor
import android.location.Location
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
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
import androidx.compose.ui.layout.layout
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import dev.chrisbanes.haze.HazeState
import kotlinx.coroutines.delay
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
import uz.amora.app.ui.components.GlassBox
import uz.amora.app.ui.components.GlassTone
import uz.amora.app.ui.components.IconTile
import uz.amora.app.ui.components.RoundButton
import uz.amora.app.ui.components.fieldBorder
import uz.amora.app.ui.components.fieldColors
import uz.amora.app.ui.components.glassSource
import uz.amora.app.ui.components.rememberGlassState
import uz.amora.app.ui.theme.amber
import uz.amora.app.ui.theme.hint
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

// Xarita ustidagi yuqori tugmalar egallaydigan joy (holat satridan tashqari)
private val TOP_CONTROLS = 60.dp
private val SHEET_CORNER = 32.dp
private val PIN_HEAD = 46.dp
private val PIN_STEM = 18.dp

// Xarita surilishi shuncha vaqt to'xtab tursa, belgi joyiga "qo'nadi"
private const val PIN_SETTLE_MS = 220L

/**
 * Yetkazish manzilini tanlash. Xarita butun ekranni egallaydi va suriladi; belgi turgan joy manzil bo'ladi.
 * Tugmalar va pastki panel xarita ustida shisha bo'lib turadi. Xarita: OpenStreetMap
 * (kalit yoki to'lov talab qilmaydi).
 */
@Composable
fun AddressScreen(container: AppContainer, onBack: () -> Unit) {
    val context = LocalContext.current
    val density = LocalDensity.current
    val focusManager = LocalFocusManager.current
    val scope = rememberCoroutineScope()
    val glass = rememberGlassState()
    val saved = container.session.address.collectAsStateWithLifecycle().value
    val shop = container.catalog.state.collectAsStateWithLifecycle().value.shop
    val finder = remember { LocationFinder(context) }

    val cafeLatitude = shop?.cafeLatitude
    val cafeLongitude = shop?.cafeLongitude
    val maxDeliveryKm = shop?.maxDeliveryKm
    val cafePoint = remember(cafeLatitude, cafeLongitude) {
        if (cafeLatitude != null && cafeLongitude != null) GeoPoint(cafeLatitude, cafeLongitude) else null
    }

    val startPoint = remember {
        when {
            saved != null -> GeoPoint(saved.latitude, saved.longitude)
            cafePoint != null -> GeoPoint(cafePoint.latitude, cafePoint.longitude)
            else -> GeoPoint(DEFAULT_LATITUDE, DEFAULT_LONGITUDE)
        }
    }
    val mapView = remember {
        createMapView(
            context = context,
            start = startPoint,
            zoom = when {
                saved != null -> STREET_ZOOM
                cafePoint != null -> CITY_ZOOM
                else -> COUNTRY_ZOOM
            },
        )
    }
    val myLocationMarker = remember { createMyLocationMarker(context, mapView) }

    // Belgi xaritaning ko'rinib turgan qismi (yuqori tugmalar va pastki panel orasi) o'rtasida turadi.
    // Shu sabab u ekran markazidan `pinOffsetPx` qadar yuqoriroqda bo'ladi.
    var pinOffsetPx by remember { mutableIntStateOf(0) }
    var sheetHeightPx by remember { mutableIntStateOf(0) }
    val statusBarPx = WindowInsets.statusBars.getTop(density)
    val navigationBarPx = WindowInsets.navigationBars.getBottom(density)
    val topControlsPx = with(density) { TOP_CONTROLS.roundToPx() }

    // Belgi ko'rsatib turgan nuqta
    val pinPoint: () -> GeoPoint = {
        if (mapView.isLayoutOccurred && mapView.width > 0 && mapView.height > 0) {
            val point = mapView.projection.fromPixels(mapView.width / 2, mapView.height / 2 + pinOffsetPx)
            GeoPoint(point.latitude, point.longitude)
        } else {
            startPoint
        }
    }

    var center by remember { mutableStateOf(startPoint) }
    var moving by remember { mutableStateOf(false) }
    var note by rememberSaveable { mutableStateOf(saved?.note ?: "") }
    var locating by remember { mutableStateOf(false) }
    var notice by remember { mutableStateOf<String?>(null) }
    var locationOff by remember { mutableStateOf(false) }

    // Pastki panel balandligi ma'lum bo'lgach (yoki o'zgarsa), belgi joyi qayta hisoblanadi.
    // Tanlangan nuqta o'zgarmaydi: xarita shunga mos suriladi.
    LaunchedEffect(sheetHeightPx, statusBarPx, navigationBarPx) {
        if (sheetHeightPx > 0) {
            val offset = (statusBarPx + topControlsPx - sheetHeightPx - navigationBarPx) / 2
            if (offset != pinOffsetPx) {
                val keep = pinPoint()
                pinOffsetPx = offset
                mapView.setMapCenterOffset(0, offset)
                mapView.controller.setCenter(keep)
                mapView.invalidate()
            }
        }
    }

    val outOfZone by remember(cafePoint, maxDeliveryKm) {
        derivedStateOf {
            cafePoint != null && maxDeliveryKm != null &&
                distanceKm(cafePoint.latitude, cafePoint.longitude, center.latitude, center.longitude) > maxDeliveryKm
        }
    }

    // Xarita surilganda belgi ko'rsatayotgan nuqtani kuzatib boramiz
    DisposableEffect(mapView) {
        val listener = object : MapListener {
            override fun onScroll(event: ScrollEvent?): Boolean {
                center = pinPoint()
                moving = true
                return false
            }

            override fun onZoom(event: ZoomEvent?): Boolean {
                center = pinPoint()
                moving = true
                return false
            }
        }
        mapView.addMapListener(listener)
        onDispose { mapView.removeMapListener(listener) }
    }

    // Xarita to'xtagach belgi joyiga qo'nadi
    LaunchedEffect(center, moving) {
        if (moving) {
            delay(PIN_SETTLE_MS)
            moving = false
        }
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
            val point = pinPoint()
            container.session.saveAddress(Address(point.latitude, point.longitude, note.trim()))
            onBack()
        }
    }

    val scheme = MaterialTheme.colorScheme
    val warning = if (outOfZone) {
        "Bu joy yetkazish hududidan tashqarida. Belgini doira ichiga suring."
    } else {
        notice
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(scheme.background),
    ) {
        AndroidView(
            factory = { mapView },
            modifier = Modifier
                .fillMaxSize()
                .glassSource(glass),
        )

        MapPin(
            moving = moving,
            modifier = Modifier
                .align(Alignment.Center)
                .layout { measurable, constraints ->
                    // Belgining uchi (pastki nuqtasi) aynan tanlangan joyni ko'rsatadi
                    val placeable = measurable.measure(constraints)
                    layout(placeable.width, placeable.height) {
                        placeable.place(0, pinOffsetPx - placeable.height / 2)
                    }
                },
        )

        // Holat satri ostidagi yumshoq parda: soat va belgilar xarita ustida ham o'qiladi
        Box(
            modifier = Modifier
                .align(Alignment.TopCenter)
                .fillMaxWidth()
                .height(88.dp)
                .background(
                    Brush.verticalGradient(
                        listOf(scheme.background.copy(alpha = 0.75f), scheme.background.copy(alpha = 0f)),
                    ),
                ),
        )

        Row(
            modifier = Modifier
                .align(Alignment.TopStart)
                .fillMaxWidth()
                .statusBarsPadding()
                .padding(start = 16.dp, end = 16.dp, top = 8.dp),
            verticalAlignment = Alignment.Top,
        ) {
            RoundButton(icon = R.drawable.ic_back, label = "Orqaga", onClick = onBack, glass = glass)
            Spacer(Modifier.width(10.dp))
            MapHint(
                glass = glass,
                warning = warning,
                actionLabel = if (!outOfZone && locationOff) "Joylashuv sozlamalarini ochish" else null,
                onAction = { openLocationSettings(context) },
                modifier = Modifier.weight(1f, fill = false),
            )
        }

        Column(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .imePadding(),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(start = 10.dp, end = 16.dp, bottom = 12.dp),
                verticalAlignment = Alignment.Bottom,
            ) {
                // OpenStreetMap shartiga ko'ra xarita manbasi ko'rsatilishi kerak
                Text(
                    text = "© OpenStreetMap",
                    style = MaterialTheme.typography.bodySmall.copy(fontSize = MaterialTheme.typography.labelSmall.fontSize),
                    color = Color(0xFF333333),
                    modifier = Modifier
                        .clip(RoundedCornerShape(7.dp))
                        .background(Color(0xCCFFFFFF))
                        .padding(horizontal = 7.dp, vertical = 3.dp),
                )
                Spacer(Modifier.weight(1f))
                RoundButton(
                    icon = R.drawable.ic_gps,
                    label = "Mening joylashuvim",
                    onClick = onMyLocation,
                    size = 52.dp,
                    shape = RoundedCornerShape(18.dp),
                    tint = scheme.primary,
                    glass = glass,
                    content = if (locating) {
                        { CircularProgressIndicator(modifier = Modifier.size(22.dp), strokeWidth = 2.5.dp) }
                    } else {
                        null
                    },
                )
            }

            AddressSheet(
                glass = glass,
                note = note,
                onNoteChange = { note = it.take(MAX_NOTE_LENGTH) },
                outOfZone = outOfZone,
                onDone = { focusManager.clearFocus() },
                onConfirm = confirm,
                onMeasured = { sheetHeightPx = it },
            )
        }
    }
}

/** Xarita o'rtasidagi belgi: ustida yozuv, qizil bosh va ingichka oyoq. Xarita surilayotganda biroz ko'tariladi. */
@Composable
private fun MapPin(moving: Boolean, modifier: Modifier = Modifier) {
    val scheme = MaterialTheme.colorScheme
    val ink = Color(0xFF17130F)
    val lift by animateDpAsState(
        targetValue = if (moving) 10.dp else 0.dp,
        animationSpec = spring(dampingRatio = 0.5f, stiffness = 500f),
        label = "pin-lift",
    )
    Column(
        modifier = modifier.semantics { contentDescription = "Tanlangan joy" },
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Column(
            modifier = Modifier.offset(y = -lift),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                text = "Yetkazish shu yerga",
                style = MaterialTheme.typography.labelSmall.copy(letterSpacing = MaterialTheme.typography.bodySmall.letterSpacing),
                color = Color.White,
                maxLines = 1,
                modifier = Modifier
                    .shadow(6.dp, RoundedCornerShape(11.dp))
                    .clip(RoundedCornerShape(11.dp))
                    .background(ink)
                    .padding(horizontal = 11.dp, vertical = 7.dp),
            )
            Spacer(Modifier.height(6.dp))
            Box(
                modifier = Modifier
                    .size(PIN_HEAD)
                    .shadow(elevation = 8.dp, shape = CircleShape)
                    .clip(CircleShape)
                    .background(Color.White)
                    .padding(4.dp)
                    .clip(CircleShape)
                    .background(scheme.primary),
                contentAlignment = Alignment.Center,
            ) {
                Box(
                    modifier = Modifier
                        .size(12.dp)
                        .clip(CircleShape)
                        .background(Color.White),
                )
            }
            Box(
                modifier = Modifier
                    .size(width = 3.dp, height = PIN_STEM)
                    .clip(RoundedCornerShape(bottomStart = 2.dp, bottomEnd = 2.dp))
                    .background(ink),
            )
        }
        // Belgi ko'tarilganda ham aynan qaysi nuqta tanlanayotgani ko'rinib turadi
        Box(
            modifier = Modifier
                .offset(y = 3.dp)
                .size(width = 12.dp, height = 6.dp)
                .clip(RoundedCornerShape(50))
                .background(Color.Black.copy(alpha = 0.26f)),
        )
    }
}

/** Xarita ustidagi to'q shisha yozuv: odatda yo'riqnoma, muammo bo'lsa ogohlantirish. */
@Composable
private fun MapHint(
    glass: HazeState,
    warning: String?,
    actionLabel: String?,
    onAction: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val scheme = MaterialTheme.colorScheme
    GlassBox(
        glass = glass,
        modifier = modifier,
        shape = RoundedCornerShape(16.dp),
        tone = GlassTone.Dark,
        elevation = 8.dp,
    ) {
        AnimatedContent(
            targetState = warning,
            transitionSpec = { fadeIn(tween(220)) togetherWith fadeOut(tween(160)) },
            label = "map-hint",
        ) { message ->
            Column(modifier = Modifier.padding(horizontal = 14.dp, vertical = 12.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (message != null) {
                        Icon(
                            painter = painterResource(R.drawable.ic_info),
                            contentDescription = null,
                            tint = scheme.amber,
                            modifier = Modifier.size(16.dp),
                        )
                        Spacer(Modifier.width(8.dp))
                    }
                    Text(
                        text = message ?: "Xaritani surib, belgini yetkazish joyiga qo'ying",
                        style = MaterialTheme.typography.bodySmall,
                        color = Color.White,
                    )
                }
                if (message != null && actionLabel != null) {
                    Text(
                        text = actionLabel,
                        style = MaterialTheme.typography.labelMedium,
                        color = scheme.amber,
                        modifier = Modifier
                            .padding(top = 6.dp)
                            .clip(RoundedCornerShape(8.dp))
                            .clickable(role = Role.Button, onClick = onAction)
                            .padding(vertical = 4.dp),
                    )
                }
            }
        }
    }
}

/** Pastki shisha panel: sarlavha, mo'ljal maydoni va tasdiqlash tugmasi. */
@Composable
private fun AddressSheet(
    glass: HazeState,
    note: String,
    onNoteChange: (String) -> Unit,
    outOfZone: Boolean,
    onDone: () -> Unit,
    onConfirm: () -> Unit,
    onMeasured: (Int) -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    GlassBox(
        glass = glass,
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(topStart = SHEET_CORNER, topEnd = SHEET_CORNER),
        elevation = 20.dp,
    ) {
        Column(modifier = Modifier.navigationBarsPadding()) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .onSizeChanged { onMeasured(it.height) }
                    .padding(start = 16.dp, end = 16.dp, top = 10.dp, bottom = 14.dp),
            ) {
                Box(
                    modifier = Modifier
                        .align(Alignment.CenterHorizontally)
                        .size(width = 38.dp, height = 4.dp)
                        .clip(RoundedCornerShape(50))
                        .background(scheme.outline),
                )
                Spacer(Modifier.height(16.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconTile(
                        icon = R.drawable.ic_pin,
                        container = if (outOfZone) scheme.errorContainer else scheme.primaryContainer,
                    )
                    Spacer(Modifier.width(12.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text("Yetkazish manzili", style = MaterialTheme.typography.titleLarge)
                        Text(
                            text = if (outOfZone) "Yetkazish hududidan tashqarida" else "Xaritada belgilangan joy",
                            style = MaterialTheme.typography.bodySmall,
                            color = if (outOfZone) scheme.error else scheme.hint,
                            maxLines = 1,
                        )
                    }
                }
                Spacer(Modifier.height(16.dp))
                TextField(
                    value = note,
                    onValueChange = onNoteChange,
                    placeholder = { Text("Mo'ljal, uy, xonadon") },
                    leadingIcon = {
                        Icon(
                            painter = painterResource(R.drawable.ic_home),
                            contentDescription = null,
                            modifier = Modifier.size(20.dp),
                        )
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .fieldBorder(),
                    singleLine = true,
                    shape = RoundedCornerShape(18.dp),
                    colors = fieldColors(),
                    keyboardOptions = KeyboardOptions(
                        capitalization = KeyboardCapitalization.Sentences,
                        imeAction = ImeAction.Done,
                    ),
                    keyboardActions = KeyboardActions(onDone = { onDone() }),
                )
                Spacer(Modifier.height(14.dp))
                BigButton(
                    text = "Shu manzilga yetkazish",
                    onClick = onConfirm,
                    enabled = !outOfZone,
                )
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
    circle.setFillColor(AndroidColor.argb(22, 229, 67, 42))
    circle.setStrokeColor(AndroidColor.argb(150, 229, 67, 42))
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
