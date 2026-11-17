"""Raqamni Telegram orqali tasdiqlash: ilova, bot va bitta raqam = bitta mijoz."""

from datetime import timedelta

from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove
from sqlalchemy import select, update

from app.db import utcnow
from app.models import Customer, CustomerDevice, Order, OrderStatus, PhoneVerification
from tests.conftest import NEAR, register_unverified, verify_phone
from tests.telegram_fakes import ADMIN_ID, GROUP_ID
from tests.test_bot import place_order

CUSTOMER_TG = 7001


def order_body(seed) -> dict:
    return {"items": [{"product_id": seed["osh"], "quantity": 1}], **NEAR}


async def start(api, name="Ali", headers=None) -> dict:
    response = await api.post("/auth/telegram", json={"name": name, "platform": "android"}, headers=headers or {})
    assert response.status_code == 201, response.text
    return response.json()


async def check(api, code: str):
    return await api.post("/auth/telegram/check", json={"code": code})


# ---------- Bot orqali to'liq yo'l ----------


async def test_full_flow_through_the_bot(api, driver, tg, seed, session_factory):
    started = await start(api)
    assert started["bot_url"] == f"https://t.me/amora_test_bot?start=v_{started['code']}"
    assert started["app_url"] == f"tg://resolve?domain=amora_test_bot&start=v_{started['code']}"
    assert (await check(api, started["code"])).json() == {"status": "pending", "token": None, "customer": None}

    await driver.say(f"/start v_{started['code']}", user_id=CUSTOMER_TG)
    assert "Raqamni yuborish" in driver.screen
    markup = tg.last_screen.reply_markup
    assert isinstance(markup, ReplyKeyboardMarkup)
    assert markup.keyboard[0][0].request_contact is True
    assert (await check(api, started["code"])).json()["status"] == "pending"

    await driver.send_contact("998901234567", user_id=CUSTOMER_TG)
    assert "Raqamingiz tasdiqlandi: +998 90 123 45 67" in driver.screen
    assert isinstance(tg.last_screen.reply_markup, ReplyKeyboardRemove)

    body = (await check(api, started["code"])).json()
    assert body["status"] == "verified"
    assert body["customer"]["phone"] == "+998901234567"
    assert body["customer"]["name"] == "Ali"
    assert body["customer"]["phone_verified"] is True
    auth = {"Authorization": f"Bearer {body['token']}"}
    assert (await api.post("/orders", headers=auth, json=order_body(seed))).status_code == 201

    # Javob yo'lda yo'qolsa, ilova qayta so'raydi: shu telefonga yangi kalit, eskisi bekor
    again = await check(api, started["code"])
    assert again.status_code == 200
    retried = {"Authorization": f"Bearer {again.json()['token']}"}
    assert (await api.get("/me", headers=retried)).json()["phone"] == "+998901234567"
    assert (await api.get("/me", headers=auth)).status_code == 401
    async with session_factory() as session:
        assert len(list(await session.scalars(select(CustomerDevice)))) == 1
        # Qisqa muddatdan keyin kod butunlay eskiradi
        await session.execute(
            update(PhoneVerification).values(expires_at=utcnow() - timedelta(seconds=1))
        )
        await session.commit()
    again = await check(api, started["code"])
    assert again.status_code == 410
    assert again.json()["error"]["code"] == "verification_expired"


async def test_someone_elses_contact_is_refused(api, driver):
    started = await start(api)
    await driver.say(f"/start v_{started['code']}", user_id=CUSTOMER_TG)
    await driver.send_contact("998931112233", user_id=CUSTOMER_TG, contact_user_id=999_999)
    assert "o'zingizning raqamingizni" in driver.screen
    assert (await check(api, started["code"])).json()["status"] == "pending"


async def test_link_opened_by_another_telegram_account(api, driver):
    started = await start(api)
    await driver.say(f"/start v_{started['code']}", user_id=CUSTOMER_TG)
    await driver.say(f"/start v_{started['code']}", user_id=CUSTOMER_TG + 1)
    assert "boshqa Telegram hisobida" in driver.screen
    # Ikkinchi hisob o'z raqamini yuborsa ham, so'rov unga tegishli emas
    await driver.send_contact("998931112233", user_id=CUSTOMER_TG + 1)
    assert "topilmadi" in driver.screen
    assert (await check(api, started["code"])).json()["status"] == "pending"


async def test_expired_link_and_unknown_code(api, driver, session_factory):
    started = await start(api)
    async with session_factory() as session:
        await session.execute(
            update(PhoneVerification).values(expires_at=utcnow() - timedelta(seconds=1))
        )
        await session.commit()
    await driver.say(f"/start v_{started['code']}", user_id=CUSTOMER_TG)
    assert "eskirgan" in driver.screen
    assert (await check(api, started["code"])).status_code == 410
    assert (await check(api, "x" * 22)).status_code == 410


async def test_contact_without_request(driver):
    await driver.send_contact("998901234567", user_id=CUSTOMER_TG)
    assert "topilmadi" in driver.screen


async def test_foreign_number_is_refused(api, driver):
    started = await start(api)
    await driver.say(f"/start v_{started['code']}", user_id=CUSTOMER_TG)
    await driver.send_contact("+79161234567", user_id=CUSTOMER_TG)
    assert "O'zbekiston raqamlari" in driver.screen
    assert (await check(api, started["code"])).json()["status"] == "pending"


async def test_plain_start_from_customer_still_explains_the_bot(driver):
    await driver.say("/start", user_id=CUSTOMER_TG)
    assert "xodimlari uchun" in driver.screen


async def test_admin_can_also_verify_own_number(api, driver):
    started = await start(api)
    await driver.say(f"/start v_{started['code']}", user_id=ADMIN_ID)
    assert "Raqamni yuborish" in driver.screen
    await driver.send_contact("998901234567", user_id=ADMIN_ID)
    assert "tasdiqlandi" in driver.screen


async def test_unavailable_without_bot(client, cfg):
    cfg.bot_username = ""
    response = await client.post("/auth/telegram", json={})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "verify_unavailable"


# ---------- Bitta raqam = bitta mijoz ----------


async def test_second_phone_with_same_number_sees_the_same_orders(api, seed, session_factory):
    order, first = await place_order(api, seed)
    second = await verify_phone(api, "90 123 45 67", name="Boshqa ism")
    orders = (await api.get("/orders", headers=second)).json()["orders"]
    assert [item["id"] for item in orders] == [order["id"]]
    me = (await api.get("/me", headers=second)).json()
    assert me["name"] == "Ali"  # avvalgi ism qoladi, bitta mijoz
    # Birinchi telefon ham ishlayveradi
    assert (await api.get("/me", headers=first)).status_code == 200
    async with session_factory() as session:
        assert len(list(await session.scalars(select(Customer)))) == 1
        assert len(list(await session.scalars(select(CustomerDevice)))) == 2
    # Bekor qilishni ikkinchi telefondan ham qilsa bo'ladi
    cancelled = await api.post(f"/orders/{order['id']}/cancel", headers=second)
    assert cancelled.json()["status"] == "cancelled"


async def _old_order(session_factory, customer_phone: str) -> int:
    """Eski ilovada (tasdiqlanmagan) berilgan buyurtma."""
    async with session_factory() as session:
        customer = await session.scalar(
            select(Customer).where(Customer.phone == customer_phone).order_by(Customer.id.desc())
        )
        order = Order(
            customer_id=customer.id,
            status=OrderStatus.DELIVERED.value,
            customer_name=customer.name,
            phone=customer_phone,
            latitude=NEAR["latitude"],
            longitude=NEAR["longitude"],
            items_total=35_000,
            delivery_fee=0,
            total=35_000,
        )
        session.add(order)
        await session.commit()
        return order.id


async def test_old_accounts_merge_into_the_verified_customer(api, seed, session_factory):
    # Ikki telefonda eski ilova: bir xil raqam, ikki xil ism, ikki alohida hisob
    this_phone = await register_unverified(api, name="Ali", phone="90 123 45 67")
    first_order = await _old_order(session_factory, "+998901234567")
    other_phone = await register_unverified(api, name="Alijon", phone="90 123 45 67")
    second_order = await _old_order(session_factory, "+998901234567")
    # Eski ilovada boshqa raqam yozilgan uchinchi hisob (shu telefonning o'zi)
    own_other = await _old_order(session_factory, "+998901234567")

    verified = await verify_phone(api, "90 123 45 67", headers=this_phone)
    orders = (await api.get("/orders", headers=verified)).json()["orders"]
    assert sorted(item["id"] for item in orders) == sorted([first_order, second_order, own_other])
    # Shu telefonning eski kaliti endi ishlamaydi (yangisi berildi), tasdiqlanmagan boshqa telefon
    # ham chiqib ketadi: u ham raqamni tasdiqlashi kerak
    assert (await api.get("/me", headers=this_phone)).status_code == 401
    assert (await api.get("/me", headers=other_phone)).status_code == 401
    async with session_factory() as session:
        customers = list(await session.scalars(select(Customer)))
    assert [(c.name, c.phone, c.phone_verified) for c in customers] == [("Ali", "+998901234567", True)]


async def test_old_account_with_other_number_keeps_its_orders_on_this_phone(api, seed, session_factory):
    old = await register_unverified(api, name="Ali", phone="93 111 22 33")
    old_order = await _old_order(session_factory, "+998931112233")
    verified = await verify_phone(api, "90 123 45 67", headers=old)
    me = (await api.get("/me", headers=verified)).json()
    assert me["phone"] == "+998901234567" and me["phone_verified"] is True
    orders = (await api.get("/orders", headers=verified)).json()["orders"]
    assert [item["id"] for item in orders] == [old_order]


async def test_new_customer_gets_typed_name_or_telegram_name(api):
    auth = await verify_phone(api, "90 123 45 67", name="Sardor")
    assert (await api.get("/me", headers=auth)).json()["name"] == "Sardor"
    auth = await verify_phone(api, "93 111 22 33", name=None)
    assert (await api.get("/me", headers=auth)).json()["name"] == "Tg Ism"


async def test_telegram_account_changed_its_number(api, seed, session_factory):
    from app.services import verify

    order, _ = await place_order(api, seed)
    # Xuddi shu Telegram hisobi endi boshqa raqamga ega
    response = await api.post("/auth/telegram", json={})
    code = response.json()["code"]
    async with session_factory() as session:
        await verify.attach_telegram(session, code, 901234567, "Ali")
    async with session_factory() as session:
        await verify.confirm_contact(session, 901234567, "+998935556677")
    body = (await check(api, code)).json()
    assert body["customer"]["phone"] == "+998935556677"
    auth = {"Authorization": f"Bearer {body['token']}"}
    assert [o["id"] for o in (await api.get("/orders", headers=auth)).json()["orders"]] == [order["id"]]


async def test_recycled_number_does_not_open_previous_owners_account(api, seed, session_factory):
    # Raqamning eski egasi buyurtma bergan, keyin operator raqamni boshqa odamga berdi
    old_order, old_auth = await place_order(api, seed)
    new_owner = await verify_phone(api, "90 123 45 67", name="Yangi", telegram_id=555)
    assert (await api.get("/orders", headers=new_owner)).json()["orders"] == []
    me = (await api.get("/me", headers=new_owner)).json()
    assert me["name"] == "Yangi" and me["phone_verified"] is True
    # Eski egasining telefoni hisobdan chiqdi, buyurtmasi o'zida qoldi
    assert (await api.get("/me", headers=old_auth)).status_code == 401
    async with session_factory() as session:
        old = await session.scalar(select(Customer).where(Customer.telegram_user_id == 901234567))
        assert old.phone_verified is False
        assert (await session.get(Order, old_order["id"])).customer_id == old.id
    # Eski egasi yangi raqam bilan qaytsa, eski buyurtmalari yana ko'rinadi
    back = await verify_phone(api, "93 111 22 33", telegram_id=901234567)
    assert [o["id"] for o in (await api.get("/orders", headers=back)).json()["orders"]] == [old_order["id"]]


async def test_recycled_number_check_from_previous_owners_phone(api, seed, session_factory):
    # Yangi egasi raqamni eski egasining telefonidan (masalan, sotib olingan telefon) tasdiqlaydi
    _, old_auth = await place_order(api, seed)
    new_owner = await verify_phone(api, "90 123 45 67", headers=old_auth, telegram_id=555)
    assert (await api.get("/orders", headers=new_owner)).json()["orders"] == []
    async with session_factory() as session:
        customers = list(await session.scalars(select(Customer).order_by(Customer.id)))
    assert [(c.telegram_user_id, c.phone_verified) for c in customers] == [(901234567, False), (555, True)]


# ---------- Bloklash ----------


async def test_block_follows_the_telegram_account(api, seed, driver, session_factory):
    from app.services import verify

    await place_order(api, seed)
    await driver.say("/blok 901234567")
    assert "bloklandi" in driver.screen
    # Bloklangan odam Telegram'da raqamini almashtirib qaytdi
    response = await api.post("/auth/telegram", json={})
    code = response.json()["code"]
    async with session_factory() as session:
        await verify.attach_telegram(session, code, 901234567, "Ali")
    async with session_factory() as session:
        await verify.confirm_contact(session, 901234567, "+998935556677")
    body = (await check(api, code)).json()
    auth = {"Authorization": f"Bearer {body['token']}"}
    blocked = await api.post("/orders", headers=auth, json=order_body(seed))
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "blocked"


async def test_block_of_merged_old_account_is_kept(api, seed, driver, session_factory):
    # Eski ilovada boshqa raqam bilan ochilgan hisob bloklangan; shu telefondan yangi raqam tasdiqlandi
    old = await register_unverified(api, phone="93 111 22 33")
    await driver.say("/blok 931112233")
    assert "bloklandi" in driver.screen
    await register_unverified(api, phone="90 123 45 67")
    auth = await verify_phone(api, "90 123 45 67", headers=old)
    response = await api.post("/orders", headers=auth, json=order_body(seed))
    assert response.status_code == 403


async def test_blocked_number_stays_blocked_after_verification(api, seed, driver):
    await register_unverified(api, phone="90 123 45 67")
    await driver.say("/blok 901234567")
    auth = await verify_phone(api, "90 123 45 67")
    response = await api.post("/orders", headers=auth, json=order_body(seed))
    assert response.status_code == 403


# ---------- Guruh va mijoz kartasi ----------


async def test_group_message_links_to_customer_telegram(api, seed, tg):
    from aiogram.methods import SendMessage

    await place_order(api, seed)
    group = [m for m in tg.of_type(SendMessage) if m.chat_id == GROUP_ID][-1]
    assert '<a href="tg://user?id=901234567">Telegram</a>' in group.text


async def test_customer_card_shows_one_verified_customer(api, seed, driver):
    await place_order(api, seed)
    await verify_phone(api, "90 123 45 67", name="Boshqa")
    await driver.say("/mijoz 901234567")
    assert "Telegram orqali tasdiqlangan" in driver.screen
    assert "tg://user?id=901234567" in driver.screen
    assert "Boshqa" not in driver.screen
