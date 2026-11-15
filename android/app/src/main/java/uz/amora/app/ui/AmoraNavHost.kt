package uz.amora.app.ui

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
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
    const val MENU = "menu"
    const val CART = "cart"
    const val ADDRESS = "address"
    const val PROFILE = "profile"
    const val ORDERS = "orders"
    const val ORDER = "order/{id}"

    fun order(id: Int) = "order/$id"
}

/** Ekranlar orasidagi o'tishlar. Boshlang'ich ekran: menyu. */
@Composable
fun AmoraNavHost(container: AppContainer) {
    val nav = rememberNavController()

    NavHost(navController = nav, startDestination = Routes.MENU) {
        composable(Routes.MENU) {
            MenuScreen(
                container = container,
                onOpenCart = { nav.navigate(Routes.CART) },
                onOpenOrders = { nav.navigate(Routes.ORDERS) },
                onOpenProfile = { nav.navigate(Routes.PROFILE) },
                onOpenOrder = { id -> nav.navigate(Routes.order(id)) },
            )
        }
        composable(Routes.CART) {
            CartScreen(
                container = container,
                onBack = { nav.goBack() },
                onPickAddress = { nav.navigate(Routes.ADDRESS) },
                onEditProfile = { nav.navigate(Routes.PROFILE) },
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
        composable(Routes.PROFILE) {
            ProfileScreen(container = container, onBack = { nav.goBack() })
        }
        composable(Routes.ORDERS) {
            OrdersScreen(
                container = container,
                onBack = { nav.goBack() },
                onOpenOrder = { id -> nav.navigate(Routes.order(id)) },
            )
        }
        composable(
            route = Routes.ORDER,
            arguments = listOf(navArgument("id") { type = NavType.IntType }),
        ) { entry ->
            val orderId = entry.arguments?.getInt("id") ?: 0
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

/** Tugma ikki marta bosilsa ham boshlang'ich ekrandan chiqib ketmaydi. */
private fun NavHostController.goBack() {
    if (previousBackStackEntry != null) popBackStack()
}
