package uz.amora.app.ui.profile

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.SystemClock
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import uz.amora.app.AppContainer
import uz.amora.app.R
import uz.amora.app.data.ApiException
import uz.amora.app.data.Profile
import uz.amora.app.data.VerificationResult
import uz.amora.app.ui.components.BigButton
import uz.amora.app.ui.components.IconTile
import uz.amora.app.ui.components.SectionCard
import uz.amora.app.ui.components.SoftButton
import uz.amora.app.ui.theme.success
import uz.amora.app.ui.theme.successContainer
import uz.amora.app.util.formatPhone

enum class VerifyStep { Idle, Starting, Waiting, Done }

data class VerifyUiState(
    val step: VerifyStep = VerifyStep.Idle,
    val appUrl: String? = null,
    val botUrl: String? = null,
    val error: String? = null,
    // Telegram ochilishi kerak (bir martalik hodisa: ochilgach telegramOpened() bilan o'chadi)
    val pendingOpen: Boolean = false,
)

/**
 * Raqamni Telegram orqali tasdiqlash: serverdan kod olinadi, bot ochiladi, mijoz u yerda
 * "📱 Raqamni yuborish" ni bosadi. Ilova shu orada natijani bir necha soniyada bir so'rab turadi
 * va mijoz ilovaga qaytganda darhol tekshiradi.
 */
class PhoneVerificationViewModel(private val container: AppContainer) : ViewModel() {
    private val _state = MutableStateFlow(VerifyUiState())
    val state: StateFlow<VerifyUiState> = _state.asStateFlow()

    private var code: String? = null
    private var pollJob: Job? = null
    private val checkLock = Mutex()

    fun start(name: String?) {
        val step = _state.value.step
        if (step == VerifyStep.Starting || step == VerifyStep.Waiting) return
        _state.update { it.copy(step = VerifyStep.Starting, error = null) }
        viewModelScope.launch {
            try {
                val started = container.account.startVerification(name?.takeIf { it.isNotBlank() })
                code = started.code
                _state.update {
                    it.copy(
                        step = VerifyStep.Waiting,
                        appUrl = started.appUrl,
                        botUrl = started.botUrl,
                        pendingOpen = true,
                    )
                }
                poll(started.expiresIn)
            } catch (e: ApiException) {
                _state.update { it.copy(step = VerifyStep.Idle, error = e.message) }
            }
        }
    }

    private fun poll(expiresInSeconds: Int) {
        pollJob?.cancel()
        val deadline = SystemClock.elapsedRealtime() + expiresInSeconds * 1000L
        pollJob = viewModelScope.launch {
            while (isActive && SystemClock.elapsedRealtime() < deadline) {
                delay(POLL_MS)
                if (checkOnce()) return@launch
            }
            if (_state.value.step == VerifyStep.Waiting) {
                _state.update {
                    it.copy(step = VerifyStep.Idle, error = "Vaqt tugadi. Qaytadan urinib ko'ring")
                }
            }
        }
    }

    /** Natijani bir marta so'raydi. Kutish tugagan bo'lsa (tasdiqlandi yoki eskirdi) true. */
    private suspend fun checkOnce(): Boolean = checkLock.withLock {
        val current = code
        if (_state.value.step != VerifyStep.Waiting || current == null) return true
        try {
            when (container.account.checkVerification(current)) {
                is VerificationResult.Verified -> {
                    _state.update { it.copy(step = VerifyStep.Done, error = null) }
                    true
                }
                VerificationResult.Pending -> false
            }
        } catch (e: ApiException) {
            if (e.isNetwork) return false // internet qaytgach yana so'raladi
            _state.update { it.copy(step = VerifyStep.Idle, error = e.message) }
            true
        }
    }

    /** Mijoz Telegram'dan qaytdi: kutmasdan tekshiramiz. */
    fun checkNow() {
        if (_state.value.step != VerifyStep.Waiting) return
        viewModelScope.launch {
            if (checkOnce()) pollJob?.cancel()
        }
    }

    fun reopenTelegram() {
        _state.update { it.copy(pendingOpen = true) }
    }

    fun telegramOpened() {
        _state.update { it.copy(pendingOpen = false) }
    }

    fun cancel() {
        pollJob?.cancel()
        code = null
        _state.update { it.copy(step = VerifyStep.Idle, pendingOpen = false) }
    }

    fun clearError() {
        _state.update { it.copy(error = null) }
    }

    fun consumeDone() {
        _state.update { it.copy(step = VerifyStep.Idle) }
    }

    private companion object {
        const val POLL_MS = 2_000L
    }
}

/** Telegram ilovasini bot bilan ochadi; o'rnatilmagan bo'lsa brauzerda t.me sahifasini. */
private fun openTelegram(context: Context, appUrl: String?, botUrl: String?): Boolean {
    for (url in listOfNotNull(appUrl, botUrl)) {
        try {
            context.startActivity(
                Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
            )
            return true
        } catch (e: ActivityNotFoundException) {
            // keyingi havolani sinaymiz
        }
    }
    return false
}

/**
 * Profil ekranidagi raqam bo'limi: tasdiqlangan raqam yoki "Telegram orqali tasdiqlash" tugmasi.
 * `name`: mijoz yozgan ism (yangi hisob shu ism bilan ochiladi).
 */
@Composable
fun PhoneVerificationSection(
    container: AppContainer,
    profile: Profile?,
    name: String,
    snackbar: SnackbarHostState,
    onVerified: () -> Unit,
) {
    val vm: PhoneVerificationViewModel = viewModel(
        factory = viewModelFactory { initializer { PhoneVerificationViewModel(container) } },
    )
    val state = vm.state.collectAsStateWithLifecycle().value
    val context = LocalContext.current
    val scheme = MaterialTheme.colorScheme

    LaunchedEffect(state.pendingOpen) {
        if (state.pendingOpen) {
            // Avval o'chiramiz: ekran qayta chizilsa yoki aylantirilsa Telegram ikkinchi marta ochilmaydi
            vm.telegramOpened()
            if (!openTelegram(context, state.appUrl, state.botUrl)) {
                snackbar.showSnackbar("Telegram topilmadi. Uni o'rnatib, qaytadan urinib ko'ring")
            }
        }
    }
    LaunchedEffect(state.error) {
        val error = state.error
        if (error != null) {
            snackbar.showSnackbar(error)
            vm.clearError()
        }
    }
    LaunchedEffect(state.step) {
        if (state.step == VerifyStep.Done) {
            vm.consumeDone()
            onVerified()
        }
    }
    // Telegram'dan qaytganda natija darhol tekshiriladi
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) vm.checkNow()
        }
        lifecycle.addObserver(observer)
        onDispose { lifecycle.removeObserver(observer) }
    }

    when {
        state.step == VerifyStep.Waiting -> SectionCard {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    CircularProgressIndicator(modifier = Modifier.size(26.dp), strokeWidth = 3.dp)
                    Spacer(Modifier.width(14.dp))
                    Text(
                        text = "Telegram'da «📱 Raqamni yuborish» tugmasini bosing, so'ng shu yerga qayting",
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.weight(1f),
                    )
                }
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    SoftButton(
                        text = "Telegramni ochish",
                        onClick = vm::reopenTelegram,
                        icon = R.drawable.ic_send,
                        accent = true,
                        modifier = Modifier.weight(1f),
                    )
                    SoftButton(text = "Bekor qilish", onClick = vm::cancel, modifier = Modifier.weight(1f))
                }
            }
        }

        profile != null && profile.verified -> SectionCard {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconTile(
                    icon = R.drawable.ic_check,
                    container = scheme.successContainer,
                    tint = scheme.success,
                )
                Spacer(Modifier.width(14.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(text = formatPhone(profile.phone), style = MaterialTheme.typography.titleMedium)
                    Text(
                        text = "Telegram orqali tasdiqlangan",
                        style = MaterialTheme.typography.bodySmall,
                        color = scheme.success,
                    )
                }
                SoftButton(
                    text = "Almashtirish",
                    onClick = { vm.start(name) },
                    enabled = state.step == VerifyStep.Idle,
                )
            }
        }

        else -> SectionCard {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(
                    text = "Raqamingizni Telegram orqali tasdiqlang: kuryer shu raqamga qo'ng'iroq qiladi. " +
                        "Boshqa telefondan kirsangiz ham buyurtmalaringiz saqlanib qoladi.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = scheme.onSurfaceVariant,
                )
                BigButton(
                    text = "Telegram orqali tasdiqlash",
                    onClick = { vm.start(name) },
                    enabled = name.isNotBlank(),
                    loading = state.step == VerifyStep.Starting,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        }
    }
}
