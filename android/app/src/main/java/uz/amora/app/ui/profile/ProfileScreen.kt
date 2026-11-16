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
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Phone
import androidx.compose.material3.HorizontalDivider
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
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
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
import uz.amora.app.data.Profile
import uz.amora.app.ui.components.BackTopBar
import uz.amora.app.ui.components.BigButton
import uz.amora.app.ui.components.BottomActionBar
import uz.amora.app.ui.components.LinkRow
import uz.amora.app.ui.components.PhoneVisualTransformation
import uz.amora.app.ui.components.SectionCard
import uz.amora.app.ui.components.TitleTopBar
import uz.amora.app.ui.components.fieldColors
import uz.amora.app.ui.theme.brandGradient
import uz.amora.app.util.LOCAL_PHONE_LENGTH
import uz.amora.app.util.formatPhone
import uz.amora.app.util.fullPhone
import uz.amora.app.util.localPhoneDigits

private const val MAX_NAME_LENGTH = 60

/**
 * Mijozning ismi va telefoni. Kuryer shu raqamga qo'ng'iroq qiladi.
 *
 * Ikki xil ochiladi: pastki menyudagi "Profil" bo'limi sifatida (`onBack == null`: manzil va
 * kafe telefoni ham ko'rinadi) yoki savatdan ism-telefonni kiritish uchun (`onBack` berilgan:
 * saqlagach orqaga qaytadi).
 */
@Composable
fun ProfileScreen(
    container: AppContainer,
    onBack: (() -> Unit)?,
    onPickAddress: () -> Unit,
) {
    val context = LocalContext.current
    val focusManager = LocalFocusManager.current
    val scope = rememberCoroutineScope()
    val snackbar = remember { SnackbarHostState() }
    val scheme = MaterialTheme.colorScheme

    val profile = container.session.profile.collectAsStateWithLifecycle().value
    val address = container.session.address.collectAsStateWithLifecycle().value
    val shop = container.catalog.state.collectAsStateWithLifecycle().value.shop

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
            if (onBack != null) {
                onBack()
            } else {
                scope.launch { snackbar.showSnackbar("Saqlandi") }
            }
        }
    }

    Scaffold(
        modifier = Modifier.imePadding(),
        containerColor = scheme.background,
        topBar = {
            if (onBack != null) {
                BackTopBar(title = "Ma'lumotlarim", onBack = onBack)
            } else {
                TitleTopBar(title = "Profil")
            }
        },
        snackbarHost = { SnackbarHost(snackbar) },
        bottomBar = {
            if (onBack != null) {
                BottomActionBar {
                    BigButton(text = "Saqlash", onClick = save, enabled = valid)
                }
            }
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (onBack == null) {
                ProfileHeader(profile)
                SectionLabel("Shaxsiy ma'lumotlar")
            } else {
                Text(
                    text = "Buyurtmani yetkazishda kuryer shu ism va raqam orqali siz bilan bog'lanadi.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = scheme.onSurfaceVariant,
                    modifier = Modifier.padding(horizontal = 4.dp),
                )
            }

            TextField(
                value = name,
                onValueChange = { name = it.take(MAX_NAME_LENGTH) },
                label = { Text("Ismingiz") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(18.dp),
                colors = fieldColors(),
                keyboardOptions = KeyboardOptions(
                    capitalization = KeyboardCapitalization.Words,
                    imeAction = ImeAction.Next,
                ),
            )

            val incomplete = phoneDigits.isNotEmpty() && phoneDigits.length < LOCAL_PHONE_LENGTH
            val phoneHint: (@Composable () -> Unit)? = if (incomplete) {
                { Text("Raqamni to'liq kiriting: 9 ta raqam") }
            } else {
                null
            }
            TextField(
                value = phoneDigits,
                onValueChange = { phoneDigits = localPhoneDigits(it) },
                label = { Text("Telefon raqam") },
                prefix = { Text("+998 ") },
                placeholder = { Text("90 123 45 67") },
                supportingText = phoneHint,
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(18.dp),
                colors = fieldColors(),
                visualTransformation = PhoneVisualTransformation,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Phone,
                    imeAction = ImeAction.Done,
                ),
                keyboardActions = KeyboardActions(onDone = { save() }),
            )

            if (onBack == null) {
                // Tugma faqat biror narsa o'zgarganda chiqadi: o'zgarish bo'lmasa saqlaydigan narsa yo'q
                AnimatedVisibility(visible = changed) {
                    BigButton(text = "Saqlash", onClick = save, enabled = valid)
                }

                SectionLabel("Yetkazish va aloqa")
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
                    val cafePhone = shop?.phone
                    if (!cafePhone.isNullOrBlank()) {
                        HorizontalDivider(
                            modifier = Modifier.padding(start = 64.dp, end = 12.dp),
                            color = scheme.outlineVariant,
                        )
                        LinkRow(
                            icon = Icons.Default.Phone,
                            label = "Kafe bilan bog'lanish",
                            value = formatPhone(cafePhone),
                            onClick = { dialPhone(context, cafePhone) },
                        )
                    }
                }

                Text(
                    text = "Amora · ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})",
                    style = MaterialTheme.typography.bodySmall,
                    color = scheme.onSurfaceVariant,
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
                    .size(60.dp)
                    .clip(CircleShape)
                    .background(Brush.linearGradient(scheme.brandGradient)),
                contentAlignment = Alignment.Center,
            ) {
                if (profile == null) {
                    Icon(
                        imageVector = Icons.Default.Person,
                        contentDescription = null,
                        tint = Color.White,
                        modifier = Modifier.size(30.dp),
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

@Composable
private fun SectionLabel(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.titleMedium,
        modifier = Modifier.padding(start = 4.dp, top = 8.dp),
    )
}

/** Telefon ilovasini raqam terilgan holda ochadi (qo'ng'iroqni mijoz o'zi boshlaydi). */
fun dialPhone(context: Context, phone: String) {
    try {
        context.startActivity(Intent(Intent.ACTION_DIAL, Uri.parse("tel:$phone")))
    } catch (e: Exception) {
        // Qo'ng'iroq ilovasi yo'q qurilma (masalan planshet): hech narsa qilmaymiz
    }
}
