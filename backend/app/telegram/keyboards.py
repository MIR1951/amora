from aiogram.filters.callback_data import CallbackData
from urllib.parse import urlencode

from aiogram.types import (
    CopyTextButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models import Category, Order, OrderStatus, Product, ShopSettings, Staff
from app.services.reports import PERIODS
from app.telegram.texts import (
    REJECT_REASONS,
    VERIFY_SHARE_BUTTON,
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


def main_menu_keyboard(shop: ShopSettings, role: str = "owner") -> InlineKeyboardMarkup:
    toggle = (
        _btn("⏸ Buyurtma qabul qilishni to'xtatish", AdminCb(action="pause"))
        if shop.is_accepting_orders
        else _btn("▶️ Buyurtma qabul qilishni yoqish", AdminCb(action="resume"))
    )
    report = _btn("📊 Hisobot", AdminCb(action="report"))
    if role == "staff":
        rows = [[_btn("🍽 Menyu", AdminCb(action="menu")), report], [toggle]]
    else:
        rows = [
            [_btn("🍽 Menyu", AdminCb(action="menu")), _btn("📂 Kategoriyalar", AdminCb(action="cats"))],
            [_btn("⚙️ Sozlamalar", AdminCb(action="settings")), report],
            [
                _btn("🎉 Aksiyalar", AdminCb(action="promo")),
                _btn("👥 Xodimlar", AdminCb(action="team")),
            ],
            [toggle],
        ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def menu_keyboard(products: list[Product], full: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for product in products:
        builder.row(_btn(product_button_label(product), AdminCb(action="prod", id=product.id)))
    if full:
        builder.row(_btn("➕ Taom qo'shish", AdminCb(action="prod_add")))
    builder.row(BACK_TO_MAIN)
    return builder.as_markup()


def product_keyboard(product: Product, full: bool = True) -> InlineKeyboardMarkup:
    pid = product.id
    toggle = (
        _btn("⛔ Tugadi deb belgilash", AdminCb(action="prod_off", id=pid))
        if product.is_available
        else _btn("✅ Yana bor deb belgilash", AdminCb(action="prod_on", id=pid))
    )
    if not full:
        return InlineKeyboardMarkup(
            inline_keyboard=[[toggle], [_btn("⬅️ Menyuga qaytish", AdminCb(action="menu"))]]
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
    ("⏰ Qabul qilinmasa eslatma", "alert_accept"),
    ("⏰ Yo'lda uzoq qolsa eslatma", "alert_delivery"),
    ("📊 Kunlik hisobot", "daily_report"),
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


# ---------- Hisobot ----------


def report_keyboard(current: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, title in PERIODS.items():
        label = f"• {title} •" if key == current else title
        builder.button(text=label, callback_data=AdminCb(action="rep", value=key).pack())
    builder.adjust(2, 2, 1)
    builder.row(BACK_TO_MAIN)
    return builder.as_markup()


def daily_report_keyboard(current: str) -> InlineKeyboardMarkup:
    options = [("Guruhga", "group"), ("Adminlarga", "admins"), ("Yuborilmasin", "off")]
    row = [
        _btn(f"✅ {label}" if value == current else label, AdminCb(action="set_report", value=value))
        for label, value in options
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[row, [_btn("⬅️ Sozlamalar", AdminCb(action="settings"))]]
    )


# ---------- Mijoz kartasi ----------


def customer_keyboard(phone: str, blocked: bool, can_block: bool) -> InlineKeyboardMarkup:
    rows = []
    if can_block:
        if blocked:
            rows.append([_btn("✅ Blokdan chiqarish", AdminCb(action="cust_unblock", value=phone))])
        else:
            rows.append([_btn("🚫 Bloklash", AdminCb(action="cust_block", value=phone))])
    rows.append([BACK_TO_MAIN])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------- Xodimlar ----------


def invite_keyboard(link: str, share_text: str) -> InlineKeyboardMarkup:
    """Taklif havolasini yuborish va nusxa olish tugmalari.

    Havolani ochadigan tugma ataylab yo'q: egasi uni o'zi bosib yubormasin.
    """
    share_url = "https://t.me/share/url?" + urlencode({"url": link, "text": share_text})
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📤 Havolani yuborish", url=share_url)],
            [InlineKeyboardButton(text="📋 Nusxa olish", copy_text=CopyTextButton(text=link))],
            [_btn("⬅️ Xodimlar", AdminCb(action="team"))],
        ]
    )


def team_keyboard(members: list[Staff], can_manage_admins: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for member in members:
        if member.role == "admin" and not can_manage_admins:
            continue
        builder.row(_btn(f"🗑 {member.name}", AdminCb(action="team_del", id=member.id)))
    if can_manage_admins:
        builder.row(_btn("➕ Admin qo'shish", AdminCb(action="team_inv", value="admin")))
    builder.row(_btn("➕ Xodim qo'shish", AdminCb(action="team_inv", value="staff")))
    builder.row(BACK_TO_MAIN)
    return builder.as_markup()


def confirm_remove_keyboard(member_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn("🗑 Ha, olib tashlansin", AdminCb(action="team_del_yes", id=member_id)),
                _btn("⬅️ Yo'q", AdminCb(action="team")),
            ]
        ]
    )


# ---------- Aksiyalar ----------


def promo_menu_keyboard(codes: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_btn("🖼 Bosh sahifadagi banner", AdminCb(action="ban")))
    builder.row(_btn("🆕 Birinchi buyurtma chegirmasi", AdminCb(action="auto")))
    for promo in codes:
        mark = "🟢" if promo.is_active else "⚪️"
        builder.row(_btn(f"{mark} {promo.code}", AdminCb(action="pc", id=promo.id)))
    builder.row(_btn("➕ Promokod qo'shish", AdminCb(action="pc_add")))
    builder.row(_btn("📣 Mijozlarga xabar yuborish", AdminCb(action="bc")))
    builder.row(BACK_TO_MAIN)
    return builder.as_markup()


BACK_TO_PROMO = _btn("⬅️ Aksiyalar", AdminCb(action="promo"))


def banner_keyboard(has_custom: bool) -> InlineKeyboardMarkup:
    rows = [
        [_btn("✏️ Sarlavha", AdminCb(action="ban_edit", value="title"))],
        [_btn("✏️ Pastki matn", AdminCb(action="ban_edit", value="text"))],
    ]
    if has_custom:
        rows.append([_btn("↩️ Standart matnga qaytarish", AdminCb(action="ban_reset"))])
    rows.append([BACK_TO_PROMO])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def auto_promo_keyboard(active: bool) -> InlineKeyboardMarkup:
    rows = [[_btn("✏️ Chegirmani belgilash", AdminCb(action="auto_edit"))]]
    if active:
        rows.append([_btn("⏸ O'chirish", AdminCb(action="auto_off"))])
    rows.append([BACK_TO_PROMO])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def promo_card_keyboard(promo) -> InlineKeyboardMarkup:
    toggle = (
        _btn("⏸ To'xtatish", AdminCb(action="pc_off", id=promo.id))
        if promo.is_active
        else _btn("▶️ Yoqish", AdminCb(action="pc_on", id=promo.id))
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [toggle],
            [_btn("🗑 O'chirib tashlash", AdminCb(action="pc_del", id=promo.id))],
            [BACK_TO_PROMO],
        ]
    )


def confirm_promo_delete_keyboard(promo_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("🗑 Ha, o'chirilsin", AdminCb(action="pc_del_yes", id=promo_id))],
            [_btn("⬅️ Yo'q", AdminCb(action="pc", id=promo_id))],
        ]
    )


def promo_audience_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("👥 Hamma mijozlar", AdminCb(action="pc_new", value="0"))],
            [_btn("🆕 Faqat birinchi buyurtma", AdminCb(action="pc_new", value="1"))],
            [_btn("❌ Bekor qilish", AdminCb(action="promo"))],
        ]
    )


def broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("📣 Yuborish", AdminCb(action="bc_send"))],
            [_btn("❌ Bekor qilish", AdminCb(action="promo"))],
        ]
    )


# ---------- Raqamni tasdiqlash ----------


def share_contact_keyboard() -> ReplyKeyboardMarkup:
    """Telegram bu tugma bilan faqat hisob egasining o'z raqamini yuboradi."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=VERIFY_SHARE_BUTTON, request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
