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
import androidx.compose.ui.text.input.KeyboardType
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
import uz.amora.app.ui.components.GlassTopBar
import uz.amora.app.ui.components.LinkRow
import uz.amora.app.ui.components.PhoneVisualTransformation
import uz.amora.app.ui.components.RowDivider
import uz.amora.app.ui.components.SectionCard
import uz.amora.app.ui.components.SectionLabel
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
import uz.amora.app.util.LOCAL_PHONE_LENGTH
import uz.amora.app.util.formatPhone
import uz.amora.app.util.fullPhone
import uz.amora.app.util.localPhoneDigits

private const val MAX_NAME_LENGTH = 60

/**
 * Mijozning ismi va telefoni. Kuryer shu raqamga qo'ng'iroq qiladi.
 *
 * Ikki xil ochiladi: bosh sahifadagi "Profil" tugmasidan (manzil va kafe telefoni ham ko'rinadi)
 * yoki savatdan ism-telefonni kiritish uchun (`quickEdit`: faqat ikki maydon, saqlagach orqaga qaytadi).
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

    // Saqlangan profil o'zgarsa (masalan, savat orqali tahrirlangan bo'lsa), maydonlar ham yangilanadi
    var name by rememberSaveable(profile) { mutableStateOf(profile?.name ?: "") }
    var phoneDigits by rememberSaveable(profile) { mutableStateOf(localPhoneDigits(profile?.phone ?: "")) }

    val cleanName = name.trim().split(Regex("\\s+")).joinToString(" ")
    val phone = fullPhone(phoneDigits)
    val valid = cleanName.isNotEmpty() && phone != null
    val changed = profile == null || cleanName != profile.name || phone != profile.phone

    val save: () -> Unit = {
        if (cleanName.isNotEmpty() && phone != null) {
            container.account.saveProfile(cleanName, phone)
            focusManager.clearFocus()
            if (quickEdit) {
                onBack()
            } else {
                scope.launch { snackbar.showSnackbar("Saqlandi") }
            }
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
            if (quickEdit) {
                BottomDock(glass = glass) {
                    BigButton(text = "Saqlash", onClick = save, enabled = valid)
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
                    imeAction = ImeAction.Next,
                ),
            )

            val incomplete = phoneDigits.isNotEmpty() && phoneDigits.length < LOCAL_PHONE_LENGTH
            TextField(
                value = phoneDigits,
                onValueChange = { phoneDigits = localPhoneDigits(it) },
                label = { Text("Telefon raqam") },
                prefix = { Text("+998 ") },
                placeholder = { Text("90 123 45 67") },
                singleLine = true,
                modifier = Modifier
                    .fillMaxWidth()
                    .fieldBorder(),
                shape = RoundedCornerShape(18.dp),
                colors = fieldColors(),
                visualTransformation = PhoneVisualTransformation,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Phone,
                    imeAction = ImeAction.Done,
                ),
                keyboardActions = KeyboardActions(onDone = { save() }),
            )
            AnimatedVisibility(visible = incomplete) {
                Text(
                    text = "Raqamni to'liq kiriting: 9 ta raqam",
                    style = MaterialTheme.typography.bodySmall,
                    color = scheme.hint,
                    modifier = Modifier.padding(horizontal = 16.dp),
                )
            }

            if (!quickEdit) {
                // Tugma faqat biror narsa o'zgarganda chiqadi: o'zgarish bo'lmasa saqlaydigan narsa yo'q
                AnimatedVisibility(visible = changed) {
                    BigButton(text = "Saqlash", onClick = save, enabled = valid)
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
                    text = if (profile == null) {
                        "Buyurtma berish uchun ism va telefon raqamingizni kiriting"
                    } else {
                        formatPhone(profile.phone)
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
