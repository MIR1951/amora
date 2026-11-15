from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models import Category, Order, OrderStatus, Product, ShopSettings
from app.telegram.texts import (
    REJECT_REASONS,
    google_maps_url,
    product_button_label,
    yandex_maps_url,
)


class OrderCb(CallbackData, prefix="o"):
    """Guruhdagi buyurtma xabari tugmalari."""

    id: int
    action: str  # accept | go | done | reject | back | reason
    reason: int = 0


class AdminCb(CallbackData, prefix="a"):
    """Admin bo'limi tugmalari."""

    action: str
    id: int = 0
    value: str = ""


def _btn(text: str, callback: CallbackData) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback.pack())


# ---------- Buyurtma ----------


def _map_row(order: Order) -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton(
            text="📍 Google xarita", url=google_maps_url(order.latitude, order.longitude)
        ),
        InlineKeyboardButton(
            text="📍 Yandex xarita", url=yandex_maps_url(order.latitude, order.longitude)
        ),
    ]


def order_keyboard(order: Order) -> InlineKeyboardMarkup | None:
    """Buyurtma holatiga mos tugmalar. Tugallangan buyurtmada tugma qolmaydi."""
    status = order.status_enum
    reject = _btn("❌ Rad etish", OrderCb(id=order.id, action="reject"))
    if status == OrderStatus.NEW:
        actions = [_btn("✅ Qabul qilish", OrderCb(id=order.id, action="accept")), reject]
    elif status == OrderStatus.ACCEPTED:
        actions = [_btn("🚗 Yo'lga chiqdi", OrderCb(id=order.id, action="go")), reject]
    elif status == OrderStatus.DELIVERING:
        actions = [_btn("✅ Yetkazildi", OrderCb(id=order.id, action="done")), reject]
    else:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[actions, _map_row(order)])


def reject_reasons_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Rad etish sababini tanlash. Tasodifan bosilgan "Rad etish"dan ham himoya qiladi."""
    rows = [
        [_btn(reason, OrderCb(id=order_id, action="reason", reason=index))]
        for index, reason in enumerate(REJECT_REASONS)
    ]
    rows.append([_btn("⬅️ Orqaga", OrderCb(id=order_id, action="back"))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------- Admin ----------

BACK_TO_MAIN = _btn("⬅️ Bosh menyu", AdminCb(action="main"))


def main_menu_keyboard(shop: ShopSettings) -> InlineKeyboardMarkup:
    toggle = (
        _btn("⏸ Buyurtma qabul qilishni to'xtatish", AdminCb(action="pause"))
        if shop.is_accepting_orders
        else _btn("▶️ Buyurtma qabul qilishni yoqish", AdminCb(action="resume"))
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("🍽 Menyu", AdminCb(action="menu")), _btn("📂 Kategoriyalar", AdminCb(action="cats"))],
            [_btn("⚙️ Sozlamalar", AdminCb(action="settings")), _btn("📊 Bugungi hisobot", AdminCb(action="report"))],
            [toggle],
        ]
    )


def menu_keyboard(products: list[Product]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for product in products:
        builder.row(_btn(product_button_label(product), AdminCb(action="prod", id=product.id)))
    builder.row(_btn("➕ Taom qo'shish", AdminCb(action="prod_add")))
    builder.row(BACK_TO_MAIN)
    return builder.as_markup()


def product_keyboard(product: Product) -> InlineKeyboardMarkup:
    pid = product.id
    toggle = (
        _btn("⛔ Tugadi deb belgilash", AdminCb(action="prod_off", id=pid))
        if product.is_available
        else _btn("✅ Yana bor deb belgilash", AdminCb(action="prod_on", id=pid))
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [toggle],
            [
                _btn("✏️ Nomi", AdminCb(action="prod_edit", id=pid, value="name")),
                _btn("💰 Narxi", AdminCb(action="prod_edit", id=pid, value="price")),
            ],
            [
                _btn("📝 Tavsifi", AdminCb(action="prod_edit", id=pid, value="description")),
                _btn("🖼 Rasmi", AdminCb(action="prod_edit", id=pid, value="photo")),
            ],
            [
                _btn("📂 Kategoriyasi", AdminCb(action="prod_cat", id=pid)),
                _btn("🗑 O'chirish", AdminCb(action="prod_del", id=pid)),
            ],
            [_btn("⬅️ Menyuga qaytish", AdminCb(action="menu"))],
        ]
    )


def confirm_delete_keyboard(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn("🗑 Ha, o'chirilsin", AdminCb(action="prod_del_yes", id=product_id)),
                _btn("⬅️ Yo'q", AdminCb(action="prod", id=product_id)),
            ]
        ]
    )


def choose_category_keyboard(
    categories: list[Category], action: str, product_id: int = 0
) -> InlineKeyboardMarkup:
    """Kategoriya tanlash: mavjud taom uchun ham, yangi taom qo'shishda ham ishlatiladi."""
    builder = InlineKeyboardBuilder()
    for category in categories:
        builder.row(
            _btn(category.name, AdminCb(action=action, id=product_id, value=str(category.id)))
        )
    builder.row(_btn("Kategoriyasiz", AdminCb(action=action, id=product_id, value="0")))
    return builder.as_markup()


def categories_keyboard(categories: list[Category]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in categories:
        builder.row(_btn(f"📂 {category.name}", AdminCb(action="cat", id=category.id)))
    builder.row(_btn("➕ Kategoriya qo'shish", AdminCb(action="cat_add")))
    builder.row(BACK_TO_MAIN)
    return builder.as_markup()


def category_keyboard(category_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn("✏️ Nomini o'zgartirish", AdminCb(action="cat_rename", id=category_id)),
                _btn("🗑 O'chirish", AdminCb(action="cat_del", id=category_id)),
            ],
            [_btn("⬅️ Kategoriyalar", AdminCb(action="cats"))],
        ]
    )


SETTING_BUTTONS = [
    ("🚚 Yetkazish narxi", "delivery_fee"),
    ("🎁 Bepul yetkazish chegarasi", "free_delivery_from"),
    ("🧾 Eng kam buyurtma", "min_order_amount"),
    ("📏 Yetkazish masofasi", "max_delivery_km"),
    ("🕐 Ish vaqti", "hours"),
    ("📞 Kafe telefoni", "phone"),
    ("📍 Kafe joylashuvi", "location"),
]


def settings_keyboard() -> InlineKeyboardMarkup:
    rows = [[_btn(label, AdminCb(action="set", value=key))] for label, key in SETTING_BUTTONS]
    rows.append([BACK_TO_MAIN])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_keyboard(back: AdminCb) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("❌ Bekor qilish", back)]])


def skip_keyboard(action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("⏭ O'tkazib yuborish", AdminCb(action=action))],
            [_btn("❌ Bekor qilish", AdminCb(action="menu"))],
        ]
    )


def back_keyboard(back: AdminCb, label: str = "⬅️ Orqaga") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(label, back)]])
