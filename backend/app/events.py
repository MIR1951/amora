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
import signal
import threading
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager, suppress
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
_SNAPSHOTS = "amora_pending_snapshots"


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
    """Juda ko'p ilova ulanib turibdi (yoki server to'xtayapti)."""


class TooManyStreams(Exception):
    """Bitta manzildan (ro'yxatdan o'tmagan ilovalar) juda ko'p ulanish ochilgan."""


class Subscription:
    """Bitta ulangan ilovaning navbati."""

    def __init__(self, size: int, customer_id: int | None, key: tuple[str, object]):
        self.customer_id = customer_id
        self.key = key
        self._queue: asyncio.Queue[Event | None] = asyncio.Queue(maxsize=size)
        self._closed = False

    async def get(self) -> Event | None:
        """Keyingi hodisa. None: server to'xtayapti, ulanish yopilishi kerak."""
        return await self._queue.get()

    def _clear(self) -> None:
        while not self._queue.empty():
            self._queue.get_nowait()

    def _put(self, item: Event) -> None:
        if self._closed:
            return
        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull:
            # Ilova xabarlarni o'qib ulgurmayapti (aloqa sust). Navbatni tozalab, o'rniga
            # bitta "hammasini qayta o'qi" xabarini qoldiramiz: hech narsa yo'qolmaydi.
            self._clear()
            self._queue.put_nowait(Event(RESYNC))

    def _close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._clear()
        self._queue.put_nowait(None)


class EventHub:
    """Hodisalarni shu jarayonga ulangan barcha ilovalarga tarqatadi.

    Ulanishlar soni cheklangan: jami, bitta mijozga va (ro'yxatdan o'tmaganlar uchun) bitta
    manzilga. Aks holda bitta kompyuter minglab bo'sh ulanish ochib, qolgan hammani jonli
    yangilanishlarsiz qoldirishi mumkin edi.

    Mijoz chegaradan oshsa, yangi ulanish rad etilmaydi: uning eng eski ulanishi yopiladi.
    Telefon Wi-Fi'dan mobil internetga o'tganda eski ulanish server tomonda bir necha daqiqa
    "tirik" ko'rinib turadi; rad etilganda aynan ishlayotgan yangi ulanish jabr ko'rar edi.
    """

    def __init__(
        self,
        max_subscribers: int = 2000,
        queue_size: int = 64,
        max_per_customer: int = 4,
        max_per_address: int = 60,
    ):
        self._subscribers: dict[Subscription, None] = {}  # ochilgan tartibida
        self._per_key: Counter[tuple[str, object]] = Counter()
        self._max_subscribers = max_subscribers
        self._queue_size = queue_size
        self._max_per_customer = max_per_customer
        self._max_per_address = max_per_address
        self._closed = False

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    @property
    def is_full(self) -> bool:
        return len(self._subscribers) >= self._max_subscribers

    def subscribe(self, customer_id: int | None = None, address: str = "") -> Subscription:
        """Yangi ulanish uchun joy oladi. `address` ro'yxatdan o'tmagan ilovalar uchun hisobga olinadi
        (bitta uy yoki aloqa operatori manzili ortida ko'p telefon bo'lishi mumkin, chegara shunga yarasha keng).
        """
        if self._closed or self.is_full:
            raise HubFull
        key: tuple[str, object]
        if customer_id is not None:
            key = ("customer", customer_id)
            if self._per_key[key] >= self._max_per_customer:
                oldest = next(item for item in self._subscribers if item.key == key)
                self.unsubscribe(oldest)
                oldest._close()
        else:
            key = ("address", address)
            if self._per_key[key] >= self._max_per_address:
                raise TooManyStreams
        subscription = Subscription(self._queue_size, customer_id, key)
        self._subscribers[subscription] = None
        self._per_key[key] += 1
        return subscription

    def unsubscribe(self, subscription: Subscription) -> None:
        if subscription not in self._subscribers:
            return
        del self._subscribers[subscription]
        self._per_key[subscription.key] -= 1
        if self._per_key[subscription.key] <= 0:
            del self._per_key[subscription.key]

    def publish(self, item: Event) -> None:
        """Faqat asyncio sikli ichidan chaqiriladi."""
        for subscription in tuple(self._subscribers):
            # Buyurtma haqidagi xabar faqat egasining navbatiga tushadi
            if item.type == ORDER and item.customer_id != subscription.customer_id:
                continue
            subscription._put(item)

    def close(self) -> None:
        """Server to'xtayapti: ochiq ulanishlar toza yopiladi, yangilari qabul qilinmaydi."""
        self._closed = True
        for subscription in tuple(self._subscribers):
            subscription._close()


@contextmanager
def close_on_stop_signal(hub: EventHub) -> Iterator[None]:
    """To'xtatish signali kelganda (`docker stop`) ochiq oqimlarni darhol yopadi.

    Oqim o'zi hech qachon tugamaydi, uvicorn esa to'xtashdan oldin ochiq so'rovlar tugashini
    kutadi: shusiz har bir qayta ishga tushirish bir necha soniyaga cho'zilar va har bir ochiq
    ulanish uchun jurnalga xato yozilar edi. Avval o'rnatilgan ishlovchi (uvicornniki) ham
    chaqiriladi, chiqishda esa joyiga qaytariladi.
    """
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    loop = asyncio.get_running_loop()
    previous: dict[int, object] = {}

    def on_stop(signum, frame) -> None:
        loop.call_soon_threadsafe(hub.close)
        handler = previous.get(signum)
        if callable(handler):
            handler(signum, frame)

    for signum in (signal.SIGTERM, signal.SIGINT):
        previous[signum] = signal.signal(signum, on_stop)
    try:
        yield
    finally:
        for signum, handler in previous.items():
            if handler is not None and signal.getsignal(signum) is on_stop:
                signal.signal(signum, handler)


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
    connection = session.connection()
    if connection.dialect.name == "postgresql":
        # NOTIFY tranzaksiya bilan birga yashaydi: commit bo'lsa jo'naydi, rollback bo'lsa
        # (savepoint ichida ham) yo'qoladi. Bir xil xabarlarni baza o'zi bittaga keltiradi,
        # shuning uchun bu yerda hisob yuritilmaydi.
        for item in events:
            connection.execute(
                text("SELECT pg_notify(:channel, :payload)"),
                {"channel": CHANNEL, "payload": item.to_json()},
            )
        return
    pending: dict[str, Event] = session.info.setdefault(_PENDING, {})
    for item in events:
        pending.setdefault(item.to_json(), item)


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
        # PostgreSQL'da bu ro'yxat doim bo'sh: hodisalarni baza o'zi yetkazadi (`listen_forever`)
        if session.in_nested_transaction():
            return  # savepoint yopildi, xolos: tashqi tranzaksiya hali saqlanmagan
        pending: dict[str, Event] = session.info.pop(_PENDING, {})
        if hub is None:
            return
        for item in pending.values():
            hub.publish(item)

    # PostgreSQL bo'lmagan bazada savepoint'ni baza o'zi hisobga olmaydi: har bir savepoint
    # ochilganda navbatdagi hodisalar eslab qolinadi va u bekor qilinsa, o'shalarga qaytiladi
    @event.listens_for(sync_maker, "after_transaction_create")
    def _after_transaction_create(session: Session, transaction) -> None:
        if transaction.nested:
            snapshots = session.info.setdefault(_SNAPSHOTS, {})
            snapshots[transaction] = dict(session.info.get(_PENDING, {}))

    @event.listens_for(sync_maker, "after_soft_rollback")
    def _after_soft_rollback(session: Session, previous_transaction) -> None:
        # `after_transaction_end` dan keyin keladi, shuning uchun eslab qolingani shu yerda olinadi.
        # Saqlangan (release) savepoint'larniki tashqi tranzaksiya tugaguncha qolaveradi.
        snapshot = session.info.get(_SNAPSHOTS, {}).pop(previous_transaction, None)
        if snapshot is not None:
            session.info[_PENDING] = snapshot

    @event.listens_for(sync_maker, "after_transaction_end")
    def _after_transaction_end(session: Session, transaction) -> None:
        # Saqlanmay yopilgan tranzaksiyaning hodisalari keyingisiga o'tib ketmasin
        if transaction.parent is None:
            session.info.pop(_PENDING, None)
            session.info.pop(_SNAPSHOTS, None)


# ---------- PostgreSQL kanalini tinglash ----------


# SQLAlchemy'ning o'ziga tegishli sozlamalar: asyncpg ularni bilmaydi
_SQLALCHEMY_ONLY = (
    "prepared_statement_cache_size",
    "prepared_statement_name_func",
    "async_creator_fn",
    "async_fallback",
)


def asyncpg_connect_args(database_url: str) -> dict:
    """`postgresql+asyncpg://...` manzilidan `asyncpg.connect` uchun parametrlar yasaydi.

    Manzilni SQLAlchemy'ning o'zi tarjima qiladi: `?ssl=require`, `?host=...` kabi sozlamalar
    asosiy ulanishdagidek tushuniladi. Aks holda baza bilan asosiy aloqa ishlab, tinglovchi
    ulanolmay qolishi mumkin edi.
    """
    from sqlalchemy.dialects.postgresql.asyncpg import PGDialect_asyncpg

    _, args = PGDialect_asyncpg().create_connect_args(make_url(database_url))
    for key in _SQLALCHEMY_ONLY:
        args.pop(key, None)
    args.setdefault("timeout", 10)
    return args


async def listen_forever(database_url: str, hub: EventHub) -> None:
    """Baza kanalini tinglaydi va hodisalarni ilovalarga uzatadi. Aloqa uzilsa, qayta ulanadi."""
    connect_args = asyncpg_connect_args(database_url)
    delay = 1.0
    failures = 0
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
            connection = await asyncpg.connect(**connect_args)
            connection.add_termination_listener(on_close)
            await connection.add_listener(CHANNEL, on_notify)
            # Ulanmagan paytda nimadir o'zgargan bo'lishi mumkin: ilovalar hammasini qayta o'qisin
            hub.publish(Event(RESYNC))
            delay = 1.0
            failures = 0
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
            failures += 1
            # Birinchi xato baland ovozda yoziladi: ulanish sozlamasi noto'g'ri bo'lsa, ilovalar
            # "ulandim" deb turadi-yu, hech qanday yangilanish kelmaydi
            level = logging.ERROR if failures == 1 else logging.WARNING
            log.log(level, "Jonli yangilanishlar kanaliga ulanib bo'lmadi (%r)", error)
        finally:
            if connection is not None and not connection.is_closed():
                with suppress(Exception):
                    await asyncio.wait_for(connection.close(), timeout=5)
        await asyncio.sleep(delay)
        delay = min(delay * 2, 30.0)
