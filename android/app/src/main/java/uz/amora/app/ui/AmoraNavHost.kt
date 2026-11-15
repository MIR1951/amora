package uz.amora.app.ui

import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import uz.amora.app.AppContainer
import uz.amora.app.ui.address.AddressScreen
import uz.amora.app.ui.cart.CartScreen
import uz.amora.app.ui.menu.MenuScreen
import uz.amora.app.ui.order.OrderScreen
import uz.amora.app.ui.orders.OrdersScreen
import uz.amora.app.ui.profile.ProfileScreen

private object Routes {
    // Pastki menyudagi uchta bo'lim
    const val MENU = "menu"
    const val ORDERS = "orders"
    const val PROFILE = "profile"

    // Ustiga ochiladigan ekranlar
    const val CART = "cart"
    const val ADDRESS = "address"
    const val PROFILE_EDIT = "profile/edit"
    const val ORDER = "order/{id}"

    fun order(id: Int) = "order/$id"
}

private data class Tab(val route: String, val label: String, val icon: ImageVector)

private val TABS = listOf(
    Tab(Routes.MENU, "Menyu", Icons.Default.Home),
    Tab(Routes.ORDERS, "Buyurtmalar", Icons.AutoMirrored.Filled.List),
    Tab(Routes.PROFILE, "Profil", Icons.Default.Person),
)

private const val FADE_IN_MS = 220
private const val FADE_OUT_MS = 140

/** Ekranlar orasidagi o'tishlar. Boshlang'ich ekran: menyu. */
@Composable
fun AmoraNavHost(container: AppContainer) {
    val nav = rememberNavController()
    val entry by nav.currentBackStackEntryAsState()
    val route = entry?.destination?.route ?: Routes.MENU
    val showTabs = TABS.any { it.route == route }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        bottomBar = {
            if (showTabs) TabBar(current = route, onSelect = { nav.openTab(it) })
        },
    ) { padding ->
        NavHost(
            navController = nav,
            startDestination = Routes.MENU,
            modifier = Modifier
                .padding(padding)
                .consumeWindowInsets(padding),
            // Ustiga ochiladigan ekranlar o'ngdan ohista kirib keladi, bo'limlar esa shunchaki almashadi
            enterTransition = { fadeIn(tween(FADE_IN_MS)) + slideInHorizontally(tween(FADE_IN_MS)) { it / 12 } },
            exitTransition = { fadeOut(tween(FADE_OUT_MS)) },
            popEnterTransition = { fadeIn(tween(FADE_IN_MS)) },
            popExitTransition = { fadeOut(tween(FADE_OUT_MS)) + slideOutHorizontally(tween(FADE_OUT_MS)) { it / 12 } },
        ) {
            composable(
                route = Routes.MENU,
                enterTransition = { fadeIn(tween(FADE_IN_MS)) },
                popExitTransition = { fadeOut(tween(FADE_OUT_MS)) },
            ) {
                MenuScreen(
                    container = container,
                    onOpenCart = { nav.navigate(Routes.CART) },
                    onPickAddress = { nav.navigate(Routes.ADDRESS) },
                    onOpenOrder = { id -> nav.navigate(Routes.order(id)) },
                )
            }
            composable(
                route = Routes.ORDERS,
                enterTransition = { fadeIn(tween(FADE_IN_MS)) },
                popExitTransition = { fadeOut(tween(FADE_OUT_MS)) },
            ) {
                OrdersScreen(
                    container = container,
                    onOpenMenu = { nav.openTab(Routes.MENU) },
                    onOpenOrder = { id -> nav.navigate(Routes.order(id)) },
                )
            }
            composable(
                route = Routes.PROFILE,
                enterTransition = { fadeIn(tween(FADE_IN_MS)) },
                popExitTransition = { fadeOut(tween(FADE_OUT_MS)) },
            ) {
                ProfileScreen(
                    container = container,
                    onBack = null,
                    onPickAddress = { nav.navigate(Routes.ADDRESS) },
                )
            }
            composable(Routes.CART) {
                CartScreen(
                    container = container,
                    onBack = { nav.goBack() },
                    onPickAddress = { nav.navigate(Routes.ADDRESS) },
                    onEditProfile = { nav.navigate(Routes.PROFILE_EDIT) },
                    onOrderCreated = { id ->
                        // Savat ekrani tarixdan olib tashlanadi: "orqaga" menyuga qaytaradi
                        nav.navigate(Routes.order(id)) {
                            popUpTo(Routes.MENU)
                        }
                    },
                )
            }
            composable(Routes.ADDRESS) {
                AddressScreen(container = container, onBack = { nav.goBack() })
            }
            composable(Routes.PROFILE_EDIT) {
                ProfileScreen(
                    container = container,
                    onBack = { nav.goBack() },
                    onPickAddress = { nav.navigate(Routes.ADDRESS) },
                )
            }
            composable(
                route = Routes.ORDER,
                arguments = listOf(navArgument("id") { type = NavType.IntType }),
            ) { backStackEntry ->
                val orderId = backStackEntry.arguments?.getInt("id") ?: 0
                OrderScreen(
                    container = container,
                    orderId = orderId,
                    onBack = { nav.goBack() },
                    onOpenCart = {
                        nav.navigate(Routes.CART) {
                            popUpTo(Routes.MENU)
                        }
                    },
                )
            }
        }
    }
}

/** Pastki menyu: Menyu, Buyurtmalar, Profil. */
@Composable
private fun TabBar(current: String, onSelect: (String) -> Unit) {
    val scheme = MaterialTheme.colorScheme
    Column {
        HorizontalDivider(color = scheme.outlineVariant, thickness = 1.dp)
        NavigationBar(containerColor = scheme.surface, tonalElevation = 0.dp) {
            for (tab in TABS) {
                NavigationBarItem(
                    selected = tab.route == current,
                    onClick = { onSelect(tab.route) },
                    icon = { Icon(tab.icon, contentDescription = null, modifier = Modifier.size(24.dp)) },
                    label = { Text(tab.label, style = MaterialTheme.typography.labelMedium, maxLines = 1) },
                    colors = NavigationBarItemDefaults.colors(
                        selectedIconColor = scheme.primary,
                        selectedTextColor = scheme.primary,
                        indicatorColor = scheme.primaryContainer,
                        unselectedIconColor = scheme.onSurfaceVariant,
                        unselectedTextColor = scheme.onSurfaceVariant,
                    ),
                )
            }
        }
    }
}

/** Pastki menyudagi bo'limga o'tadi: bo'limlar ustma-ust yig'ilib qolmaydi, "orqaga" menyuga qaytaradi. */
private fun NavHostController.openTab(route: String) {
    navigate(route) {
        popUpTo(Routes.MENU) { saveState = true }
        launchSingleTop = true
        restoreState = true
    }
}

/** Tugma ikki marta bosilsa ham boshlang'ich ekrandan chiqib ketmaydi. */
private fun NavHostController.goBack() {
    if (previousBackStackEntry != null) popBackStack()
}
