package uz.amora.app.ui.menu

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.LocalIndication
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.DragInteraction
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.grid.rememberLazyGridState
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
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
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.layout.layout
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import dev.chrisbanes.haze.HazeState
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import uz.amora.app.AppContainer
import uz.amora.app.R
import uz.amora.app.data.Menu
import uz.amora.app.data.Order
import uz.amora.app.data.Product
import uz.amora.app.data.Shop
import uz.amora.app.data.resolveImageUrl
import uz.amora.app.ui.components.AddButton
import uz.amora.app.ui.components.BigButton
import uz.amora.app.ui.components.BlurBehindEffect
import uz.amora.app.ui.components.GlassBox
import uz.amora.app.ui.components.GlassFade
import uz.amora.app.ui.components.GlassStrip
import uz.amora.app.ui.components.GlassTone
import uz.amora.app.ui.components.IconTile
import uz.amora.app.ui.components.LogoTile
import uz.amora.app.ui.components.MessageBox
import uz.amora.app.ui.components.OrderProgressBar
import uz.amora.app.ui.components.PriceText
import uz.amora.app.ui.components.ProductImage
import uz.amora.app.ui.components.QuantityStepper
import uz.amora.app.ui.components.RefreshBox
import uz.amora.app.ui.components.RoundButton
import uz.amora.app.ui.components.SectionCard
import uz.amora.app.ui.components.SkeletonBox
import uz.amora.app.ui.components.TabChip
import uz.amora.app.ui.components.fieldBorder
import uz.amora.app.ui.components.fieldColors
import uz.amora.app.ui.components.glassSource
import uz.amora.app.ui.components.pressScale
import uz.amora.app.ui.components.rememberGlassState
import uz.amora.app.ui.components.softShadow
import uz.amora.app.ui.components.statusIcon
import uz.amora.app.ui.theme.PriceStyle
import uz.amora.app.ui.theme.amber
import uz.amora.app.ui.theme.hint
import uz.amora.app.ui.theme.ink
import uz.amora.app.ui.theme.onInkMuted
import uz.amora.app.ui.theme.success
import uz.amora.app.util.formatNumber
import uz.amora.app.util.formatSum

private const val ACTIVE_ORDERS_REFRESH_MS = 15_000L

// Qidiruv maydoni menyu shunchadan katta bo'lsagina ko'rinadi: bir nechta taomda u ortiqcha
private const val SEARCH_MIN_PRODUCTS = 6

// Ro'yxat tepasida qotib turadigan bo'limlar qatorining balandligi
private val PINNED_CHIPS_HEIGHT = 52.dp

// Qotib turgan qator yuqori satrning "tumaniga" shuncha kirib turadi: ikkalasi bitta shishadek ko'rinadi
private val PINNED_CHIPS_OVERLAP = 18.dp

/** Menyudagi bitta bo'lim: kategoriya va uning taomlari. */
private data class MenuSection(val id: Int, val title: String, val products: List<Product>)

private fun buildSections(menu: Menu): List<MenuSection> {
    val byCategory = menu.products.groupBy { it.categoryId }
    val sections = ArrayList<MenuSection>()
    for (category in menu.categories) {
        val products = byCategory[category.id]
        if (!products.isNullOrEmpty()) sections.add(MenuSection(category.id, category.name, products))
    }
    val withoutCategory = byCategory[null]
    if (!withoutCategory.isNullOrEmpty()) {
        val title = if (sections.isEmpty()) "Menyu" else "Boshqa taomlar"
        sections.add(MenuSection(0, title, withoutCategory))
    }
    return sections
}

private fun searchProducts(menu: Menu, query: String): List<Product> {
    val needle = query.trim()
    return menu.products.filter {
        it.name.contains(needle, ignoreCase = true) || it.description.contains(needle, ignoreCase = true)
    }
}

/**
 * Bosh sahifa. Yuqorida kafe va ikki tugma (buyurtmalarim, profil), o'rtada menyu,
 * savatda taom bo'lsa pastda suzib turadigan shisha "Savat" paneli.
 */
@Composable
fun MenuScreen(
    container: AppContainer,
    onOpenCart: () -> Unit,
    onOpenOrders: () -> Unit,
    onOpenProfile: () -> Unit,
    onOpenOrder: (Int) -> Unit,
) {
    val vm: MenuViewModel = viewModel(
        factory = viewModelFactory { initializer { MenuViewModel(container) } },
    )
    val catalog by container.catalog.state.collectAsStateWithLifecycle()
    val cart by container.cart.items.collectAsStateWithLifecycle()
    val activeOrders by vm.activeOrders.collectAsStateWithLifecycle()
    val refreshing by vm.refreshing.collectAsStateWithLifecycle()
    val glass = rememberGlassState()

    // Ekran ko'rinib turganda menyu yangilanadi va faol buyurtmalar tekshirib turiladi
    val lifecycleOwner = LocalLifecycleOwner.current
    LaunchedEffect(lifecycleOwner) {
        lifecycleOwner.repeatOnLifecycle(Lifecycle.State.RESUMED) {
            vm.refreshCatalog()
            while (true) {
                vm.refreshActiveOrders()
                delay(ACTIVE_ORDERS_REFRESH_MS)
            }
        }
    }

    val menu = catalog.menu
    val shop = catalog.shop
    val productsById = remember(menu) { (menu?.products ?: emptyList()).associateBy { it.id } }
    val sections = remember(menu) { if (menu == null) emptyList() else buildSections(menu) }

    LaunchedEffect(menu) {
        if (menu != null) container.cart.retain(productsById.keys)
    }

    val cartCount = cart.values.sum()
    val cartTotal = cart.entries.fold(0) { sum, entry ->
        sum + (productsById[entry.key]?.price ?: 0) * entry.value
    }

    var selectedProductId by rememberSaveable { mutableStateOf<Int?>(null) }
    var query by rememberSaveable { mutableStateOf("") }

    Scaffold(
        modifier = Modifier.imePadding(),
        containerColor = MaterialTheme.colorScheme.background,
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        topBar = {
            HomeTopBar(
                glass = glass,
                shop = shop,
                hasActiveOrders = activeOrders.isNotEmpty(),
                onOpenOrders = onOpenOrders,
                onOpenProfile = onOpenProfile,
            )
        },
        bottomBar = {
            // Savat bo'sh bo'lsa ham shu joy tizim tugmalari balandligini egallab turadi
            Box(modifier = Modifier.navigationBarsPadding()) {
                AnimatedVisibility(
                    visible = cartCount > 0,
                    enter = slideInVertically(tween(320)) { it } + fadeIn(tween(320)),
                    exit = slideOutVertically(tween(240)) { it } + fadeOut(tween(240)),
                ) {
                    CartBar(glass = glass, count = cartCount, total = cartTotal, onClick = onOpenCart)
                }
            }
        },
    ) { padding ->
        val top = padding.calculateTopPadding()
        val bottom = padding.calculateBottomPadding()
        when {
            menu == null && catalog.loading -> MenuSkeleton(
                modifier = Modifier.glassSource(glass),
                top = top,
            )

            menu == null -> RefreshBox(
                refreshing = refreshing,
                onRefresh = { vm.pullToRefresh() },
                modifier = Modifier
                    .fillMaxSize()
                    .glassSource(glass),
                indicatorTop = top,
            ) {
                MessageBox(
                    icon = R.drawable.ic_refresh,
                    title = "Menyu yuklanmadi",
                    text = catalog.error,
                    actionLabel = "Qayta urinish",
                    onAction = { vm.retry() },
                    modifier = Modifier.padding(top = top, bottom = bottom),
                )
            }

            else -> MenuContent(
                glass = glass,
                shop = shop,
                menu = menu,
                sections = sections,
                query = query,
                onQueryChange = { query = it },
                cart = cart,
                activeOrders = activeOrders,
                baseUrl = container.baseUrl,
                top = top,
                bottom = bottom,
                refreshing = refreshing,
                onRefresh = { vm.pullToRefresh() },
                onAdd = { container.cart.add(it) },
                onRemove = { container.cart.remove(it) },
                onOpenProduct = { selectedProductId = it },
                onOpenOrder = onOpenOrder,
            )
        }
    }

    val selectedProduct = selectedProductId?.let { productsById[it] }
    if (selectedProduct != null) {
        ProductSheet(
            product = selectedProduct,
            imageUrl = resolveImageUrl(container.baseUrl, selectedProduct.imageUrl),
            quantity = cart[selectedProduct.id] ?: 0,
            onAdd = { container.cart.add(selectedProduct.id) },
            onRemove = { container.cart.remove(selectedProduct.id) },
            onDismiss = { selectedProductId = null },
        )
    }
}

private fun shopStatusLine(shop: Shop): String = when {
    !shop.isAcceptingOrders -> "Buyurtma olinmayapti"
    !shop.isOpen -> "Yopiq · ${shop.openTime}–${shop.closeTime}"
    shop.openTime == shop.closeTime -> "Ochiq · kecha-kunduz"
    else -> "Ochiq · ${shop.openTime}–${shop.closeTime}"
}

/** Yuqori satr: kafe nomi va holati, o'ngda "Buyurtmalarim" va "Profil" tugmalari. */
@Composable
private fun HomeTopBar(
    glass: HazeState,
    shop: Shop?,
    hasActiveOrders: Boolean,
    onOpenOrders: () -> Unit,
    onOpenProfile: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    val name = shop?.cafeName?.takeIf { it.isNotBlank() } ?: "Amora"
    Box {
        GlassStrip(glass = glass, modifier = Modifier.matchParentSize(), fade = GlassFade.Bottom)
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .statusBarsPadding()
                .padding(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            LogoTile(letter = name.take(1).uppercase())
            Spacer(Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = name,
                    style = MaterialTheme.typography.titleLarge,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                if (shop != null) {
                    val open = shop.isOpen && shop.isAcceptingOrders
                    val color = if (open) scheme.success else scheme.hint
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            modifier = Modifier
                                .size(6.dp)
                                .clip(CircleShape)
                                .background(color),
                        )
                        Spacer(Modifier.width(6.dp))
                        Text(
                            text = shopStatusLine(shop),
                            style = MaterialTheme.typography.labelSmall.copy(letterSpacing = 0.sp),
                            color = color,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
            }
            Spacer(Modifier.width(8.dp))
            Box {
                RoundButton(icon = R.drawable.ic_receipt, label = "Buyurtmalarim", onClick = onOpenOrders)
                if (hasActiveOrders) {
                    // Faol buyurtma borligini bildiruvchi nuqta
                    Box(
                        modifier = Modifier
                            .align(Alignment.TopEnd)
                            .offset(x = (-2).dp, y = 2.dp)
                            .size(10.dp)
                            .clip(CircleShape)
                            .background(scheme.background)
                            .padding(2.dp)
                            .clip(CircleShape)
                            .background(scheme.primary),
                    )
                }
            }
            Spacer(Modifier.width(8.dp))
            RoundButton(icon = R.drawable.ic_user, label = "Profil", onClick = onOpenProfile)
        }
    }
}

@Composable
private fun MenuContent(
    glass: HazeState,
    shop: Shop?,
    menu: Menu,
    sections: List<MenuSection>,
    query: String,
    onQueryChange: (String) -> Unit,
    cart: Map<Int, Int>,
    activeOrders: List<Order>,
    baseUrl: String,
    top: Dp,
    bottom: Dp,
    refreshing: Boolean,
    onRefresh: () -> Unit,
    onAdd: (Int) -> Unit,
    onRemove: (Int) -> Unit,
    onOpenProduct: (Int) -> Unit,
    onOpenOrder: (Int) -> Unit,
) {
    val gridState = rememberLazyGridState()
    val scope = rememberCoroutineScope()
    val pinnedChipsPx = with(LocalDensity.current) { PINNED_CHIPS_HEIGHT.roundToPx() }

    val searching = query.isNotBlank()
    val showSearch = menu.products.size >= SEARCH_MIN_PRODUCTS
    val closed = shop != null && !shop.isOpen
    val hasOrders = activeOrders.isNotEmpty()

    // Qidiruv paytida bo'limlar o'rniga bitta natijalar ro'yxati ko'rsatiladi
    val shownSections = remember(sections, menu, query) {
        if (query.isBlank()) {
            sections
        } else {
            val found = searchProducts(menu, query)
            if (found.isEmpty()) emptyList() else listOf(MenuSection(-1, "Qidiruv natijalari", found))
        }
    }
    val showChips = !searching && sections.size > 1

    // Ro'yxat boshidagi bloklar. Ulardan keyin har bo'lim: sarlavha + taomlar.
    val leading = remember(showSearch, hasOrders, closed, showChips) {
        buildList {
            add("hero")
            if (hasOrders) add("orders")
            if (closed) add("closed")
            if (showSearch) add("search")
            if (showChips) add("chips")
        }
    }
    val chipsIndex = leading.indexOf("chips")
    val headerIndexes = remember(shownSections, leading) {
        val indexes = ArrayList<Int>(shownSections.size)
        var next = leading.size
        for (section in shownSections) {
            indexes.add(next)
            next += 1 + section.products.size
        }
        indexes
    }
    // Ro'yxatdagi element joylashuvi yuqori satr ostidagi chiziqdan hisoblanadi (0 = satr osti)
    val scrolledSection by remember(headerIndexes, pinnedChipsPx) {
        derivedStateOf {
            if (!gridState.canScrollForward && gridState.canScrollBackward) {
                // Ro'yxat oxiriga yetdi: oxirgi bo'lim qisqa bo'lsa ham u belgilanadi
                headerIndexes.lastIndex.coerceAtLeast(0)
            } else {
                // Qotib turgan bo'limlar qatori ostidan ko'rinib turgan birinchi element qaysi bo'limda?
                val first = gridState.layoutInfo.visibleItemsInfo
                    .firstOrNull { it.offset.y + it.size.height > pinnedChipsPx }
                val index = first?.index ?: gridState.firstVisibleItemIndex
                headerIndexes.indexOfLast { it <= index }.coerceAtLeast(0)
            }
        }
    }
    // Bo'lim tugmasi bosilganda aynan o'sha bo'lim belgilanadi (ro'yxat u yergacha surila olmasa ham).
    // Mijoz ro'yxatni o'zi sura boshlashi bilan yana surilish joyiga qarab aniqlanadi.
    var tappedSection by remember(headerIndexes) { mutableStateOf<Int?>(null) }
    LaunchedEffect(gridState, headerIndexes) {
        gridState.interactionSource.interactions.collect { interaction ->
            if (interaction is DragInteraction.Start) tappedSection = null
        }
    }
    val currentSection = tappedSection ?: scrolledSection
    val chipsPinned by remember(chipsIndex) {
        derivedStateOf {
            if (chipsIndex < 0) {
                false
            } else {
                val item = gridState.layoutInfo.visibleItemsInfo.firstOrNull { it.index == chipsIndex }
                if (item != null) item.offset.y < 0 else gridState.firstVisibleItemIndex > chipsIndex
            }
        }
    }
    val selectSection: (Int) -> Unit = { index ->
        val target = headerIndexes.getOrNull(index)
        if (target != null) {
            tappedSection = index
            scope.launch { gridState.animateScrollToItem(target, scrollOffset = -pinnedChipsPx) }
        }
    }

    Box(modifier = Modifier.fillMaxSize()) {
        RefreshBox(
            refreshing = refreshing,
            onRefresh = onRefresh,
            modifier = Modifier
                .fillMaxSize()
                .glassSource(glass),
            indicatorTop = top,
        ) {
            LazyVerticalGrid(
                columns = GridCells.Adaptive(minSize = 156.dp),
                state = gridState,
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = top, bottom = bottom + 20.dp),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                for (block in leading) {
                    item(key = block, span = { GridItemSpan(maxLineSpan) }, contentType = block) {
                        when (block) {
                            "hero" -> ShopHero(shop)
                            "search" -> SearchField(query = query, onChange = onQueryChange)
                            "orders" -> ActiveOrders(activeOrders, onOpenOrder)
                            "closed" -> if (shop != null) ClosedNotice(shop)
                            "chips" -> CategoryChips(
                                sections = sections,
                                selectedIndex = currentSection,
                                onSelect = selectSection,
                                modifier = Modifier.bleed(16.dp),
                            )
                        }
                    }
                }

                if (shownSections.isEmpty()) {
                    item(key = "empty", span = { GridItemSpan(maxLineSpan) }, contentType = "empty") {
                        if (searching) {
                            EmptyHint(
                                icon = R.drawable.ic_search,
                                title = "Hech narsa topilmadi",
                                text = "Boshqa so'z bilan qidirib ko'ring",
                            )
                        } else {
                            EmptyHint(
                                icon = R.drawable.ic_info,
                                title = "Menyu hozircha bo'sh",
                                text = "Taomlar tez orada qo'shiladi",
                            )
                        }
                    }
                }

                for (section in shownSections) {
                    item(
                        key = "section-${section.id}",
                        span = { GridItemSpan(maxLineSpan) },
                        contentType = "header",
                    ) {
                        SectionHeader(title = section.title, count = section.products.size)
                    }
                    items(
                        items = section.products,
                        key = { it.id },
                        contentType = { "product" },
                    ) { product ->
                        ProductCard(
                            product = product,
                            imageUrl = resolveImageUrl(baseUrl, product.imageUrl),
                            quantity = cart[product.id] ?: 0,
                            onAdd = { onAdd(product.id) },
                            onRemove = { onRemove(product.id) },
                            onClick = { onOpenProduct(product.id) },
                            modifier = Modifier.animateItem(),
                        )
                    }
                }
            }
        }

        // Bo'limlar qatori ro'yxat bilan birga surilib ketgach, yuqori satr ostida shisha bo'lib qotadi
        AnimatedVisibility(
            visible = chipsPinned,
            modifier = Modifier
                .align(Alignment.TopCenter)
                .padding(top = (top - PINNED_CHIPS_OVERLAP).coerceAtLeast(0.dp)),
            enter = fadeIn(),
            exit = fadeOut(),
        ) {
            Box {
                GlassStrip(glass = glass, modifier = Modifier.matchParentSize(), fade = GlassFade.Bottom)
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = PINNED_CHIPS_OVERLAP, bottom = 14.dp)
                        .height(PINNED_CHIPS_HEIGHT),
                    contentAlignment = Alignment.CenterStart,
                ) {
                    CategoryChips(sections = sections, selectedIndex = currentSection, onSelect = selectSection)
                }
            }
        }
    }
}

/** Ro'yxat ichidagi blokni ekran chetigacha cho'zadi (ro'yxatning yon bo'shlig'ini bosib o'tadi). */
private fun Modifier.bleed(horizontal: Dp): Modifier = layout { measurable, constraints ->
    val extra = (horizontal * 2).roundToPx()
    val placeable = measurable.measure(constraints.copy(maxWidth = constraints.maxWidth + extra))
    layout(placeable.width - extra, placeable.height) {
        placeable.place(-extra / 2, 0)
    }
}

/** Banner sarlavhasi va izohi: yetkazish shartlari serverdan olinadi. */
private fun heroLines(shop: Shop?): Pair<String, String> {
    val warm = "Issiq holda, eshigingizgacha"
    if (shop == null) return "Mazali taomlar\nuyingizgacha" to warm
    if (shop.deliveryFee <= 0) return "Yetkazish\nbepul" to warm
    val freeFrom = shop.freeDeliveryFrom
    val sub = if (freeFrom != null) "${formatSum(freeFrom)}dan yetkazish bepul" else warm
    return "Yetkazish\n${formatSum(shop.deliveryFee)}" to sub
}

/** Ko'mir rangli banner: kafe nomi, yetkazish sharti va o'ngda pitsa rasmi. */
@Composable
private fun ShopHero(shop: Shop?) {
    val scheme = MaterialTheme.colorScheme
    val name = shop?.cafeName?.takeIf { it.isNotBlank() } ?: "Amora"
    val (title, sub) = heroLines(shop)
    val shape = RoundedCornerShape(28.dp)
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(154.dp)
            .softShadow(shape, elevation = 14.dp, alpha = 0.22f)
            .clip(shape)
            .background(scheme.ink),
    ) {
        PizzaArt(modifier = Modifier.matchParentSize())
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(start = 18.dp, top = 18.dp, bottom = 14.dp, end = 104.dp),
        ) {
            Text(
                text = name.uppercase(),
                style = MaterialTheme.typography.labelSmall.copy(letterSpacing = 1.4.sp, fontSize = 11.sp),
                color = Color(0xFFF7B8A8),
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Spacer(Modifier.height(6.dp))
            Text(
                text = title,
                style = MaterialTheme.typography.headlineLarge.copy(fontSize = 29.sp, lineHeight = 30.sp),
                color = Color.White,
                maxLines = 2,
                modifier = Modifier.weight(1f),
            )
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    painter = painterResource(R.drawable.ic_bolt),
                    contentDescription = null,
                    tint = scheme.amber,
                    modifier = Modifier.size(14.dp),
                )
                Spacer(Modifier.width(6.dp))
                Text(
                    text = sub,
                    style = MaterialTheme.typography.bodySmall,
                    color = scheme.onInkMuted,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

// Pitsa ustidagi kolbasa va rayhon joylari (markazdan, radius ulushida)
private val PIZZA_SPOTS = listOf(
    -0.52f to -0.34f,
    -0.08f to -0.58f,
    -0.60f to 0.16f,
    -0.14f to -0.06f,
    -0.34f to 0.52f,
    0.12f to 0.40f,
    0.28f to -0.26f,
)
private val PIZZA_LEAVES = listOf(
    Triple(-0.34f, -0.02f, 30f),
    Triple(-0.02f, -0.30f, -40f),
    Triple(-0.12f, 0.24f, 70f),
    Triple(-0.50f, -0.10f, -20f),
)

/** Bannerning o'ng chetidan yarmi ko'rinib turadigan pitsa (oddiy shakllardan chizilgan). */
@Composable
private fun PizzaArt(modifier: Modifier = Modifier) {
    Canvas(modifier = modifier) {
        val radius = size.height * 0.56f
        val center = Offset(size.width - radius * 0.42f, size.height * 0.48f)
        drawCircle(Color(0xFFD08A3C), radius, center)
        drawCircle(Color(0xFFEFB45F), radius * 0.955f, center)
        drawCircle(Color(0xFFE5432A), radius * 0.83f, center)
        drawCircle(Color(0xFFF7D98B), radius * 0.79f, center)
        for ((dx, dy) in PIZZA_SPOTS) {
            val spot = Offset(center.x + dx * radius, center.y + dy * radius)
            drawCircle(Color(0xFFC7321C), radius * 0.135f, spot)
            drawCircle(Color(0xFFE5432A), radius * 0.105f, spot)
        }
        for ((dx, dy, angle) in PIZZA_LEAVES) {
            val leaf = Offset(center.x + dx * radius, center.y + dy * radius)
            val leafSize = Size(radius * 0.17f, radius * 0.085f)
            rotate(angle, leaf) {
                drawOval(
                    color = Color(0xFF1E9E61),
                    topLeft = Offset(leaf.x - leafSize.width / 2, leaf.y - leafSize.height / 2),
                    size = leafSize,
                )
            }
        }
    }
}

@Composable
private fun SearchField(query: String, onChange: (String) -> Unit) {
    val focusManager = LocalFocusManager.current
    val clearButton: (@Composable () -> Unit)? = if (query.isEmpty()) {
        null
    } else {
        {
            IconButton(onClick = { onChange("") }) {
                Icon(
                    painter = painterResource(R.drawable.ic_close),
                    contentDescription = "Qidiruvni tozalash",
                    modifier = Modifier.size(20.dp),
                )
            }
        }
    }
    TextField(
        value = query,
        onValueChange = { onChange(it.take(40)) },
        modifier = Modifier
            .fillMaxWidth()
            .fieldBorder(),
        placeholder = { Text("Taom qidirish") },
        leadingIcon = {
            Icon(
                painter = painterResource(R.drawable.ic_search),
                contentDescription = null,
                modifier = Modifier.size(20.dp),
            )
        },
        trailingIcon = clearButton,
        singleLine = true,
        shape = RoundedCornerShape(18.dp),
        colors = fieldColors(),
        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
        keyboardActions = KeyboardActions(onSearch = { focusManager.clearFocus() }),
    )
}

/** Faol buyurtmalar: bosilsa, buyurtma holati ekrani ochiladi. */
@Composable
private fun ActiveOrders(orders: List<Order>, onOpenOrder: (Int) -> Unit) {
    val scheme = MaterialTheme.colorScheme
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        for (order in orders) {
            SectionCard(onClick = { onOpenOrder(order.id) }, padding = 14.dp) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconTile(icon = statusIcon(order.status))
                    Spacer(Modifier.width(12.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = "Buyurtma №${order.id}",
                            style = MaterialTheme.typography.bodySmall,
                            color = scheme.hint,
                        )
                        Text(
                            text = order.statusLabel,
                            style = MaterialTheme.typography.titleMedium,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                    Icon(
                        painter = painterResource(R.drawable.ic_chevron),
                        contentDescription = null,
                        tint = scheme.hint,
                        modifier = Modifier.size(20.dp),
                    )
                }
                Spacer(Modifier.height(12.dp))
                OrderProgressBar(status = order.status)
            }
        }
    }
}

@Composable
private fun ClosedNotice(shop: Shop) {
    val scheme = MaterialTheme.colorScheme
    Surface(
        shape = MaterialTheme.shapes.large,
        color = scheme.errorContainer,
        contentColor = scheme.onErrorContainer,
    ) {
        Text(
            text = if (shop.isAcceptingOrders) {
                "Kafe hozir yopiq. Ish vaqti: ${shop.openTime} dan ${shop.closeTime} gacha. " +
                    "Menyuni ko'rishingiz mumkin, buyurtma esa ish vaqtida qabul qilinadi."
            } else {
                "Kafe hozir buyurtma qabul qilmayapti. Birozdan keyin qayta urinib ko'ring."
            },
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 14.dp),
        )
    }
}

@Composable
private fun CategoryChips(
    sections: List<MenuSection>,
    selectedIndex: Int,
    onSelect: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    val listState = rememberLazyListState()
    // Tanlangan bo'lim tugmasi har doim ko'rinib turadi
    LaunchedEffect(selectedIndex) {
        listState.animateScrollToItem(selectedIndex)
    }
    LazyRow(
        state = listState,
        modifier = modifier.fillMaxWidth(),
        contentPadding = PaddingValues(horizontal = 16.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        itemsIndexed(sections, key = { _, section -> section.id }) { index, section ->
            TabChip(text = section.title, selected = index == selectedIndex, onClick = { onSelect(index) })
        }
    }
}

@Composable
private fun SectionHeader(title: String, count: Int) {
    Row(
        modifier = Modifier.padding(start = 4.dp, end = 4.dp, top = 12.dp, bottom = 2.dp),
        verticalAlignment = Alignment.Bottom,
    ) {
        Text(
            text = title,
            style = MaterialTheme.typography.headlineSmall,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.weight(1f),
        )
        Text(
            text = "$count ta taom",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.hint,
            modifier = Modifier.padding(bottom = 4.dp),
        )
    }
}

/** Ro'yxat ichidagi bo'sh holat (masalan, qidiruvda hech narsa topilmadi). */
@Composable
private fun EmptyHint(icon: Int, title: String, text: String) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 40.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        IconTile(icon = icon, size = 80.dp, iconSize = 34.dp)
        Spacer(Modifier.height(16.dp))
        Text(title, style = MaterialTheme.typography.titleLarge, textAlign = TextAlign.Center)
        Spacer(Modifier.height(4.dp))
        Text(
            text = text,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
    }
}

/** Taom kartochkasi: rasm, nom, qisqa tavsif, pastda narx va "+" (savatda bo'lsa son tanlagich). */
@Composable
private fun ProductCard(
    product: Product,
    imageUrl: String?,
    quantity: Int,
    onAdd: () -> Unit,
    onRemove: () -> Unit,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val scheme = MaterialTheme.colorScheme
    val shape = MaterialTheme.shapes.large
    val source = remember { MutableInteractionSource() }
    // Nom ikki qatorga sig'sa, tavsif ko'rsatilmaydi: hamma kartochka bir xil balandlikda qoladi
    var nameLines by remember(product.name) { mutableIntStateOf(1) }
    val textBlockHeight = with(LocalDensity.current) { 42.sp.toDp() }
    Surface(
        onClick = onClick,
        modifier = modifier
            .pressScale(source, 0.98f)
            .softShadow(shape),
        shape = shape,
        color = scheme.surface,
        interactionSource = source,
    ) {
        Column(modifier = Modifier.padding(start = 6.dp, end = 6.dp, top = 6.dp, bottom = 10.dp)) {
            Box {
                ProductImage(
                    url = imageUrl,
                    modifier = Modifier
                        .fillMaxWidth()
                        .aspectRatio(1.2f)
                        .clip(RoundedCornerShape(19.dp))
                        .alpha(if (product.isAvailable) 1f else 0.5f),
                    seed = product.id,
                )
                if (!product.isAvailable) {
                    Text(
                        text = "Tugagan",
                        style = MaterialTheme.typography.labelSmall.copy(letterSpacing = 0.sp),
                        color = scheme.onSurface,
                        modifier = Modifier
                            .align(Alignment.TopStart)
                            .padding(8.dp)
                            .clip(RoundedCornerShape(9.dp))
                            .background(scheme.surface)
                            .padding(horizontal = 9.dp, vertical = 5.dp),
                    )
                }
            }
            Column(modifier = Modifier.padding(start = 6.dp, end = 6.dp, top = 10.dp)) {
                Column(modifier = Modifier.height(textBlockHeight)) {
                    Text(
                        text = product.name,
                        style = MaterialTheme.typography.titleMedium.copy(lineHeight = 20.sp),
                        color = if (product.isAvailable) scheme.onSurface else scheme.onSurfaceVariant,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                        onTextLayout = { nameLines = it.lineCount },
                        modifier = Modifier.testTag("product-name"),
                    )
                    if (nameLines < 2 && product.description.isNotBlank()) {
                        Text(
                            text = product.description,
                            style = MaterialTheme.typography.bodySmall,
                            color = scheme.hint,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                            modifier = Modifier.padding(top = 2.dp),
                        )
                    }
                }
                Spacer(Modifier.height(8.dp))
                Row(
                    modifier = Modifier.height(38.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    if (!product.isAvailable) {
                        Text(
                            text = "Hozircha yo'q",
                            style = MaterialTheme.typography.labelMedium,
                            color = scheme.hint,
                        )
                    } else {
                        // Savatga qo'shilgach "so'm" yozuvi yashiriladi: tor ekranda son tanlagichga joy qoladi
                        PriceText(
                            amount = product.price,
                            unit = quantity == 0,
                            modifier = Modifier.weight(1f),
                        )
                        if (quantity == 0) {
                            AddButton(onClick = onAdd)
                        } else {
                            QuantityStepper(quantity = quantity, onMinus = onRemove, onPlus = onAdd)
                        }
                    }
                }
            }
        }
    }
}

/** Pastda suzib turadigan to'q shisha "Savat" paneli: savatda taom bo'lsa ko'rinadi. */
@Composable
private fun CartBar(glass: HazeState, count: Int, total: Int, onClick: () -> Unit) {
    val scheme = MaterialTheme.colorScheme
    val source = remember { MutableInteractionSource() }
    val ink = Color(0xFF17130F)
    GlassBox(
        glass = glass,
        modifier = Modifier
            .padding(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 12.dp)
            .fillMaxWidth()
            .height(64.dp)
            .pressScale(source),
        shape = RoundedCornerShape(22.dp),
        tone = GlassTone.Dark,
        elevation = 16.dp,
    ) {
        Row(
            modifier = Modifier
                .fillMaxSize()
                .clickable(
                    interactionSource = source,
                    indication = LocalIndication.current,
                    role = Role.Button,
                    onClick = onClick,
                )
                .padding(horizontal = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box {
                Box(
                    modifier = Modifier
                        .size(44.dp)
                        .clip(RoundedCornerShape(15.dp))
                        .background(scheme.primary),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        painter = painterResource(R.drawable.ic_bag),
                        contentDescription = null,
                        tint = Color.White,
                        modifier = Modifier.size(22.dp),
                    )
                }
                Box(
                    modifier = Modifier
                        .align(Alignment.TopEnd)
                        .offset(x = 5.dp, y = (-5).dp)
                        .defaultMinSize(minWidth = 19.dp, minHeight = 19.dp)
                        .clip(CircleShape)
                        .background(Color.White)
                        .padding(horizontal = 5.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        text = count.toString(),
                        style = MaterialTheme.typography.labelSmall.copy(letterSpacing = 0.sp, fontSize = 11.sp),
                        color = ink,
                        maxLines = 1,
                    )
                }
            }
            Spacer(Modifier.width(14.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "Savat",
                    style = MaterialTheme.typography.bodySmall,
                    color = scheme.onInkMuted,
                )
                Text(
                    text = formatSum(total),
                    style = PriceStyle.copy(fontSize = 17.sp),
                    color = Color.White,
                    maxLines = 1,
                )
            }
            Row(
                modifier = Modifier
                    .height(40.dp)
                    .clip(RoundedCornerShape(13.dp))
                    .background(Color.White)
                    .padding(start = 14.dp, end = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(text = "Savatga", style = MaterialTheme.typography.labelLarge, color = ink, maxLines = 1)
                Spacer(Modifier.width(2.dp))
                Icon(
                    painter = painterResource(R.drawable.ic_chevron),
                    contentDescription = null,
                    tint = ink,
                    modifier = Modifier.size(18.dp),
                )
            }
        }
    }
}

/** Taom haqida to'liq ma'lumot: katta rasm, tavsif va savatga qo'shish. */
@Composable
private fun ProductSheet(
    product: Product,
    imageUrl: String?,
    quantity: Int,
    onAdd: () -> Unit,
    onRemove: () -> Unit,
    onDismiss: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = scheme.surface,
        shape = RoundedCornerShape(topStart = 32.dp, topEnd = 32.dp),
    ) {
        BlurBehindEffect()
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
                .padding(start = 16.dp, end = 16.dp, bottom = 20.dp),
        ) {
            ProductImage(
                url = imageUrl,
                modifier = Modifier
                    .fillMaxWidth()
                    .aspectRatio(1.3f)
                    .clip(RoundedCornerShape(24.dp)),
                iconSize = 76.dp,
                seed = product.id,
            )
            Spacer(Modifier.height(18.dp))
            Text(
                text = product.name,
                style = MaterialTheme.typography.headlineMedium,
                modifier = Modifier.padding(horizontal = 4.dp),
            )
            if (product.description.isNotBlank()) {
                Spacer(Modifier.height(8.dp))
                Text(
                    text = product.description,
                    style = MaterialTheme.typography.bodyLarge,
                    color = scheme.onSurfaceVariant,
                    modifier = Modifier.padding(horizontal = 4.dp),
                )
            }
            Spacer(Modifier.height(22.dp))
            when {
                !product.isAvailable -> BigButton(text = "Hozircha yo'q", onClick = {}, enabled = false)

                quantity == 0 -> BigButton(
                    text = "Savatga qo'shish",
                    onClick = onAdd,
                    trailing = formatSum(product.price),
                )

                else -> QuantityStepper(
                    quantity = quantity,
                    onMinus = onRemove,
                    onPlus = onAdd,
                    modifier = Modifier.fillMaxWidth(),
                    height = 58.dp,
                    corner = 20.dp,
                    buttonWidth = 60.dp,
                    label = "$quantity ta · ${formatNumber(product.price * quantity)} so'm",
                    expand = true,
                )
            }
        }
    }
}

/** Menyu birinchi marta yuklanayotganda ko'rinadigan "skelet": haqiqiy sahifa shaklini takrorlaydi. */
@Composable
private fun MenuSkeleton(modifier: Modifier = Modifier, top: Dp) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(start = 16.dp, end = 16.dp, top = top),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        SkeletonBox(
            modifier = Modifier
                .fillMaxWidth()
                .height(154.dp),
            shape = RoundedCornerShape(28.dp),
        )
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(start = 4.dp, end = 4.dp, top = 12.dp, bottom = 2.dp),
            verticalAlignment = Alignment.Bottom,
        ) {
            SkeletonBox(modifier = Modifier.size(width = 110.dp, height = 26.dp))
            Spacer(Modifier.weight(1f))
            SkeletonBox(modifier = Modifier.size(width = 64.dp, height = 14.dp))
        }
        repeat(2) {
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                repeat(2) {
                    ProductCardSkeleton(modifier = Modifier.weight(1f))
                }
            }
        }
    }
}

@Composable
private fun ProductCardSkeleton(modifier: Modifier = Modifier) {
    val scheme = MaterialTheme.colorScheme
    val shape = MaterialTheme.shapes.large
    Column(
        modifier = modifier
            .softShadow(shape)
            .clip(shape)
            .background(scheme.surface)
            .padding(start = 6.dp, end = 6.dp, top = 6.dp, bottom = 10.dp),
    ) {
        SkeletonBox(
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(1.2f),
            shape = RoundedCornerShape(19.dp),
        )
        Column(modifier = Modifier.padding(start = 6.dp, end = 6.dp, top = 12.dp)) {
            SkeletonBox(modifier = Modifier.size(width = 84.dp, height = 16.dp))
            Spacer(Modifier.height(8.dp))
            SkeletonBox(modifier = Modifier.size(width = 112.dp, height = 12.dp))
            Spacer(Modifier.height(12.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                SkeletonBox(modifier = Modifier.size(width = 72.dp, height = 18.dp))
                Spacer(Modifier.weight(1f))
                SkeletonBox(modifier = Modifier.size(38.dp))
            }
        }
    }
}
