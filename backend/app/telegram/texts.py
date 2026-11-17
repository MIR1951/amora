"""Telegram xabarlari matni. Hamma joyda HTML formatlash ishlatiladi."""

from datetime import datetime, timedelta
from html import escape as _html_escape
from zoneinfo import ZoneInfo

from app.models import STATUS_LABELS, Order, OrderStatus, Product, ShopSettings, Staff
from app.services import promos
from app.services.orders import CUSTOMER_ACTOR
from app.services.reports import Report
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
    if order.discount:
        lines.append(f"🎉 Chegirma ({escape(order.promo_code or '')}): −{format_sum(order.discount)}")
    lines.append(f"<b>Jami: {format_sum(order.total)}</b> (naqd)")
    lines.append("")

    customer = f"👤 {escape(order.customer_name)}"
    if order.customer_order_no == 1:
        customer += " · 🆕 yangi mijoz"
    elif order.customer_order_no:
        customer += f" · {order.customer_order_no}-buyurtmasi"
    lines.append(customer)
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


def main_menu_text(shop: ShopSettings, is_open: bool, role: str = "owner") -> str:
    if not shop.is_accepting_orders:
        state = "⏸ Buyurtma qabul qilish to'xtatilgan"
    elif is_open:
        state = "✅ Buyurtmalar qabul qilinmoqda"
    else:
        state = "🌙 Hozir ish vaqti emas"
    text = f"<b>{escape(shop.cafe_name)} boshqaruvi</b>\n\n{state}\nIsh vaqti: {hours_text(shop)}"
    if role == "staff":
        text += "\n\nMijoz haqida bilish uchun: /mijoz 901234567"
    return text


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
        "",
        f"⏰ Qabul qilinmasa eslatma: {minutes_text(shop.alert_accept_minutes)}",
        f"⏰ Yo'lda uzoq qolsa eslatma: {minutes_text(shop.alert_delivery_minutes)}",
        f"📊 Kunlik hisobot: {DAILY_REPORT_TARGETS[shop.daily_report_to]}",
    ]
    if shop.max_delivery_km and not has_location:
        lines += ["", "⚠️ Masofa chegarasi ishlashi uchun kafe joylashuvini belgilang."]
    return "\n".join(lines)


def minutes_text(minutes: int) -> str:
    return f"{minutes} daqiqadan keyin" if minutes else "o'chiq"


DAILY_REPORT_TARGETS = {
    "group": "kafe yopilganda guruhga",
    "admins": "kafe yopilganda adminlarga",
    "off": "yuborilmaydi",
}


def help_text(role: str) -> str:
    lines = [
        "<b>Buyruqlar</b>",
        "/start — boshqaruv menyusi",
        "/mijoz 901234567 — mijoz kartasi: buyurtmalari va jami xaridi",
    ]
    if role != "staff":
        lines += [
            "/blok 901234567 — raqamni bloklash (soxta buyurtma bergan mijoz)",
            "/ochish 901234567 — raqamni blokdan chiqarish",
        ]
    lines += [
        "/id — shu chat va sizning Telegram ID raqamingiz",
        "/bekor — boshlangan amalni bekor qilish",
    ]
    return "\n".join(lines)


HELP_TEXT = help_text("owner")


# ---------- Hisobot ----------


def _percent_change(now: int, before: int) -> str:
    if before == 0:
        return "yangi" if now else "o'zgarmadi"
    change = round((now - before) * 100 / before)
    return f"{change:+d}%"


def _range_text(report: Report, tz_name: str) -> str:
    zone = ZoneInfo(tz_name)
    start = report.start.astimezone(zone)
    end = report.end.astimezone(zone)
    if end - start <= timedelta(days=1) and start.date() == (end - timedelta(seconds=1)).date():
        return f"{start:%d.%m.%Y}, {start:%H:%M}–{end:%H:%M}"
    return f"{start:%d.%m.%Y %H:%M} – {end:%d.%m.%Y %H:%M}"


def report_text(report: Report, tz_name: str, compare_title: str | None = None) -> str:
    lines = [f"📊 <b>Hisobot: {escape(report.title)}</b>", _range_text(report, tz_name), ""]
    if not report.orders:
        lines.append("Bu davrda buyurtma bo'lmadi.")
    else:
        status = report.by_status
        lines += [
            f"🧾 Buyurtmalar: {report.orders}",
            f"✅ Yetkazildi: {report.delivered} · ⏳ Jarayonda: {report.in_progress}",
            f"❌ Rad etildi: {status[OrderStatus.REJECTED]} · "
            f"🚫 Bekor qilindi: {status[OrderStatus.CANCELLED]}",
            "",
            f"💰 Tushum (yetkazilganlar): <b>{format_sum(report.revenue)}</b>",
            f"taomlar {format_sum(report.items_revenue)}, "
            f"yetkazish {format_sum(report.delivery_revenue)}",
            f"🧮 O'rtacha chek: {format_sum(report.average_check)}",
        ]
        if report.discounts:
            lines.append(
                f"🎉 Chegirmalar: {format_sum(report.discounts)} ({report.promo_orders} ta buyurtma)"
            )
    if compare_title and report.previous_revenue is not None:
        lines.append(
            f"📈 {compare_title.capitalize()} nisbatan: "
            f"{_percent_change(report.revenue, report.previous_revenue)} "
            f"(u yerda {format_sum(report.previous_revenue)}, {report.previous_delivered} ta)"
        )
    if report.orders:
        customers = report.new_customers + report.returning_customers
        lines += ["", f"👥 Mijozlar: {customers}, shundan yangi: {report.new_customers}"]
        if report.busiest_hour:
            hour, count = report.busiest_hour
            lines.append(f"🕖 Eng band soat: {hour:02d}:00–{(hour + 1) % 24:02d}:00 ({count} ta)")
    if report.top_products:
        lines += ["", "🏆 <b>Ko'p sotilgan taomlar</b>"]
        for place, (name, quantity, amount) in enumerate(report.top_products, start=1):
            lines.append(f"{place}. {escape(name)} — {quantity} ta, {format_sum(amount)}")
    if report.reject_reasons:
        lines += ["", "❌ <b>Rad etish sabablari</b>"]
        for reason, count in report.reject_reasons:
            lines.append(f"{escape(reason)} — {count}")
    return "\n".join(lines)


# ---------- Kechikish eslatmasi ----------


def delay_alert_text(order: Order, minutes: int) -> str:
    if order.status_enum == OrderStatus.NEW:
        return (
            f"⏰ <b>№{order.id}</b> buyurtma {minutes} daqiqadan beri qabul qilinmadi! "
            "Mijoz javob kutyapti."
        )
    return (
        f"⏰ <b>№{order.id}</b> buyurtma {minutes} daqiqadan beri yo'lda. "
        f"Kuryer bilan bog'lanib, holatini bilib oling. Mijoz: {escape(order.phone)}"
    )


# ---------- Mijoz kartasi ----------


def customer_card(
    phone: str,
    names: list[str],
    orders: list[Order],
    favourites: list[tuple[str, int]],
    blocked: bool,
    tz_name: str,
) -> str:
    zone = ZoneInfo(tz_name)
    counts = {status: 0 for status in OrderStatus}
    spent = 0
    for order in orders:
        counts[order.status_enum] += 1
        if order.status_enum == OrderStatus.DELIVERED:
            spent += order.total
    delivered = counts[OrderStatus.DELIVERED]
    title = ", ".join(escape(name) for name in names) or "Ismi yo'q"
    lines = [f"👤 <b>{title}</b>", f"📞 {escape(phone)}"]
    if blocked:
        lines.append("🚫 <b>Bloklangan:</b> bu raqamdan buyurtma berib bo'lmaydi")
    lines.append("")
    if not orders:
        lines.append("Bu raqamdan hali buyurtma berilmagan.")
        return "\n".join(lines)
    first = min(order.created_at for order in orders).astimezone(zone)
    last = max(order.created_at for order in orders).astimezone(zone)
    lines += [
        f"🧾 Buyurtmalar: {len(orders)} ta",
        f"✅ Yetkazildi: {delivered} · ❌ Rad etildi: {counts[OrderStatus.REJECTED]} · "
        f"🚫 Bekor qildi: {counts[OrderStatus.CANCELLED]}",
        f"💰 Jami xarid: {format_sum(spent)}"
        + (f" · o'rtacha {format_sum(round(spent / delivered))}" if delivered else ""),
        f"📅 Birinchi buyurtma: {first:%d.%m.%Y}, oxirgisi: {last:%d.%m.%Y}",
    ]
    fake = sum(1 for order in orders if order.reject_reason == "Soxta buyurtma")
    if fake:
        lines.append(f"⚠️ {fake} marta soxta buyurtma deb rad etilgan")
    if favourites:
        liked = ", ".join(f"{escape(name)} ({quantity})" for name, quantity in favourites)
        lines.append(f"❤️ Ko'p oladi: {liked}")
    lines += ["", "<b>Oxirgi buyurtmalar</b>"]
    for order in sorted(orders, key=lambda item: item.id, reverse=True)[:5]:
        moment = order.created_at.astimezone(zone)
        lines.append(
            f"№{order.id} · {moment:%d.%m %H:%M} · {format_sum(order.total)} · "
            f"{STATUS_EMOJI[order.status_enum]} {STATUS_LABELS[order.status_enum]}"
        )
    return "\n".join(lines)


# ---------- Xodimlar ----------


def team_text(owner_ids: list[int], members: list[Staff]) -> str:
    lines = [
        "👥 <b>Adminlar va xodimlar</b>",
        "",
        "Admin hamma narsani qila oladi. Xodim esa faqat taomni bor/tugadi qiladi, "
        "qabulni to'xtatadi, hisobot va mijoz kartasini ko'radi.",
        "",
        "Buyurtmalar guruhidagi tugmalarni guruhning har bir a'zosi bosa oladi. "
        "Kimnidir botdan olib tashlasangiz, guruhdan ham Telegram'da chiqarib qo'ying.",
        "",
    ]
    for owner_id in owner_ids:
        lines.append(f"👑 Egasi · ID <code>{owner_id}</code>")
    for member in members:
        mark = "🛡 Admin" if member.role == "admin" else "🙋 Xodim"
        lines.append(f"{mark} · {escape(member.name)}")
    if not members:
        lines += ["", "Hali hech kim qo'shilmagan."]
    return "\n".join(lines)


def invite_text(link: str, role: str, hours: int) -> str:
    who = "admin" if role == "admin" else "xodim"
    return (
        f"🔗 <b>Yangi {who} uchun taklif havolasi</b>\n\n"
        f"{escape(link)}\n\n"
        f"Havolani faqat o'sha odamga yuboring. U havolani bosib, botda <b>Start</b> ni "
        f"bossa, {who} bo'lib qo'shiladi. Havola {hours} soat amal qiladi va faqat bir marta ishlaydi."
    )


# ---------- Aksiyalar ----------

BANNER_TITLE_MAX = 40
BANNER_TEXT_MAX = 80
DEFAULT_BANNER = "Yetkazish narxi va bepul yetkazish sharti (ilova o'zi yozadi)"


def promo_status(promo, now: datetime) -> str:
    if not promo.is_active:
        return "⏸ to'xtatilgan"
    if promo.expires_at is not None and promo.expires_at <= now:
        return "⌛️ muddati tugagan"
    if promo.usage_limit is not None and promo.used_count >= promo.usage_limit:
        return "🔚 soni tugagan"
    return "🟢 ishlayapti"


def promo_menu_text(shop: ShopSettings, auto, codes: list, now: datetime) -> str:
    lines = ["🎉 <b>Aksiyalar</b>", ""]
    if shop.banner_title or shop.banner_text:
        lines.append(f"🖼 Banner: <b>{escape(shop.banner_title or '')}</b> {escape(shop.banner_text or '')}")
    else:
        lines.append("🖼 Banner: standart (yetkazish narxi)")
    if auto is not None and auto.is_active:
        lines.append(f"🆕 Birinchi buyurtma: {promos.describe(auto)}")
    else:
        lines.append("🆕 Birinchi buyurtma chegirmasi: yo'q")
    lines.append("")
    if codes:
        lines.append("Promokodlar:")
        for promo in codes:
            lines.append(
                f"• <code>{promo.code}</code> {promos.describe(promo)} · {promo_status(promo, now)}"
            )
    else:
        lines.append("Promokodlar hali yo'q.")
    return "\n".join(lines)


def banner_screen_text(shop: ShopSettings) -> str:
    title = shop.banner_title
    text = shop.banner_text
    return "\n".join(
        [
            "🖼 <b>Bosh sahifadagi banner</b>",
            "",
            "Ilovada menyuning tepasidagi katta yozuv.",
            "",
            f"Sarlavha: <b>{escape(title) if title else 'standart'}</b>",
            f"Pastki matn: {escape(text) if text else 'standart'}",
            "",
            f"Standart holatda: {DEFAULT_BANNER}.",
            "O'zgarish ilovada darhol ko'rinadi.",
        ]
    )


def banner_prompt(field: str) -> str:
    if field == "title":
        return (
            f"Banner sarlavhasini yozing (ko'pi bilan {BANNER_TITLE_MAX} ta harf).\n"
            "Ikki qatorga bo'lish uchun yangi qatordan yozing. Masalan:\n"
            "<i>Birinchi buyurtmaga\n−15% chegirma</i>\n\n"
            "Standartga qaytarish uchun <code>-</code> yuboring."
        )
    return (
        f"Pastki matnni yozing (ko'pi bilan {BANNER_TEXT_MAX} ta harf). Masalan:\n"
        "<i>Promokod: AMORA10</i>\n\n"
        "Standartga qaytarish uchun <code>-</code> yuboring."
    )


def auto_promo_text(auto, given: int, total: int) -> str:
    lines = ["🆕 <b>Birinchi buyurtma chegirmasi</b>", ""]
    lines.append(
        "Ilovadan birinchi marta buyurtma berayotgan mijozga kod kiritmasdan o'zi beriladi. "
        "Telefon raqami bo'yicha tekshiriladi."
    )
    lines.append("")
    if auto is not None and auto.is_active:
        lines.append(f"Hozir: <b>{promos.describe(auto)}</b>")
    else:
        lines.append("Hozir: <b>o'chiq</b>")
    if given:
        lines.append(f"Berilgan: {given} ta buyurtma, jami {format_sum(total)}")
    lines.append("")
    lines.append("Bannerga ham yozib qo'ysangiz, mijozlar ko'radi.")
    return "\n".join(lines)


AUTO_PROMO_PROMPT = (
    "Chegirmani yozing:\n"
    "<code>15%</code> — taomlar summasidan 15%\n"
    "<code>15% 30000</code> — 15%, lekin ko'pi bilan 30 000 so'm\n"
    "<code>20000</code> — 20 000 so'm\n"
    "<code>0</code> — o'chirish"
)


def promo_card_text(promo, given: int, total: int, now: datetime, tz_name: str) -> str:
    lines = [f"🎟 <b>{promo.code}</b> · {promo_status(promo, now)}", ""]
    lines.append(f"Chegirma: {promos.describe(promo)}")
    if promo.min_order:
        lines.append(f"Eng kam buyurtma: {format_sum(promo.min_order)}")
    lines.append("Kim uchun: " + ("faqat birinchi buyurtma" if promo.first_order_only else "hamma"))
    lines.append("Har bir mijoz bir marta ishlata oladi.")
    limit = f"{promo.usage_limit} tadan" if promo.usage_limit is not None else "cheklanmagan"
    lines.append(f"Ishlatildi: {promo.used_count} ({limit})")
    if promo.expires_at is not None:
        expires = promo.expires_at.astimezone(ZoneInfo(tz_name))
        lines.append(f"Muddati: {expires:%d.%m.%Y %H:%M} gacha")
    if given:
        lines.append(f"Berilgan chegirma: {format_sum(total)} ({given} ta buyurtma)")
    return "\n".join(lines)


PROMO_WIZARD = {
    "code": (
        "Promokod nomini yozing: lotin harflari va raqamlar, 3–20 ta belgi.\n"
        "Masalan: <code>AMORA10</code>"
    ),
    "discount": AUTO_PROMO_PROMPT.replace("\n<code>0</code> — o'chirish", ""),
    "min_order": (
        "Eng kam buyurtma summasi qancha bo'lsin? Masalan: <code>50000</code>\n"
        "Cheklov kerak bo'lmasa <code>0</code> yuboring."
    ),
    "limit": (
        "Promokod nechta buyurtmaga ishlasin? Masalan: <code>100</code>\n"
        "Cheklov kerak bo'lmasa <code>0</code> yuboring."
    ),
    "days": (
        "Necha kun amal qilsin? Masalan: <code>7</code>\n"
        "Muddatsiz bo'lsa <code>0</code> yuboring."
    ),
    "audience": "Kim ishlata oladi?",
}
