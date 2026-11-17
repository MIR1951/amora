"""Jonli yangilanishlar oqimi (Server-Sent Events).

Ilova ochiq turganda shu manzilga bitta doimiy ulanish ushlab turadi. Menyu, kafe
sozlamalari yoki mijozning buyurtmasi o'zgarsa, server shu ulanish orqali qisqa xabar
yuboradi va ilova kerakli ma'lumotni qayta o'qiydi. Xabarning o'zida ma'lumot yo'q
(buyurtma holatidan tashqari): manba har doim oddiy so'rovlar bo'lib qoladi.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.errors import ApiError
from app.events import (
    MENU,
    ORDER,
    RESYNC,
    SHOP,
    Event,
    EventHub,
    HubFull,
    Subscription,
    TooManyStreams,
)
from app.models import STATUS_LABELS, CustomerDevice, OrderStatus
from app.security import hash_token

router = APIRouter(tags=["jonli"])

_bearer = HTTPBearer(auto_error=False)

# Xabar bo'lmasa ham shuncha soniyada bir marta bo'sh satr yuboriladi: aloqa operatori
# va proksi jim turgan ulanishni uzib qo'ymasin, ilova esa uzilishni tez sezsin
HEARTBEAT_SECONDS = 20.0


def sse(name: str, data: dict | None = None) -> str:
    body = json.dumps(data or {}, ensure_ascii=False, separators=(",", ":"))
    return f"event: {name}\ndata: {body}\n\n"


def client_message(item: Event, customer_id: int | None) -> str | None:
    """Hodisani ilovaga yuboriladigan matnga aylantiradi. Bu ilovaga tegishli bo'lmasa None."""
    if item.type in (MENU, SHOP, RESYNC):
        return sse(item.type)
    if item.type == ORDER:
        # Buyurtma haqidagi xabar faqat egasiga boradi
        if customer_id is None or item.customer_id != customer_id or item.order_id is None:
            return None
        try:
            label = STATUS_LABELS[OrderStatus(item.status)]
        except ValueError:
            return None
        data = {"order_id": item.order_id, "status": item.status, "status_label": label}
        if item.reject_reason:
            data["reject_reason"] = item.reject_reason
        return sse(ORDER, data)
    return None


async def event_stream(
    subscription: Subscription, heartbeat: float = HEARTBEAT_SECONDS
) -> AsyncIterator[str]:
    """Bitta ilovaga ketadigan oqim. Navbatni bo'shatish chaqiruvchining ishi (`EventStreamResponse`)."""
    loop = asyncio.get_running_loop()
    # Ilova shu xabarni olgach "ulandim" deb hisoblaydi va ma'lumotni bir marta yangilaydi
    yield sse("ready")
    # "Ping" oxirgi YUBORILGAN satrdan hisoblanadi: ilovaga tegishli bo'lmagan hodisalar
    # (boshqalarning buyurtmalari) ulanishni jim qoldirmasligi kerak
    deadline = loop.time() + heartbeat
    while True:
        try:
            item = await asyncio.wait_for(
                subscription.get(), timeout=max(0.0, deadline - loop.time())
            )
        except TimeoutError:
            message = ": ping\n\n"
        else:
            if item is None:
                return  # server to'xtayapti
            message = client_message(item, subscription.customer_id)
            if message is None:
                continue
        yield message
        deadline = loop.time() + heartbeat


class EventStreamResponse(StreamingResponse):
    """Oqim tugagach (ilova uzildi, server to'xtadi yoki javob umuman boshlanmadi) navbatni bo'shatadi."""

    def __init__(self, hub: EventHub, subscription: Subscription):
        super().__init__(
            event_stream(subscription),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",  # nginx xabarlarni ushlab turmasin
            },
        )
        self._hub = hub
        self._subscription = subscription

    async def __call__(self, scope, receive, send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            self._hub.unsubscribe(self._subscription)


@router.get(
    "/events",
    summary="Jonli yangilanishlar (SSE)",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def stream_events(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> StreamingResponse:
    """Doimiy ulanish. Xabar turlari:

    - `ready`: ulanish o'rnatildi;
    - `menu`: menyu o'zgardi, `GET /menu` ni qayta o'qing;
    - `shop`: kafe sozlamalari o'zgardi, `GET /shop` ni qayta o'qing;
    - `order`: mijozning buyurtmasi holati o'zgardi (`order_id`, `status`, `status_label`);
      faqat `Authorization` yuborilgan bo'lsa keladi;
    - `resync`: ba'zi xabarlar o'tkazib yuborilgan bo'lishi mumkin, hammasini qayta o'qing.
    """
    hub: EventHub = request.app.state.events
    if hub.is_full:
        raise ApiError(503, "busy", "Server band. Birozdan keyin qayta urinib ko'ring")

    customer_id = None
    if credentials is not None and credentials.credentials:
        # Sessiya shu yerning o'zida yopiladi: ulanish soatlab ochiq tursa ham baza band bo'lmaydi
        async with request.app.state.session_factory() as session:
            customer_id = await session.scalar(
                select(CustomerDevice.customer_id).where(
                    CustomerDevice.token_hash == hash_token(credentials.credentials)
                )
            )

    # Joy shu yerda, javob qaytarilishidan oldin olinadi: tekshiruv va band qilish bitta qadam
    address = request.client.host if request.client else ""
    try:
        subscription = hub.subscribe(customer_id=customer_id, address=address)
    except HubFull:
        raise ApiError(503, "busy", "Server band. Birozdan keyin qayta urinib ko'ring") from None
    except TooManyStreams:
        raise ApiError(
            429, "too_many_streams", "Juda ko'p ulanish ochilgan. Birozdan keyin qayta urinib ko'ring"
        ) from None
    return EventStreamResponse(hub, subscription)
