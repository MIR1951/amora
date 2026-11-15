package uz.amora.app.ui.menu

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
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
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
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
import uz.amora.app.data.Menu
import uz.amora.app.data.Order
import uz.amora.app.data.Product
import uz.amora.app.data.Shop
import uz.amora.app.data.resolveImageUrl
import uz.amora.app.ui.components.AddButton
import uz.amora.app.ui.components.LoadingBox
import uz.amora.app.ui.components.MessageBox
import uz.amora.app.ui.components.ProductImage
import uz.amora.app.ui.components.QuantityStepper
import uz.amora.app.ui.theme.success
import uz.amora.app.util.formatSum

private const val ACTIVE_ORDERS_REFRESH_MS = 15_000L

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

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = { MenuTopBar(shop, onOpenOrders, onOpenProfile) },
        bottomBar = {
            if (cartCount > 0) CartBar(cartCount, cartTotal, onOpenCart)
        },
    ) { padding ->
        PullToRefreshBox(
            isRefreshing = refreshing,
            onRefresh = { vm.pullToRefresh() },
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            when {
                menu == null && catalog.loading -> LoadingBox()

                menu == null -> MessageBox(
                    emoji = "📡",
                    title = "Menyu yuklanmadi",
                    text = catalog.error,
                    actionLabel = "Qayta urinish",
                    onAction = { vm.retry() },
                )

                sections.isEmpty() -> MessageBox(
                    emoji = "🍽️",
                    title = "Menyu hozircha bo'sh",
                    text = "Taomlar tez orada qo'shiladi",
                )

                else -> MenuContent(
                    shop = shop,
                    sections = sections,
                    cart = cart,
                    activeOrders = activeOrders,
                    baseUrl = container.baseUrl,
                    onAdd = { container.cart.add(it) },
                    onRemove = { container.cart.remove(it) },
                    onOpenProduct = { selectedProductId = it },
                    onOpenOrder = onOpenOrder,
                )
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

@Composable
private fun MenuTopBar(shop: Shop?, onOpenOrders: () -> Unit, onOpenProfile: () -> Unit) {
    val scheme = MaterialTheme.colorScheme
    TopAppBar(
        title = {
            Column {
                Text(
                    text = shop?.cafeName ?: "Amora",
                    style = MaterialTheme.typography.titleLarge,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                if (shop != null) {
                    Text(
                        text = shopStatusLine(shop),
                        style = MaterialTheme.typography.labelMedium,
                        color = if (shop.isOpen) scheme.success else scheme.error,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        },
        actions = {
            IconButton(onClick = onOpenOrders) {
                Icon(Icons.AutoMirrored.Filled.List, contentDescription = "Buyurtmalarim")
            }
            IconButton(onClick = onOpenProfile) {
                Icon(Icons.Default.Person, contentDescription = "Profil")
            }
        },
        colors = TopAppBarDefaults.topAppBarColors(
            containerColor = scheme.background,
            scrolledContainerColor = scheme.background,
        ),
    )
}

private fun shopStatusLine(shop: Shop): String = when {
    !shop.isAcceptingOrders -> "Hozir buyurtma qabul qilinmayapti"
    !shop.isOpen -> "Yopiq · ish vaqti ${shop.openTime}–${shop.closeTime}"
    shop.openTime == shop.closeTime -> "Ochiq · kecha-kunduz"
    else -> "Ochiq · ${shop.openTime}–${shop.closeTime}"
}

private fun deliveryInfoLine(shop: Shop): String {
    val parts = ArrayList<String>()
    if (shop.deliveryFee <= 0) {
        parts.add("Yetkazish bepul")
    } else {
        parts.add("Yetkazish: ${formatSum(shop.deliveryFee)}")
        val freeFrom = shop.freeDeliveryFrom
        if (freeFrom != null) parts.add("${formatSum(freeFrom)}dan bepul")
    }
    if (shop.minOrderAmount > 0) parts.add("Eng kam buyurtma: ${formatSum(shop.minOrderAmount)}")
    return parts.joinToString(" · ")
}

@Composable
private fun MenuContent(
    shop: Shop?,
    sections: List<MenuSection>,
    cart: Map<Int, Int>,
    activeOrders: List<Order>,
    baseUrl: String,
    onAdd: (Int) -> Unit,
    onRemove: (Int) -> Unit,
    onOpenProduct: (Int) -> Unit,
    onOpenOrder: (Int) -> Unit,
) {
    val gridState = rememberLazyGridState()
    val scope = rememberCoroutineScope()

    // Ro'yxatning 0-qatori: e'lonlar bloki. Undan keyin har bo'lim: sarlavha + taomlar.
    val headerIndexes = remember(sections) {
        val indexes = ArrayList<Int>(sections.size)
        var next = 1
        for (section in sections) {
            indexes.add(next)
            next += 1 + section.products.size
        }
        indexes
    }
    val currentSection by remember(headerIndexes) {
        derivedStateOf {
            val firstVisible = gridState.firstVisibleItemIndex
            headerIndexes.indexOfLast { it <= firstVisible }.coerceAtLeast(0)
        }
    }

    Column(modifier = Modifier.fillMaxSize()) {
        if (sections.size > 1) {
            CategoryChips(
                sections = sections,
                selectedIndex = currentSection,
                onSelect = { index ->
                    scope.launch { gridState.animateScrollToItem(headerIndexes[index]) }
                },
            )
        }
        LazyVerticalGrid(
            columns = GridCells.Adaptive(minSize = 156.dp),
            state = gridState,
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 24.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item(key = "notices", span = { GridItemSpan(maxLineSpan) }, contentType = "notices") {
                Notices(shop = shop, activeOrders = activeOrders, onOpenOrder = onOpenOrder)
            }
            for (section in sections) {
                item(
                    key = "section-${section.id}",
                    span = { GridItemSpan(maxLineSpan) },
                    contentType = "header",
                ) {
                    Text(
                        text = section.title,
                        style = MaterialTheme.typography.titleLarge,
                        modifier = Modifier.padding(top = 8.dp),
                    )
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
    }
}

@Composable
private fun CategoryChips(
    sections: List<MenuSection>,
    selectedIndex: Int,
    onSelect: (Int) -> Unit,
) {
    val listState = rememberLazyListState()
    // Tanlangan bo'lim tugmasi har doim ko'rinib turadi
    LaunchedEffect(selectedIndex) {
        listState.animateScrollToItem(selectedIndex)
    }
    LazyRow(
        state = listState,
        modifier = Modifier.fillMaxWidth(),
        contentPadding = PaddingValues(horizontal = 16.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        itemsIndexed(sections, key = { _, section -> section.id }) { index, section ->
            FilterChip(
                selected = index == selectedIndex,
                onClick = { onSelect(index) },
                label = { Text(section.title) },
                shape = RoundedCornerShape(50),
                colors = FilterChipDefaults.filterChipColors(
                    selectedContainerColor = MaterialTheme.colorScheme.primary,
                    selectedLabelColor = MaterialTheme.colorScheme.onPrimary,
                ),
            )
        }
    }
}

/** Menyu tepasidagi e'lonlar: faol buyurtma, kafe yopiqligi va yetkazish shartlari. */
@Composable
private fun Notices(shop: Shop?, activeOrders: List<Order>, onOpenOrder: (Int) -> Unit) {
    val scheme = MaterialTheme.colorScheme
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        for (order in activeOrders) {
            Surface(
                onClick = { onOpenOrder(order.id) },
                shape = MaterialTheme.shapes.medium,
                color = scheme.primaryContainer,
                contentColor = scheme.onPrimaryContainer,
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text("Buyurtma №${order.id}", style = MaterialTheme.typography.labelMedium)
                        Text(order.statusLabel, style = MaterialTheme.typography.titleSmall)
                    }
                    Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = null)
                }
            }
        }
        if (shop != null && !shop.isOpen) {
            Surface(
                shape = MaterialTheme.shapes.medium,
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
                        .padding(horizontal = 16.dp, vertical = 12.dp),
                )
            }
        }
        if (shop != null) {
            Text(
                text = deliveryInfoLine(shop),
                style = MaterialTheme.typography.bodySmall,
                color = scheme.onSurfaceVariant,
            )
        }
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
        shadowElevation = 1.dp,
    ) {
        Column {
            ProductImage(
                url = imageUrl,
                modifier = Modifier
                    .fillMaxWidth()
                    .aspectRatio(1.2f)
                    .alpha(if (product.isAvailable) 1f else 0.45f),
            )
            Column(modifier = Modifier.padding(12.dp)) {
                Text(
                    text = product.name,
                    style = MaterialTheme.typography.titleSmall,
                    color = if (product.isAvailable) scheme.onSurface else scheme.onSurfaceVariant,
                    minLines = 2,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    text = formatSum(product.price),
                    style = MaterialTheme.typography.titleMedium,
                    color = if (product.isAvailable) scheme.onSurface else scheme.onSurfaceVariant,
                    maxLines = 1,
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

                    quantity == 0 -> AddButton(
                        text = "Qo'shish",
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

/** Ekran pastidagi "Savat" tugmasi: savatda taom bo'lsa ko'rinadi. */
@Composable
private fun CartBar(count: Int, total: Int, onClick: () -> Unit) {
    val scheme = MaterialTheme.colorScheme
    Surface(color = scheme.background, shadowElevation = 12.dp) {
        Button(
            onClick = onClick,
            modifier = Modifier
                .fillMaxWidth()
                .navigationBarsPadding()
                .padding(horizontal = 16.dp, vertical = 12.dp)
                .height(54.dp),
            shape = MaterialTheme.shapes.medium,
            contentPadding = PaddingValues(horizontal = 16.dp),
        ) {
            Box(
                modifier = Modifier
                    .size(28.dp)
                    .clip(CircleShape)
                    .background(scheme.onPrimary.copy(alpha = 0.2f)),
                contentAlignment = Alignment.Center,
            ) {
                Text(count.toString(), style = MaterialTheme.typography.labelLarge, maxLines = 1)
            }
            Spacer(Modifier.width(10.dp))
            Text(
                text = "Savat",
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.weight(1f),
            )
            Text(formatSum(total), style = MaterialTheme.typography.titleMedium, maxLines = 1)
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
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
                .padding(start = 20.dp, end = 20.dp, bottom = 28.dp),
        ) {
            ProductImage(
                url = imageUrl,
                modifier = Modifier
                    .fillMaxWidth()
                    .aspectRatio(1.4f)
                    .clip(MaterialTheme.shapes.large),
                emojiSize = 64.sp,
            )
            Spacer(Modifier.height(16.dp))
            Text(product.name, style = MaterialTheme.typography.headlineSmall)
            if (product.description.isNotBlank()) {
                Spacer(Modifier.height(8.dp))
                Text(
                    text = product.description,
                    style = MaterialTheme.typography.bodyLarge,
                    color = scheme.onSurfaceVariant,
                )
            }
            Spacer(Modifier.height(20.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = formatSum(product.price),
                    style = MaterialTheme.typography.titleLarge,
                    modifier = Modifier.weight(1f),
                )
                when {
                    !product.isAvailable -> Text(
                        text = "Hozircha yo'q",
                        style = MaterialTheme.typography.labelLarge,
                        color = scheme.onSurfaceVariant,
                    )

                    quantity == 0 -> AddButton(text = "Savatga qo'shish", onClick = onAdd)

                    else -> QuantityStepper(
                        quantity = quantity,
                        onMinus = onRemove,
                        onPlus = onAdd,
                        modifier = Modifier.width(148.dp),
                    )
                }
            }
        }
    }
}
