"""Telegram xabarlari matni. Hamma joyda HTML formatlash ishlatiladi."""

from datetime import datetime
from html import escape as _html_escape
from zoneinfo import ZoneInfo

from app.models import Order, OrderStatus, Product, ShopSettings
from app.services.orders import CUSTOMER_ACTOR
from app.services.shop import format_sum

def escape(value: str) -> str:
    """Telegram HTML uchun faqat <, > va & almashtiriladi. Tutuq belgisi (o', g') o'z holicha qoladi."""
    return _html_escape(value, quote=False)


STATUS_EMOJI = {
    OrderStatus.NEW: "🆕",
    OrderStatus.ACCEPTED: "👨‍🍳",
    OrderStatus.DELIVERING: "🚗",
    OrderStatus.DELIVERED: "✅",
    OrderStatus.REJECTED: "❌",
    OrderStatus.CANCELLED: "🚫",
}

# Guruhdagi xabar sarlavhasi
STATUS_TITLE = {
    OrderStatus.NEW: "Yangi buyurtma",
    OrderStatus.ACCEPTED: "Tayyorlanmoqda",
    OrderStatus.DELIVERING: "Kuryer yo'lda",
    OrderStatus.DELIVERED: "Yetkazildi",
    OrderStatus.REJECTED: "Rad etildi",
    OrderStatus.CANCELLED: "Mijoz bekor qildi",
}

# Tarix qatorlari: kim nima qildi
HISTORY_VERB = {
    OrderStatus.NEW: "Buyurtma berildi",
    OrderStatus.ACCEPTED: "Qabul qildi",
    OrderStatus.DELIVERING: "Yo'lga chiqardi",
    OrderStatus.DELIVERED: "Yetkazildi deb belgiladi",
    OrderStatus.REJECTED: "Rad etdi",
    OrderStatus.CANCELLED: "Mijoz bekor qildi",
}

REJECT_REASONS = [
    "Mahsulot tugadi",
    "Kafe juda band",
    "Manzil juda uzoq",
    "Mijoz bilan bog'lanib bo'lmadi",
    "Soxta buyurtma",
]


def local_time(moment: datetime, tz_name: str) -> str:
    return moment.astimezone(ZoneInfo(tz_name)).strftime("%H:%M")


def google_maps_url(latitude: float, longitude: float) -> str:
    return f"https://www.google.com/maps?q={latitude:.6f},{longitude:.6f}"


def yandex_maps_url(latitude: float, longitude: float) -> str:
    # Yandex'da tartib teskari: avval uzunlik, keyin kenglik
    point = f"{longitude:.6f},{latitude:.6f}"
    return f"https://yandex.com/maps/?pt={point}&z=17&l=map"


def order_text(order: Order, tz_name: str) -> str:
    status = order.status_enum
    lines = [f"{STATUS_EMOJI[status]} <b>№{order.id} · {STATUS_TITLE[status]}</b>", ""]

    for item in order.items:
        lines.append(f"{item.quantity} × {escape(item.name)} — {format_sum(item.line_total)}")
    lines.append("")
    lines.append(f"Taomlar: {format_sum(order.items_total)}")
    delivery = format_sum(order.delivery_fee) if order.delivery_fee else "bepul"
    lines.append(f"Yetkazish: {delivery}")
    lines.append(f"<b>Jami: {format_sum(order.total)}</b> (naqd)")
    lines.append("")

    lines.append(f"👤 {escape(order.customer_name)}")
    lines.append(f"📞 {escape(order.phone)}")
    address = escape(order.address_note) if order.address_note else "xaritada ko'rsatilgan"
    if order.distance_km is not None:
        address += f" (kafedan {order.distance_km:.1f} km)"
    lines.append(f"📍 {address}")
    if order.comment:
        lines.append(f"💬 {escape(order.comment)}")
    lines.append("")

    for event in order.history:
        event_status = OrderStatus(event.status)
        verb = HISTORY_VERB[event_status]
        who = ""
        if event.actor and event.actor != CUSTOMER_ACTOR:
            who = f": {escape(event.actor)}"
        lines.append(f"🕐 {local_time(event.created_at, tz_name)} {verb}{who}")
    if status == OrderStatus.REJECTED and order.reject_reason:
        lines.append(f"Sabab: {escape(order.reject_reason)}")

    return "\n".join(lines)


def cancelled_notice(order: Order) -> str:
    return f"🚫 №{order.id} buyurtmani mijoz bekor qildi."


# ---------- Admin bo'limi ----------


def availability_mark(product: Product) -> str:
    return "✅" if product.is_available else "⛔"


def product_button_label(product: Product) -> str:
    return f"{availability_mark(product)} {product.name} · {format_sum(product.price)}"


def product_card(product: Product, category_name: str | None) -> str:
    state = "bor" if product.is_available else "tugagan (mijozlar buyurtma bera olmaydi)"
    category = escape(category_name) if category_name else "yo'q"
    image = "bor" if product.image_path else "qo'yilmagan"
    lines = [
        f"🍽 <b>{escape(product.name)}</b>",
        f"Narxi: {format_sum(product.price)}",
        f"Holati: {availability_mark(product)} {state}",
        f"Kategoriya: {category}",
        f"Rasm: {image}",
    ]
    if product.description:
        lines += ["", escape(product.description)]
    return "\n".join(lines)


def hours_text(shop: ShopSettings) -> str:
    if shop.open_time == shop.close_time:
        return "kecha-kunduz"
    return f"{shop.open_time:%H:%M}–{shop.close_time:%H:%M}"


def main_menu_text(shop: ShopSettings, is_open: bool) -> str:
    if not shop.is_accepting_orders:
        state = "⏸ Buyurtma qabul qilish to'xtatilgan"
    elif is_open:
        state = "✅ Buyurtmalar qabul qilinmoqda"
    else:
        state = "🌙 Hozir ish vaqti emas"
    return f"<b>{escape(shop.cafe_name)} boshqaruvi</b>\n\n{state}\nIsh vaqti: {hours_text(shop)}"


def settings_text(shop: ShopSettings) -> str:
    free_from = (
        f"{format_sum(shop.free_delivery_from)} dan" if shop.free_delivery_from else "yo'q"
    )
    min_order = format_sum(shop.min_order_amount) if shop.min_order_amount else "yo'q"
    radius = f"{shop.max_delivery_km:g} km gacha" if shop.max_delivery_km else "cheklanmagan"
    has_location = shop.cafe_latitude is not None and shop.cafe_longitude is not None
    location = "belgilangan" if has_location else "belgilanmagan"
    lines = [
        "⚙️ <b>Sozlamalar</b>",
        "",
        f"Yetkazish narxi: {format_sum(shop.delivery_fee) if shop.delivery_fee else 'bepul'}",
        f"Bepul yetkazish chegarasi: {free_from}",
        f"Eng kam buyurtma: {min_order}",
        f"Yetkazish masofasi: {radius}",
        f"Ish vaqti: {hours_text(shop)}",
        f"Kafe telefoni: {escape(shop.phone) if shop.phone else 'yozilmagan'}",
        f"Kafe joylashuvi: {location}",
    ]
    if shop.max_delivery_km and not has_location:
        lines += ["", "⚠️ Masofa chegarasi ishlashi uchun kafe joylashuvini belgilang."]
    return "\n".join(lines)


HELP_TEXT = (
    "<b>Buyruqlar</b>\n"
    "/start — boshqaruv menyusi\n"
    "/blok 901234567 — raqamni bloklash (soxta buyurtma bergan mijoz)\n"
    "/ochish 901234567 — raqamni blokdan chiqarish\n"
    "/id — shu chat va sizning Telegram ID raqamingiz\n"
    "/bekor — boshlangan amalni bekor qilish"
)
