"""Promokodlar, birinchi buyurtma chegirmasi va banner: server va bot."""

from datetime import timedelta

from aiogram.methods import AnswerCallbackQuery, SendMessage
from aiogram.types import User
from sqlalchemy import select, update

from app.db import utcnow
from app.models import Order, OrderStatus, PromoCode, ShopSettings, Staff
from app.services import orders as order_service
from app.services.promos import evaluate
from tests.conftest import NEAR, register
from tests.telegram_fakes import GROUP_ID



def cart(seed, osh: int = 2, lagmon: int = 1) -> list[dict]:
    """Osh 35 000 × 2 + Lag'mon 30 000 = 100 000 so'm."""
    items = [{"product_id": seed["osh"], "quantity": osh}]
    if lagmon:
        items.append({"product_id": seed["lagmon"], "quantity": lagmon})
    return items


async def add_promo(session_factory, **values) -> int:
    values.setdefault("kind", "percent")
    values.setdefault("value", 10)
    async with session_factory() as session:
        promo = PromoCode(**values)
        session.add(promo)
        await session.commit()
        return promo.id


async def get_promo(session_factory, promo_id: int) -> PromoCode:
    async with session_factory() as session:
        return await session.get(PromoCode, promo_id)


async def quote(client, seed, headers=None, **extra) -> dict:
    response = await client.post(
        "/orders/quote", headers=headers or {}, json={"items": cart(seed), **NEAR, **extra}
    )
    assert response.status_code == 200, response.text
    return response.json()


async def order(client, seed, auth, **extra):
    return await client.post("/orders", headers=auth, json={"items": cart(seed), **NEAR, **extra})


# ---------- Hisoblash ----------


async def test_quote_with_promo_code(client, seed, session_factory):
    await add_promo(session_factory, code="AMORA10", value=10)
    result = await quote(client, seed, promo_code=" amora10 ")
    assert result["items_total"] == 100_000
    assert result["discount"] == 10_000
    assert result["delivery_fee"] == 10_000
    assert result["total"] == 100_000
    assert result["promo_title"] == "AMORA10: −10%"
    assert result["promo_error"] is None
    assert result["can_order"] is True


async def test_unknown_code_does_not_block_quote(client, seed):
    result = await quote(client, seed, promo_code="YOQKOD")
    assert result["discount"] == 0 and result["total"] == 110_000
    assert result["promo_error"] == "Bunday promokod yo'q"
    assert result["can_order"] is True


async def test_percent_cap_amount_and_min_order(client, seed, session_factory):
    await add_promo(session_factory, code="KATTA", value=50, max_discount=20_000)
    await add_promo(session_factory, code="PUL", kind="amount", value=15_000, min_order=120_000)
    assert (await quote(client, seed, promo_code="KATTA"))["discount"] == 20_000
    small = await quote(client, seed, promo_code="PUL")
    assert small["discount"] == 0
    assert small["promo_error"] == "Promokod 120 000 so'mdan boshlab amal qiladi"


async def test_amount_discount_never_exceeds_food(client, seed, session_factory):
    await add_promo(session_factory, code="BEPUL", kind="amount", value=500_000)
    result = await quote(client, seed, promo_code="BEPUL")
    assert result["discount"] == 100_000
    assert result["total"] == 10_000  # yetkazish baribir to'lanadi


async def test_expired_inactive_and_used_up_codes(client, seed, session_factory):
    await add_promo(session_factory, code="ESKI", expires_at=utcnow() - timedelta(minutes=1))
    await add_promo(session_factory, code="OCHIQ", is_active=False)
    await add_promo(session_factory, code="TUGADI", usage_limit=3, used_count=3)
    assert (await quote(client, seed, promo_code="ESKI"))["promo_error"] == "Promokod muddati tugagan"
    assert (await quote(client, seed, promo_code="OCHIQ"))["promo_error"] == (
        "Bu promokod hozir ishlamaydi"
    )
    assert (await quote(client, seed, promo_code="TUGADI"))["promo_error"] == "Promokod tugab qolgan"


async def test_free_delivery_threshold_uses_sum_before_discount(client, seed, session_factory):
    async with session_factory() as session:
        await session.execute(update(ShopSettings).values(free_delivery_from=100_000))
        await session.commit()
    await add_promo(session_factory, code="AMORA10")
    result = await quote(client, seed, promo_code="AMORA10")
    assert result["delivery_fee"] == 0 and result["total"] == 90_000


# ---------- Buyurtma ----------


async def test_order_with_code_is_used_once_per_customer(client, seed, auth, session_factory):
    promo_id = await add_promo(session_factory, code="AMORA10")
    response = await order(client, seed, auth, promo_code="amora10", expected_total=100_000)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["discount"] == 10_000 and body["total"] == 100_000
    assert body["promo_code"] == "AMORA10"
    assert (await get_promo(session_factory, promo_id)).used_count == 1

    # Shu mijoz ikkinchi marta ishlata olmaydi
    again = await quote(client, seed, headers=auth, promo_code="AMORA10")
    assert again["promo_error"] == "Siz bu promokoddan foydalangansiz"
    response = await order(client, seed, auth, promo_code="AMORA10")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "promo_invalid"

    # Bekor qilsa, promokod qaytadi
    cancel = await client.post(f"/orders/{body['id']}/cancel", headers=auth)
    assert cancel.status_code == 200
    assert (await get_promo(session_factory, promo_id)).used_count == 0
    response = await order(client, seed, auth, promo_code="AMORA10")
    assert response.status_code == 201


async def test_usage_limit_is_shared_and_returned_on_reject(client, seed, session_factory):
    promo_id = await add_promo(session_factory, code="BIRTA", usage_limit=1)
    first = await register(client, phone="90 111 11 11")
    second = await register(client, phone="90 222 22 22")
    response = await order(client, seed, first, promo_code="BIRTA")
    assert response.status_code == 201
    order_id = response.json()["id"]

    response = await order(client, seed, second, promo_code="BIRTA")
    assert response.status_code == 409
    assert response.json()["error"]["message"] == "Promokod tugab qolgan"

    async with session_factory() as session:
        await order_service.set_status_by_staff(
            session, order_id, OrderStatus.REJECTED, "Kassir", "Taom tugagan"
        )
    assert (await get_promo(session_factory, promo_id)).used_count == 0
    response = await order(client, seed, second, promo_code="BIRTA")
    assert response.status_code == 201


async def test_used_count_cannot_go_over_limit(session_factory, seed):
    from app.services.promos import take_use

    promo_id = await add_promo(session_factory, code="IKKI", usage_limit=2)
    async with session_factory() as session:
        assert await take_use(session, promo_id)
        assert await take_use(session, promo_id)
        assert not await take_use(session, promo_id)
        await session.commit()
    assert (await get_promo(session_factory, promo_id)).used_count == 2


async def test_first_order_only_code(client, seed, auth, session_factory):
    await add_promo(session_factory, code="YANGI", first_order_only=True)
    assert (await quote(client, seed, headers=auth, promo_code="YANGI"))["discount"] == 10_000
    assert (await order(client, seed, auth)).status_code == 201
    result = await quote(client, seed, headers=auth, promo_code="YANGI")
    assert result["promo_error"] == "Bu promokod faqat birinchi buyurtma uchun"


# ---------- Birinchi buyurtma chegirmasi ----------


async def test_first_order_discount_is_automatic(client, seed, session_factory):
    await add_promo(session_factory, is_auto=True, value=15, first_order_only=True)
    # Eski ilova so'ramaydi: summa o'zgarmaydi
    assert (await quote(client, seed))["discount"] == 0
    # Yangi ilova, mijoz hali ro'yxatdan o'tmagan
    result = await quote(client, seed, apply_auto_promo=True)
    assert result["discount"] == 15_000
    assert result["promo_title"] == "Birinchi buyurtma: −15%"

    auth = await register(client)
    response = await order(client, seed, auth, apply_auto_promo=True, expected_total=95_000)
    assert response.status_code == 201, response.text
    assert response.json()["promo_code"] == "Birinchi buyurtma"
    assert response.json()["discount"] == 15_000

    # Ikkinchi buyurtmada endi yo'q
    assert (await quote(client, seed, headers=auth, apply_auto_promo=True))["discount"] == 0
    response = await order(client, seed, auth, apply_auto_promo=True, expected_total=110_000)
    assert response.status_code == 201 and response.json()["discount"] == 0


async def test_entered_code_replaces_first_order_discount(client, seed, session_factory):
    await add_promo(session_factory, is_auto=True, value=15)
    await add_promo(session_factory, code="AMORA10", value=10)
    result = await quote(client, seed, apply_auto_promo=True, promo_code="AMORA10")
    assert result["discount"] == 10_000 and result["promo_title"].startswith("AMORA10")


async def test_auto_promo_is_not_usable_as_a_code(session_factory, seed):
    await add_promo(session_factory, is_auto=True, value=15)
    async with session_factory() as session:
        result = await evaluate(session, "", False, 100_000, None)
        assert result.promo is None and result.error is None


async def test_old_cancelled_order_still_counts_as_first(client, seed, auth, session_factory):
    await add_promo(session_factory, is_auto=True, value=15)
    response = await order(client, seed, auth)
    await client.post(f"/orders/{response.json()['id']}/cancel", headers=auth)
    assert (await quote(client, seed, headers=auth, apply_auto_promo=True))["discount"] == 15_000


# ---------- Banner ----------


async def test_shop_returns_banner(client, seed, session_factory):
    shop = (await client.get("/shop")).json()
    assert shop["banner_title"] is None and shop["banner_text"] is None
    async with session_factory() as session:
        await session.execute(
            update(ShopSettings).values(banner_title="Birinchi buyurtmaga\n−15%", banner_text="Kod: AMORA")
        )
        await session.commit()
    shop = (await client.get("/shop")).json()
    assert shop["banner_title"] == "Birinchi buyurtmaga\n−15%"
    assert shop["banner_text"] == "Kod: AMORA"


# ---------- Guruh xabari va hisobot ----------


async def test_group_message_shows_discount(api, seed, tg, session_factory):
    await add_promo(session_factory, code="AMORA10")
    auth = await register(api)
    response = await order(api, seed, auth, promo_code="AMORA10")
    assert response.status_code == 201
    text = [m for m in tg.of_type(SendMessage) if m.chat_id == GROUP_ID][0].text
    assert "🎉 Chegirma (AMORA10): −10 000 so'm" in text
    assert "<b>Jami: 100 000 so'm</b>" in text


async def test_report_counts_discounts(session_factory, seed, client, auth):
    from app.services.reports import build_report

    await add_promo(session_factory, code="AMORA10")
    response = await order(client, seed, auth, promo_code="AMORA10")
    async with session_factory() as session:
        await session.execute(update(Order).values(status=OrderStatus.DELIVERED.value))
        await session.commit()
    async with session_factory() as session:
        now = utcnow()
        report = await build_report(
            session, "Bugun", now - timedelta(hours=1), now + timedelta(hours=1), "Asia/Tashkent"
        )
    assert response.status_code == 201
    assert report.discounts == 10_000 and report.promo_orders == 1
    assert report.revenue == 100_000


# ---------- Bot: Aksiyalar bo'limi ----------


async def open_promos(driver):
    await driver.say("/start")
    await driver.press("Aksiyalar")


async def test_bot_banner_editing(driver, seed, session_factory):
    await open_promos(driver)
    assert "Banner: standart" in driver.screen
    await driver.press("Bosh sahifadagi banner")
    await driver.press("Sarlavha")
    await driver.say("Birinchi   buyurtmaga\n−15% chegirma")
    assert "Sarlavha: <b>Birinchi buyurtmaga\n−15% chegirma</b>" in driver.screen
    await driver.press("Pastki matn")
    await driver.say("x" * 57)
    assert "Juda uzun" in driver.screen
    await driver.say("Promokod: AMORA10")
    async with session_factory() as session:
        shop = await session.get(ShopSettings, 1)
        assert shop.banner_title == "Birinchi buyurtmaga\n−15% chegirma"
        assert shop.banner_text == "Promokod: AMORA10"

    await driver.press("Standart matnga qaytarish")
    async with session_factory() as session:
        shop = await session.get(ShopSettings, 1)
        assert shop.banner_title is None and shop.banner_text is None


async def test_bot_first_order_discount(driver, seed, session_factory, client):
    await open_promos(driver)
    await driver.press("Birinchi buyurtma chegirmasi")
    assert "Hozir: <b>o'chiq</b>" in driver.screen
    await driver.press("Chegirmani belgilash")
    await driver.say("15 foiz")
    assert "Foizni" in driver.screen or "Chegirmani shunday" in driver.screen
    await driver.say("15% 10 000")
    assert "Hozir: <b>−15% (ko'pi bilan 10 000 so'm)</b>" in driver.screen
    result = await quote(client, seed, apply_auto_promo=True)
    assert result["discount"] == 10_000

    await driver.press("O'chirish")
    assert "Hozir: <b>o'chiq</b>" in driver.screen
    assert (await quote(client, seed, apply_auto_promo=True))["discount"] == 0


async def test_bot_creates_and_manages_promo_code(driver, seed, session_factory, client):
    await open_promos(driver)
    await driver.press("Promokod qo'shish")
    await driver.say("am")
    assert "3–20" in driver.screen
    await driver.say("amora10")
    await driver.say("10%")
    await driver.say("50 000")
    await driver.say("100")
    await driver.say("7")
    assert driver.buttons[:2] == ["👥 Hamma mijozlar", "🆕 Faqat birinchi buyurtma"]
    await driver.press("Hamma mijozlar")
    screen = driver.screen
    assert "🎟 <b>AMORA10</b> · 🟢 ishlayapti" in screen
    assert "Eng kam buyurtma: 50 000 so'm" in screen
    assert "Ishlatildi: 0 (100 tadan)" in screen
    assert "gacha" in screen

    async with session_factory() as session:
        promo = await session.scalar(select(PromoCode).where(PromoCode.code == "AMORA10"))
        assert promo.min_order == 50_000 and promo.usage_limit == 100
        assert not promo.first_order_only and promo.created_by is not None
    assert (await quote(client, seed, promo_code="AMORA10"))["discount"] == 10_000

    await driver.press("To'xtatish")
    assert "to'xtatilgan" in driver.screen
    assert (await quote(client, seed, promo_code="AMORA10"))["promo_error"]
    await driver.press("Yoqish")

    # Xuddi shu nom bilan ikkinchisi qo'shilmaydi
    await open_promos(driver)
    assert "🟢 AMORA10" in driver.buttons
    await driver.press("Promokod qo'shish")
    await driver.say("AMORA10")
    assert "allaqachon bor" in driver.screen
    await driver.say("/bekor")
    assert "boshqaruvi" in driver.screen

    await open_promos(driver)
    await driver.press("AMORA10")
    await driver.press("O'chirib tashlash")
    await driver.press("Ha, o'chirilsin")
    assert "Promokodlar hali yo'q" in driver.screen


async def test_staff_cannot_open_promotions(driver, seed, tg, session_factory):
    async with session_factory() as session:
        session.add(Staff(telegram_id=888, name="Sardor", role="staff"))
        await session.commit()
    await driver.say("/start", user_id=888)
    assert "🎉 Aksiyalar" not in driver.buttons
    tg.clear()
    user = User(id=888, is_bot=False, first_name="S")
    await driver.press_data("a:promo:0:", user, 888)
    assert "faqat admin" in tg.of_type(AnswerCallbackQuery)[-1].text


# ---------- Tekshiruvdan keyingi tuzatishlar ----------


async def test_bad_code_keeps_first_order_discount_and_order_matches(client, seed, session_factory):
    await add_promo(session_factory, is_auto=True, value=15)
    result = await quote(client, seed, apply_auto_promo=True, promo_code="XATO")
    assert result["promo_error"] == "Bunday promokod yo'q"
    assert result["discount"] == 15_000 and result["total"] == 95_000
    assert result["promo_title"] == "Birinchi buyurtma: −15%"
    # Ilova ishlamagan kodni buyurtmaga qo'shmaydi: summa savatdagi bilan bir xil
    auth = await register(client)
    response = await order(client, seed, auth, apply_auto_promo=True, expected_total=95_000)
    assert response.status_code == 201, response.text


async def test_quote_uses_known_phone_before_registration(client, seed, session_factory):
    await add_promo(session_factory, is_auto=True, value=15)
    auth = await register(client, phone="90 123 45 67")
    assert (await order(client, seed, auth)).status_code == 201
    # Ilova qayta o'rnatilgan: token yo'q, lekin telefon ma'lum
    again = await quote(client, seed, apply_auto_promo=True, phone="+998 90 123 45 67")
    assert again["discount"] == 0
    stranger = await quote(client, seed, apply_auto_promo=True, phone="90 000 00 00")
    assert stranger["discount"] == 15_000
    junk = await quote(client, seed, apply_auto_promo=True, phone="abc")
    assert junk["discount"] == 15_000


async def test_recreated_code_is_still_once_per_customer(client, seed, auth, session_factory):
    first = await add_promo(session_factory, code="AMORA10")
    assert (await order(client, seed, auth, promo_code="AMORA10")).status_code == 201
    async with session_factory() as session:
        await session.delete(await session.get(PromoCode, first))
        await session.commit()
    await add_promo(session_factory, code="AMORA10")
    result = await quote(client, seed, headers=auth, promo_code="AMORA10")
    assert result["promo_error"] == "Siz bu promokoddan foydalangansiz"


async def test_banner_title_lines_must_fit(driver, seed, session_factory):
    await open_promos(driver)
    await driver.press("Bosh sahifadagi banner")
    await driver.press("Sarlavha")
    await driver.say("Birinchi buyurtmaga katta chegirma\n−15%")
    assert "Har bir qator" in driver.screen
    async with session_factory() as session:
        assert (await session.get(ShopSettings, 1)).banner_title is None
