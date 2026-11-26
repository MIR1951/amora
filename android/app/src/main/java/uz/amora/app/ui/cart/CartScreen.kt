package uz.amora.app.ui.cart

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
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
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.input.ImeAction
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
import uz.amora.app.ui.components.BigButton
import uz.amora.app.ui.components.BottomDock
import uz.amora.app.ui.components.ConfirmDialog
import uz.amora.app.ui.components.DashedDivider
import uz.amora.app.ui.components.GlassTopBar
import uz.amora.app.ui.components.IconTile
import uz.amora.app.ui.components.LinkRow
import uz.amora.app.ui.components.LoadingBox
import uz.amora.app.ui.components.MessageBox
import uz.amora.app.ui.components.PriceText
import uz.amora.app.ui.components.ProductImage
import uz.amora.app.ui.components.QuantityStepper
import uz.amora.app.ui.components.RowDivider
import uz.amora.app.ui.components.SectionCard
import uz.amora.app.ui.components.SectionLabel
import uz.amora.app.ui.components.SkeletonBox
import uz.amora.app.ui.components.SummaryRow
import uz.amora.app.ui.components.fieldColors
import uz.amora.app.ui.components.glassSource
import uz.amora.app.ui.components.rememberGlassState
import uz.amora.app.ui.theme.PriceLargeStyle
import uz.amora.app.ui.theme.hint
import uz.amora.app.ui.theme.info
import uz.amora.app.ui.theme.infoContainer
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
    val glass = rememberGlassState()

    val snackbar = remember { SnackbarHostState() }
    var confirming by rememberSaveable { mutableStateOf(false) }
    var confirmClear by rememberSaveable { mutableStateOf(false) }

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
    // Summa hozir qo'llangan promokod bilan hisoblanganmi (yangi kod tekshirilayotgan bo'lishi mumkin)
    val promoFresh = state.quotePromo == state.appliedPromo
    val codeWorks = promoFresh && state.appliedPromo != null && quote?.promoError == null
    val canOrder = quote != null && quote.canOrder && !state.quoteLoading && state.quoteError == null &&
        promoFresh
    // Summa birinchi marta serverdan kutilayotganda raqamlar o'rnida skelet ko'rinadi
    val quotePending = quote == null && state.quoteError == null

    // "Bepul yetkazishgacha yana ..." qatori: kafe shunday chegara qo'ygan bo'lsa va
    // server hisoblagan yetkazish narxi bunga zid kelmasa ko'rinadi
    val freeFrom = shop?.freeDeliveryFrom
    val showFreeDelivery = shop != null && shop.deliveryFee > 0 && freeFrom != null && freeFrom > 0 &&
        (quote == null || (quote.deliveryFee == 0) == (itemsTotal >= freeFrom))

    val active = cart.isNotEmpty() && createdOrderId == null
    // Klaviatura ochiq paytda pastki tugma yashirinadi: yozilayotgan izoh uning ortida qolib ketmaydi
    val ime = WindowInsets.ime
    val density = LocalDensity.current
    val keyboardOpen by remember(ime, density) { derivedStateOf { ime.getBottom(density) > 0 } }
    // Faqat shu ekrandagi maydonga yozilayotganda: boshqa ekrandan (masalan, profildagi ism
    // maydonidan) ochiq qolgan klaviatura tugmani yashirmaydi va o'zi yopiladi
    var fieldFocused by remember { mutableStateOf(false) }
    val keyboard = LocalSoftwareKeyboardController.current
    LaunchedEffect(keyboardOpen, fieldFocused) {
        if (keyboardOpen && !fieldFocused) keyboard?.hide()
    }
    val docked = active && !(keyboardOpen && fieldFocused)

    Scaffold(
        modifier = Modifier.imePadding().onFocusChanged { fieldFocused = it.hasFocus },
        containerColor = scheme.background,
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        topBar = {
            GlassTopBar(
                glass = glass,
                title = "Savat",
                onBack = onBack,
                actions = {
                    if (active) {
                        // Buyurtma yuborilayotgan paytda savatni tozalab bo'lmaydi
                        TextButton(onClick = { confirmClear = true }, enabled = !state.submitting) {
                            Text(
                                text = "Tozalash",
                                style = MaterialTheme.typography.labelLarge,
                                color = scheme.primary,
                            )
                        }
                    }
                },
            )
        },
        snackbarHost = {
            // Pastki panel bor paytda u tizim tugmalari uchun joyni o'zi qoldiradi
            SnackbarHost(snackbar, modifier = if (docked) Modifier else Modifier.navigationBarsPadding())
        },
        bottomBar = {
            if (docked) {
                BottomDock(glass = glass) {
                    when {
                        address == null -> BigButton(text = "Manzilni tanlang", onClick = onPickAddress)

                        profile == null || !profile.verified -> BigButton(
                            text = "Raqamni tasdiqlang",
                            onClick = onEditProfile,
                        )

                        else -> BigButton(
                            text = "Buyurtma berish",
                            onClick = { confirming = true },
                            enabled = canOrder,
                            loading = state.submitting,
                            trailing = quote?.let { formatSum(it.total) },
                        )
                    }
                }
            }
        },
    ) { padding ->
        when {
            createdOrderId != null -> LoadingBox(Modifier.padding(padding))

            cart.isEmpty() -> MessageBox(
                icon = R.drawable.ic_bag,
                title = "Savat bo'sh",
                text = "Menyudan yoqqan taomingizni tanlang",
                actionLabel = "Menyuga qaytish",
                onAction = onBack,
                modifier = Modifier
                    .glassSource(glass)
                    .padding(padding)
                    .navigationBarsPadding(),
            )

            else -> LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .glassSource(glass),
                contentPadding = PaddingValues(
                    start = 16.dp,
                    end = 16.dp,
                    top = padding.calculateTopPadding(),
                    bottom = padding.calculateBottomPadding() + 8.dp,
                ),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                if (showFreeDelivery && freeFrom != null) {
                    item(key = "free-delivery") {
                        FreeDeliveryCard(itemsTotal = itemsTotal, freeFrom = freeFrom)
                    }
                }

                item(key = "items") {
                    SectionCard(padding = 0.dp) {
                        cart.entries.forEachIndexed { index, entry ->
                            val productId = entry.key
                            val quantity = entry.value
                            val product = productsById[productId]
                            val line = quoteLines[productId]
                            if (index > 0) RowDivider(inset = 16.dp)
                            CartLine(
                                productId = productId,
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

                item(key = "delivery-label") {
                    SectionLabel("Yetkazish")
                }

                item(key = "delivery") {
                    SectionCard(padding = 0.dp) {
                        LinkRow(
                            icon = R.drawable.ic_pin,
                            label = "Yetkazish manzili",
                            value = when {
                                address == null -> "Xaritadan tanlang"
                                address.note.isBlank() -> "Xaritada belgilangan joy"
                                else -> address.note
                            },
                            highlighted = address == null,
                            onClick = onPickAddress,
                        )
                        RowDivider()
                        LinkRow(
                            icon = R.drawable.ic_user,
                            label = "Qabul qiluvchi",
                            value = if (profile == null || !profile.verified) {
                                "Raqamni Telegram orqali tasdiqlang"
                            } else {
                                "${profile.name}, ${formatPhone(profile.phone)}"
                            },
                            highlighted = profile == null || !profile.verified,
                            onClick = onEditProfile,
                            tileContainer = scheme.infoContainer,
                            tileTint = scheme.info,
                        )
                        RowDivider()
                        Row(
                            modifier = Modifier.padding(start = 16.dp, top = 4.dp, bottom = 4.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            IconTile(
                                icon = R.drawable.ic_message,
                                container = scheme.surfaceVariant,
                                tint = scheme.onSurfaceVariant,
                            )
                            TextField(
                                value = state.comment,
                                onValueChange = { vm.setComment(it) },
                                placeholder = { Text("Kafe uchun izoh (ixtiyoriy)") },
                                modifier = Modifier.weight(1f),
                                maxLines = 4,
                                textStyle = MaterialTheme.typography.bodyLarge,
                                colors = fieldColors(Color.Transparent),
                                keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences),
                            )
                        }
                    }
                }

                item(key = "promo") {
                    PromoCard(
                        input = state.promoInput,
                        applied = state.appliedPromo,
                        title = quote?.promoTitle?.takeIf { codeWorks },
                        error = quote?.promoError?.takeIf { promoFresh && state.appliedPromo != null },
                        onInput = vm::setPromoInput,
                        onApply = vm::applyPromo,
                        onRemove = vm::removePromo,
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
                            valueColor = if (quote != null && quote.deliveryFee == 0) {
                                scheme.success
                            } else {
                                Color.Unspecified
                            },
                            loading = quotePending,
                        )
                        if (quote != null && quote.discount > 0) {
                            SummaryRow(
                                label = if (codeWorks) "Chegirma (${state.appliedPromo})" else "Chegirma",
                                value = "−${formatSum(quote.discount)}",
                                valueColor = scheme.success,
                            )
                            // Kod kiritmasdan berilgan chegirma: nimaga berilganini aytamiz
                            val autoTitle = quote.promoTitle
                            if (!codeWorks && autoTitle != null) {
                                Text(
                                    text = "🎉 $autoTitle",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = scheme.success,
                                    modifier = Modifier.padding(bottom = 4.dp),
                                )
                            }
                        }
                        Spacer(Modifier.height(10.dp))
                        DashedDivider()
                        Spacer(Modifier.height(12.dp))
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                text = "Jami",
                                style = MaterialTheme.typography.titleMedium,
                                modifier = Modifier.weight(1f),
                            )
                            when {
                                quote != null -> PriceText(
                                    amount = quote.total,
                                    style = PriceLargeStyle,
                                    unitColor = scheme.onSurface,
                                )

                                quotePending -> SkeletonBox(modifier = Modifier.size(width = 116.dp, height = 24.dp))

                                else -> Text("—", style = PriceLargeStyle)
                            }
                        }
                        Spacer(Modifier.height(14.dp))
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(14.dp))
                                .background(scheme.surfaceVariant)
                                .padding(horizontal = 12.dp, vertical = 11.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Icon(
                                painter = painterResource(R.drawable.ic_cash),
                                contentDescription = null,
                                tint = scheme.success,
                                modifier = Modifier.size(18.dp),
                            )
                            Spacer(Modifier.width(10.dp))
                            Text(
                                text = "To'lov: kuryerga naqd pul bilan",
                                style = MaterialTheme.typography.bodySmall,
                                color = scheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            }
        }
    }

    if (confirmClear) {
        ConfirmDialog(
            title = "Savatni tozalaysizmi?",
            text = "Savatdagi hamma taom, izoh va promokod o'chiriladi.",
            confirmLabel = "Tozalash",
            dismissLabel = "Yo'q, qolsin",
            onConfirm = {
                confirmClear = false
                container.cart.clear()
            },
            onDismiss = { confirmClear = false },
        )
    }

    if (confirming && quote != null) {
        ConfirmDialog(
            title = "Buyurtmani tasdiqlaysizmi?",
            text = "Jami: ${formatSum(quote.total)}. To'lov kuryerga naqd pul bilan beriladi.",
            confirmLabel = "Tasdiqlash",
            dismissLabel = "Orqaga",
            onConfirm = {
                confirming = false
                vm.submit()
            },
            onDismiss = { confirming = false },
        )
    }
}

/** Promokod maydoni: "Qo'llash" bosilgach server tekshiradi, natija pastda yoziladi. */
@Composable
private fun PromoCard(
    input: String,
    applied: String?,
    title: String?,
    error: String?,
    onInput: (String) -> Unit,
    onApply: () -> Unit,
    onRemove: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    val editing = applied == null || input != applied
    SectionCard(padding = 0.dp) {
        Row(
            modifier = Modifier.padding(start = 16.dp, end = 8.dp, top = 4.dp, bottom = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconTile(
                icon = R.drawable.ic_tag,
                container = scheme.successContainer,
                tint = scheme.success,
            )
            TextField(
                value = input,
                onValueChange = onInput,
                placeholder = { Text("Promokod") },
                modifier = Modifier.weight(1f),
                singleLine = true,
                textStyle = MaterialTheme.typography.bodyLarge,
                colors = fieldColors(Color.Transparent),
                keyboardOptions = KeyboardOptions(
                    capitalization = KeyboardCapitalization.Characters,
                    autoCorrectEnabled = false,
                    imeAction = ImeAction.Done,
                ),
                keyboardActions = KeyboardActions(onDone = { if (editing) onApply() }),
            )
            if (editing) {
                TextButton(onClick = onApply, enabled = input.isNotBlank()) {
                    Text("Qo'llash", style = MaterialTheme.typography.labelLarge)
                }
            } else {
                TextButton(onClick = onRemove) {
                    Text(
                        "Olib tashlash",
                        style = MaterialTheme.typography.labelLarge,
                        color = scheme.onSurfaceVariant,
                    )
                }
            }
        }
        val message = when {
            editing -> null
            error != null -> error
            title != null -> "✓ $title"
            else -> null
        }
        if (message != null) {
            Text(
                text = message,
                style = MaterialTheme.typography.bodySmall,
                color = if (error != null) scheme.error else scheme.success,
                modifier = Modifier.padding(start = 72.dp, end = 16.dp, bottom = 12.dp),
            )
        }
    }
}

/** Bepul yetkazishgacha qancha qolganini ko'rsatadi: savatni to'ldirishga undaydi. */
@Composable
private fun FreeDeliveryCard(itemsTotal: Int, freeFrom: Int) {
    val scheme = MaterialTheme.colorScheme
    val reached = itemsTotal >= freeFrom
    val fraction by animateFloatAsState(
        targetValue = (itemsTotal.toFloat() / freeFrom).coerceIn(0f, 1f),
        animationSpec = tween(500),
        label = "free-delivery",
    )
    val accent = if (reached) scheme.success else scheme.primary
    SectionCard(padding = 14.dp) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconTile(
                icon = R.drawable.ic_bike,
                container = if (reached) scheme.successContainer else scheme.primaryContainer,
                tint = accent,
            )
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
    productId: Int,
    name: String,
    lineTotal: Int,
    imageUrl: String?,
    quantity: Int,
    problem: String?,
    onMinus: () -> Unit,
    onPlus: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    Row(
        modifier = Modifier.padding(horizontal = 12.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        ProductImage(
            url = imageUrl,
            modifier = Modifier
                .size(58.dp)
                .clip(RoundedCornerShape(17.dp)),
            iconSize = 28.dp,
            seed = productId,
        )
        Spacer(Modifier.width(12.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = name,
                style = MaterialTheme.typography.titleMedium,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            Spacer(Modifier.height(2.dp))
            Text(
                text = formatSum(lineTotal),
                style = MaterialTheme.typography.bodyMedium,
                color = scheme.hint,
            )
            if (problem != null) {
                Text(
                    text = problem,
                    style = MaterialTheme.typography.labelMedium,
                    color = scheme.error,
                )
            }
        }
        Spacer(Modifier.width(8.dp))
        QuantityStepper(
            quantity = quantity,
            onMinus = onMinus,
            onPlus = onPlus,
            height = 40.dp,
            corner = 14.dp,
            buttonWidth = 36.dp,
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
                Text(
                    text = actionLabel,
                    style = MaterialTheme.typography.labelLarge,
                    modifier = Modifier
                        .clip(RoundedCornerShape(12.dp))
                        .clickable(role = Role.Button, onClick = onAction)
                        .padding(horizontal = 12.dp, vertical = 10.dp),
                )
            }
        }
    }
}
