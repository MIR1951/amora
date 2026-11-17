"""Botning boshqaruv vositalari: hisobot, kechikish eslatmasi, mijoz kartasi, adminlar va xodimlar."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import AnswerCallbackQuery, SendMessage
from aiogram.types import User
from sqlalchemy import select, update

from app.db import utcnow
from app.models import Order, OrderItem, OrderStatus, OrderStatusEvent, ShopSettings, Staff
from app.services.reports import build_report, business_day, period_bounds
from app.telegram.watch import check_delays, send_daily_report
from tests.conftest import NEAR, register
from app.telegram.keyboards import OrderCb
from tests.telegram_fakes import ADMIN_ID, GROUP_ID, STAFF, STRANGER_ID
from tests.test_bot import db_order, place_order

TZ = "Asia/Tashkent"
ZONE = ZoneInfo(TZ)
NEW_PERSON = 777
STAFF_PERSON = 888


async def add_order(
    session_factory,
    created_at: datetime,
    status: OrderStatus = OrderStatus.DELIVERED,
    phone: str = "+998901234567",
    items: tuple[tuple[str, int, int], ...] = (("Osh", 35_000, 2),),
    delivery_fee: int = 10_000,
    reason: str | None = None,
) -> int:
    """Bazaga tayyor buyurtma yozadi (hisobot uchun vaqti va holati qo'lda beriladi)."""
    items_total = sum(price * quantity for _, price, quantity in items)
    async with session_factory() as session:
        from app.models import Customer

        customer = await session.scalar(select(Customer).where(Customer.phone == phone))
        if customer is None:
            customer = Customer(name="Ali", phone=phone, token_hash=f"hash-{phone}")
            session.add(customer)
            await session.flush()
        order = Order(
            customer_id=customer.id,
            status=status.value,
            customer_name="Ali",
            phone=phone,
            items_total=items_total,
            delivery_fee=delivery_fee,
            total=items_total + delivery_fee,
            reject_reason=reason,
            created_at=created_at,
            items=[OrderItem(name=name, price=price, quantity=qty) for name, price, qty in items],
            **NEAR,
        )
        session.add(order)
        await session.commit()
        return order.id


def local(day_offset: int, hour: int, minute: int = 0, now: datetime | None = None) -> datetime:
    base = (now or datetime.now(ZONE)).astimezone(ZONE).date() + timedelta(days=day_offset)
    return datetime.combine(base, time(hour, minute), tzinfo=ZONE)


# ---------- Hisobot ----------


def test_period_bounds():
    now = datetime(2026, 11, 17, 14, 30, tzinfo=ZONE)
    assert period_bounds("today", TZ, now) == (datetime(2026, 11, 17, tzinfo=ZONE), now)
    assert period_bounds("yesterday", TZ, now) == (
        datetime(2026, 11, 16, tzinfo=ZONE),
        datetime(2026, 11, 17, tzinfo=ZONE),
    )
    assert period_bounds("week", TZ, now)[0] == datetime(2026, 11, 11, tzinfo=ZONE)
    assert period_bounds("this_month", TZ, now)[0] == datetime(2026, 11, 1, tzinfo=ZONE)


@pytest.mark.parametrize(
    ("hours", "now", "expected"),
    [
        # Oddiy kun: 09:00-23:00. 23:05 da shu kun tugagan
        ((9, 23), (17, 23, 5), ((17, 9), (17, 23))),
        # 22:00 da hali tugamagan: oxirgi tugagani kechagi kun
        ((9, 23), (17, 22, 0), ((16, 9), (16, 23))),
        # Yarim tundan o'tadigan ish vaqti: 18:00-02:00
        ((18, 2), (18, 2, 30), ((17, 18), (18, 2))),
        # Kecha-kunduz: yarim tunda yopiladi, 24 soatlik oraliq
        ((0, 0), (17, 0, 10), ((16, 0), (17, 0))),
    ],
)
def test_business_day(hours, now, expected):
    shop = ShopSettings(open_time=time(hours[0]), close_time=time(hours[1]))
    moment = datetime(2026, 11, now[0], now[1], now[2], tzinfo=ZONE)
    start, end = business_day(shop, TZ, moment)
    assert start == datetime(2026, 11, expected[0][0], expected[0][1], tzinfo=ZONE)
    assert end == datetime(2026, 11, expected[1][0], expected[1][1], tzinfo=ZONE)


async def test_report_numbers(session_factory, seed):
    now = datetime(2026, 11, 17, 14, 30, tzinfo=ZONE)
    # Oldingi mijoz kecha ham buyurtma bergan, demak bugun u qaytgan mijoz
    await add_order(session_factory, local(-1, 10, now=now), phone="+998900000001")
    await add_order(session_factory, local(0, 0, 5, now=now), phone="+998900000001")
    await add_order(
        session_factory,
        local(0, 0, 10, now=now),
        phone="+998900000002",
        items=(("Lag'mon", 30_000, 3), ("Osh", 35_000, 1)),
        delivery_fee=0,
    )
    await add_order(
        session_factory,
        local(0, 0, 15, now=now),
        status=OrderStatus.REJECTED,
        phone="+998900000003",
        reason="Mahsulot tugadi",
    )
    await add_order(session_factory, local(0, 0, 20, now=now), status=OrderStatus.NEW)

    start, end = period_bounds("today", TZ, now)
    async with session_factory() as session:
        report = await build_report(session, "Bugun", start, end, TZ, timedelta(days=1))
    assert report.orders == 4
    assert report.delivered == 2
    assert report.revenue == 80_000 + 125_000
    assert report.items_revenue == 70_000 + 125_000 and report.delivery_revenue == 10_000
    assert report.average_check == 102_500
    assert report.in_progress == 1
    assert report.new_customers == 3 and report.returning_customers == 1
    assert report.top_products == [("Osh", 3, 105_000), ("Lag'mon", 3, 90_000)]
    assert report.reject_reasons == [("Mahsulot tugadi", 1)]
    assert report.busiest_hour == (0, 4)
    # Kechaning shu vaqtigacha bo'lgan qism bilan solishtiriladi
    assert report.previous_revenue == 80_000 and report.previous_delivered == 1


async def test_report_screens_in_bot(driver, seed, session_factory):
    await add_order(session_factory, local(-1, 12), items=(("Somsa", 8_000, 5),), delivery_fee=0)
    await driver.say("/start")
    await driver.press("Hisobot")
    assert "Bu davrda buyurtma bo'lmadi" in driver.screen
    assert "• Bugun •" in driver.buttons
    await driver.press("Kecha")
    screen = driver.screen
    assert "Hisobot: Kecha" in screen
    assert "Tushum (yetkazilganlar): <b>40 000 so'm</b>" in screen
    assert "1. Somsa — 5 ta, 40 000 so'm" in screen
    assert "Undan oldingi kunga nisbatan: yangi" in screen
    await driver.press("7 kun")
    assert "So'nggi 7 kun" in driver.screen


# ---------- Kunlik hisobot ----------


async def set_shop(session_factory, **values) -> None:
    async with session_factory() as session:
        await session.execute(update(ShopSettings).where(ShopSettings.id == 1).values(**values))
        await session.commit()


async def test_daily_report_is_sent_once_after_closing(bot, tg, bot_cfg, session_factory, seed):
    await set_shop(session_factory, open_time=time(9), close_time=time(23))
    await add_order(session_factory, local(0, 12))
    # Yopilishdan oldin: oxirgi tugagan ish kuni kecha edi, u allaqachon eskirgan
    assert await send_daily_report(session_factory, bot, bot_cfg, local(0, 22, 50)) is False
    assert tg.of_type(SendMessage) == []

    after_close = local(0, 23, 5)
    assert await send_daily_report(session_factory, bot, bot_cfg, after_close) is True
    sent = tg.of_type(SendMessage)
    assert len(sent) == 1 and sent[0].chat_id == GROUP_ID
    assert "Hisobot: Kunlik hisobot" in sent[0].text and "Buyurtmalar: 1" in sent[0].text

    # Bir necha daqiqadan keyin yana tekshiriladi: ikkinchi marta yuborilmaydi
    assert await send_daily_report(session_factory, bot, bot_cfg, local(0, 23, 6)) is False
    assert len(tg.of_type(SendMessage)) == 1


async def test_daily_report_to_admins_or_off(bot, tg, bot_cfg, session_factory, seed):
    await set_shop(session_factory, open_time=time(9), close_time=time(23), daily_report_to="admins")
    async with session_factory() as session:
        session.add(Staff(telegram_id=NEW_PERSON, name="Vali", role="admin"))
        session.add(Staff(telegram_id=STAFF_PERSON, name="Sardor", role="staff"))
        await session.commit()
    assert await send_daily_report(session_factory, bot, bot_cfg, local(0, 23, 1)) is True
    assert sorted(m.chat_id for m in tg.of_type(SendMessage)) == [ADMIN_ID, NEW_PERSON]

    tg.clear()
    await set_shop(session_factory, daily_report_to="off")
    assert await send_daily_report(session_factory, bot, bot_cfg, local(1, 23, 1)) is False
    assert tg.of_type(SendMessage) == []


async def test_daily_report_is_retried_when_telegram_fails(bot, tg, bot_cfg, session_factory, seed):
    await set_shop(session_factory, open_time=time(9), close_time=time(23))
    tg.fail_with = TelegramNetworkError(method=None, message="timeout")
    assert await send_daily_report(session_factory, bot, bot_cfg, local(0, 23, 1)) is False
    tg.fail_with = None
    assert await send_daily_report(session_factory, bot, bot_cfg, local(0, 23, 2)) is True


async def test_stale_daily_report_is_skipped(bot, tg, bot_cfg, session_factory, seed):
    await set_shop(session_factory, open_time=time(9), close_time=time(10))
    # Server kun bo'yi o'chiq turgan: ertalabki hisobot kechqurun yuborilmaydi
    assert await send_daily_report(session_factory, bot, bot_cfg, local(0, 20)) is False


# ---------- Kechikish eslatmasi ----------


async def age_order(session_factory, order_id: int, minutes: int) -> None:
    """Buyurtmani va uning tarixini `minutes` daqiqa oldinga suradi."""
    async with session_factory() as session:
        order = await session.get(Order, order_id)
        order.created_at = order.created_at - timedelta(minutes=minutes)
        events = await session.scalars(
            select(OrderStatusEvent).where(OrderStatusEvent.order_id == order_id)
        )
        for event in events:
            event.created_at = event.created_at - timedelta(minutes=minutes)
        await session.commit()


async def test_unaccepted_order_gets_one_reminder(api, seed, bot, tg, session_factory):
    order, _ = await place_order(api, seed)
    assert await check_delays(session_factory, bot) == 0  # hali erta

    await age_order(session_factory, order["id"], 6)
    assert await check_delays(session_factory, bot) == 1
    alert = tg.of_type(SendMessage)[-1]
    assert alert.chat_id == GROUP_ID and alert.reply_to_message_id == 1001
    assert f"№{order['id']}</b> buyurtma 6 daqiqadan beri qabul qilinmadi" in alert.text

    assert await check_delays(session_factory, bot) == 0  # bir holat uchun bir marta


async def test_long_delivery_gets_reminder(api, seed, bot, tg, driver, session_factory):
    order, _ = await place_order(api, seed)
    await driver.press_in_group("Qabul qilish", 1001)
    await driver.press_in_group("Yo'lga chiqdi", 1001)
    await age_order(session_factory, order["id"], 30)
    assert await check_delays(session_factory, bot) == 0

    await age_order(session_factory, order["id"], 20)
    assert await check_delays(session_factory, bot) == 1
    alert = tg.of_type(SendMessage)[-1]
    assert "50 daqiqadan beri yo'lda" in alert.text and "+998901234567" in alert.text

    done = OrderCb(id=order["id"], action="done").pack()
    await driver.press_data(done, STAFF, GROUP_ID, 1001, "supergroup")
    assert (await db_order(session_factory, order["id"])).status == "delivered"
    await age_order(session_factory, order["id"], 100)
    assert await check_delays(session_factory, bot) == 0


async def test_reminders_can_be_turned_off(api, seed, bot, tg, session_factory, driver):
    await driver.say("/start")
    await driver.press("Sozlamalar")
    await driver.press("Qabul qilinmasa")
    await driver.say("ko'p")
    assert "raqam bilan" in driver.screen
    await driver.say("0")
    assert "Qabul qilinmasa eslatma: o'chiq" in driver.screen

    order, _ = await place_order(api, seed)
    await age_order(session_factory, order["id"], 60)
    assert await check_delays(session_factory, bot) == 0


async def test_reminder_is_retried_when_telegram_fails(api, seed, bot, tg, session_factory):
    order, _ = await place_order(api, seed)
    await age_order(session_factory, order["id"], 6)
    tg.fail_with = TelegramNetworkError(method=None, message="timeout")
    assert await check_delays(session_factory, bot) == 0
    tg.fail_with = None
    assert await check_delays(session_factory, bot) == 1


async def test_daily_report_target_setting(driver, seed, session_factory):
    await driver.say("/start")
    await driver.press("Sozlamalar")
    assert "Kunlik hisobot: kafe yopilganda guruhga" in driver.screen
    await driver.press("Kunlik hisobot")
    await driver.press("Adminlarga")
    assert "Kunlik hisobot: kafe yopilganda adminlarga" in driver.screen


# ---------- Mijoz kartasi ----------


async def test_order_message_marks_new_and_returning_customer(api, seed, tg, bot_cfg):
    bot_cfg.max_active_orders = 5
    auth = await register(api)
    await place_order(api, seed, auth)
    assert "🆕 yangi mijoz" in tg.of_type(SendMessage)[-1].text
    await place_order(api, seed, auth)
    assert "2-buyurtmasi" in tg.of_type(SendMessage)[-1].text


async def test_customer_card(api, seed, driver, session_factory, bot_cfg):
    await add_order(session_factory, local(-3, 12), items=(("Osh", 35_000, 2),))
    await add_order(
        session_factory,
        local(-2, 12),
        status=OrderStatus.REJECTED,
        reason="Soxta buyurtma",
    )
    order_id = await add_order(session_factory, local(-1, 12), items=(("Lag'mon", 30_000, 1),))

    await driver.say("/mijoz")
    assert "/mijoz 901234567" in driver.screen
    await driver.say("/mijoz 93 000 00 00")
    screen = driver.screen
    assert "hali buyurtma berilmagan" in screen

    await driver.say("/mijoz 90 123 45 67")
    screen = driver.screen
    assert "Ali" in screen and "+998901234567" in screen
    assert "Buyurtmalar: 3 ta" in screen
    assert "Yetkazildi: 2 · ❌ Rad etildi: 1" in screen
    assert "Jami xarid: 120 000 so'm · o'rtacha 60 000 so'm" in screen
    assert "1 marta soxta buyurtma" in screen
    assert "Ko'p oladi: Osh (2), Lag'mon (1)" in screen
    assert f"№{order_id}" in screen

    # Buyurtma raqami bo'yicha ham topiladi
    await driver.say(f"/mijoz {order_id}")
    assert "Buyurtmalar: 3 ta" in driver.screen

    await driver.press("Bloklash")
    assert "Bloklangan" in driver.screen
    async with session_factory() as session:
        from app.models import Customer

        customer = await session.scalar(select(Customer).where(Customer.phone == "+998901234567"))
        assert customer.is_blocked
    await driver.press("Blokdan chiqarish")
    assert "Bloklangan" not in driver.screen


# ---------- Adminlar va xodimlar ----------


def person(user_id: int, name: str) -> User:
    return User(id=user_id, is_bot=False, first_name=name)


async def invite(driver, role_label: str) -> str:
    await driver.say("/start")
    await driver.press("Adminlar va xodimlar")
    await driver.press(role_label)
    screen = driver.screen
    assert "https://t.me/amora_test_bot?start=inv_" in screen
    return screen.split("start=", 1)[1].split()[0]


async def start_as(driver, user_id: int, args: str = "") -> None:
    await driver.say(f"/start {args}".strip(), user_id=user_id)


async def test_owner_invites_admin(driver, seed, tg, session_factory):
    payload = await invite(driver, "Admin qo'shish")

    await start_as(driver, NEW_PERSON)
    assert "taklif havolasini" in driver.screen  # hali begona

    tg.clear()
    await start_as(driver, NEW_PERSON, payload)
    assert "admin</b> bo'lib qo'shildingiz" in tg.of_type(SendMessage)[0].text
    assert tg.of_type(SendMessage)[1].chat_id == ADMIN_ID  # egasiga xabar

    await start_as(driver, NEW_PERSON)
    assert "boshqaruvi" in driver.screen
    assert "⚙️ Sozlamalar" in driver.buttons

    # Havola ikkinchi marta ishlamaydi
    await start_as(driver, STRANGER_ID, payload)
    assert "eskirgan yoki allaqachon ishlatilgan" in driver.screen
    await start_as(driver, STRANGER_ID)
    assert "taklif havolasini" in driver.screen


async def test_expired_invite_does_not_work(driver, seed, session_factory):
    from app.models import StaffInvite

    payload = await invite(driver, "Xodim qo'shish")
    async with session_factory() as session:
        await session.execute(update(StaffInvite).values(expires_at=utcnow() - timedelta(minutes=1)))
        await session.commit()
    await start_as(driver, NEW_PERSON, payload)
    assert "eskirgan" in driver.screen


async def test_staff_can_do_daily_work_only(api, driver, seed, tg, session_factory, bot_cfg):
    payload = await invite(driver, "Xodim qo'shish")
    await start_as(driver, STAFF_PERSON, payload)
    await start_as(driver, STAFF_PERSON)
    assert driver.buttons == ["🍽 Menyu", "📊 Hisobot", "⏸ Buyurtma qabul qilishni to'xtatish"]
    assert "/mijoz 901234567" in driver.screen

    # Taomni tugadi deb belgilaydi, lekin narxini o'zgartira olmaydi
    await driver.press("Menyu", user_id=STAFF_PERSON)
    assert "Taom qo'shish" not in " ".join(driver.buttons)
    await driver.press("Osh", user_id=STAFF_PERSON)
    assert driver.buttons == ["⛔ Tugadi deb belgilash", "⬅️ Menyuga qaytish"]
    await driver.press("Tugadi", user_id=STAFF_PERSON)
    assert "tugagan" in driver.screen

    # Sozlamalar va xodimlar tugmasi qo'lda yuborilsa ham ishlamaydi
    tg.clear()
    await driver.press_data("a:settings:0:", person(STAFF_PERSON, "S"), STAFF_PERSON)
    answer = tg.of_type(AnswerCallbackQuery)[-1]
    assert answer.show_alert and "faqat admin" in answer.text
    await driver.press_data("a:team_inv:0:staff", person(STAFF_PERSON, "S"), STAFF_PERSON)
    assert "faqat admin" in tg.of_type(AnswerCallbackQuery)[-1].text
    assert tg.of_type(SendMessage) == [] and "Taklif" not in str(tg.requests)

    await driver.say("/blok 901234567", user_id=STAFF_PERSON)
    assert "faqat admin" in driver.screen

    # Hisobot va mijoz kartasi ochiq, bloklash tugmasi esa yo'q
    await driver.press_data("a:report:0:", person(STAFF_PERSON, "S"), STAFF_PERSON)
    assert "Hisobot: Bugun" in driver.screen
    await add_order(session_factory, local(-1, 12))
    await driver.say("/mijoz 901234567", user_id=STAFF_PERSON)
    assert "Buyurtmalar: 1 ta" in driver.screen
    assert driver.buttons == ["⬅️ Bosh menyu"]


async def test_admin_can_add_staff_but_not_admins(driver, seed, tg, session_factory):
    async with session_factory() as session:
        session.add(Staff(telegram_id=NEW_PERSON, name="Vali", role="admin"))
        session.add(Staff(telegram_id=STAFF_PERSON, name="Sardor", role="staff"))
        await session.commit()

    await start_as(driver, NEW_PERSON)
    await driver.press("Adminlar va xodimlar", user_id=NEW_PERSON)
    screen = driver.screen
    assert "Egasi" in screen and "Admin · Vali" in screen and "Xodim · Sardor" in screen
    assert "➕ Admin qo'shish" not in driver.buttons
    assert "➕ Xodim qo'shish" in driver.buttons
    assert "🗑 Vali" not in driver.buttons  # admin boshqa adminni (o'zini ham) olib tashlamaydi

    tg.clear()
    await driver.press_data("a:team_inv:0:admin", person(NEW_PERSON, "V"), NEW_PERSON)
    assert "faqat egasi" in tg.of_type(AnswerCallbackQuery)[-1].text

    await start_as(driver, NEW_PERSON)
    await driver.press("Adminlar va xodimlar", user_id=NEW_PERSON)
    await driver.press("🗑 Sardor", user_id=NEW_PERSON)
    await driver.press("Ha, olib tashlansin", user_id=NEW_PERSON)
    assert "Olib tashlandi" in str(tg.of_type(AnswerCallbackQuery)[-1].text)
    assert "Sardor" not in driver.screen

    # Olib tashlangan xodim endi begona
    await start_as(driver, STAFF_PERSON)
    assert "taklif havolasini" in driver.screen


async def test_owner_removes_admin(driver, seed, session_factory):
    async with session_factory() as session:
        session.add(Staff(telegram_id=NEW_PERSON, name="Vali", role="admin"))
        await session.commit()
    await driver.say("/start")
    await driver.press("Adminlar va xodimlar")
    await driver.press("🗑 Vali")
    assert "Vali (admin) botdan olib tashlansinmi?" in driver.screen
    await driver.press("Ha, olib tashlansin")
    async with session_factory() as session:
        assert await session.scalar(select(Staff)) is None


# ---------- Tekshiruvdan keyingi tuzatishlar ----------


async def test_staff_cannot_block_with_photo_caption(driver, seed, session_factory):
    from app.models import Customer

    async with session_factory() as session:
        session.add(Staff(telegram_id=STAFF_PERSON, name="Sardor", role="staff"))
        session.add(Customer(name="Ali", phone="+998901234567", token_hash="h"))
        await session.commit()
    await driver.send_photo(user_id=STAFF_PERSON, caption="/blok 901234567")
    assert "faqat admin" in driver.screen
    async with session_factory() as session:
        customer = await session.scalar(select(Customer))
        assert not customer.is_blocked


async def test_removed_admins_invites_stop_working(driver, seed, session_factory):
    async with session_factory() as session:
        session.add(Staff(telegram_id=NEW_PERSON, name="Vali", role="admin"))
        await session.commit()
    await start_as(driver, NEW_PERSON)
    await driver.press("Adminlar va xodimlar", user_id=NEW_PERSON)
    await driver.press("Xodim qo'shish", user_id=NEW_PERSON)
    payload = driver.screen.split("start=", 1)[1].split()[0]

    # Egasi adminni olib tashlaydi: u yaratgan havola ham ishlamay qoladi
    await driver.say("/start")
    await driver.press("Adminlar va xodimlar")
    await driver.press("🗑 Vali")
    await driver.press("Ha, olib tashlansin")
    await start_as(driver, NEW_PERSON, payload)
    assert "eskirgan" in driver.screen
    await start_as(driver, STAFF_PERSON, payload)
    assert "eskirgan" in driver.screen
    async with session_factory() as session:
        assert await session.scalar(select(Staff)) is None


async def test_invite_from_demoted_inviter_is_refused(driver, seed, session_factory):
    async with session_factory() as session:
        session.add(Staff(telegram_id=NEW_PERSON, name="Vali", role="admin"))
        await session.commit()
    await start_as(driver, NEW_PERSON)
    await driver.press("Adminlar va xodimlar", user_id=NEW_PERSON)
    await driver.press("Xodim qo'shish", user_id=NEW_PERSON)
    payload = driver.screen.split("start=", 1)[1].split()[0]
    async with session_factory() as session:
        await session.execute(update(Staff).values(role="staff"))
        await session.commit()
    await start_as(driver, STAFF_PERSON, payload)
    assert "endi ishlamaydi" in driver.screen


async def test_staff_invite_does_not_demote_admin(driver, seed, session_factory):
    async with session_factory() as session:
        session.add(Staff(telegram_id=NEW_PERSON, name="Vali", role="admin"))
        await session.commit()
    payload = await invite(driver, "Xodim qo'shish")
    await start_as(driver, NEW_PERSON, payload)
    assert "allaqachon adminsiz" in driver.screen
    async with session_factory() as session:
        assert (await session.scalar(select(Staff))).role == "admin"
    # Havola ishlatilmadi: haqiqiy xodim uni hali ham ishlata oladi
    await start_as(driver, STAFF_PERSON, payload)
    async with session_factory() as session:
        member = await session.scalar(select(Staff).where(Staff.telegram_id == STAFF_PERSON))
        assert member.role == "staff"


async def test_daily_report_waits_for_orders_on_the_way(bot, tg, bot_cfg, session_factory, seed):
    await set_shop(session_factory, open_time=time(9), close_time=time(23))
    await add_order(session_factory, local(0, 12))
    late = await add_order(session_factory, local(0, 22, 50), status=OrderStatus.DELIVERING)
    # Yopilishda bitta buyurtma hali yo'lda: kutamiz
    assert await send_daily_report(session_factory, bot, bot_cfg, local(0, 23, 1)) is False
    async with session_factory() as session:
        order = await session.get(Order, late)
        order.status = OrderStatus.DELIVERED.value
        await session.commit()
    assert await send_daily_report(session_factory, bot, bot_cfg, local(0, 23, 20)) is True
    text = tg.of_type(SendMessage)[0].text
    assert "Yetkazildi: 2" in text and "160 000" in text


async def test_daily_report_does_not_wait_forever(bot, tg, bot_cfg, session_factory, seed):
    await set_shop(session_factory, open_time=time(9), close_time=time(23))
    await add_order(session_factory, local(0, 22, 50), status=OrderStatus.DELIVERING)
    assert await send_daily_report(session_factory, bot, bot_cfg, local(0, 23, 30)) is False
    assert await send_daily_report(session_factory, bot, bot_cfg, local(1, 0, 31)) is True
    assert "Jarayonda: 1" in tg.of_type(SendMessage)[0].text


async def test_longer_hours_after_report_do_not_count_twice(
    bot, tg, bot_cfg, session_factory, seed
):
    await set_shop(session_factory, open_time=time(9), close_time=time(22))
    await add_order(session_factory, local(0, 12))
    assert await send_daily_report(session_factory, bot, bot_cfg, local(0, 22, 1)) is True
    await set_shop(session_factory, close_time=time(23))
    await add_order(session_factory, local(0, 22, 30))
    assert await send_daily_report(session_factory, bot, bot_cfg, local(0, 23, 1)) is True
    second = tg.of_type(SendMessage)[1].text
    assert "Buyurtmalar: 1" in second


async def test_daily_report_claim_is_released_on_error(
    bot, tg, bot_cfg, session_factory, seed, monkeypatch
):
    import app.telegram.watch as watch

    await set_shop(session_factory, open_time=time(9), close_time=time(23))
    real_build = watch.build_report

    async def broken(*args, **kwargs):
        raise ConnectionError("baza uzildi")

    monkeypatch.setattr(watch, "build_report", broken)
    with pytest.raises(ConnectionError):
        await send_daily_report(session_factory, bot, bot_cfg, local(0, 23, 1))
    monkeypatch.setattr(watch, "build_report", real_build)
    assert await send_daily_report(session_factory, bot, bot_cfg, local(0, 23, 2)) is True


async def test_unreachable_chat_does_not_block_other_alerts(api, seed, bot, tg, session_factory):
    from aiogram.exceptions import TelegramForbiddenError

    first, _ = await place_order(api, seed)
    second, _ = await place_order(api, seed, auth=await register(api, phone="90 765 43 21"))
    # Birinchi buyurtma eski guruhga ketgan, bot u yerdan chiqarilgan
    old_group = -100999
    async with session_factory() as session:
        await session.execute(update(Order).where(Order.id == first["id"]).values(tg_chat_id=old_group))
        await session.commit()
    tg.failing_chats[old_group] = TelegramForbiddenError(method=None, message="kicked")
    await age_order(session_factory, first["id"], 10)
    await age_order(session_factory, second["id"], 10)

    assert await check_delays(session_factory, bot) == 1
    assert f"№{second['id']}</b>" in tg.of_type(SendMessage)[-1].text
    assert await check_delays(session_factory, bot) == 0  # buzuq chatga qayta-qayta urinmaydi


async def test_alert_is_kept_when_bot_stops_during_send(api, seed, bot, tg, session_factory):
    import asyncio

    order, _ = await place_order(api, seed)
    await age_order(session_factory, order["id"], 6)
    tg.fail_with = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await check_delays(session_factory, bot)
    tg.fail_with = None
    assert await check_delays(session_factory, bot) == 1


async def test_daily_report_is_not_repeated_after_partial_send(
    bot, tg, bot_cfg, session_factory, seed
):
    import asyncio

    await set_shop(session_factory, open_time=time(9), close_time=time(23), daily_report_to="admins")
    async with session_factory() as session:
        session.add(Staff(telegram_id=NEW_PERSON, name="Vali", role="admin"))
        await session.commit()
    real_send = bot.send_message
    calls = 0

    async def send_then_stop(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise asyncio.CancelledError()
        return await real_send(*args, **kwargs)

    bot.send_message = send_then_stop
    with pytest.raises(asyncio.CancelledError):
        await send_daily_report(session_factory, bot, bot_cfg, local(0, 23, 1))
    bot.send_message = real_send
    # Birinchi odam olgan: ikkinchi marta hammaga yuborilmaydi
    assert await send_daily_report(session_factory, bot, bot_cfg, local(0, 23, 2)) is False
    assert len(tg.of_type(SendMessage)) == 1
