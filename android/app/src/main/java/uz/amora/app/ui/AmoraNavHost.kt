package uz.amora.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Modifier
import androidx.lifecycle.Lifecycle
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import uz.amora.app.AppContainer
import uz.amora.app.ui.address.AddressScreen
import uz.amora.app.ui.cart.CartScreen
import uz.amora.app.ui.components.screenEnter
import uz.amora.app.ui.components.screenExit
import uz.amora.app.ui.components.screenPopEnter
import uz.amora.app.ui.components.screenPopExit
import uz.amora.app.ui.menu.MenuScreen
import uz.amora.app.ui.order.OrderScreen
import uz.amora.app.ui.orders.OrdersScreen
import uz.amora.app.ui.profile.ProfileScreen

private object Routes {
    // Bosh sahifa: menyu. Qolgan hamma ekran uning ustiga ochiladi va "orqaga" bilan yopiladi.
    const val MENU = "menu"
    const val ORDERS = "orders"
    const val PROFILE = "profile"
    const val CART = "cart"
    const val ADDRESS = "address"
    const val PROFILE_EDIT = "profile/edit"
    const val ORDER = "order/{id}"

    fun order(id: Int) = "order/$id"
}

/**
 * Ekranlar orasidagi o'tishlar. Boshlang'ich ekran: menyu.
 * Hamma o'tish bir xil: yangi ekran o'ngdan sirpanib kiradi, orqaga qaytganda o'ngga chiqib ketadi.
 */
@Composable
fun AmoraNavHost(
    container: AppContainer,
    openOrderId: Int? = null,
    onOrderOpened: () -> Unit = {},
) {
    val nav = rememberNavController()

    // Bildirishnoma bosildi: o'sha buyurtma ochiladi, undan "orqaga" menyuga qaytaradi
    LaunchedEffect(openOrderId) {
        if (openOrderId != null) {
            nav.navigate(Routes.order(openOrderId)) {
                popUpTo(Routes.MENU)
                launchSingleTop = true
            }
            onOrderOpened()
        }
    }

    NavHost(
        navController = nav,
        startDestination = Routes.MENU,
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background),
        enterTransition = screenEnter,
        exitTransition = screenExit,
        popEnterTransition = screenPopEnter,
        popExitTransition = screenPopExit,
    ) {
        composable(Routes.MENU) {
            MenuScreen(
                container = container,
                onOpenCart = { nav.open(Routes.CART) },
                onOpenOrders = { nav.open(Routes.ORDERS) },
                onOpenProfile = { nav.open(Routes.PROFILE) },
                onOpenOrder = { id -> nav.open(Routes.order(id)) },
            )
        }
        composable(Routes.ORDERS) {
            OrdersScreen(
                container = container,
                onBack = { nav.goBack() },
                onOpenOrder = { id -> nav.open(Routes.order(id)) },
                onOpenCart = { nav.openCartFromOrders() },
            )
        }
        composable(Routes.PROFILE) {
            ProfileScreen(
                container = container,
                onBack = { nav.goBack() },
                onPickAddress = { nav.open(Routes.ADDRESS) },
            )
        }
        composable(Routes.CART) {
            CartScreen(
                container = container,
                onBack = { nav.goBack() },
                onPickAddress = { nav.open(Routes.ADDRESS) },
                onEditProfile = { nav.open(Routes.PROFILE_EDIT) },
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
                onPickAddress = { nav.open(Routes.ADDRESS) },
                quickEdit = true,
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
                onOpenCart = { nav.openCartFromOrders() },
            )
        }
    }
}

/**
 * Tugma bosilganda yangi ekran ochadi. O'tish animatsiyasi tugamaguncha ikkinchi bosish
 * hisobga olinmaydi: bitta ekran ikki marta ochilib qolmaydi.
 */
private fun NavHostController.open(route: String) {
    if (currentBackStackEntry?.lifecycle?.currentState == Lifecycle.State.RESUMED) {
        navigate(route) { launchSingleTop = true }
    }
}

/** "Yana shunday buyurtma": savat ochiladi, undan "orqaga" bosilsa menyuga qaytiladi. */
private fun NavHostController.openCartFromOrders() {
    navigate(Routes.CART) {
        popUpTo(Routes.MENU)
        launchSingleTop = true
    }
}

/** Tugma ikki marta bosilsa ham boshlang'ich ekrandan chiqib ketmaydi. */
private fun NavHostController.goBack() {
    if (previousBackStackEntry != null) popBackStack()
}
