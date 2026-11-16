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
from app.events import MENU, ORDER, RESYNC, SHOP, Event, EventHub, HubFull
from app.models import STATUS_LABELS, Customer, OrderStatus
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
    hub: EventHub, customer_id: int | None, heartbeat: float = HEARTBEAT_SECONDS
) -> AsyncIterator[str]:
    try:
        subscription = hub.subscribe()
    except HubFull:
        return
    try:
        # Ilova shu xabarni olgach "ulandim" deb hisoblaydi va ma'lumotni bir marta yangilaydi
        yield sse("ready")
        while True:
            try:
                item = await asyncio.wait_for(subscription.get(), timeout=heartbeat)
            except TimeoutError:
                yield ": ping\n\n"
                continue
            message = client_message(item, customer_id)
            if message is not None:
                yield message
    finally:
        hub.unsubscribe(subscription)


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
                select(Customer.id).where(
                    Customer.token_hash == hash_token(credentials.credentials)
                )
            )

    return StreamingResponse(
        event_stream(hub, customer_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # nginx xabarlarni ushlab turmasin
        },
    )
