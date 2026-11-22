package uz.amora.app.ui.profile

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.runtime.Composable
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
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.launch
import uz.amora.app.AppContainer
import uz.amora.app.BuildConfig
import uz.amora.app.R
import uz.amora.app.data.Profile
import uz.amora.app.ui.components.BigButton
import uz.amora.app.ui.components.BottomDock
import uz.amora.app.ui.components.ConfirmDialog
import uz.amora.app.ui.components.GlassTopBar
import uz.amora.app.ui.components.LinkRow
import uz.amora.app.ui.components.RowDivider
import uz.amora.app.ui.components.SectionCard
import uz.amora.app.ui.components.SectionLabel
import uz.amora.app.ui.components.SoftButton
import uz.amora.app.ui.components.fieldBorder
import uz.amora.app.ui.components.fieldColors
import uz.amora.app.ui.components.glassSource
import uz.amora.app.ui.components.rememberGlassState
import uz.amora.app.ui.components.rememberNotificationSwitch
import uz.amora.app.ui.theme.hint
import uz.amora.app.ui.theme.info
import uz.amora.app.ui.theme.infoContainer
import uz.amora.app.ui.theme.ink
import uz.amora.app.ui.theme.success
import uz.amora.app.ui.theme.successContainer
import uz.amora.app.util.formatPhone

private const val MAX_NAME_LENGTH = 60

/**
 * Mijozning ismi va telefoni. Kuryer shu raqamga qo'ng'iroq qiladi. Raqam qo'lda yozilmaydi:
 * u Telegram orqali tasdiqlanadi (soxta yoki birovning raqamini yozib bo'lmaydi).
 *
 * Ikki xil ochiladi: bosh sahifadagi "Profil" tugmasidan (manzil va kafe telefoni ham ko'rinadi)
 * yoki savatdan (`quickEdit`: ism va raqam, tasdiqlangach orqaga qaytadi).
 */
@Composable
fun ProfileScreen(
    container: AppContainer,
    onBack: () -> Unit,
    onPickAddress: () -> Unit,
    quickEdit: Boolean = false,
) {
    val context = LocalContext.current
    val focusManager = LocalFocusManager.current
    val scope = rememberCoroutineScope()
    val snackbar = remember { SnackbarHostState() }
    val scheme = MaterialTheme.colorScheme
    val glass = rememberGlassState()

    val profile = container.session.profile.collectAsStateWithLifecycle().value
    val address = container.session.address.collectAsStateWithLifecycle().value
    val shop = container.catalog.state.collectAsStateWithLifecycle().value.shop
    val notifications = rememberNotificationSwitch(container)

    // Saqlangan profil o'zgarsa (masalan, boshqa telefonda ism o'zgargan bo'lsa), maydon ham yangilanadi
    var name by rememberSaveable(profile?.name) { mutableStateOf(profile?.name ?: "") }

    val cleanName = name.trim().split(Regex("\\s+")).joinToString(" ")
    val verified = profile?.verified == true
    // Ism faqat tasdiqlangan hisobda alohida saqlanadi; yangi mijozning ismi tasdiqlash bilan ketadi
    val canSaveName = verified && cleanName.isNotEmpty() && cleanName != profile?.name

    var saving by remember { mutableStateOf(false) }
    val save: () -> Unit = {
        if (canSaveName && !saving) {
            focusManager.clearFocus()
            saving = true
            scope.launch {
                // Server qabul qilgandan keyingina "Saqlandi" deyiladi; xato bo'lsa, sababi ko'rsatiladi
                val error = try {
                    container.account.saveName(cleanName)
                } finally {
                    saving = false
                }
                when {
                    error != null -> snackbar.showSnackbar(error)
                    quickEdit -> onBack()
                    else -> snackbar.showSnackbar("Saqlandi")
                }
            }
        }
    }

    // Hisobdan chiqish va hisobni o'chirish: ikkalasi ham tasdiq so'raydi
    var confirmLogout by rememberSaveable { mutableStateOf(false) }
    var confirmDelete by rememberSaveable { mutableStateOf(false) }
    var accountBusy by remember { mutableStateOf(false) }
    val logout: () -> Unit = {
        if (!accountBusy) {
            accountBusy = true
            scope.launch {
                try {
                    container.logout()
                } finally {
                    accountBusy = false
                }
                snackbar.showSnackbar("Hisobdan chiqdingiz")
            }
        }
    }
    val deleteAccount: () -> Unit = {
        if (!accountBusy) {
            accountBusy = true
            scope.launch {
                val error = try {
                    container.deleteAccount()
                } finally {
                    accountBusy = false
                }
                // Xato matni serverdan keladi (masalan tugallanmagan buyurtma bor): o'zicha ko'rsatiladi
                snackbar.showSnackbar(error ?: "Hisobingiz o'chirildi")
            }
        }
    }
    val onVerified: () -> Unit = {
        focusManager.clearFocus()
        if (quickEdit) {
            onBack()
        } else {
            scope.launch { snackbar.showSnackbar("Raqam tasdiqlandi") }
        }
    }

    // Pastki panel bor paytda u tizim tugmalari uchun joyni o'zi qoldiradi
    val systemBarSpace = if (quickEdit) Modifier else Modifier.navigationBarsPadding()

    Scaffold(
        modifier = Modifier.imePadding(),
        containerColor = scheme.background,
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        topBar = {
            GlassTopBar(
                glass = glass,
                title = if (quickEdit) "Ma'lumotlarim" else "Profil",
                onBack = onBack,
            )
        },
        snackbarHost = { SnackbarHost(snackbar, modifier = systemBarSpace) },
        bottomBar = {
            if (quickEdit && verified) {
                BottomDock(glass = glass) {
                    BigButton(text = "Saqlash", onClick = save, enabled = canSaveName, loading = saving)
                }
            }
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .glassSource(glass)
                .verticalScroll(rememberScrollState())
                .padding(
                    start = 16.dp,
                    end = 16.dp,
                    top = padding.calculateTopPadding(),
                    bottom = padding.calculateBottomPadding(),
                )
                .then(systemBarSpace)
                .padding(bottom = 20.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (quickEdit) {
                Text(
                    text = "Buyurtmani yetkazishda kuryer shu ism va raqam orqali siz bilan bog'lanadi.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = scheme.onSurfaceVariant,
                    modifier = Modifier.padding(horizontal = 4.dp),
                )
            } else {
                ProfileHeader(profile)
                SectionLabel("Shaxsiy ma'lumotlar")
            }

            TextField(
                value = name,
                onValueChange = { name = it.take(MAX_NAME_LENGTH) },
                label = { Text("Ismingiz") },
                singleLine = true,
                modifier = Modifier
                    .fillMaxWidth()
                    .fieldBorder(),
                shape = RoundedCornerShape(18.dp),
                colors = fieldColors(),
                keyboardOptions = KeyboardOptions(
                    capitalization = KeyboardCapitalization.Words,
                    imeAction = ImeAction.Done,
                ),
                keyboardActions = KeyboardActions(onDone = { save() }),
            )

            PhoneVerificationSection(
                container = container,
                profile = profile,
                name = cleanName,
                snackbar = snackbar,
                onVerified = onVerified,
            )

            if (!quickEdit) {
                // Tugma faqat biror narsa o'zgarganda chiqadi: o'zgarish bo'lmasa saqlaydigan narsa yo'q
                AnimatedVisibility(visible = canSaveName) {
                    BigButton(text = "Saqlash", onClick = save, loading = saving)
                }

                SectionLabel("Yetkazish va aloqa")
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
                    val cafePhone = shop?.phone
                    if (!cafePhone.isNullOrBlank()) {
                        RowDivider()
                        LinkRow(
                            icon = R.drawable.ic_phone,
                            label = "Kafe bilan bog'lanish",
                            value = formatPhone(cafePhone),
                            onClick = { dialPhone(context, cafePhone) },
                            tileContainer = scheme.successContainer,
                            tileTint = scheme.success,
                        )
                    }
                    // Buyurtma holati haqidagi xabarlar: o'chiq bo'lsa, shu yerdan yoqiladi
                    RowDivider()
                    LinkRow(
                        icon = R.drawable.ic_bell,
                        label = "Bildirishnomalar",
                        value = if (notifications.enabled) "Yoqilgan" else "O'chirilgan. Yoqish uchun bosing",
                        highlighted = !notifications.enabled,
                        onClick = notifications.toggle,
                        tileContainer = scheme.infoContainer,
                        tileTint = scheme.info,
                    )
                }

                // Faqat hisobga kirilgan bo'lsa ko'rinadi
                if (verified) {
                    SectionLabel("Hisob")
                    SoftButton(
                        text = "Chiqish",
                        onClick = { confirmLogout = true },
                        enabled = !accountBusy,
                    )
                    SoftButton(
                        text = "Hisobni o'chirish",
                        onClick = { confirmDelete = true },
                        icon = R.drawable.ic_close,
                        enabled = !accountBusy,
                        danger = true,
                    )
                }

                Text(
                    text = "Amora · ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})",
                    style = MaterialTheme.typography.bodySmall,
                    color = scheme.hint,
                    textAlign = TextAlign.Center,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 8.dp),
                )
            }
        }
    }
    if (confirmLogout) {
        ConfirmDialog(
            title = "Hisobdan chiqasizmi?",
            text = "Buyurtma berish uchun raqamingizni Telegram orqali qayta tasdiqlashingiz kerak bo'ladi.",
            confirmLabel = "Chiqish",
            dismissLabel = "Bekor qilish",
            onConfirm = {
                confirmLogout = false
                logout()
            },
            onDismiss = { confirmLogout = false },
        )
    }

    if (confirmDelete) {
        ConfirmDialog(
            title = "Hisobni o'chirasizmi?",
            text = "Ismingiz va manzillaringiz o'chiriladi, buyurtmalar tarixi hisobingizda boshqa " +
                "ko'rinmaydi. Buni ortga qaytarib bo'lmaydi.",
            confirmLabel = "O'chirish",
            dismissLabel = "Bekor qilish",
            onConfirm = {
                confirmDelete = false
                deleteAccount()
            },
            onDismiss = { confirmDelete = false },
        )
    }
}

/** Profil boshidagi kartochka: ismning bosh harfi, ism va telefon. */
@Composable
private fun ProfileHeader(profile: Profile?) {
    val scheme = MaterialTheme.colorScheme
    SectionCard {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                modifier = Modifier
                    .size(58.dp)
                    .clip(RoundedCornerShape(19.dp))
                    .background(scheme.ink),
                contentAlignment = Alignment.Center,
            ) {
                if (profile == null) {
                    Icon(
                        painter = painterResource(R.drawable.ic_user),
                        contentDescription = null,
                        tint = Color.White,
                        modifier = Modifier.size(26.dp),
                    )
                } else {
                    Text(
                        text = profile.name.take(1).uppercase(),
                        style = MaterialTheme.typography.headlineMedium,
                        color = Color.White,
                    )
                }
            }
            Spacer(Modifier.width(14.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = profile?.name ?: "Xush kelibsiz!",
                    style = MaterialTheme.typography.titleLarge,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = when {
                        profile == null -> "Buyurtma berish uchun ismingizni yozing va raqamingizni tasdiqlang"
                        !profile.verified -> "Raqamingizni Telegram orqali tasdiqlang"
                        else -> formatPhone(profile.phone)
                    },
                    style = MaterialTheme.typography.bodyMedium,
                    color = scheme.onSurfaceVariant,
                )
            }
        }
    }
}

/** Telefon ilovasini raqam terilgan holda ochadi (qo'ng'iroqni mijoz o'zi boshlaydi). */
fun dialPhone(context: Context, phone: String) {
    try {
        context.startActivity(Intent(Intent.ACTION_DIAL, Uri.parse("tel:$phone")))
    } catch (e: Exception) {
        // Qo'ng'iroq ilovasi yo'q qurilma (masalan planshet): hech narsa qilmaymiz
    }
}
