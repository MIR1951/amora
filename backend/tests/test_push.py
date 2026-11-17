"""Push-bildirishnomalar: Firebase (FCM) bilan ishlash, buyurtma holati va botdan xabar."""

import asyncio
import json

import jwt
import pytest
from aiohttp import web
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select

from app.models import Customer, CustomerDevice
from app.services import push as push_service
from app.services.push import PushSender, broadcast_message, notify_order_status, order_message
from tests.conftest import register
from tests.telegram_fakes import GROUP_ID, STAFF
from tests.test_bot import db_order, place_order


class FakePush(PushSender):
    """Haqiqiy Firebase o'rniga: yuborilgan xabarlarni yozib boradi."""

    def __init__(self, result=None):
        super().__init__(None)
        self.sent: list[dict] = []
        self.result = result

    @property
    def enabled(self) -> bool:
        return True

    async def send(self, message: dict):
        self.sent.append(message)
        return self.result


# ---------- Xabar ko'rinishi ----------


def test_order_message_is_data_only():
    from app.models import Order

    order = Order(id=7, status="rejected", reject_reason="Taom tugagan")
    message = order_message("tok", order)
    assert message["token"] == "tok"
    assert "notification" not in message  # ilova o'zi ko'rsatadi: jonli xabar bilan ikkilanmaydi
    assert message["data"] == {
        "type": "order",
        "order_id": "7",
        "status": "rejected",
        "status_label": "Rad etildi",
        "reject_reason": "Taom tugagan",
    }
    assert all(isinstance(value, str) for value in message["data"].values())
    assert message["android"]["priority"] == "HIGH"


def test_broadcast_goes_to_topic_with_notification():
    message = broadcast_message("Bugun −20%", "Promokod: PITSA20")
    assert message["topic"] == "all"
    assert message["notification"] == {"title": "Bugun −20%", "body": "Promokod: PITSA20"}
    assert message["android"]["notification"]["channel_id"] == "promo"


def test_dead_token_detection():
    unregistered = {"error": {"status": "NOT_FOUND", "details": [{"errorCode": "UNREGISTERED"}]}}
    assert push_service._is_dead_token(404, unregistered)
    assert not push_service._is_dead_token(500, {"error": {"status": "INTERNAL"}})
    assert not push_service._is_dead_token(429, {"error": {"status": "RESOURCE_EXHAUSTED"}})


def test_missing_credentials_disable_push(tmp_path, caplog):
    assert not PushSender(None).enabled
    assert not PushSender(tmp_path / "yoq.json").enabled
    assert "Firebase kaliti o'qilmadi" in caplog.text


def test_broken_key_disables_push(tmp_path, caplog):
    # Kalit nusxalanganda buzilgan: bot ishga tushganda bilinadi, har bir buyurtmada emas
    credentials = tmp_path / "firebase.json"
    credentials.write_text(
        json.dumps(
            {
                "project_id": "amora-test",
                "client_email": "push@amora-test.iam.gserviceaccount.com",
                "private_key": "-----BEGIN PRIVATE KEY-----\\nbuzilgan\\n-----END PRIVATE KEY-----",
            }
        )
    )
    assert not PushSender(credentials).enabled
    assert "Firebase kaliti o'qilmadi" in caplog.text


# ---------- Firebase bilan haqiqiy so'rovlar (mahalliy soxta server) ----------


@pytest.fixture
async def fcm(tmp_path, monkeypatch):
    """Google token va FCM manzillarini o'ynaydigan mahalliy server."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    state = {"tokens": 0, "sent": [], "dead": set(), "assertions": [], "html_error": False}

    async def token(request):
        form = await request.post()
        claims = jwt.decode(
            form["assertion"], key.public_key(), algorithms=["RS256"], audience=str(request.url)
        )
        state["assertions"].append(claims)
        state["tokens"] += 1
        return web.json_response({"access_token": f"acc{state['tokens']}", "expires_in": 3600})

    async def send(request):
        assert request.headers["Authorization"].startswith("Bearer acc")
        body = await request.json()
        if state["html_error"]:
            # Google old tomonidagi proksi: JSON emas, HTML sahifa
            return web.Response(text="<html><body>502 Bad Gateway</body></html>", status=502, content_type="text/html")
        state["sent"].append(body["message"])
        if body["message"].get("token") in state["dead"]:
            return web.json_response(
                {"error": {"status": "NOT_FOUND", "details": [{"errorCode": "UNREGISTERED"}]}},
                status=404,
            )
        return web.json_response({"name": "projects/amora-test/messages/1"})

    app = web.Application()
    app.router.add_post("/token", token)
    app.router.add_post("/v1/projects/{project}/messages:send", send)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    base = f"http://127.0.0.1:{port}"

    credentials = tmp_path / "firebase.json"
    credentials.write_text(
        json.dumps(
            {
                "type": "service_account",
                "project_id": "amora-test",
                "private_key_id": "k1",
                "private_key": pem,
                "client_email": "push@amora-test.iam.gserviceaccount.com",
                "token_uri": f"{base}/token",
            }
        )
    )
    monkeypatch.setattr(push_service, "SEND_URL", base + "/v1/projects/{project}/messages:send")
    sender = PushSender(credentials)
    state["sender"] = sender
    yield state
    await sender.close()
    await runner.cleanup()


async def test_sender_signs_in_once_and_sends(fcm):
    sender = fcm["sender"]
    assert sender.enabled
    assert await sender.send(broadcast_message("Salom", "Matn")) is None
    assert await sender.send(broadcast_message("Yana", "Matn")) is None
    assert fcm["tokens"] == 1  # kirish kaliti bir soat qayta ishlatiladi
    claims = fcm["assertions"][0]
    assert claims["iss"] == "push@amora-test.iam.gserviceaccount.com"
    assert claims["scope"] == push_service.SCOPE
    assert [m["notification"]["title"] for m in fcm["sent"]] == ["Salom", "Yana"]


async def test_html_error_page_is_a_push_error(fcm, api, seed, session_factory):
    from app.models import OrderStatus
    from app.services.orders import set_status_by_staff

    fcm["html_error"] = True
    with pytest.raises(push_service.PushError):
        await push_service.broadcast(fcm["sender"], "Salom", "Matn")

    order, auth = await place_order(api, seed)
    await api.patch("/me", headers=auth, json={"fcm_token": "telefon-1"})
    async with session_factory() as session:
        await set_status_by_staff(session, order["id"], OrderStatus.ACCEPTED, "Kassir")
    # Xato jurnalga yoziladi, token o'chirilmaydi
    assert await notify_order_status(fcm["sender"], session_factory, order["id"]) is False
    async with session_factory() as session:
        assert (await session.scalar(select(CustomerDevice))).fcm_token == "telefon-1"


async def test_order_status_push_and_dead_token_cleanup(fcm, api, seed, session_factory):
    order, auth = await place_order(api, seed)
    response = await api.patch("/me", headers=auth, json={"fcm_token": "telefon-1"})
    assert response.status_code == 200

    from app.models import OrderStatus
    from app.services.orders import set_status_by_staff

    async with session_factory() as session:
        await set_status_by_staff(session, order["id"], OrderStatus.ACCEPTED, "Kassir")
    assert await notify_order_status(fcm["sender"], session_factory, order["id"]) is True
    assert fcm["sent"][-1]["token"] == "telefon-1"
    assert fcm["sent"][-1]["data"]["status"] == "accepted"

    # Ilova o'chirilgan: Firebase tokenni tanimaydi, u bazadan o'chiriladi
    fcm["dead"].add("telefon-1")
    assert await notify_order_status(fcm["sender"], session_factory, order["id"]) is False
    async with session_factory() as session:
        device = await session.scalar(select(CustomerDevice))
        assert device.fcm_token is None


async def test_order_status_reaches_every_phone_of_the_customer(api, seed, session_factory):
    from app.models import OrderStatus
    from app.services.orders import set_status_by_staff
    from tests.conftest import verify_phone

    fake = FakePush()
    order, first_phone = await place_order(api, seed)
    second_phone = await verify_phone(api, "90 123 45 67")  # o'sha raqam, ikkinchi telefon
    await api.patch("/me", headers=first_phone, json={"fcm_token": "telefon-1"})
    await api.patch("/me", headers=second_phone, json={"fcm_token": "telefon-2"})
    async with session_factory() as session:
        await set_status_by_staff(session, order["id"], OrderStatus.ACCEPTED, "Kassir")
    assert await notify_order_status(fake, session_factory, order["id"]) is True
    assert sorted(message["token"] for message in fake.sent) == ["telefon-1", "telefon-2"]


async def test_no_push_for_new_order_or_without_token(api, seed, session_factory):
    fake = FakePush()
    order, auth = await place_order(api, seed)
    assert await notify_order_status(fake, session_factory, order["id"]) is False  # tokeni yo'q
    await api.patch("/me", headers=auth, json={"fcm_token": "telefon-1"})
    assert await notify_order_status(fake, session_factory, order["id"]) is False  # hali "yangi"
    assert fake.sent == []


async def test_same_phone_token_moves_to_new_account(client, seed, session_factory):
    first = await register(client, phone="90 111 11 11")
    second = await register(client, phone="90 222 22 22")
    await client.patch("/me", headers=first, json={"fcm_token": "bitta-telefon"})
    await client.patch("/me", headers=second, json={"fcm_token": "bitta-telefon"})
    async with session_factory() as session:
        tokens = dict(
            (
                await session.execute(
                    select(Customer.phone, CustomerDevice.fcm_token).join(
                        CustomerDevice, CustomerDevice.customer_id == Customer.id
                    )
                )
            ).all()
        )
    assert tokens == {"+998901111111": None, "+998902222222": "bitta-telefon"}


# ---------- Bot ----------


async def test_group_button_sends_push(api, seed, driver, tg, session_factory):
    fake = FakePush()
    driver.dispatcher["push"] = fake
    order, auth = await place_order(api, seed)
    await api.patch("/me", headers=auth, json={"fcm_token": "telefon-1"})
    await driver.press_in_group("Qabul qilish", 1001)
    await asyncio.sleep(0.05)  # push fonda ketadi
    assert (await db_order(session_factory, order["id"])).status == "accepted"
    assert [m["data"]["status"] for m in fake.sent] == ["accepted"]

    # Ikkinchi marta bosish holatni o'zgartirmaydi: push ham qayta ketmaydi
    from app.telegram.keyboards import OrderCb

    await driver.press_data(OrderCb(id=order["id"], action="accept").pack(), STAFF, GROUP_ID, 1001, "supergroup")
    await asyncio.sleep(0.05)
    assert len(fake.sent) == 1


async def test_broadcast_from_bot(driver, seed, session_factory, tg):
    from aiogram.methods import AnswerCallbackQuery

    await driver.say("/start")
    await driver.press("Aksiyalar")
    await driver.press("Mijozlarga xabar yuborish")
    assert "sozlanmagan" in tg.of_type(AnswerCallbackQuery)[-1].text

    fake = FakePush()
    driver.dispatcher["push"] = fake
    await driver.press("Mijozlarga xabar yuborish")
    await driver.say("x" * 51)
    assert "Juda uzun" in driver.screen
    await driver.say("Bugun hamma pitsalarga −20%")
    await driver.say("Faqat bugun   soat 22:00 gacha")
    assert "Xabar shunday ko'rinadi" in driver.screen
    assert fake.sent == []
    await driver.press("Yuborish")
    assert len(fake.sent) == 1
    assert fake.sent[0]["notification"] == {
        "title": "Bugun hamma pitsalarga −20%",
        "body": "Faqat bugun soat 22:00 gacha",
    }
    assert "Xabar yuborildi" in tg.of_type(AnswerCallbackQuery)[-1].text

    # Eski "Yuborish" tugmasi qayta bosilsa, ikkinchi marta ketmaydi
    from aiogram.types import User

    from tests.telegram_fakes import ADMIN_ID

    admin = User(id=ADMIN_ID, is_bot=False, first_name="Ega")
    await driver.press_data("a:bc_send:0:", admin, ADMIN_ID)
    assert len(fake.sent) == 1


async def test_broadcast_failure_is_reported(driver, seed, tg):
    from aiogram.methods import AnswerCallbackQuery

    driver.dispatcher["push"] = FakePush(result="disabled")
    await driver.say("/start")
    await driver.press("Aksiyalar")
    await driver.press("Mijozlarga xabar yuborish")
    await driver.say("Sarlavha")
    await driver.say("Matn")
    await driver.press("Yuborish")
    assert "Yuborilmadi" in tg.of_type(AnswerCallbackQuery)[-1].text


async def test_double_tap_on_send_is_answered_once_sent_once(driver, seed, tg):
    from aiogram.methods import AnswerCallbackQuery
    from aiogram.types import User

    from tests.telegram_fakes import ADMIN_ID

    fake = FakePush()
    driver.dispatcher["push"] = fake
    await driver.say("/start")
    await driver.press("Aksiyalar")
    await driver.press("Mijozlarga xabar yuborish")
    await driver.say("Sarlavha")
    await driver.say("Matn")
    tg.clear()
    admin = User(id=ADMIN_ID, is_bot=False, first_name="Ega")
    await asyncio.gather(
        driver.press_data("a:bc_send:0:", admin, ADMIN_ID),
        driver.press_data("a:bc_send:0:", admin, ADMIN_ID),
    )
    assert len(fake.sent) == 1
    answers = [answer.text for answer in tg.of_type(AnswerCallbackQuery)]
    assert len(answers) == 2
    assert any("Xabar yuborildi" in text for text in answers)
