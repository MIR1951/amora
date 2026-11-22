"""Tekshiruvda topilgan kamchiliklar tuzatilganini ushlab turadigan testlar."""

import math
from datetime import timedelta

import httpx
import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramMigrateToChat
from aiogram.methods import SendMessage
from sqlalchemy import select, update

from app.db import utcnow
from app.main import create_app
from app.models import Customer, CustomerDevice, Order, OrderItem, OrderStatus, Product
from app.services import customers as customer_service
from app.telegram import publisher
from app.telegram.parsing import parse_amount, parse_count, parse_km
from app.telegram.publisher import UnsentWatch, sweep_unsent
from app.telegram.texts import order_text
from tests.conftest import NEAR, register
from tests.telegram_fakes import ADMIN_ID, GROUP_ID


def cart(seed) -> list[dict]:
    return [{"product_id": seed["osh"], "quantity": 1}]


async def place(client, seed, auth, **extra):
    return await client.post("/orders", headers=auth, json={"items": cart(seed), **NEAR, **extra})


# ---------- Hisobdan chiqish va hisobni o'chirish ----------


async def test_logout_revokes_only_this_device(client, seed):
    first = await register(client)
    second = await register(client)  # shu raqam, ikkinchi telefon
    assert (await client.post("/auth/logout", headers=first)).status_code == 204
    assert (await client.get("/me", headers=first)).status_code == 401
    assert (await client.get("/me", headers=second)).status_code == 200


async def test_delete_account_needs_no_active_orders(client, seed, auth):
    order = (await place(client, seed, auth)).json()
    response = await client.delete("/me", headers=auth)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "has_active_orders"
    assert (await client.get("/me", headers=auth)).status_code == 200

    await client.post(f"/orders/{order['id']}/cancel", headers=auth)
    assert (await client.delete("/me", headers=auth)).status_code == 204
    assert (await client.get("/me", headers=auth)).status_code == 401


async def test_deleted_account_data_is_scrubbed_and_not_merged_back(client, seed, session_factory):
    auth = await register(client, name="Ali", phone="90 123 45 67")
    order = (await place(client, seed, auth, address_note="12-uy", comment="Tezroq")).json()
    await client.post(f"/orders/{order['id']}/cancel", headers=auth)
    assert (await client.delete("/me", headers=auth)).status_code == 204

    async with session_factory() as session:
        stored = await session.get(Order, order["id"])
        assert stored.customer_name == customer_service.DELETED_NAME
        assert stored.address_note == "" and stored.comment == ""
        assert stored.customer_telegram_id is None
        assert (stored.latitude, stored.longitude) == (0.0, 0.0)
        old = await session.get(Customer, stored.customer_id)
        assert old.phone == "" and not old.phone_verified and old.telegram_user_id is None
        assert not list(await session.scalars(select(CustomerDevice)))

    # Shu raqam bilan qayta kirilsa, yangi hisob ochiladi: eski buyurtmalar unga qaytmaydi
    again = await register(client, name="Ali", phone="90 123 45 67")
    assert (await client.get("/orders", headers=again)).json()["orders"] == []


async def test_blocked_customer_stays_blocked_after_deleting_account(client, seed, session_factory):
    auth = await register(client, phone="90 123 45 67")
    async with session_factory() as session:
        await customer_service.set_blocked(session, "+998901234567", True)
    assert (await client.delete("/me", headers=auth)).status_code == 204
    again = await register(client, phone="90 123 45 67")
    assert (await place(client, seed, again)).json()["error"]["code"] == "blocked"


# ---------- Buyurtma chegaralari ----------


async def test_orders_per_hour_limit(cfg, engine, notifier, seed):
    cfg.max_orders_per_hour = 2
    app = create_app(cfg, engine=engine, notifier=notifier)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        auth = await register(client)
        for _ in range(2):
            created = await place(client, seed, auth)
            assert created.status_code == 201
            await client.post(f"/orders/{created.json()['id']}/cancel", headers=auth)
        refused = await place(client, seed, auth)
        assert refused.status_code == 429
        assert refused.json()["error"]["code"] == "too_many_orders"


async def test_legacy_register_is_off_by_default(cfg, engine, notifier):
    cfg.allow_legacy_register = False
    app = create_app(cfg, engine=engine, notifier=notifier)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        response = await client.post("/auth/register", json={"name": "Ali", "phone": "901234567"})
    assert response.status_code == 410
    assert response.json()["error"]["code"] == "update_required"


async def test_docs_are_hidden_unless_debug(client):
    transport = client._transport
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as root:
        assert (await root.get("/docs")).status_code == 404
        assert (await root.get("/openapi.json")).status_code == 404


# ---------- Kirish haqida xabar va "Bu men emas" ----------


async def test_sign_in_is_announced_once(client, notifier):
    await register(client, phone="90 123 45 67")
    assert notifier.signed_in_ids == [901234567]


async def test_revoke_signs_out_every_device(client, session_factory):
    first = await register(client, phone="90 123 45 67")
    second = await register(client, phone="90 123 45 67")
    other = await register(client, phone="90 000 00 01")
    async with session_factory() as session:
        assert await customer_service.sign_out_telegram_account(session, 901234567) == 2
    assert (await client.get("/me", headers=first)).status_code == 401
    assert (await client.get("/me", headers=second)).status_code == 401
    assert (await client.get("/me", headers=other)).status_code == 200


async def test_revoke_button_in_bot(api, driver, tg, session_factory):
    from aiogram.types import User

    from app.telegram.keyboards import VerifyCb

    auth = await register(api, phone="90 123 45 67")
    user = User(id=901234567, is_bot=False, first_name="Ali")
    await driver.press_data(VerifyCb(action="revoke").pack(), user, chat_id=901234567)
    assert "chiqarildi" in tg.last_screen.text
    assert (await api.get("/me", headers=auth)).status_code == 401


# ---------- Guruhga yuborish ----------


async def new_order(api, seed, **extra) -> dict:
    auth = await register(api)
    response = await api.post(
        "/orders", headers=auth, json={"items": cart(seed), **NEAR, **extra}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def age_orders(session_factory, minutes: int) -> None:
    async with session_factory() as session:
        await session.execute(
            update(Order.__table__).values(created_at=utcnow() - timedelta(minutes=minutes))
        )
        await session.commit()


async def test_owners_are_told_when_orders_do_not_reach_the_group(api, seed, tg, bot, session_factory, bot_cfg):
    tg.failing_chats[GROUP_ID] = TelegramForbiddenError(method=None, message="bot was kicked")
    order = await new_order(api, seed)
    await age_orders(session_factory, 5)
    assert await sweep_unsent(session_factory, bot, GROUP_ID, bot_cfg.timezone) == 0

    watch = UnsentWatch({ADMIN_ID}, GROUP_ID)
    assert await watch.check(session_factory, bot) is True
    alert = tg.of_type(SendMessage)[-1]
    assert alert.chat_id == ADMIN_ID and f"№{order['id']}" in alert.text
    # Qayta-qayta yozilmaydi
    assert await watch.check(session_factory, bot) is False

    # Muammo hal bo'ldi: buyurtma guruhga tushadi, ogohlantirish to'xtaydi
    tg.failing_chats.clear()
    assert await sweep_unsent(session_factory, bot, GROUP_ID, bot_cfg.timezone) == 1
    assert await watch.check(session_factory, bot) is False


async def test_sweep_skips_an_order_telegram_rejects(seed, tg, bot, session_factory, bot_cfg, api):
    first = await new_order(api, seed)
    tg.clear()
    async with session_factory() as session:
        await session.execute(update(Order.__table__).values(tg_message_id=None, tg_chat_id=None))
        second = Order(
            customer_id=1, status="new", customer_name="Vali", phone="+998900000002",
            latitude=39.66, longitude=66.96, items_total=1, delivery_fee=0, total=1,
            items=[OrderItem(name="Osh", price=1, quantity=1)],
            created_at=utcnow() - timedelta(minutes=5),
        )
        session.add(second)
        await session.commit()
        second_id = second.id
    await age_orders(session_factory, 5)

    original = tg.make_request
    rejected = []

    async def flaky(bot_, method, timeout=None):
        if isinstance(method, SendMessage) and f"№{first['id']} " in method.text and not rejected:
            rejected.append(method)
            raise TelegramBadRequest(method=method, message="message is too long")
        return await original(bot_, method, timeout)

    tg.make_request = flaky
    assert await sweep_unsent(session_factory, bot, GROUP_ID, bot_cfg.timezone) == 1
    async with session_factory() as session:
        assert (await session.get(Order, second_id)).tg_message_id is not None
        assert (await session.get(Order, first["id"])).tg_message_id is None


async def test_group_migration_is_followed(seed, tg, bot, session_factory, bot_cfg, api):
    new_chat = -1009999999999
    tg.failing_chats[GROUP_ID] = TelegramMigrateToChat(
        method=None, message="group upgraded", migrate_to_chat_id=new_chat
    )
    publisher._migrated_chats.clear()
    try:
        order = await new_order(api, seed)
        async with session_factory() as session:
            stored = await session.get(Order, order["id"])
            assert stored.tg_chat_id == new_chat and stored.tg_message_id is not None
        assert publisher.current_chat_id(GROUP_ID) == new_chat
        watch = UnsentWatch({ADMIN_ID}, GROUP_ID)
        assert await watch.check(session_factory, bot) is True
        assert str(new_chat) in tg.of_type(SendMessage)[-1].text
    finally:
        publisher._migrated_chats.clear()


async def test_duplicate_group_message_loses_its_buttons(api, seed, driver, tg, session_factory):
    from aiogram.methods import EditMessageReplyMarkup

    order = await new_order(api, seed)
    async with session_factory() as session:
        real_message = (await session.get(Order, order["id"])).tg_message_id
    await driver.press_in_group("Qabul qilish", real_message + 50)  # eski nusxa
    async with session_factory() as session:
        assert (await session.get(Order, order["id"])).status == OrderStatus.NEW.value
    stripped = tg.of_type(EditMessageReplyMarkup)[-1]
    assert stripped.message_id == real_message + 50 and stripped.reply_markup is None


def test_very_long_order_fits_into_one_telegram_message():
    order = Order(
        id=1, status="new", customer_name="A" * 60, phone="+998901234567",
        latitude=1.0, longitude=1.0, address_note="m" * 255, comment="i" * 500,
        items_total=1, delivery_fee=0, discount=0, total=1,
        items=[OrderItem(name="T" * 100, price=1000, quantity=2) for _ in range(30)],
        history=[],
    )
    assert len(order_text(order, "Asia/Tashkent")) < 4096


# ---------- Kiritishni tushunish ----------


@pytest.mark.parametrize("raw", ["35000.00", "12,5", "35 000,50 so'm", "3²", "٣٥٠٠٠"])
def test_amount_rejects_decimals_and_odd_digits(raw):
    with pytest.raises(ValueError):
        parse_amount(raw)


@pytest.mark.parametrize("raw, expected", [("35.000", 35000), ("1,250,000 so'm", 1_250_000), ("35 000", 35000)])
def test_amount_still_accepts_thousand_separators(raw, expected):
    assert parse_amount(raw) == expected


@pytest.mark.parametrize("raw", ["nan", "inf", "-1", "201"])
def test_km_rejects_nan_and_out_of_range(raw):
    with pytest.raises(ValueError):
        parse_km(raw)
    assert not math.isnan(parse_km("3,5"))


def test_count_rejects_superscript_digits():
    with pytest.raises(ValueError):
        parse_count("²", 100, "10")


# ---------- Yarim qolgan sehrgar ----------


async def test_abandoned_rename_does_not_eat_the_next_message(driver, seed, session_factory):
    await driver.say("/start")
    await driver.press("Menyu")
    await driver.press("Osh")
    await driver.press("Nomi")
    await driver.say("/mijoz 901234567")  # "Bekor"ni bosmasdan boshqa ishga o'tdi
    await driver.say("salom")
    async with session_factory() as session:
        assert (await session.get(Product, seed["osh"])).name == "Osh"


async def test_stale_button_is_answered(driver, seed):
    from aiogram.types import User

    from app.telegram.keyboards import AdminCb

    await driver.press_data(
        AdminCb(action="add_skip_photo").pack(), User(id=ADMIN_ID, is_bot=False, first_name="A"), ADMIN_ID
    )
    from aiogram.methods import AnswerCallbackQuery

    answers = driver.session.of_type(AnswerCallbackQuery)
    assert answers and "eskirgan" in (answers[-1].text or "")
    assert "Amora boshqaruvi" in driver.screen


async def test_order_response_carries_client_order_id(client, seed, auth):
    key = "6f1c2f0e-3a53-4c0e-9d59-0f6f3c1a2b4d"
    created = (await place(client, seed, auth, client_order_id=key)).json()
    assert created["client_order_id"] == key
    listed = (await client.get("/orders", headers=auth)).json()["orders"]
    assert [order["client_order_id"] for order in listed] == [key]
