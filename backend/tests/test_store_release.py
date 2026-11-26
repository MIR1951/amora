"""Do'konlarga chiqarish uchun kerakli narsalar: tekshiruvchining sinov kodi va ochiq sahifalar."""

import httpx
import pytest
from sqlalchemy import select

from app.main import create_app
from app.models import Customer, Order
from app.services import verify
from app.telegram.texts import order_text
from tests.conftest import NEAR, register

REVIEW_CODE = "AMORA-REVIEW-7Q2X9"


@pytest.fixture
async def review_client(cfg, engine, notifier):
    app = create_app(cfg.model_copy(update={"review_code": REVIEW_CODE}), engine=engine, notifier=notifier)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test/api/v1"
    ) as client:
        yield client


async def sign_in(client, name: str):
    code = (await client.post("/auth/telegram", json={"name": name, "platform": "ios"})).json()["code"]
    return await client.post("/auth/telegram/check", json={"code": code})


async def test_review_code_signs_in_without_telegram(review_client, seed, session_factory, notifier):
    response = await sign_in(review_client, REVIEW_CODE)
    body = response.json()
    assert body["status"] == "verified"
    assert body["customer"]["phone"] == verify.REVIEW_PHONE
    assert body["customer"]["name"] == verify.REVIEW_NAME
    auth = {"Authorization": f"Bearer {body['token']}"}

    order = await review_client.post(
        "/orders", headers=auth, json={"items": [{"product_id": seed["osh"], "quantity": 1}], **NEAR}
    )
    assert order.status_code == 201, order.text
    async with session_factory() as session:
        saved = await session.scalar(select(Order).where(Order.id == order.json()["id"]))
        await session.refresh(saved, ["items", "history"])
        text = order_text(saved, "Asia/Tashkent")
    assert "SINOV BUYURTMA" in text
    assert "tg://user" not in text

    # Ikkinchi marta kirilsa, o'sha sinov hisobining o'zi ochiladi
    again = (await sign_in(review_client, REVIEW_CODE)).json()
    assert again["customer"]["id"] == body["customer"]["id"]
    async with session_factory() as session:
        accounts = list(await session.scalars(select(Customer).where(Customer.phone == verify.REVIEW_PHONE)))
    assert len(accounts) == 1


async def test_review_account_does_not_absorb_other_customers(review_client, seed, session_factory):
    other = await register(review_client, name="Vali", phone="93 555 44 33")
    await sign_in(review_client, REVIEW_CODE)
    me = (await review_client.get("/me", headers=other)).json()
    assert me["name"] == "Vali"
    assert me["phone"] != verify.REVIEW_PHONE


async def test_wrong_code_and_ordinary_names_stay_pending(review_client):
    for name in ("Ali", REVIEW_CODE + "x", REVIEW_CODE.lower()):
        assert (await sign_in(review_client, name)).json()["status"] == "pending"


async def test_review_code_is_off_by_default(client):
    assert (await sign_in(client, REVIEW_CODE)).json()["status"] == "pending"


@pytest.mark.parametrize("code", ["", "   ", "short", "12345678901"])
def test_short_review_code_never_matches(code):
    assert not verify.is_review_code(code, code)
    assert not verify.is_review_code("Ali", code)


async def test_public_pages(cfg, engine, notifier):
    app = create_app(cfg, engine=engine, notifier=notifier)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as web:
        privacy = await web.get("/privacy")
        deletion = await web.get("/delete-account")
    for page in (privacy, deletion):
        assert page.status_code == 200
        assert page.headers["content-type"].startswith("text/html")
        assert "+998772231951" in page.text
    assert "Privacy Policy" in privacy.text
    assert "Hisobni o'chirish" in deletion.text
