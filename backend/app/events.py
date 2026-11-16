"""Jonli yangilanishlar: bazada biror narsa o'zgarsa, ochiq turgan ilovalarga darhol xabar boradi.

Zanjir shunday ishlaydi:

1. API ham, bot ham bazaga bitta joydan (`make_session_factory`) yozadi. Shu yerda ulangan
   kuzatuvchilar har bir yozuvni ko'radi va undan hodisa yasaydi: menyu o'zgardi, kafe
   sozlamalari o'zgardi, buyurtma holati o'zgardi. Kod yozuvchi buni har joyda eslab
   chaqirishi shart emas.
2. PostgreSQL'da hodisa shu tranzaksiyaning o'zida `pg_notify` orqali jo'natiladi:
   tranzaksiya saqlansa yetib boradi, bekor bo'lsa yo'qoladi. Bot va API alohida
   jarayonlar bo'lgani uchun aynan baza ular orasidagi "sim" vazifasini bajaradi.
3. API jarayoni shu kanalni tinglaydi (`listen_forever`) va hodisani `EventHub` orqali
   ulanib turgan barcha ilovalarga tarqatadi (`app/api/events.py`, SSE oqimi).

Testlardagi SQLite'da `pg_notify` yo'q: u yerda hodisa saqlangandan so'ng to'g'ridan-to'g'ri
`EventHub`ga beriladi.
"""

import asyncio
import json
import logging
from contextlib import suppress
from dataclasses import asdict, dataclass

import asyncpg
from sqlalchemy import event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.models import Category, Order, Product, ShopSettings

log = logging.getLogger(__name__)

CHANNEL = "amora_events"

MENU = "menu"  # taom yoki bo'lim qo'shildi, o'zgardi, tugadi, o'chirildi
SHOP = "shop"  # kafe sozlamalari: ish vaqti, yetkazish narxi, buyurtma qabul qilish
ORDER = "order"  # bitta buyurtmaning holati o'zgardi
RESYNC = "resync"  # ba'zi hodisalar o'tkazib yuborilgan bo'lishi mumkin: hammasini qayta o'qing

_PENDING = "amora_pending_events"


@dataclass(frozen=True)
class Event:
    type: str
    order_id: int | None = None
    customer_id: int | None = None
    status: str | None = None
    reject_reason: str | None = None

    def to_json(self) -> str:
        data = {key: value for key, value in asdict(self).items() if value is not None}
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_json(cls, payload: str) -> "Event | None":
        """Tushunarsiz xabar kelsa None qaytaradi: tinglovchi yiqilmasligi kerak."""
        try:
            data = json.loads(payload)
            return cls(
                type=str(data["type"]),
                order_id=_int_or_none(data.get("order_id")),
                customer_id=_int_or_none(data.get("customer_id")),
                status=_str_or_none(data.get("status")),
                reject_reason=_str_or_none(data.get("reject_reason")),
            )
        except (ValueError, KeyError, TypeError):
            return None


def _int_or_none(value) -> int | None:
    return int(value) if value is not None else None


def _str_or_none(value) -> str | None:
    return str(value) if value is not None else None


class HubFull(Exception):
    """Juda ko'p ilova ulanib turibdi."""


class Subscription:
    """Bitta ulangan ilovaning navbati."""

    def __init__(self, size: int):
        self._queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=size)

    async def get(self) -> Event:
        return await self._queue.get()

    def _put(self, item: Event) -> None:
        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull:
            # Ilova xabarlarni o'qib ulgurmayapti (aloqa sust). Navbatni tozalab, o'rniga
            # bitta "hammasini qayta o'qi" xabarini qoldiramiz: hech narsa yo'qolmaydi.
            while not self._queue.empty():
                self._queue.get_nowait()
            self._queue.put_nowait(Event(RESYNC))


class EventHub:
    """Hodisalarni shu jarayonga ulangan barcha ilovalarga tarqatadi."""

    def __init__(self, max_subscribers: int = 2000, queue_size: int = 64):
        self._subscribers: set[Subscription] = set()
        self._max_subscribers = max_subscribers
        self._queue_size = queue_size

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    @property
    def is_full(self) -> bool:
        return len(self._subscribers) >= self._max_subscribers

    def subscribe(self) -> Subscription:
        if self.is_full:
            raise HubFull
        subscription = Subscription(self._queue_size)
        self._subscribers.add(subscription)
        return subscription

    def unsubscribe(self, subscription: Subscription) -> None:
        self._subscribers.discard(subscription)

    def publish(self, item: Event) -> None:
        """Faqat asyncio sikli ichidan chaqiriladi."""
        for subscription in tuple(self._subscribers):
            subscription._put(item)


# ---------- Bazaga yozilgan narsadan hodisa yasash ----------


def _order_event(order: Order) -> Event:
    return Event(
        ORDER,
        order_id=order.id,
        customer_id=order.customer_id,
        status=order.status,
        reject_reason=order.reject_reason or None,
    )


def _events_from_flush(session: Session) -> list[Event]:
    found: dict[Event, None] = {}  # tartibni saqlaydigan to'plam
    for obj in session.new:
        if isinstance(obj, Product | Category):
            found[Event(MENU)] = None
        elif isinstance(obj, ShopSettings):
            found[Event(SHOP)] = None
        elif isinstance(obj, Order):
            found[_order_event(obj)] = None
    for obj in session.dirty:
        if not session.is_modified(obj):
            continue
        if isinstance(obj, Product | Category):
            found[Event(MENU)] = None
        elif isinstance(obj, ShopSettings):
            found[Event(SHOP)] = None
        elif isinstance(obj, Order):
            # Guruhdagi xabar raqami kabi ichki ustunlar o'zgarsa, mijozga xabar kerak emas
            if inspect(obj).attrs.status.history.has_changes():
                found[_order_event(obj)] = None
    for obj in session.deleted:
        if isinstance(obj, Product | Category):
            found[Event(MENU)] = None
        elif isinstance(obj, ShopSettings):
            found[Event(SHOP)] = None
    return list(found)


def _emit(session: Session, events: list[Event]) -> None:
    """Hodisalarni shu tranzaksiyaga biriktiradi."""
    if not events:
        return
    pending: dict[str, Event] = session.info.setdefault(_PENDING, {})
    fresh = []
    for item in events:
        payload = item.to_json()
        if payload not in pending:
            pending[payload] = item
            fresh.append(payload)
    if not fresh:
        return
    connection = session.connection()
    if connection.dialect.name == "postgresql":
        # NOTIFY tranzaksiya bilan birga yashaydi: commit bo'lsa jo'naydi, rollback bo'lsa yo'q
        for payload in fresh:
            connection.execute(
                text("SELECT pg_notify(:channel, :payload)"),
                {"channel": CHANNEL, "payload": payload},
            )


def attach_event_hooks(sync_maker: sessionmaker, hub: EventHub | None = None) -> None:
    """Sessiyalar fabrikasiga kuzatuvchilarni ulaydi.

    `hub` faqat PostgreSQL bo'lmagan bazada (testlar) ishlatiladi: u yerda hodisa
    saqlangandan keyin to'g'ridan-to'g'ri shu jarayondagi ilovalarga beriladi.
    """

    @event.listens_for(sync_maker, "after_flush")
    def _after_flush(session: Session, _flush_context) -> None:
        _emit(session, _events_from_flush(session))

    @event.listens_for(sync_maker, "do_orm_execute")
    def _on_execute(state) -> None:
        # `update(Product)...` kabi ommaviy so'rovlar obyektlarni chetlab o'tadi
        if not (state.is_update or state.is_delete or state.is_insert):
            return
        mapper = state.bind_mapper
        if mapper is None:
            return
        if issubclass(mapper.class_, Product | Category):
            _emit(state.session, [Event(MENU)])
        elif issubclass(mapper.class_, ShopSettings):
            _emit(state.session, [Event(SHOP)])

    @event.listens_for(sync_maker, "after_commit")
    def _after_commit(session: Session) -> None:
        pending: dict[str, Event] = session.info.pop(_PENDING, {})
        if not pending or hub is None:
            return
        bind = session.get_bind()
        if bind.dialect.name == "postgresql":
            return  # baza o'zi yetkazadi: `listen_forever`
        for item in pending.values():
            hub.publish(item)

    @event.listens_for(sync_maker, "after_transaction_end")
    def _after_transaction_end(session: Session, transaction) -> None:
        # Saqlanmay yopilgan tranzaksiyaning hodisalari keyingisiga o'tib ketmasin
        if transaction.parent is None:
            session.info.pop(_PENDING, None)


# ---------- PostgreSQL kanalini tinglash ----------


def asyncpg_dsn(database_url: str) -> str:
    """`postgresql+asyncpg://...` manzilini asyncpg tushunadigan ko'rinishga keltiradi."""
    return make_url(database_url).set(drivername="postgresql").render_as_string(hide_password=False)


async def listen_forever(database_url: str, hub: EventHub) -> None:
    """Baza kanalini tinglaydi va hodisalarni ilovalarga uzatadi. Aloqa uzilsa, qayta ulanadi."""
    dsn = asyncpg_dsn(database_url)
    delay = 1.0
    while True:
        connection = None
        closed = asyncio.Event()

        def on_notify(_connection, _pid, _channel, payload: str) -> None:
            item = Event.from_json(payload)
            if item is not None:
                hub.publish(item)

        def on_close(_connection) -> None:
            closed.set()

        try:
            connection = await asyncpg.connect(dsn, timeout=10)
            connection.add_termination_listener(on_close)
            await connection.add_listener(CHANNEL, on_notify)
            # Ulanmagan paytda nimadir o'zgargan bo'lishi mumkin: ilovalar hammasini qayta o'qisin
            hub.publish(Event(RESYNC))
            delay = 1.0
            log.info("Jonli yangilanishlar kanali tinglanmoqda")
            while not closed.is_set():
                with suppress(TimeoutError):
                    await asyncio.wait_for(closed.wait(), timeout=30)
                if not closed.is_set():
                    await connection.execute("SELECT 1", timeout=10)  # aloqa tirikmi
            log.warning("Jonli yangilanishlar kanali uzildi, qayta ulanamiz")
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001
            log.warning("Jonli yangilanishlar kanaliga ulanib bo'lmadi (%s)", error)
        finally:
            if connection is not None and not connection.is_closed():
                with suppress(Exception):
                    await asyncio.wait_for(connection.close(), timeout=5)
        await asyncio.sleep(delay)
        delay = min(delay * 2, 30.0)
