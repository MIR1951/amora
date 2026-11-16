package uz.amora.app.ui.menu

import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.Phone
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
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
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.layout
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import uz.amora.app.AppContainer
import uz.amora.app.data.Address
import uz.amora.app.data.Menu
import uz.amora.app.data.Order
import uz.amora.app.data.Product
import uz.amora.app.data.Shop
import uz.amora.app.data.resolveImageUrl
import uz.amora.app.ui.components.BigButton
import uz.amora.app.ui.components.CircleIconButton
import uz.amora.app.ui.components.IconBadge
import uz.amora.app.ui.components.MessageBox
import uz.amora.app.ui.components.OrderProgressBar
import uz.amora.app.ui.components.OrderStatusIcon
import uz.amora.app.ui.components.PriceAddButton
import uz.amora.app.ui.components.ProductImage
import uz.amora.app.ui.components.QuantityStepper
import uz.amora.app.ui.components.SkeletonBox
import uz.amora.app.ui.components.fieldColors
import uz.amora.app.ui.profile.dialPhone
import uz.amora.app.ui.theme.brandGradient
import uz.amora.app.util.formatSum

private const val ACTIVE_ORDERS_REFRESH_MS = 15_000L

// Qidiruv maydoni menyu shunchadan katta bo'lsagina ko'rinadi: bir nechta taomda u ortiqcha
private const val SEARCH_MIN_PRODUCTS = 6

// Ro'yxat tepasida qotib turadigan bo'limlar qatorining balandligi
private val PINNED_CHIPS_HEIGHT = 56.dp

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

@Composable
fun MenuScreen(
    container: AppContainer,
    onOpenCart: () -> Unit,
    onPickAddress: () -> Unit,
    onOpenOrder: (Int) -> Unit,
) {
    val vm: MenuViewModel = viewModel(
        factory = viewModelFactory { initializer { MenuViewModel(container) } },
    )
    val catalog by container.catalog.state.collectAsStateWithLifecycle()
    val cart by container.cart.items.collectAsStateWithLifecycle()
    val address by container.session.address.collectAsStateWithLifecycle()
    val activeOrders by vm.activeOrders.collectAsStateWithLifecycle()
    val refreshing by vm.refreshing.collectAsStateWithLifecycle()
    val context = LocalContext.current

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
        topBar = {
            HomeTopBar(
                address = address,
                cafePhone = shop?.phone,
                onPickAddress = onPickAddress,
                onCall = { dialPhone(context, it) },
            )
        },
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            PullToRefreshBox(
                isRefreshing = refreshing,
                onRefresh = { vm.pullToRefresh() },
                modifier = Modifier.fillMaxSize(),
            ) {
                when {
                    menu == null && catalog.loading -> MenuSkeleton()

                    menu == null -> MessageBox(
                        icon = Icons.Default.Refresh,
                        title = "Menyu yuklanmadi",
                        text = catalog.error,
                        actionLabel = "Qayta urinish",
                        onAction = { vm.retry() },
                    )

                    else -> MenuContent(
                        shop = shop,
                        menu = menu,
                        sections = sections,
                        query = query,
                        onQueryChange = { query = it },
                        cart = cart,
                        activeOrders = activeOrders,
                        baseUrl = container.baseUrl,
                        bottomSpace = if (cartCount > 0) 100.dp else 24.dp,
                        onAdd = { container.cart.add(it) },
                        onRemove = { container.cart.remove(it) },
                        onOpenProduct = { selectedProductId = it },
                        onOpenOrder = onOpenOrder,
                    )
                }
            }

            androidx.compose.animation.AnimatedVisibility(
                visible = cartCount > 0,
                modifier = Modifier.align(Alignment.BottomCenter),
                enter = slideInVertically { it } + fadeIn(),
                exit = slideOutVertically { it } + fadeOut(),
            ) {
                CartBar(count = cartCount, total = cartTotal, onClick = onOpenCart)
            }
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

/** Yuqori satr: yetkazish manzili (bosilsa xarita ochiladi) va kafega qo'ng'iroq tugmasi. */
@Composable
private fun HomeTopBar(
    address: Address?,
    cafePhone: String?,
    onPickAddress: () -> Unit,
    onCall: (String) -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(scheme.background)
            .statusBarsPadding()
            .padding(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Row(
            modifier = Modifier
                .weight(1f)
                .clip(RoundedCornerShape(16.dp))
                .clickable(onClickLabel = "Manzilni o'zgartirish", onClick = onPickAddress)
                .padding(vertical = 2.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconBadge(size = 44.dp) {
                Icon(
                    imageVector = Icons.Default.LocationOn,
                    contentDescription = null,
                    tint = scheme.primary,
                    modifier = Modifier.size(22.dp),
                )
            }
            Spacer(Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "Yetkazish manzili",
                    style = MaterialTheme.typography.labelMedium,
                    color = scheme.onSurfaceVariant,
                )
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = when {
                            address == null -> "Manzilni belgilang"
                            address.note.isBlank() -> "Xaritada belgilangan joy"
                            else -> address.note
                        },
                        style = MaterialTheme.typography.titleMedium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f, fill = false),
                    )
                    Icon(
                        imageVector = Icons.Default.KeyboardArrowDown,
                        contentDescription = null,
                        modifier = Modifier.size(20.dp),
                    )
                }
            }
        }
        if (!cafePhone.isNullOrBlank()) {
            Spacer(Modifier.width(12.dp))
            CircleIconButton(
                icon = Icons.Default.Phone,
                label = "Kafega qo'ng'iroq qilish",
                onClick = { onCall(cafePhone) },
            )
        }
    }
}

private fun shopStatusLine(shop: Shop): String = when {
    !shop.isAcceptingOrders -> "Hozir buyurtma qabul qilinmayapti"
    !shop.isOpen -> "Yopiq · ish vaqti ${shop.openTime}–${shop.closeTime}"
    shop.openTime == shop.closeTime -> "Ochiq · kecha-kunduz"
    else -> "Ochiq · ${shop.openTime}–${shop.closeTime}"
}

/** Kafe kartochkasidagi qisqa yozuvlar: yetkazish narxi, bepul yetkazish chegarasi, eng kam buyurtma. */
private fun deliveryFacts(shop: Shop): List<String> {
    val facts = ArrayList<String>()
    if (shop.deliveryFee <= 0) {
        facts.add("Yetkazish bepul")
    } else {
        facts.add("Yetkazish ${formatSum(shop.deliveryFee)}")
        val freeFrom = shop.freeDeliveryFrom
        if (freeFrom != null) facts.add("${formatSum(freeFrom)}dan bepul")
    }
    if (shop.minOrderAmount > 0) facts.add("Eng kam buyurtma ${formatSum(shop.minOrderAmount)}")
    return facts
}

@Composable
private fun MenuContent(
    shop: Shop?,
    menu: Menu,
    sections: List<MenuSection>,
    query: String,
    onQueryChange: (String) -> Unit,
    cart: Map<Int, Int>,
    activeOrders: List<Order>,
    baseUrl: String,
    bottomSpace: Dp,
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
            if (showSearch) add("search")
            if (hasOrders) add("orders")
            if (closed) add("closed")
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
    val currentSection by remember(headerIndexes, pinnedChipsPx) {
        derivedStateOf {
            // Qotib turgan bo'limlar qatori ostidan ko'rinib turgan birinchi element qaysi bo'limda?
            val info = gridState.layoutInfo
            val edge = info.viewportStartOffset + pinnedChipsPx
            val first = info.visibleItemsInfo.firstOrNull { it.offset.y + it.size.height > edge }
            val index = first?.index ?: gridState.firstVisibleItemIndex
            headerIndexes.indexOfLast { it <= index }.coerceAtLeast(0)
        }
    }
    val chipsPinned by remember(chipsIndex) {
        derivedStateOf { chipsIndex >= 0 && gridState.firstVisibleItemIndex > chipsIndex }
    }
    val selectSection: (Int) -> Unit = { index ->
        val target = headerIndexes.getOrNull(index)
        if (target != null) {
            scope.launch { gridState.animateScrollToItem(target, scrollOffset = -pinnedChipsPx) }
        }
    }

    Box(modifier = Modifier.fillMaxSize()) {
        LazyVerticalGrid(
            columns = GridCells.Adaptive(minSize = 156.dp),
            state = gridState,
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 4.dp, bottom = bottomSpace),
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
                            icon = Icons.Default.Search,
                            title = "Hech narsa topilmadi",
                            text = "Boshqa so'z bilan qidirib ko'ring",
                        )
                    } else {
                        EmptyHint(
                            icon = Icons.Default.Info,
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
                    )
                }
            }
        }

        // Bo'limlar qatori ro'yxat bilan birga surilib ketgach, tepada qotib turadi
        androidx.compose.animation.AnimatedVisibility(
            visible = chipsPinned,
            modifier = Modifier.align(Alignment.TopCenter),
            enter = fadeIn(),
            exit = fadeOut(),
        ) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(PINNED_CHIPS_HEIGHT)
                    .background(MaterialTheme.colorScheme.background),
                contentAlignment = Alignment.CenterStart,
            ) {
                CategoryChips(sections = sections, selectedIndex = currentSection, onSelect = selectSection)
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

/** Kafe kartochkasi: nomi, ochiq-yopiqligi va yetkazish shartlari. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ShopHero(shop: Shop?) {
    val scheme = MaterialTheme.colorScheme
    val name = shop?.cafeName?.takeIf { it.isNotBlank() } ?: "Amora"
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(26.dp))
            .background(Brush.linearGradient(scheme.brandGradient))
            .drawBehind {
                // Fondagi yumshoq doiralar: kartochkaga chuqurlik beradi
                drawCircle(
                    color = Color.White.copy(alpha = 0.10f),
                    radius = size.height * 0.80f,
                    center = Offset(size.width * 0.95f, size.height * 0.02f),
                )
                drawCircle(
                    color = Color.White.copy(alpha = 0.07f),
                    radius = size.height * 0.50f,
                    center = Offset(size.width * 0.66f, size.height * 1.12f),
                )
            }
            .padding(20.dp),
    ) {
        Column {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .size(56.dp)
                        .clip(CircleShape)
                        .background(Color.White),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        text = name.take(1).uppercase(),
                        style = MaterialTheme.typography.headlineMedium,
                        color = Color(0xFFE8442A),
                    )
                }
                Spacer(Modifier.width(14.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = name,
                        style = MaterialTheme.typography.headlineSmall,
                        color = Color.White,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    if (shop != null) {
                        Spacer(Modifier.height(4.dp))
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(
                                modifier = Modifier
                                    .size(8.dp)
                                    .clip(CircleShape)
                                    .background(if (shop.isOpen) Color(0xFF7CF2B4) else Color.White.copy(alpha = 0.6f)),
                            )
                            Spacer(Modifier.width(8.dp))
                            Text(
                                text = shopStatusLine(shop),
                                style = MaterialTheme.typography.labelLarge,
                                color = Color.White.copy(alpha = 0.95f),
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }
                    }
                }
            }
            if (shop != null) {
                Spacer(Modifier.height(18.dp))
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    for (fact in deliveryFacts(shop)) {
                        Text(
                            text = fact,
                            style = MaterialTheme.typography.labelMedium,
                            color = Color.White,
                            maxLines = 1,
                            modifier = Modifier
                                .clip(RoundedCornerShape(50))
                                .background(Color.White.copy(alpha = 0.18f))
                                .padding(horizontal = 12.dp, vertical = 7.dp),
                        )
                    }
                }
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
                Icon(Icons.Default.Close, contentDescription = "Qidiruvni tozalash")
            }
        }
    }
    TextField(
        value = query,
        onValueChange = { onChange(it.take(40)) },
        modifier = Modifier.fillMaxWidth(),
        placeholder = { Text("Taom qidirish") },
        leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
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
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        for (order in orders) {
            Surface(
                onClick = { onOpenOrder(order.id) },
                shape = MaterialTheme.shapes.large,
                color = scheme.surface,
            ) {
                Column(modifier = Modifier.padding(14.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        IconBadge(size = 44.dp) {
                            OrderStatusIcon(
                                status = order.status,
                                modifier = Modifier.size(22.dp),
                                tint = scheme.primary,
                            )
                        }
                        Spacer(Modifier.width(12.dp))
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = "Buyurtma №${order.id}",
                                style = MaterialTheme.typography.labelMedium,
                                color = scheme.onSurfaceVariant,
                            )
                            Text(
                                text = order.statusLabel,
                                style = MaterialTheme.typography.titleMedium,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.KeyboardArrowRight,
                            contentDescription = null,
                            tint = scheme.onSurfaceVariant,
                        )
                    }
                    Spacer(Modifier.height(12.dp))
                    OrderProgressBar(status = order.status)
                }
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
    val scheme = MaterialTheme.colorScheme
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
            val selected = index == selectedIndex
            Surface(
                onClick = { onSelect(index) },
                shape = RoundedCornerShape(50),
                color = if (selected) scheme.secondary else scheme.surface,
                contentColor = if (selected) scheme.onSecondary else scheme.onSurface,
            ) {
                Text(
                    text = section.title,
                    style = MaterialTheme.typography.labelLarge,
                    maxLines = 1,
                    modifier = Modifier.padding(horizontal = 18.dp, vertical = 11.dp),
                )
            }
        }
    }
}

@Composable
private fun SectionHeader(title: String, count: Int) {
    Row(
        modifier = Modifier.padding(top = 10.dp, bottom = 2.dp),
        verticalAlignment = Alignment.Bottom,
    ) {
        Text(text = title, style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.width(8.dp))
        Text(
            text = count.toString(),
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(bottom = 2.dp),
        )
    }
}

/** Ro'yxat ichidagi bo'sh holat (masalan, qidiruvda hech narsa topilmadi). */
@Composable
private fun EmptyHint(icon: ImageVector, title: String, text: String) {
    val scheme = MaterialTheme.colorScheme
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 40.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        IconBadge(size = 80.dp) {
            Icon(icon, contentDescription = null, tint = scheme.primary, modifier = Modifier.size(34.dp))
        }
        Spacer(Modifier.height(16.dp))
        Text(title, style = MaterialTheme.typography.titleLarge, textAlign = TextAlign.Center)
        Spacer(Modifier.height(4.dp))
        Text(
            text = text,
            style = MaterialTheme.typography.bodyMedium,
            color = scheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
    }
}

@Composable
private fun ProductCard(
    product: Product,
    imageUrl: String?,
    quantity: Int,
    onAdd: () -> Unit,
    onRemove: () -> Unit,
    onClick: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    Surface(
        onClick = onClick,
        shape = MaterialTheme.shapes.large,
        color = scheme.surface,
    ) {
        Column(modifier = Modifier.padding(6.dp)) {
            Box {
                ProductImage(
                    url = imageUrl,
                    modifier = Modifier
                        .fillMaxWidth()
                        .aspectRatio(1.12f)
                        .clip(RoundedCornerShape(17.dp))
                        .alpha(if (product.isAvailable) 1f else 0.5f),
                )
                if (!product.isAvailable) {
                    Text(
                        text = "Tugagan",
                        style = MaterialTheme.typography.labelMedium,
                        color = scheme.onSurface,
                        modifier = Modifier
                            .align(Alignment.TopStart)
                            .padding(8.dp)
                            .clip(RoundedCornerShape(50))
                            .background(scheme.surface)
                            .padding(horizontal = 10.dp, vertical = 5.dp),
                    )
                } else if (quantity > 0) {
                    // Savatdagi soni: rasm burchagidagi belgi
                    Box(
                        modifier = Modifier
                            .align(Alignment.TopEnd)
                            .padding(8.dp)
                            .size(28.dp)
                            .clip(CircleShape)
                            .background(scheme.primary),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(
                            text = quantity.toString(),
                            style = MaterialTheme.typography.labelMedium,
                            color = scheme.onPrimary,
                            maxLines = 1,
                        )
                    }
                }
            }
            Column(modifier = Modifier.padding(start = 8.dp, end = 8.dp, top = 10.dp, bottom = 6.dp)) {
                Text(
                    text = product.name,
                    style = MaterialTheme.typography.titleSmall,
                    color = if (product.isAvailable) scheme.onSurface else scheme.onSurfaceVariant,
                    minLines = 2,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.testTag("product-name"),
                )
                Spacer(Modifier.height(10.dp))
                when {
                    !product.isAvailable -> Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(44.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(
                            text = "Hozircha yo'q",
                            style = MaterialTheme.typography.labelLarge,
                            color = scheme.onSurfaceVariant,
                        )
                    }

                    quantity == 0 -> PriceAddButton(
                        price = formatSum(product.price),
                        onClick = onAdd,
                        modifier = Modifier.fillMaxWidth(),
                    )

                    else -> QuantityStepper(
                        quantity = quantity,
                        onMinus = onRemove,
                        onPlus = onAdd,
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            }
        }
    }
}

/** Ekran pastida suzib turadigan "Savat" tugmasi: savatda taom bo'lsa ko'rinadi. */
@Composable
private fun CartBar(count: Int, total: Int, onClick: () -> Unit) {
    val scheme = MaterialTheme.colorScheme
    val shape = RoundedCornerShape(20.dp)
    Surface(
        onClick = onClick,
        modifier = Modifier
            .padding(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 12.dp)
            .fillMaxWidth()
            .height(60.dp)
            .shadow(elevation = 14.dp, shape = shape, ambientColor = scheme.primary, spotColor = scheme.primary),
        shape = shape,
        color = scheme.primary,
        contentColor = scheme.onPrimary,
    ) {
        Row(
            modifier = Modifier.padding(start = 14.dp, end = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .size(32.dp)
                    .clip(CircleShape)
                    .background(scheme.onPrimary.copy(alpha = 0.2f)),
                contentAlignment = Alignment.Center,
            ) {
                Text(count.toString(), style = MaterialTheme.typography.labelLarge, maxLines = 1)
            }
            Spacer(Modifier.width(12.dp))
            Text(
                text = "Savat",
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.weight(1f),
            )
            Text(formatSum(total), style = MaterialTheme.typography.titleMedium, maxLines = 1)
            Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = null)
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
        shape = RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp),
    ) {
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
                    .clip(RoundedCornerShape(22.dp)),
                iconSize = 76.dp,
            )
            Spacer(Modifier.height(18.dp))
            Text(
                text = product.name,
                style = MaterialTheme.typography.headlineSmall,
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
                    height = 56.dp,
                    corner = 18.dp,
                    label = "$quantity ta · ${formatSum(product.price * quantity)}",
                )
            }
        }
    }
}

/** Menyu birinchi marta yuklanayotganda ko'rinadigan "skelet". */
@Composable
private fun MenuSkeleton() {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(start = 16.dp, end = 16.dp, top = 4.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        SkeletonBox(
            modifier = Modifier
                .fillMaxWidth()
                .height(150.dp),
            shape = RoundedCornerShape(26.dp),
        )
        SkeletonBox(
            modifier = Modifier
                .padding(top = 10.dp)
                .width(150.dp)
                .height(28.dp),
        )
        repeat(2) {
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                repeat(2) {
                    SkeletonBox(
                        modifier = Modifier
                            .weight(1f)
                            .height(236.dp),
                        shape = MaterialTheme.shapes.large,
                    )
                }
            }
        }
    }
}
