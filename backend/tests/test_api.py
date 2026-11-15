from datetime import time
from uuid import uuid4

from sqlalchemy import select

from app.models import Customer, Product, ShopSettings
from tests.conftest import NEAR, register


async def update_shop(session_factory, **values):
    async with session_factory() as session:
        shop = await session.get(ShopSettings, 1)
        for key, value in values.items():
            setattr(shop, key, value)
        await session.commit()


def order_body(seed, **extra) -> dict:
    return {"items": [{"product_id": seed["osh"], "quantity": 2}], **NEAR, **extra}


# ---------- Xizmat ----------


async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_unknown_path_uses_error_shape(client):
    response = await client.get("/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# ---------- Menyu va kafe ----------


async def test_menu_hides_deleted_and_flags_unavailable(client, seed):
    response = await client.get("/menu")
    assert response.status_code == 200
    body = response.json()
    assert [c["name"] for c in body["categories"]] == ["Asosiy taomlar"]
    products = {p["name"]: p for p in body["products"]}
    assert set(products) == {"Osh", "Lag'mon", "Somsa"}
    assert products["Osh"]["price"] == 35_000
    assert products["Osh"]["image_url"] == "https://api.test/media/products/osh.jpg"
    assert products["Lag'mon"]["image_url"] is None
    assert products["Somsa"]["is_available"] is False
    assert products["Osh"]["category_id"] == seed["category"]
    assert products["Somsa"]["category_id"] is None


async def test_shop_info_creates_defaults_when_missing(client):
    response = await client.get("/shop")
    assert response.status_code == 200
    body = response.json()
    assert body["cafe_name"] == "Amora"
    assert body["open_time"] == "09:00"
    assert body["close_time"] == "23:00"


async def test_shop_info(client, seed, session_factory):
    await update_shop(session_factory, is_accepting_orders=False, free_delivery_from=100_000)
    body = (await client.get("/shop")).json()
    assert body["is_open"] is False
    assert body["delivery_fee"] == 10_000
    assert body["free_delivery_from"] == 100_000


# ---------- Mijoz ----------


async def test_register_normalizes_phone_and_returns_token(client):
    response = await client.post(
        "/auth/register", json={"name": "  Ali   Valiyev ", "phone": "+998 (90) 123-45-67"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["customer"]["phone"] == "+998901234567"
    assert body["customer"]["name"] == "Ali Valiyev"
    assert len(body["token"]) >= 40

    me = await client.get("/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert me.status_code == 200
    assert me.json()["phone"] == "+998901234567"


async def test_register_rejects_bad_phone_with_uzbek_message(client):
    response = await client.post("/auth/register", json={"name": "Ali", "phone": "12345"})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert "Telefon raqam noto'g'ri" in error["message"]
    assert error["fields"][0]["field"] == "phone"


async def test_register_rejects_blank_name(client):
    response = await client.post("/auth/register", json={"name": "   ", "phone": "901234567"})
    assert response.status_code == 422


async def test_register_rate_limit(cfg, engine, notifier):
    import httpx

    from app.main import create_app

    cfg.register_limit_per_hour = 2
    app = create_app(cfg, engine=engine, notifier=notifier)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test/api/v1"
    ) as client:
        codes = [
            (await client.post("/auth/register", json={"name": "A", "phone": "901234567"})).status_code
            for _ in range(3)
        ]
    assert codes == [201, 201, 429]


async def test_token_is_stored_hashed(client, session_factory):
    response = await client.post("/auth/register", json={"name": "Ali", "phone": "901234567"})
    token = response.json()["token"]
    async with session_factory() as session:
        customer = await session.scalar(select(Customer))
    assert customer.token_hash != token
    assert token not in customer.token_hash


async def test_auth_required(client, seed):
    for method, path in [("get", "/me"), ("get", "/orders"), ("post", "/orders")]:
        response = await getattr(client, method)(path)
        assert response.status_code == 401, path
        assert response.json()["error"]["code"] == "unauthorized"
    bad = await client.get("/me", headers={"Authorization": "Bearer nope"})
    assert bad.status_code == 401


async def test_update_profile(client, auth):
    response = await client.patch(
        "/me", headers=auth, json={"name": "Vali", "phone": "93 111 22 33", "fcm_token": "abc"}
    )
    assert response.status_code == 200
    assert response.json() == {"id": response.json()["id"], "name": "Vali", "phone": "+998931112233"}


# ---------- Savatni hisoblash ----------


async def test_quote_totals(client, seed):
    response = await client.post(
        "/orders/quote",
        json={
            "items": [
                {"product_id": seed["osh"], "quantity": 2},
                {"product_id": seed["lagmon"], "quantity": 1},
            ],
            **NEAR,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items_total"] == 100_000
    assert body["delivery_fee"] == 10_000
    assert body["total"] == 110_000
    assert body["can_order"] is True
    assert 0.5 < body["distance_km"] < 1.5


async def test_quote_merges_duplicate_lines(client, seed):
    response = await client.post(
        "/orders/quote",
        json={
            "items": [
                {"product_id": seed["osh"], "quantity": 1},
                {"product_id": seed["osh"], "quantity": 2},
            ]
        },
    )
    body = response.json()
    assert len(body["lines"]) == 1
    assert body["lines"][0]["quantity"] == 3
    assert body["items_total"] == 105_000


async def test_quote_free_delivery_threshold(client, seed, session_factory):
    await update_shop(session_factory, free_delivery_from=70_000)
    below = await client.post(
        "/orders/quote", json={"items": [{"product_id": seed["osh"], "quantity": 1}]}
    )
    assert below.json()["delivery_fee"] == 10_000
    at = await client.post(
        "/orders/quote", json={"items": [{"product_id": seed["osh"], "quantity": 2}]}
    )
    assert at.json()["delivery_fee"] == 0
    assert at.json()["total"] == 70_000


async def test_quote_reports_problems(client, seed, session_factory):
    await update_shop(session_factory, min_order_amount=50_000, max_delivery_km=5)
    response = await client.post(
        "/orders/quote",
        json={
            "items": [
                {"product_id": seed["osh"], "quantity": 1},
                {"product_id": seed["somsa"], "quantity": 1},
                {"product_id": seed["deleted"], "quantity": 1},
                {"product_id": 999_999, "quantity": 1},
            ],
            "latitude": 41.3111,  # Toshkent: hududdan tashqarida
            "longitude": 69.2797,
        },
    )
    body = response.json()
    assert body["can_order"] is False
    codes = [problem["code"] for problem in body["problems"]]
    assert codes.count("product_not_found") == 2
    assert "product_unavailable" in codes
    assert "below_min_order" in codes
    assert "out_of_zone" in codes
    # Hisobga faqat mavjud taom kiradi
    assert body["items_total"] == 35_000
    unavailable = next(p for p in body["problems"] if p["code"] == "product_unavailable")
    assert unavailable["product_id"] == seed["somsa"]
    assert "Somsa" in unavailable["message"]


async def test_quote_shop_closed(client, seed, session_factory):
    await update_shop(session_factory, is_accepting_orders=False)
    response = await client.post(
        "/orders/quote", json={"items": [{"product_id": seed["osh"], "quantity": 1}]}
    )
    assert [p["code"] for p in response.json()["problems"]] == ["shop_closed"]


async def test_quote_validation(client, seed):
    for items in ([], [{"product_id": seed["osh"], "quantity": 0}], [{"product_id": seed["osh"], "quantity": 51}]):
        response = await client.post("/orders/quote", json={"items": items})
        assert response.status_code == 422, items


# ---------- Buyurtma ----------


async def test_create_order(client, seed, auth, notifier):
    response = await client.post(
        "/orders",
        headers=auth,
        json=order_body(seed, address_note=" 12-uy,  3-kvartira ", comment="Achchiq bo'lmasin"),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "new"
    assert body["status_label"] == "Kafe javobi kutilmoqda"
    assert body["can_cancel"] is True
    assert body["is_active"] is True
    assert body["items"] == [
        {"product_id": seed["osh"], "name": "Osh", "price": 35_000, "quantity": 2, "line_total": 70_000}
    ]
    assert body["items_total"] == 70_000
    assert body["delivery_fee"] == 10_000
    assert body["total"] == 80_000
    assert body["phone"] == "+998901234567"
    assert body["customer_name"] == "Ali"
    assert body["address_note"] == "12-uy, 3-kvartira"
    assert [event["status"] for event in body["history"]] == ["new"]
    assert body["created_at"].endswith(("Z", "+00:00"))
    assert notifier.created == [body["id"]]


async def test_order_keeps_price_snapshot(client, seed, auth, session_factory):
    order = (await client.post("/orders", headers=auth, json=order_body(seed))).json()
    async with session_factory() as session:
        product = await session.get(Product, seed["osh"])
        product.price = 99_000
        product.name = "Yangi osh"
        await session.commit()
    again = (await client.get(f"/orders/{order['id']}", headers=auth)).json()
    assert again["items"][0]["price"] == 35_000
    assert again["items"][0]["name"] == "Osh"
    assert again["total"] == 80_000


async def test_order_is_idempotent_by_client_order_id(client, seed, auth, notifier):
    body = order_body(seed, client_order_id=str(uuid4()))
    first = await client.post("/orders", headers=auth, json=body)
    second = await client.post("/orders", headers=auth, json=body)
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert len(notifier.created) == 1
    listing = (await client.get("/orders", headers=auth)).json()
    assert len(listing["orders"]) == 1


async def test_order_rejected_when_price_changed(client, seed, auth, notifier):
    response = await client.post("/orders", headers=auth, json=order_body(seed, expected_total=70_000))
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "price_changed"
    assert error["total"] == 80_000
    assert notifier.created == []

    ok = await client.post("/orders", headers=auth, json=order_body(seed, expected_total=80_000))
    assert ok.status_code == 201


async def test_order_rejected_for_unavailable_product(client, seed, auth):
    response = await client.post(
        "/orders",
        headers=auth,
        json={"items": [{"product_id": seed["somsa"], "quantity": 1}], **NEAR},
    )
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "product_unavailable"
    assert error["product_id"] == seed["somsa"]


async def test_order_rejected_when_closed(client, seed, auth, session_factory):
    await update_shop(session_factory, is_accepting_orders=False)
    response = await client.post("/orders", headers=auth, json=order_body(seed))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "shop_closed"


async def test_order_rejected_out_of_zone(client, seed, auth, session_factory):
    await update_shop(session_factory, max_delivery_km=0.5)
    response = await client.post("/orders", headers=auth, json=order_body(seed))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "out_of_zone"


async def test_order_requires_location(client, seed, auth):
    response = await client.post(
        "/orders", headers=auth, json={"items": [{"product_id": seed["osh"], "quantity": 1}]}
    )
    assert response.status_code == 422
    response = await client.post(
        "/orders",
        headers=auth,
        json={"items": [{"product_id": seed["osh"], "quantity": 1}], "latitude": 95, "longitude": 0},
    )
    assert response.status_code == 422


async def test_active_order_limit(client, seed, auth):
    for _ in range(2):
        assert (await client.post("/orders", headers=auth, json=order_body(seed))).status_code == 201
    third = await client.post("/orders", headers=auth, json=order_body(seed))
    assert third.status_code == 409
    assert third.json()["error"]["code"] == "too_many_active_orders"

    # Bittasi bekor qilinsa, yana buyurtma berish mumkin
    first_id = (await client.get("/orders", headers=auth)).json()["orders"][-1]["id"]
    assert (await client.post(f"/orders/{first_id}/cancel", headers=auth)).status_code == 200
    assert (await client.post("/orders", headers=auth, json=order_body(seed))).status_code == 201


async def test_order_can_use_other_contact(client, seed, auth):
    response = await client.post(
        "/orders", headers=auth, json=order_body(seed, name="Onam", phone="99 888 77 66")
    )
    assert response.status_code == 201
    assert response.json()["customer_name"] == "Onam"
    assert response.json()["phone"] == "+998998887766"


async def test_blocked_phone_cannot_order(client, seed, auth, session_factory):
    async with session_factory() as session:
        customer = await session.scalar(select(Customer))
        customer.is_blocked = True
        await session.commit()
    blocked = await client.post("/orders", headers=auth, json=order_body(seed))
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "blocked"

    # Xuddi shu raqam bilan qayta ro'yxatdan o'tish ham yordam bermaydi
    again = await register(client, name="Boshqa", phone="901234567")
    response = await client.post("/orders", headers=again, json=order_body(seed))
    assert response.status_code == 403

    # Boshqa raqamli mijozga ta'sir qilmaydi
    other = await register(client, name="Vali", phone="931112233")
    assert (await client.post("/orders", headers=other, json=order_body(seed))).status_code == 201


async def test_orders_are_private(client, seed, auth):
    order = (await client.post("/orders", headers=auth, json=order_body(seed))).json()
    # Xuddi shu raqamni yozgan boshqa qurilma ham buyurtmani ko'ra olmaydi
    stranger = await register(client, name="Begona", phone="90 123 45 67")
    assert (await client.get(f"/orders/{order['id']}", headers=stranger)).status_code == 404
    assert (await client.post(f"/orders/{order['id']}/cancel", headers=stranger)).status_code == 404
    assert (await client.get("/orders", headers=stranger)).json()["orders"] == []


async def test_list_orders_newest_first_with_paging(client, seed, auth, cfg):
    cfg.max_active_orders = 10
    ids = [
        (await client.post("/orders", headers=auth, json=order_body(seed))).json()["id"]
        for _ in range(3)
    ]
    page = (await client.get("/orders?limit=2", headers=auth)).json()
    assert [order["id"] for order in page["orders"]] == ids[::-1][:2]
    assert page["has_more"] is True
    rest = (await client.get("/orders?limit=2&offset=2", headers=auth)).json()
    assert [order["id"] for order in rest["orders"]] == ids[:1]
    assert rest["has_more"] is False


async def test_cancel_order(client, seed, auth, notifier):
    order = (await client.post("/orders", headers=auth, json=order_body(seed))).json()
    response = await client.post(f"/orders/{order['id']}/cancel", headers=auth)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cancelled"
    assert body["can_cancel"] is False
    assert body["is_active"] is False
    assert [event["status"] for event in body["history"]] == ["new", "cancelled"]
    assert notifier.cancelled == [order["id"]]

    # Ikkinchi marta bosilsa xato bermaydi va xabar qayta yuborilmaydi
    again = await client.post(f"/orders/{order['id']}/cancel", headers=auth)
    assert again.status_code == 200
    assert notifier.cancelled == [order["id"]]


async def test_shop_hours_respected(client, seed, auth, session_factory, monkeypatch):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    import app.services.shop as shop_service

    await update_shop(session_factory, open_time=time(9, 0), close_time=time(23, 0))

    class Night(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 16, 3, 0, tzinfo=ZoneInfo("Asia/Tashkent"))

    monkeypatch.setattr(shop_service, "datetime", Night)
    response = await client.post("/orders", headers=auth, json=order_body(seed))
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "shop_closed"
    assert "09:00" in error["message"] and "23:00" in error["message"]
