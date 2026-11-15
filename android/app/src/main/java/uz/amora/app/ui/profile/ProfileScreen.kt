package uz.amora.app.ui.profile

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.amora.app.AppContainer
import uz.amora.app.BuildConfig
import uz.amora.app.ui.components.BackTopBar
import uz.amora.app.ui.components.BigButton
import uz.amora.app.ui.components.BottomActionBar
import uz.amora.app.ui.components.PhoneVisualTransformation
import uz.amora.app.ui.components.SectionCard
import uz.amora.app.util.LOCAL_PHONE_LENGTH
import uz.amora.app.util.formatPhone
import uz.amora.app.util.fullPhone
import uz.amora.app.util.localPhoneDigits

private const val MAX_NAME_LENGTH = 60

/** Mijozning ismi va telefoni. Kuryer shu raqamga qo'ng'iroq qiladi. */
@Composable
fun ProfileScreen(container: AppContainer, onBack: () -> Unit) {
    val context = LocalContext.current
    val profile = container.session.profile.collectAsStateWithLifecycle().value
    val shop = container.catalog.state.collectAsStateWithLifecycle().value.shop

    var name by rememberSaveable { mutableStateOf(profile?.name ?: "") }
    var phoneDigits by rememberSaveable { mutableStateOf(localPhoneDigits(profile?.phone ?: "")) }

    val cleanName = name.trim().split(Regex("\\s+")).joinToString(" ")
    val phone = fullPhone(phoneDigits)
    val canSave = cleanName.isNotEmpty() && phone != null

    val save: () -> Unit = {
        if (cleanName.isNotEmpty() && phone != null) {
            container.account.saveProfile(cleanName, phone)
            onBack()
        }
    }

    Scaffold(
        modifier = Modifier.imePadding(),
        containerColor = MaterialTheme.colorScheme.background,
        topBar = { BackTopBar(title = "Profil", onBack = onBack) },
        bottomBar = {
            BottomActionBar {
                BigButton(text = "Saqlash", onClick = save, enabled = canSave)
            }
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                text = "Buyurtmani yetkazishda kuryer shu ism va raqam orqali siz bilan bog'lanadi.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            OutlinedTextField(
                value = name,
                onValueChange = { name = it.take(MAX_NAME_LENGTH) },
                label = { Text("Ismingiz") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                shape = MaterialTheme.shapes.medium,
                keyboardOptions = KeyboardOptions(
                    capitalization = KeyboardCapitalization.Words,
                    imeAction = ImeAction.Next,
                ),
            )
            OutlinedTextField(
                value = phoneDigits,
                onValueChange = { phoneDigits = localPhoneDigits(it) },
                label = { Text("Telefon raqam") },
                prefix = { Text("+998 ") },
                placeholder = { Text("90 123 45 67") },
                supportingText = {
                    if (phoneDigits.isNotEmpty() && phoneDigits.length < LOCAL_PHONE_LENGTH) {
                        Text("Raqamni to'liq kiriting: 9 ta raqam")
                    }
                },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                shape = MaterialTheme.shapes.medium,
                visualTransformation = PhoneVisualTransformation,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Phone,
                    imeAction = ImeAction.Done,
                ),
                keyboardActions = KeyboardActions(onDone = { save() }),
            )

            val cafePhone = shop?.phone
            if (!cafePhone.isNullOrBlank()) {
                Spacer(Modifier.height(4.dp))
                SectionCard {
                    Text(
                        text = "Kafe bilan bog'lanish",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    TextButton(onClick = { dialPhone(context, cafePhone) }) {
                        Text(formatPhone(cafePhone), style = MaterialTheme.typography.titleMedium)
                    }
                }
            }

            Text(
                text = "Amora · ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
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
