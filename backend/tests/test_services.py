from datetime import time

import pytest

from app.models import OrderStatus
from app.security import RateLimiter, normalize_phone
from app.services import orders as order_service
from app.services.orders import StatusChangeError
from app.services.shop import distance_km, format_sum, is_within_hours
from tests.conftest import NEAR


@pytest.mark.parametrize(
    "raw",
    ["901234567", "90 123 45 67", "998901234567", "+998901234567", "+998 (90) 123-45-67"],
)
def test_normalize_phone_accepts(raw):
    assert normalize_phone(raw) == "+998901234567"


@pytest.mark.parametrize("raw", ["", "12345", "79001234567", "9012345678", "abc", "+99890123456"])
def test_normalize_phone_rejects(raw):
    with pytest.raises(ValueError):
        normalize_phone(raw)


@pytest.mark.parametrize(
    ("open_", "close", "now", "expected"),
    [
        (time(9), time(23), time(9, 0), True),
        (time(9), time(23), time(22, 59), True),
        (time(9), time(23), time(23, 0), False),
        (time(9), time(23), time(8, 59), False),
        # Yarim tundan o'tadigan ish vaqti
        (time(18), time(2), time(23, 30), True),
        (time(18), time(2), time(1, 59), True),
        (time(18), time(2), time(2, 0), False),
        (time(18), time(2), time(12, 0), False),
        # Bir xil vaqt: kecha-kunduz
        (time(0), time(0), time(4, 0), True),
    ],
)
def test_is_within_hours(open_, close, now, expected):
    assert is_within_hours(open_, close, now) is expected


def test_distance_km():
    # Samarqand - Toshkent taxminan 265-270 km
    assert 255 < distance_km(39.6542, 66.9597, 41.3111, 69.2797) < 280
    assert distance_km(39.65, 66.95, 39.65, 66.95) == 0


def test_format_sum():
    assert format_sum(8000) == "8 000 so'm"
    assert format_sum(1250000) == "1 250 000 so'm"
    assert format_sum(0) == "0 so'm"


def test_rate_limiter():
    limiter = RateLimiter(limit=2, window=3600)
    assert limiter.allow("a") and limiter.allow("a")
    assert not limiter.allow("a")
    assert limiter.allow("b")


async def _make_order(client, seed, auth) -> int:
    response = await client.post(
        "/orders",
        headers=auth,
        json={"items": [{"product_id": seed["osh"], "quantity": 1}], **NEAR},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_staff_full_flow(client, seed, auth, session_factory):
    order_id = await _make_order(client, seed, auth)

    for status in (OrderStatus.ACCEPTED, OrderStatus.DELIVERING, OrderStatus.DELIVERED):
        async with session_factory() as session:
            order, changed = await order_service.set_status_by_staff(
                session, order_id, status, actor="Sardor"
            )
        assert changed is True
        assert order.status == status.value

    body = (await client.get(f"/orders/{order_id}", headers=auth)).json()
    assert body["status"] == "delivered"
    assert body["status_label"] == "Yetkazildi"
    assert body["is_active"] is False
    assert [e["status"] for e in body["history"]] == ["new", "accepted", "delivering", "delivered"]


async def test_staff_double_tap_is_harmless(client, seed, auth, session_factory):
    order_id = await _make_order(client, seed, auth)
    async with session_factory() as session:
        await order_service.set_status_by_staff(session, order_id, OrderStatus.ACCEPTED, "A")
    async with session_factory() as session:
        order, changed = await order_service.set_status_by_staff(
            session, order_id, OrderStatus.ACCEPTED, "B"
        )
    assert changed is False
    assert [event.status for event in order.history] == ["new", "accepted"]


async def test_staff_cannot_skip_or_go_back(client, seed, auth, session_factory):
    order_id = await _make_order(client, seed, auth)
    async with session_factory() as session:
        with pytest.raises(StatusChangeError):
            await order_service.set_status_by_staff(session, order_id, OrderStatus.DELIVERED, "A")
    async with session_factory() as session:
        await order_service.set_status_by_staff(session, order_id, OrderStatus.ACCEPTED, "A")
        await order_service.set_status_by_staff(session, order_id, OrderStatus.DELIVERING, "A")
        await order_service.set_status_by_staff(session, order_id, OrderStatus.DELIVERED, "A")
    async with session_factory() as session:
        with pytest.raises(StatusChangeError):
            await order_service.set_status_by_staff(session, order_id, OrderStatus.REJECTED, "A")
    async with session_factory() as session:
        with pytest.raises(StatusChangeError) as info:
            await order_service.set_status_by_staff(session, 999_999, OrderStatus.ACCEPTED, "A")
    assert "topilmadi" in info.value.message


async def test_staff_reject_with_reason(client, seed, auth, session_factory):
    order_id = await _make_order(client, seed, auth)
    async with session_factory() as session:
        await order_service.set_status_by_staff(
            session, order_id, OrderStatus.REJECTED, "Sardor", reason="  Mahsulot tugadi "
        )
    body = (await client.get(f"/orders/{order_id}", headers=auth)).json()
    assert body["status"] == "rejected"
    assert body["reject_reason"] == "Mahsulot tugadi"


async def test_customer_cannot_cancel_after_accept(client, seed, auth, session_factory):
    order_id = await _make_order(client, seed, auth)
    async with session_factory() as session:
        await order_service.set_status_by_staff(session, order_id, OrderStatus.ACCEPTED, "A")
    response = await client.post(f"/orders/{order_id}/cancel", headers=auth)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "cannot_cancel"


async def test_staff_cannot_accept_cancelled_order(client, seed, auth, session_factory):
    order_id = await _make_order(client, seed, auth)
    await client.post(f"/orders/{order_id}/cancel", headers=auth)
    async with session_factory() as session:
        with pytest.raises(StatusChangeError) as info:
            await order_service.set_status_by_staff(session, order_id, OrderStatus.ACCEPTED, "A")
    assert "bekor qilgan" in info.value.message
    assert info.value.order.status == "cancelled"
