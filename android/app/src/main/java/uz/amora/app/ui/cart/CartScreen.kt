package uz.amora.app.ui.cart

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.ShoppingCart
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TextField
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import uz.amora.app.AppContainer
import uz.amora.app.R
import uz.amora.app.data.resolveImageUrl
import uz.amora.app.ui.components.BackTopBar
import uz.amora.app.ui.components.BigButton
import uz.amora.app.ui.components.BottomActionBar
import uz.amora.app.ui.components.IconBadge
import uz.amora.app.ui.components.LinkRow
import uz.amora.app.ui.components.LoadingBox
import uz.amora.app.ui.components.MessageBox
import uz.amora.app.ui.components.ProductImage
import uz.amora.app.ui.components.QuantityStepper
import uz.amora.app.ui.components.SectionCard
import uz.amora.app.ui.components.SummaryRow
import uz.amora.app.ui.components.fieldColors
import uz.amora.app.ui.theme.success
import uz.amora.app.ui.theme.successContainer
import uz.amora.app.util.formatPhone
import uz.amora.app.util.formatSum

@Composable
fun CartScreen(
    container: AppContainer,
    onBack: () -> Unit,
    onPickAddress: () -> Unit,
    onEditProfile: () -> Unit,
    onOrderCreated: (Int) -> Unit,
) {
    val vm: CartViewModel = viewModel(
        factory = viewModelFactory { initializer { CartViewModel(container) } },
    )
    val state = vm.state.collectAsStateWithLifecycle().value
    val cart = container.cart.items.collectAsStateWithLifecycle().value
    val catalog = container.catalog.state.collectAsStateWithLifecycle().value
    val address = container.session.address.collectAsStateWithLifecycle().value
    val profile = container.session.profile.collectAsStateWithLifecycle().value
    val menu = catalog.menu
    val shop = catalog.shop
    val scheme = MaterialTheme.colorScheme

    val snackbar = remember { SnackbarHostState() }
    var confirming by rememberSaveable { mutableStateOf(false) }

    val createdOrderId = state.createdOrderId
    LaunchedEffect(createdOrderId) {
        if (createdOrderId != null) onOrderCreated(createdOrderId)
    }
    val submitError = state.submitError
    LaunchedEffect(submitError) {
        if (submitError != null) {
            snackbar.showSnackbar(submitError)
            vm.clearSubmitError()
        }
    }

    val productsById = remember(menu) { (menu?.products ?: emptyList()).associateBy { it.id } }
    val quote = state.quote
    val quoteLines = remember(quote) { (quote?.lines ?: emptyList()).associateBy { it.productId } }
    val problems = quote?.problems ?: emptyList()
    val generalProblems = problems.filter { it.productId == null }

    val localItemsTotal = cart.entries.fold(0) { sum, entry ->
        sum + (productsById[entry.key]?.price ?: 0) * entry.value
    }
    val itemsTotal = quote?.itemsTotal ?: localItemsTotal
    val canOrder = quote != null && quote.canOrder && !state.quoteLoading && state.quoteError == null

    // "Bepul yetkazishgacha yana ..." qatori: kafe shunday chegara qo'ygan bo'lsa va
    // server hisoblagan yetkazish narxi bunga zid kelmasa ko'rinadi
    val freeFrom = shop?.freeDeliveryFrom
    val showFreeDelivery = shop != null && shop.deliveryFee > 0 && freeFrom != null && freeFrom > 0 &&
        (quote == null || (quote.deliveryFee == 0) == (itemsTotal >= freeFrom))

    Scaffold(
        modifier = Modifier.imePadding(),
        containerColor = scheme.background,
        topBar = {
            BackTopBar(
                title = "Savat",
                onBack = onBack,
                actions = {
                    if (cart.isNotEmpty() && createdOrderId == null) {
                        TextButton(
                            onClick = { container.cart.clear() },
                            modifier = Modifier.padding(end = 8.dp),
                        ) {
                            Text(
                                text = "Tozalash",
                                style = MaterialTheme.typography.labelLarge,
                                color = scheme.onSurfaceVariant,
                            )
                        }
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
        bottomBar = {
            if (cart.isNotEmpty() && createdOrderId == null) {
                BottomActionBar {
                    when {
                        address == null -> BigButton(text = "Manzilni tanlang", onClick = onPickAddress)

                        profile == null -> BigButton(
                            text = "Ism va telefonni kiriting",
                            onClick = onEditProfile,
                        )

                        else -> BigButton(
                            text = if (quote != null) {
                                "Buyurtma berish · ${formatSum(quote.total)}"
                            } else {
                                "Buyurtma berish"
                            },
                            onClick = { confirming = true },
                            enabled = canOrder,
                            loading = state.submitting,
                        )
                    }
                }
            }
        },
    ) { padding ->
        when {
            createdOrderId != null -> LoadingBox(Modifier.padding(padding))

            cart.isEmpty() -> MessageBox(
                icon = Icons.Default.ShoppingCart,
                title = "Savat bo'sh",
                text = "Menyudan yoqqan taomingizni tanlang",
                actionLabel = "Menyuga qaytish",
                onAction = onBack,
                modifier = Modifier.padding(padding),
            )

            else -> LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 20.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                if (showFreeDelivery && freeFrom != null) {
                    item(key = "free-delivery") {
                        FreeDeliveryCard(itemsTotal = itemsTotal, freeFrom = freeFrom)
                    }
                }

                item(key = "items") {
                    SectionCard(padding = 14.dp) {
                        cart.entries.forEachIndexed { index, entry ->
                            val productId = entry.key
                            val quantity = entry.value
                            val product = productsById[productId]
                            val line = quoteLines[productId]
                            if (index > 0) {
                                HorizontalDivider(
                                    modifier = Modifier.padding(vertical = 12.dp),
                                    color = scheme.outlineVariant,
                                )
                            }
                            CartLine(
                                name = line?.name ?: product?.name ?: "Taom",
                                lineTotal = (line?.price ?: product?.price ?: 0) * quantity,
                                imageUrl = resolveImageUrl(container.baseUrl, product?.imageUrl),
                                quantity = quantity,
                                problem = problems.firstOrNull { it.productId == productId }?.message,
                                onMinus = { container.cart.remove(productId) },
                                onPlus = { container.cart.add(productId) },
                            )
                        }
                    }
                }

                item(key = "delivery") {
                    SectionCard(padding = 4.dp) {
                        LinkRow(
                            icon = Icons.Default.LocationOn,
                            label = "Yetkazish manzili",
                            value = when {
                                address == null -> "Xaritadan tanlang"
                                address.note.isBlank() -> "Xaritada belgilangan joy"
                                else -> address.note
                            },
                            highlighted = address == null,
                            onClick = onPickAddress,
                        )
                        HorizontalDivider(
                            modifier = Modifier.padding(start = 64.dp, end = 12.dp),
                            color = scheme.outlineVariant,
                        )
                        LinkRow(
                            icon = Icons.Default.Person,
                            label = "Qabul qiluvchi",
                            value = if (profile == null) {
                                "Ism va telefon raqamni kiriting"
                            } else {
                                "${profile.name}, ${formatPhone(profile.phone)}"
                            },
                            highlighted = profile == null,
                            onClick = onEditProfile,
                        )
                    }
                }

                item(key = "comment") {
                    TextField(
                        value = state.comment,
                        onValueChange = { vm.setComment(it) },
                        placeholder = { Text("Kafe uchun izoh (ixtiyoriy)") },
                        modifier = Modifier.fillMaxWidth(),
                        minLines = 2,
                        maxLines = 4,
                        shape = MaterialTheme.shapes.large,
                        colors = fieldColors(),
                        keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences),
                    )
                }

                if (generalProblems.isNotEmpty()) {
                    item(key = "problems") {
                        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            for (problem in generalProblems) {
                                NoticeCard(problem.message)
                            }
                        }
                    }
                }

                val quoteError = state.quoteError
                if (quoteError != null) {
                    item(key = "quote-error") {
                        NoticeCard(quoteError, actionLabel = "Qayta urinish", onAction = { vm.refreshQuote() })
                    }
                }

                item(key = "summary") {
                    SectionCard {
                        SummaryRow("Taomlar", formatSum(itemsTotal))
                        SummaryRow(
                            label = "Yetkazish",
                            value = when {
                                quote == null -> "—"
                                quote.deliveryFee == 0 -> "Bepul"
                                else -> formatSum(quote.deliveryFee)
                            },
                            valueColor = if (quote != null && quote.deliveryFee == 0) scheme.success else scheme.onSurface,
                        )
                        HorizontalDivider(
                            modifier = Modifier.padding(vertical = 8.dp),
                            color = scheme.outlineVariant,
                        )
                        SummaryRow(
                            "Jami",
                            if (quote == null) "—" else formatSum(quote.total),
                            strong = true,
                        )
                        Spacer(Modifier.height(10.dp))
                        Text(
                            text = "To'lov: kuryerga naqd pul bilan",
                            style = MaterialTheme.typography.labelMedium,
                            color = scheme.onSurfaceVariant,
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(12.dp))
                                .background(scheme.surfaceVariant)
                                .padding(horizontal = 12.dp, vertical = 10.dp),
                        )
                    }
                }
            }
        }
    }

    if (confirming && quote != null) {
        AlertDialog(
            onDismissRequest = { confirming = false },
            containerColor = scheme.surface,
            title = { Text("Buyurtmani tasdiqlaysizmi?", style = MaterialTheme.typography.titleLarge) },
            text = {
                Text(
                    text = "Jami: ${formatSum(quote.total)}. To'lov kuryerga naqd pul bilan beriladi.",
                    style = MaterialTheme.typography.bodyLarge,
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        confirming = false
                        vm.submit()
                    },
                    shape = MaterialTheme.shapes.medium,
                ) { Text("Tasdiqlash", style = MaterialTheme.typography.labelLarge) }
            },
            dismissButton = {
                TextButton(onClick = { confirming = false }) {
                    Text("Orqaga", style = MaterialTheme.typography.labelLarge, color = scheme.onSurfaceVariant)
                }
            },
        )
    }
}

/** Bepul yetkazishgacha qancha qolganini ko'rsatadi: savatni to'ldirishga undaydi. */
@Composable
private fun FreeDeliveryCard(itemsTotal: Int, freeFrom: Int) {
    val scheme = MaterialTheme.colorScheme
    val reached = itemsTotal >= freeFrom
    val fraction = (itemsTotal.toFloat() / freeFrom).coerceIn(0f, 1f)
    val accent = if (reached) scheme.success else scheme.primary
    SectionCard(padding = 14.dp) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconBadge(
                size = 40.dp,
                container = if (reached) scheme.successContainer else scheme.primaryContainer,
            ) {
                Icon(
                    painter = painterResource(R.drawable.ic_scooter),
                    contentDescription = null,
                    tint = accent,
                    modifier = Modifier.size(22.dp),
                )
            }
            Spacer(Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = if (reached) {
                        "Yetkazish bepul"
                    } else {
                        "Bepul yetkazishgacha yana ${formatSum(freeFrom - itemsTotal)}"
                    },
                    style = MaterialTheme.typography.titleSmall,
                )
                Spacer(Modifier.height(8.dp))
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(6.dp)
                        .clip(RoundedCornerShape(50))
                        .background(scheme.surfaceVariant),
                ) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth(fraction)
                            .fillMaxHeight()
                            .clip(RoundedCornerShape(50))
                            .background(accent),
                    )
                }
            }
        }
    }
}

@Composable
private fun CartLine(
    name: String,
    lineTotal: Int,
    imageUrl: String?,
    quantity: Int,
    problem: String?,
    onMinus: () -> Unit,
    onPlus: () -> Unit,
) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        ProductImage(
            url = imageUrl,
            modifier = Modifier
                .size(64.dp)
                .clip(RoundedCornerShape(16.dp)),
            iconSize = 28.dp,
        )
        Spacer(Modifier.width(12.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = name,
                style = MaterialTheme.typography.titleSmall,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            Spacer(Modifier.height(2.dp))
            Text(
                text = formatSum(lineTotal),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (problem != null) {
                Text(
                    text = problem,
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.error,
                )
            }
        }
        Spacer(Modifier.width(8.dp))
        QuantityStepper(
            quantity = quantity,
            onMinus = onMinus,
            onPlus = onPlus,
            modifier = Modifier.width(112.dp),
            height = 40.dp,
            corner = 13.dp,
            tonal = true,
        )
    }
}

/** Buyurtma berishga to'sqinlik qilayotgan sabab (kafe yopiq, eng kam summa va h.k.). */
@Composable
private fun NoticeCard(message: String, actionLabel: String? = null, onAction: (() -> Unit)? = null) {
    val scheme = MaterialTheme.colorScheme
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.large,
        color = scheme.errorContainer,
        contentColor = scheme.onErrorContainer,
    ) {
        Row(
            modifier = Modifier.padding(start = 16.dp, end = 8.dp, top = 8.dp, bottom = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = message,
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier
                    .weight(1f)
                    .padding(vertical = 6.dp),
            )
            if (actionLabel != null && onAction != null) {
                TextButton(onClick = onAction) {
                    Text(actionLabel, style = MaterialTheme.typography.labelLarge)
                }
            }
        }
    }
}
