from datetime import time

import httpx
import pytest
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import (
    AnswerCallbackQuery,
    EditMessageReplyMarkup,
    EditMessageText,
    SendMessage,
)
from aiogram.types import User

from app.main import create_app
from app.models import Category, Order, OrderStatus, ShopSettings
from app.telegram.parsing import parse_amount, parse_hours, parse_km
from app.telegram.publisher import TelegramNotifier, publish_order, sweep_unsent
from tests.conftest import NEAR, register
from tests.telegram_fakes import (
    ADMIN_ID,
    FAKE_JPEG,
    GROUP_ID,
    STRANGER_ID,
    Driver,
    button_labels,
    find_button,
    get_dispatcher,
    make_fake_bot,
)


@pytest.fixture
def bot_cfg(cfg):
    cfg.orders_chat_id = GROUP_ID
    cfg.admin_ids = str(ADMIN_ID)
    return cfg


@pytest.fixture
async def bot():
    return make_fake_bot()


@pytest.fixture
def tg(bot):
    return bot.session


@pytest.fixture
def driver(bot, bot_cfg, session_factory) -> Driver:
    return Driver(get_dispatcher(bot_cfg, session_factory), bot)


@pytest.fixture
async def api(bot, bot_cfg, engine, session_factory):
    """API haqiqiy TelegramNotifier bilan: buyurtma berilganda (soxta) guruhga xabar ketadi."""
    notifier = TelegramNotifier(bot, GROUP_ID, session_factory, bot_cfg.timezone)
    app = create_app(bot_cfg, engine=engine, notifier=notifier)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        yield client


async def place_order(api, seed, auth=None, **extra) -> tuple[dict, dict]:
    auth = auth or await register(api)
    body = {
        "items": [
            {"product_id": seed["osh"], "quantity": 2},
            {"product_id": seed["lagmon"], "quantity": 1},
        ],
        **NEAR,
        **extra,
    }
    response = await api.post("/orders", headers=auth, json=body)
    assert response.status_code == 201, response.text
    return response.json(), auth


async def db_order(session_factory, order_id: int) -> Order:
    async with session_factory() as session:
        return await session.get(Order, order_id)


# ---------- Buyurtma guruhga keladi ----------


async def test_new_order_is_posted_to_group(api, seed, tg, session_factory):
    order, _ = await place_order(api, seed, address_note="12-uy", comment="Tezroq <b>iltimos</b>")

    sent = tg.of_type(SendMessage)
    assert len(sent) == 1
    message = sent[0]
    assert message.chat_id == GROUP_ID
    text = message.text
    assert f"№{order['id']}" in text and "Yangi buyurtma" in text
    assert "2 × Osh — 70 000 so'm" in text
    assert "1 × Lag'mon — 30 000 so'm" in text
    assert "Jami: 110 000 so'm" in text and "naqd" in text
    assert "+998901234567" in text
    assert "12-uy" in text and "km" in text
    # Mijoz yozgan matn HTML sifatida ishlamasligi kerak
    assert "&lt;b&gt;iltimos&lt;/b&gt;" in text and "<b>iltimos" not in text

    labels = button_labels(message.reply_markup)
    assert labels == ["✅ Qabul qilish", "❌ Rad etish", "📍 Google xarita", "📍 Yandex xarita"]
    google = find_button(message.reply_markup, "Google")
    assert "39.660000,66.968000" in google.url
    yandex = find_button(message.reply_markup, "Yandex")
    assert "66.968000,39.660000" in yandex.url  # Yandex'da avval uzunlik

    saved = await db_order(session_factory, order["id"])
    assert saved.tg_chat_id == GROUP_ID
    assert saved.tg_message_id == 1001


async def test_order_is_not_posted_twice(api, seed, tg, bot, session_factory, bot_cfg):
    order, _ = await place_order(api, seed)
    again = await publish_order(session_factory, bot, GROUP_ID, order["id"], bot_cfg.timezone)
    assert again is False
    assert len(tg.of_type(SendMessage)) == 1


# ---------- Xodim tugmalarni bosadi ----------


async def test_staff_full_flow_updates_message_and_app(api, seed, tg, driver):
    order, auth = await place_order(api, seed)
    message_id = 1001

    await driver.press_in_group("Qabul qilish", message_id)
    edit = tg.of_type(EditMessageText)[-1]
    assert edit.chat_id == GROUP_ID and edit.message_id == message_id
    assert "Tayyorlanmoqda" in edit.text and "Qabul qildi: Sardor" in edit.text
    assert button_labels(edit.reply_markup)[:2] == ["🚗 Yo'lga chiqdi", "❌ Rad etish"]
    assert "Tayyorlanmoqda" in tg.of_type(AnswerCallbackQuery)[-1].text
    assert (await api.get(f"/orders/{order['id']}", headers=auth)).json()["status"] == "accepted"

    await driver.press_in_group("Yo'lga chiqdi", message_id)
    edit = tg.of_type(EditMessageText)[-1]
    assert "Kuryer yo'lda" in edit.text
    assert button_labels(edit.reply_markup)[:2] == ["✅ Yetkazildi", "❌ Rad etish"]

    await driver.press_in_group("Yetkazildi", message_id)
    edit = tg.of_type(EditMessageText)[-1]
    assert "Yetkazildi" in edit.text
    assert edit.reply_markup is None  # tugallangan buyurtmada tugma qolmaydi

    body = (await api.get(f"/orders/{order['id']}", headers=auth)).json()
    assert body["status"] == "delivered"
    assert [e["status"] for e in body["history"]] == ["new", "accepted", "delivering", "delivered"]


async def test_reject_asks_reason_first(api, seed, tg, driver):
    order, auth = await place_order(api, seed)

    await driver.press_in_group("Rad etish", 1001)
    markup = tg.of_type(EditMessageReplyMarkup)[-1].reply_markup
    assert "Mahsulot tugadi" in button_labels(markup)
    # Hali rad etilmadi: bu faqat sabab so'rash
    assert (await api.get(f"/orders/{order['id']}", headers=auth)).json()["status"] == "new"

    await driver.press_in_group("Orqaga", 1001)
    assert button_labels(tg.last_markup)[0] == "✅ Qabul qilish"

    await driver.press_in_group("Rad etish", 1001)
    await driver.press_in_group("Mahsulot tugadi", 1001)
    edit = tg.of_type(EditMessageText)[-1]
    assert "Rad etildi" in edit.text and "Sabab: Mahsulot tugadi" in edit.text
    assert edit.reply_markup is None

    body = (await api.get(f"/orders/{order['id']}", headers=auth)).json()
    assert body["status"] == "rejected"
    assert body["reject_reason"] == "Mahsulot tugadi"


async def test_buttons_do_not_work_outside_orders_group(api, seed, tg, driver):
    order, auth = await place_order(api, seed)
    await driver.press_in_group("Qabul qilish", 1001, chat_id=-100999)
    answer = tg.of_type(AnswerCallbackQuery)[-1]
    assert answer.show_alert is True
    assert (await api.get(f"/orders/{order['id']}", headers=auth)).json()["status"] == "new"


async def test_second_staff_tap_is_harmless(api, seed, tg, driver):
    await place_order(api, seed)
    accept = find_button(tg.last_markup, "Qabul qilish").callback_data
    other = User(id=556, is_bot=False, first_name="Dilnoza")
    await driver.press_data(accept, other, GROUP_ID, 1001, "supergroup")
    await driver.press_data(accept, other, GROUP_ID, 1001, "supergroup")
    assert tg.of_type(AnswerCallbackQuery)[-1].text == "Bu allaqachon belgilangan"
    assert tg.of_type(EditMessageText)[-1].text.count("Qabul qildi") == 1


async def test_customer_cancel_updates_group(api, seed, tg, driver):
    order, auth = await place_order(api, seed)
    accept = find_button(tg.last_markup, "Qabul qilish").callback_data
    tg.clear()

    assert (await api.post(f"/orders/{order['id']}/cancel", headers=auth)).status_code == 200
    edit = tg.of_type(EditMessageText)[-1]
    assert "Mijoz bekor qildi" in edit.text and edit.reply_markup is None
    notice = tg.of_type(SendMessage)[-1]
    assert notice.reply_to_message_id == 1001
    assert f"№{order['id']}" in notice.text

    # Xodim eski tugmani bosib qolsa
    await driver.press_data(accept, User(id=555, is_bot=False, first_name="S"), GROUP_ID, 1001, "supergroup")
    answer = tg.of_type(AnswerCallbackQuery)[-1]
    assert answer.show_alert is True and "bekor qilgan" in answer.text
    assert (await api.get(f"/orders/{order['id']}", headers=auth)).json()["status"] == "cancelled"


# ---------- Telegram ishlamay qolsa ----------


async def test_order_survives_telegram_outage_and_is_resent(api, seed, tg, bot, session_factory, bot_cfg):
    tg.fail_with = TelegramNetworkError(method=None, message="internet yo'q")
    order, auth = await place_order(api, seed)  # mijoz baribir 201 oladi
    assert (await db_order(session_factory, order["id"])).tg_message_id is None

    # Telegram hali ham ishlamayapti: tekshiruv yiqilmaydi
    assert await sweep_unsent(session_factory, bot, GROUP_ID, bot_cfg.timezone, min_age=0) == 0

    tg.fail_with = None
    assert await sweep_unsent(session_factory, bot, GROUP_ID, bot_cfg.timezone, min_age=0) == 1
    assert len(tg.of_type(SendMessage)) == 1
    assert (await db_order(session_factory, order["id"])).tg_message_id is not None
    # Qayta tekshiruv ikkinchi marta yubormaydi
    assert await sweep_unsent(session_factory, bot, GROUP_ID, bot_cfg.timezone, min_age=0) == 0


async def test_sweep_skips_fresh_and_cancelled_orders(api, seed, tg, bot, session_factory, bot_cfg):
    tg.fail_with = TelegramNetworkError(method=None, message="internet yo'q")
    order, auth = await place_order(api, seed)
    tg.fail_with = None
    # Yangi buyurtmaga API'ning o'zi ulgurishi uchun 15 soniya beriladi
    assert await sweep_unsent(session_factory, bot, GROUP_ID, bot_cfg.timezone) == 0

    await api.post(f"/orders/{order['id']}/cancel", headers=auth)
    assert await sweep_unsent(session_factory, bot, GROUP_ID, bot_cfg.timezone, min_age=0) == 0
    assert tg.of_type(SendMessage) == []  # bekor qilingan buyurtma bilan xodimlar bezovta qilinmaydi


# ---------- Admin: kirish huquqi ----------


async def test_stranger_gets_id_not_menu(driver, seed, session_factory):
    await driver.say("/start", user_id=STRANGER_ID)
    assert str(STRANGER_ID) in driver.screen
    assert driver.buttons == []

    # Begona odam admin tugmasini bosa olmaydi
    await driver.press_data(
        "a:pause:0:", User(id=STRANGER_ID, is_bot=False, first_name="B"), STRANGER_ID
    )
    async with session_factory() as session:
        assert (await session.get(ShopSettings, 1)).is_accepting_orders is True


async def test_admin_menu_is_private_only(driver, seed):
    await driver.say("/start", chat_id=GROUP_ID)
    # Guruhda admin menyusi chiqmaydi
    assert driver.session.of_type(SendMessage) == []


async def test_id_command_in_group(driver):
    await driver.say("/id", user_id=STRANGER_ID, chat_id=GROUP_ID)
    assert str(GROUP_ID) in driver.screen and str(STRANGER_ID) in driver.screen


async def test_id_command_for_admin_in_private(driver, seed):
    await driver.say("/id")
    assert f"Sizning ID: <code>{ADMIN_ID}</code>" in driver.screen
    assert driver.buttons == []


async def test_admin_main_menu(driver, seed):
    await driver.say("/start")
    assert "Amora boshqaruvi" in driver.screen
    assert "Buyurtmalar qabul qilinmoqda" in driver.screen
    assert driver.buttons == [
        "🍽 Menyu",
        "📂 Kategoriyalar",
        "⚙️ Sozlamalar",
        "📊 Bugungi hisobot",
        "⏸ Buyurtma qabul qilishni to'xtatish",
    ]


async def test_pause_and_resume_orders(driver, seed, client):
    await driver.say("/start")
    await driver.press("to'xtatish")
    assert "to'xtatilgan" in driver.screen
    shop = (await client.get("/shop")).json()
    assert shop["is_open"] is False and shop["is_accepting_orders"] is False

    await driver.press("yoqish")
    assert (await client.get("/shop")).json()["is_open"] is True


# ---------- Admin: menyu ----------


async def test_add_product_with_photo(driver, client, bot_cfg):
    await driver.say("/start")
    await driver.press("Menyu")
    assert "Hozircha taom yo'q" in driver.screen
    await driver.press("Taom qo'shish")
    await driver.say("  Qozon   kabob ")
    await driver.say("abc")
    assert "faqat raqam" in driver.screen
    await driver.say("45 000 so'm")
    await driver.say("Qo'y go'shti, 300 g")
    await driver.say("rasm o'rniga matn")
    assert "oddiy rasm sifatida" in driver.screen
    await driver.send_photo()
    assert "Qozon kabob" in driver.screen and "45 000 so'm" in driver.screen
    assert "Rasm: bor" in driver.screen

    product = (await client.get("/menu")).json()["products"][0]
    assert product["name"] == "Qozon kabob"
    assert product["price"] == 45_000
    assert product["description"] == "Qo'y go'shti, 300 g"
    assert product["is_available"] is True
    assert product["image_url"].startswith("https://api.test/media/products/")
    saved = bot_cfg.media_dir / product["image_url"].split("/media/")[1]
    assert saved.read_bytes() == FAKE_JPEG
    # Rasm API orqali ham ochiladi
    media = await client.get(product["image_url"].replace("https://api.test", "http://test"))
    assert media.status_code == 200 and media.content == FAKE_JPEG


async def test_add_product_skipping_optional_steps_and_choosing_category(driver, client, session_factory):
    await driver.say("/start")
    await driver.press("Kategoriyalar")
    await driver.press("Kategoriya qo'shish")
    await driver.say("Ichimliklar")
    assert "📂 Ichimliklar" in driver.buttons

    await driver.press("Bosh menyu")
    await driver.press("Menyu")
    await driver.press("Taom qo'shish")
    await driver.say("Choy")
    await driver.say("5000")
    await driver.press("O'tkazib yuborish")
    await driver.press("O'tkazib yuborish")
    assert "qaysi kategoriyada" in driver.screen
    await driver.press("Ichimliklar")
    assert "Kategoriya: Ichimliklar" in driver.screen and "Rasm: qo'yilmagan" in driver.screen

    menu = (await client.get("/menu")).json()
    assert menu["categories"][0]["name"] == "Ichimliklar"
    assert menu["products"][0]["category_id"] == menu["categories"][0]["id"]
    assert menu["products"][0]["image_url"] is None


async def test_edit_product(driver, seed, client, bot_cfg):
    await driver.say("/start")
    await driver.press("Menyu")
    assert "✅ Osh · 35 000 so'm" in driver.buttons
    assert "⛔ Somsa · 8 000 so'm" in driver.buttons
    assert not any("Eski taom" in label for label in driver.buttons)

    await driver.press("Osh")
    await driver.press("Narxi")
    await driver.say("0")
    assert "0 dan katta" in driver.screen
    await driver.say("38.000")
    assert "38 000 so'm" in driver.screen

    await driver.press("Nomi")
    await driver.say("To'y oshi")
    await driver.press("Tavsifi")
    await driver.say("Devzira guruch")
    await driver.press("Rasmi")
    await driver.send_photo()

    products = {p["id"]: p for p in (await client.get("/menu")).json()["products"]}
    osh = products[seed["osh"]]
    assert osh["name"] == "To'y oshi" and osh["price"] == 38_000
    assert osh["description"] == "Devzira guruch"
    new_path = osh["image_url"].split("/media/")[1]
    assert new_path != "products/osh.jpg"
    assert (bot_cfg.media_dir / new_path).exists()

    # Rasmni olib tashlash faylni ham o'chiradi
    await driver.press("Rasmi")
    await driver.say("-")
    assert "Rasm: qo'yilmagan" in driver.screen
    assert not (bot_cfg.media_dir / new_path).exists()


async def test_edit_can_be_cancelled(driver, seed, client):
    await driver.say("/start")
    await driver.press("Menyu")
    await driver.press("Osh")
    await driver.press("Narxi")
    await driver.press("Bekor qilish")
    assert "Narxi: 35 000 so'm" in driver.screen
    # Bekor qilingandan keyin yozilgan matn narx deb qabul qilinmaydi
    await driver.say("99000")
    products = {p["id"]: p for p in (await client.get("/menu")).json()["products"]}
    assert products[seed["osh"]]["price"] == 35_000


async def test_stop_list_toggle(driver, seed, client):
    await driver.say("/start")
    await driver.press("Menyu")
    await driver.press("Osh")
    await driver.press("Tugadi deb belgilash")
    assert "tugagan" in driver.screen
    products = {p["id"]: p for p in (await client.get("/menu")).json()["products"]}
    assert products[seed["osh"]]["is_available"] is False

    await driver.press("Yana bor deb belgilash")
    products = {p["id"]: p for p in (await client.get("/menu")).json()["products"]}
    assert products[seed["osh"]]["is_available"] is True


async def test_delete_product_needs_confirmation(driver, seed, client):
    await driver.say("/start")
    await driver.press("Menyu")
    await driver.press("Lag'mon")
    await driver.press("O'chirish")
    assert "butunlay o'chirilsinmi" in driver.screen
    await driver.press("Yo'q")
    assert seed["lagmon"] in {p["id"] for p in (await client.get("/menu")).json()["products"]}

    await driver.press("O'chirish")
    await driver.press("Ha, o'chirilsin")
    assert seed["lagmon"] not in {p["id"] for p in (await client.get("/menu")).json()["products"]}
    assert not any("Lag'mon" in label for label in driver.buttons)


async def test_category_rename_and_delete_keeps_products(driver, seed, client, session_factory):
    await driver.say("/start")
    await driver.press("Kategoriyalar")
    await driver.press("Asosiy taomlar")
    assert "Taomlar soni: 2" in driver.screen
    await driver.press("Nomini o'zgartirish")
    await driver.say("Issiq taomlar")
    assert "📂 Issiq taomlar" in driver.buttons

    await driver.press("Issiq taomlar")
    await driver.press("O'chirish")
    menu = (await client.get("/menu")).json()
    assert menu["categories"] == []
    assert len(menu["products"]) == 3
    assert all(p["category_id"] is None for p in menu["products"])

    await driver.press("Bosh menyu")
    await driver.press("Menyu")
    await driver.press("Osh")
    await driver.press("Kategoriyasi")
    answer = driver.session.of_type(AnswerCallbackQuery)[-1]
    assert answer.show_alert is True and "kategoriya qo'shing" in answer.text


async def test_change_product_category(driver, seed, client, session_factory):
    async with session_factory() as session:
        session.add(Category(name="Ichimliklar", sort_order=5))
        await session.commit()
    await driver.say("/start")
    await driver.press("Menyu")
    await driver.press("Somsa")
    await driver.press("Kategoriyasi")
    await driver.press("Ichimliklar")
    assert "Kategoriya: Ichimliklar" in driver.screen
    await driver.press("Kategoriyasi")
    await driver.press("Kategoriyasiz")
    assert "Kategoriya: yo'q" in driver.screen


# ---------- Admin: sozlamalar ----------


async def test_settings(driver, seed, client):
    await driver.say("/start")
    await driver.press("Sozlamalar")
    assert "Yetkazish narxi: 10 000 so'm" in driver.screen

    await driver.press("Yetkazish narxi")
    await driver.say("15000")
    await driver.press("Bepul yetkazish chegarasi")
    await driver.say("150 000")
    await driver.press("Eng kam buyurtma")
    await driver.say("30000")
    await driver.press("Yetkazish masofasi")
    await driver.say("7,5 km")
    await driver.press("Ish vaqti")
    await driver.say("25:00-26:00")
    assert "Bunday vaqt yo'q" in driver.screen
    await driver.say("10:00-22:30")
    await driver.press("Kafe telefoni")
    await driver.say("12")
    assert "Telefon raqam noto'g'ri" in driver.screen
    await driver.say("93 555 44 33")
    await driver.press("Kafe joylashuvi")
    await driver.say("Registon")
    assert "Joylashuv" in driver.screen
    await driver.send_location(39.6547, 66.9758)

    screen = driver.screen
    assert "Yetkazish narxi: 15 000 so'm" in screen
    assert "Bepul yetkazish chegarasi: 150 000 so'm dan" in screen
    assert "Eng kam buyurtma: 30 000 so'm" in screen
    assert "Yetkazish masofasi: 7.5 km gacha" in screen
    assert "Ish vaqti: 10:00–22:30" in screen
    assert "Kafe telefoni: +998935554433" in screen
    assert "Kafe joylashuvi: belgilangan" in screen

    shop = (await client.get("/shop")).json()
    assert shop["delivery_fee"] == 15_000
    assert shop["free_delivery_from"] == 150_000
    assert shop["min_order_amount"] == 30_000
    assert shop["max_delivery_km"] == 7.5
    assert (shop["open_time"], shop["close_time"]) == ("10:00", "22:30")
    assert shop["phone"] == "+998935554433"
    assert (shop["cafe_latitude"], shop["cafe_longitude"]) == (39.6547, 66.9758)

    # 0 yozilsa cheklov olib tashlanadi
    await driver.press("Bepul yetkazish chegarasi")
    await driver.say("0")
    await driver.press("Yetkazish masofasi")
    await driver.say("0")
    shop = (await client.get("/shop")).json()
    assert shop["free_delivery_from"] is None and shop["max_delivery_km"] is None
    assert "cheklanmagan" in driver.screen


async def test_settings_affect_orders(driver, seed, client, auth):
    await driver.say("/start")
    await driver.press("Sozlamalar")
    await driver.press("Eng kam buyurtma")
    await driver.say("100000")
    response = await client.post(
        "/orders", headers=auth, json={"items": [{"product_id": seed["osh"], "quantity": 1}], **NEAR}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "below_min_order"


# ---------- Admin: hisobot va bloklash ----------


async def test_daily_report(api, seed, driver, session_factory, bot_cfg):
    bot_cfg.max_active_orders = 10
    auth = await register(api)
    orders = [(await place_order(api, seed, auth))[0] for _ in range(4)]

    # Birinchi buyurtma xabaridagi tugma (oxirgi xabar to'rtinchi buyurtmaniki)
    first_message = driver.session.of_type(SendMessage)[0]
    accept = find_button(first_message.reply_markup, "Qabul qilish").callback_data
    await driver.press_data(accept, User(id=555, is_bot=False, first_name="S"), GROUP_ID, 1001, "supergroup")
    await driver.press_in_group("Yo'lga chiqdi", 1001)
    await driver.press_in_group("Yetkazildi", 1001)
    cancelled = await api.post(f"/orders/{orders[3]['id']}/cancel", headers=auth)
    assert cancelled.status_code == 200
    async with session_factory() as session:
        (await session.get(Order, orders[2]["id"])).status = OrderStatus.REJECTED.value
        await session.commit()

    await driver.say("/start")
    await driver.press("Bugungi hisobot")
    screen = driver.screen
    assert "Jami buyurtmalar: 4" in screen
    assert "Yetkazildi: 1 ta, 110 000 so'm" in screen
    assert "Jarayonda: 1" in screen
    assert "Rad etildi: 1" in screen
    assert "Mijoz bekor qildi: 1" in screen


async def test_block_and_unblock_phone(driver, seed, client, auth, session_factory):
    await driver.say("/blok")
    assert "/blok 901234567" in driver.screen
    await driver.say("/blok 93 000 00 00")
    assert "topilmadi" in driver.screen

    await driver.say("/blok 90 123 45 67")
    assert "bloklandi" in driver.screen
    body = {"items": [{"product_id": seed["osh"], "quantity": 1}], **NEAR}
    assert (await client.post("/orders", headers=auth, json=body)).status_code == 403

    await driver.say("/ochish 901234567")
    assert "blokdan chiqarildi" in driver.screen
    assert (await client.post("/orders", headers=auth, json=body)).status_code == 201


async def test_unknown_text_shows_main_menu(driver, seed):
    await driver.say("salom")
    assert "Amora boshqaruvi" in driver.screen


# ---------- Qiymatlarni tushunish ----------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("35000", 35_000), ("35 000", 35_000), ("35.000", 35_000), ("35,000 so'm", 35_000), ("0", 0), ("12 500 UZS", 12_500)],
)
def test_parse_amount(raw, expected):
    assert parse_amount(raw) == expected


@pytest.mark.parametrize("raw", ["", "abc", "-5", "35k", "1e5", "999999999999"])
def test_parse_amount_rejects(raw):
    with pytest.raises(ValueError):
        parse_amount(raw)


@pytest.mark.parametrize(("raw", "expected"), [("5", 5.0), ("3.5", 3.5), ("3,5 km", 3.5), ("0", 0.0)])
def test_parse_km(raw, expected):
    assert parse_km(raw) == expected


@pytest.mark.parametrize("raw", ["", "uzoq", "-1", "500"])
def test_parse_km_rejects(raw):
    with pytest.raises(ValueError):
        parse_km(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("09:00-23:00", (time(9), time(23))),
        ("9-23", (time(9), time(23))),
        ("18.00 – 02.00", (time(18), time(2))),
        ("10:30 - 22:45", (time(10, 30), time(22, 45))),
        ("9-24", (time(9), time(0))),
        ("00:00-00:00", (time(0), time(0))),
    ],
)
def test_parse_hours(raw, expected):
    assert parse_hours(raw) == expected


@pytest.mark.parametrize("raw", ["", "ertalab", "25:00-26:00", "9:75-10:00", "9"])
def test_parse_hours_rejects(raw):
    with pytest.raises(ValueError):
        parse_hours(raw)


# ---------- Ulash ----------


async def test_api_uses_telegram_when_configured(bot_cfg, engine):
    from app.notifier import NullNotifier

    bot_cfg.bot_token = "42:TEST"
    app = create_app(bot_cfg, engine=engine)
    assert isinstance(app.state.notifier, TelegramNotifier)
    assert app.state.notifier.chat_id == GROUP_ID
    await app.state.notifier.close()

    bot_cfg.bot_token = ""
    assert isinstance(create_app(bot_cfg, engine=engine).state.notifier, NullNotifier)


async def test_dispatcher_listens_to_needed_updates(driver):
    used = driver.dispatcher.resolve_used_update_types()
    assert {"message", "callback_query", "my_chat_member"} <= set(used)
