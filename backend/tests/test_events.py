"""Jonli yangilanishlar: bazaga yozilgan narsa hodisaga aylanishi va ilovaga yetib borishi."""

import asyncio
import json
import signal
from contextlib import asynccontextmanager, suppress

import httpx
import pytest
import uvicorn
from sqlalchemy import select, update
from sqlalchemy.engine import make_url

from app.api.events import client_message, event_stream
from app.db import make_session_factory
from app.events import (
    MENU,
    ORDER,
    RESYNC,
    SHOP,
    Event,
    EventHub,
    HubFull,
    TooManyStreams,
    asyncpg_connect_args,
    close_on_stop_signal,
    listen_forever,
)
from app.main import create_app
from app.models import Category, Customer, Order, OrderStatus, Product, ShopSettings
from app.services import orders as order_service
from tests.conftest import NEAR, TEST_DATABASE_URL, register

IS_POSTGRES = TEST_DATABASE_URL.startswith("postgresql")


async def next_event(subscription, timeout: float = 5.0) -> Event:
    return await asyncio.wait_for(subscription.get(), timeout=timeout)


async def assert_silent(subscription, wait: float = 0.3) -> None:
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(subscription.get(), timeout=wait)


class RecordingHub(EventHub):
    """Markazdan o'tgan hamma hodisani (begona buyurtmalarnikini ham) yozib boradi."""

    def __init__(self) -> None:
        super().__init__()
        self.published: asyncio.Queue[Event] = asyncio.Queue()

    def publish(self, item: Event) -> None:
        self.published.put_nowait(item)
        super().publish(item)


@pytest.fixture
async def live(engine, seed):
    """Hodisalar markazi, unga ulangan sessiyalar fabrikasi va markazdan o'tgan hodisalar navbati.

    PostgreSQL'da hodisalar baza kanali orqali keladi, shuning uchun kanal tinglovchisi ham
    ishga tushiriladi (haqiqiy serverda buni API jarayoni qiladi).
    """
    hub = RecordingHub()
    factory = make_session_factory(engine, hub)
    subscription = hub.published
    listener = None
    if IS_POSTGRES:
        listener = asyncio.create_task(listen_forever(TEST_DATABASE_URL, hub))
        assert (await next_event(subscription)).type == RESYNC  # kanal tinglanmoqda
    yield hub, factory, subscription
    if listener is not None:
        listener.cancel()
        with suppress(asyncio.CancelledError):
            await listener


async def make_order(factory, seed, phone: str = "+998901234567") -> tuple[int, int]:
    """Bazaga to'g'ridan-to'g'ri bitta yangi buyurtma yozadi. (buyurtma, mijoz) raqamlarini qaytaradi."""
    async with factory() as session:
        customer = Customer(name="Ali", phone=phone, token_hash=f"hash-{phone}")
        session.add(customer)
        await session.flush()
        order = Order(
            customer_id=customer.id,
            status=OrderStatus.NEW.value,
            customer_name="Ali",
            phone=phone,
            items_total=35_000,
            delivery_fee=10_000,
            total=45_000,
            **NEAR,
        )
        session.add(order)
        await session.commit()
        return order.id, customer.id


# ---------- Bazaga yozuv -> hodisa ----------


async def test_marking_product_unavailable_publishes_menu_event(live, seed):
    _, factory, subscription = live
    async with factory() as session:
        product = await session.get(Product, seed["osh"])
        product.is_available = False
        await session.commit()
    assert await next_event(subscription) == Event(MENU)
    await assert_silent(subscription)  # bitta o'zgarish, bitta xabar


async def test_new_and_deleted_category_publish_menu_events(live):
    _, factory, subscription = live
    async with factory() as session:
        category = Category(name="Ichimliklar")
        session.add(category)
        await session.commit()
        assert await next_event(subscription) == Event(MENU)
        await session.delete(category)
        await session.commit()
    assert await next_event(subscription) == Event(MENU)


async def test_bulk_update_publishes_menu_event(live, seed):
    _, factory, subscription = live
    async with factory() as session:
        await session.execute(update(Product).values(is_available=False))
        await session.commit()
    assert await next_event(subscription) == Event(MENU)


async def test_shop_settings_change_publishes_shop_event(live):
    _, factory, subscription = live
    async with factory() as session:
        shop = await session.get(ShopSettings, 1)
        shop.is_accepting_orders = False
        await session.commit()
    assert await next_event(subscription) == Event(SHOP)


async def test_reading_does_not_publish(live, seed):
    _, factory, subscription = live
    async with factory() as session:
        await session.scalars(select(Product))
        product = await session.get(Product, seed["osh"])
        product.is_available = True  # qiymat o'zgarmadi
        await session.commit()
    await assert_silent(subscription)


async def test_rolled_back_change_is_not_published(live, seed):
    _, factory, subscription = live
    async with factory() as session:
        product = await session.get(Product, seed["osh"])
        product.price = 1
        await session.flush()
        await session.rollback()
        # Bekor qilingan tranzaksiyaning hodisasi keyingi saqlashda ham chiqib ketmasligi kerak
        await session.commit()
    await assert_silent(subscription)


async def test_change_inside_rolled_back_savepoint_does_not_swallow_the_next_one(live, seed):
    _, factory, subscription = live
    async with factory() as session:
        product = await session.get(Product, seed["osh"])
        savepoint = await session.begin_nested()
        product.is_available = False
        await session.flush()
        await savepoint.rollback()  # shu bilan birinchi xabar ham bekor bo'ldi
        await session.refresh(product)
        product.price = 99_000
        await session.commit()
    assert await next_event(subscription) == Event(MENU)
    await assert_silent(subscription)


async def test_change_only_inside_rolled_back_savepoint_is_not_published(live, seed):
    _, factory, subscription = live
    async with factory() as session:
        product = await session.get(Product, seed["osh"])
        savepoint = await session.begin_nested()
        product.is_available = False
        await session.flush()
        await savepoint.rollback()
        session.add(Customer(name="Ali", phone="+998900000001", token_hash="h1"))
        await session.commit()  # saqlangan narsa menyuga aloqasi yo'q
    await assert_silent(subscription)

    async with factory() as session:
        product = await session.get(Product, seed["osh"])
        outer = await session.begin_nested()
        async with session.begin_nested():
            product.is_available = False  # ichki savepoint saqlandi...
        await outer.rollback()  # ...lekin uni o'z ichiga olgani bekor qilindi
        await session.commit()
    await assert_silent(subscription)


async def test_released_savepoint_publishes_only_after_outer_commit(live, seed):
    _, factory, subscription = live
    async with factory() as session:
        product = await session.get(Product, seed["osh"])
        async with session.begin_nested():
            product.is_available = False
        # Savepoint yopildi, lekin tashqi tranzaksiya hali saqlanmagan: boshqalar ko'rmaydi
        await assert_silent(subscription)
        await session.commit()
    assert await next_event(subscription) == Event(MENU)
    await assert_silent(subscription)

    async with factory() as session:
        product = await session.get(Product, seed["osh"])
        async with session.begin_nested():
            product.is_available = True
        await session.rollback()  # savepoint yopilgan edi, lekin hammasi bekor qilindi
    await assert_silent(subscription)


async def test_order_lifecycle_publishes_order_events(live, seed):
    _, factory, subscription = live
    order_id, customer_id = await make_order(factory, seed)
    assert await next_event(subscription) == Event(
        ORDER, order_id=order_id, customer_id=customer_id, status="new"
    )

    async with factory() as session:
        await order_service.set_status_by_staff(session, order_id, OrderStatus.ACCEPTED, "Vali")
    assert await next_event(subscription) == Event(
        ORDER, order_id=order_id, customer_id=customer_id, status="accepted"
    )

    async with factory() as session:
        # Tugma ikki marta bosildi: holat o'zgarmadi, xabar ham yo'q
        await order_service.set_status_by_staff(session, order_id, OrderStatus.ACCEPTED, "Vali")
    await assert_silent(subscription)

    async with factory() as session:
        await order_service.set_status_by_staff(
            session, order_id, OrderStatus.REJECTED, "Vali", reason="Mahsulot tugadi"
        )
    assert await next_event(subscription) == Event(
        ORDER,
        order_id=order_id,
        customer_id=customer_id,
        status="rejected",
        reject_reason="Mahsulot tugadi",
    )


async def test_internal_order_columns_do_not_publish(live, seed):
    _, factory, subscription = live
    order_id, _ = await make_order(factory, seed)
    await next_event(subscription)
    async with factory() as session:
        order = await session.get(Order, order_id)
        order.tg_chat_id = -100
        order.tg_message_id = 55  # bot guruhga xabar yubordi: mijozga aloqasi yo'q
        await session.commit()
    await assert_silent(subscription)


# ---------- Markaz ----------


def test_event_json_round_trip_and_garbage():
    item = Event(ORDER, order_id=7, customer_id=3, status="rejected", reject_reason="Yo'q")
    assert Event.from_json(item.to_json()) == item
    assert Event.from_json(Event(MENU).to_json()) == Event(MENU)
    assert Event(MENU).to_json() == '{"type":"menu"}'
    for garbage in ("", "salom", "[]", "{}", '{"type":"order","order_id":"x"}'):
        assert Event.from_json(garbage) is None


def test_asyncpg_connect_args_keep_credentials_and_url_options():
    assert asyncpg_connect_args("postgresql+asyncpg://amora:s3cr%40t@db:5432/amora") == {
        "host": "db",
        "port": 5432,
        "user": "amora",
        "password": "s3cr@t",
        "database": "amora",
        "timeout": 10,
    }
    # Manzil oxiridagi sozlamalar: asyncpgniki uzatiladi, SQLAlchemy'ning o'ziniki tashlab yuboriladi
    args = asyncpg_connect_args(
        "postgresql+asyncpg://amora@db/amora?ssl=require&prepared_statement_cache_size=0&timeout=3"
    )
    assert args["ssl"] == "require"
    assert args["timeout"] == "3"
    assert "prepared_statement_cache_size" not in args
    assert "port" not in args
    # Server manzili so'rov qismida berilishi ham mumkin: asosiy ulanish buni tushunadi
    args = asyncpg_connect_args("postgresql+asyncpg://amora@/amora?host=10.0.0.5:6432")
    assert (args["host"], args["port"]) == ("10.0.0.5", 6432)


@pytest.mark.skipif(not IS_POSTGRES, reason="faqat PostgreSQL bilan")
async def test_listener_connects_with_host_given_in_query():
    url = make_url(TEST_DATABASE_URL)
    query_url = url.set(host=None, port=None).update_query_dict(
        {"host": f"{url.host}:{url.port or 5432}"}
    )
    hub = EventHub()
    subscription = hub.subscribe()
    listener = asyncio.create_task(
        listen_forever(query_url.render_as_string(hide_password=False), hub)
    )
    try:
        assert await next_event(subscription) == Event(RESYNC)  # kanalga ulandi
    finally:
        listener.cancel()
        with suppress(asyncio.CancelledError):
            await listener


async def test_slow_subscriber_gets_resync_instead_of_growing_queue():
    hub = EventHub(queue_size=3)
    subscription = hub.subscribe()
    for _ in range(4):
        hub.publish(Event(MENU))
    assert await next_event(subscription) == Event(RESYNC)
    await assert_silent(subscription, wait=0.05)


async def test_hub_limits_subscribers():
    hub = EventHub(max_subscribers=1)
    first = hub.subscribe()
    assert hub.is_full
    with pytest.raises(HubFull):
        hub.subscribe()
    hub.unsubscribe(first)
    hub.unsubscribe(first)  # ikki marta bo'shatish hisobni buzmaydi
    assert hub.subscriber_count == 0
    hub.subscribe()


async def test_hub_limits_anonymous_streams_per_address():
    hub = EventHub(max_per_address=2)
    first = hub.subscribe(address="10.0.0.1")
    hub.subscribe(address="10.0.0.1")
    with pytest.raises(TooManyStreams):
        hub.subscribe(address="10.0.0.1")
    hub.subscribe(address="10.0.0.2")  # boshqa manzilga aloqasi yo'q
    hub.subscribe(customer_id=1, address="10.0.0.1")  # kirgan mijoz o'z hisobida
    hub.unsubscribe(first)
    hub.subscribe(address="10.0.0.1")
    assert hub.subscriber_count == 4


async def test_extra_stream_of_a_customer_replaces_the_oldest_one():
    hub = EventHub(max_per_customer=2)
    first = hub.subscribe(customer_id=7)
    second = hub.subscribe(customer_id=7)
    other = hub.subscribe(customer_id=8)
    third = hub.subscribe(customer_id=7)  # telefon tarmoqni almashtirib, qayta ulandi
    assert hub.subscriber_count == 3
    assert await next_event(first) is None  # eng eski ulanish yopildi
    hub.publish(Event(ORDER, order_id=1, customer_id=7, status="accepted"))
    assert (await next_event(second)).order_id == 1
    assert (await next_event(third)).order_id == 1
    await assert_silent(other, wait=0.05)
    hub.unsubscribe(first)  # yopilgan ulanish javobi tugaganda: hisob o'zgarmaydi
    assert hub.subscriber_count == 3


async def test_order_event_is_queued_only_for_its_owner():
    hub = EventHub(queue_size=3)
    owner = hub.subscribe(customer_id=3)
    stranger = hub.subscribe(customer_id=4)
    anonymous = hub.subscribe()
    for number in range(10):  # gavjum payt: begonalarning navbati to'lib ketmasligi kerak
        hub.publish(Event(ORDER, order_id=number, customer_id=3, status="accepted"))
    await assert_silent(stranger, wait=0.05)
    await assert_silent(anonymous, wait=0.05)
    assert await next_event(owner) == Event(RESYNC)


async def test_closed_hub_ends_streams_and_refuses_new_ones():
    hub = EventHub()
    subscription = hub.subscribe()
    stream = event_stream(subscription, heartbeat=5)
    assert await anext(stream) == "event: ready\ndata: {}\n\n"
    hub.publish(Event(MENU))
    hub.close()
    hub.publish(Event(MENU))
    with pytest.raises(StopAsyncIteration):  # navbatdagi xabarlar emas, darhol yopilish
        await asyncio.wait_for(anext(stream), timeout=1)
    with pytest.raises(HubFull):
        hub.subscribe()


async def test_stop_signal_closes_hub_and_calls_previous_handler():
    hub = EventHub()
    subscription = hub.subscribe()
    seen: list[int] = []
    original = signal.signal(signal.SIGTERM, lambda signum, frame: seen.append(signum))
    try:
        with close_on_stop_signal(hub):
            signal.raise_signal(signal.SIGTERM)
            assert await next_event(subscription, timeout=1) is None
        assert seen == [signal.SIGTERM]  # avvalgi ishlovchi (uvicornniki) ham chaqirildi
        signal.raise_signal(signal.SIGTERM)
        assert seen == [signal.SIGTERM, signal.SIGTERM]  # chiqishda joyiga qaytarildi
    finally:
        signal.signal(signal.SIGTERM, original)


# ---------- Ilovaga yuboriladigan matn ----------


def test_order_message_goes_only_to_its_owner():
    item = Event(ORDER, order_id=7, customer_id=3, status="delivering")
    assert client_message(item, customer_id=None) is None
    assert client_message(item, customer_id=4) is None
    message = client_message(item, customer_id=3)
    assert message.startswith("event: order\ndata: ")
    assert message.endswith("\n\n")
    data = json.loads(message.split("data: ", 1)[1])
    assert data == {"order_id": 7, "status": "delivering", "status_label": "Kuryer yo'lda"}


def test_reject_reason_is_included_and_unknown_events_are_dropped():
    rejected = Event(ORDER, order_id=7, customer_id=3, status="rejected", reject_reason="Tugadi")
    data = json.loads(client_message(rejected, 3).split("data: ", 1)[1])
    assert data["reject_reason"] == "Tugadi"
    assert client_message(Event(MENU), None) == "event: menu\ndata: {}\n\n"
    assert client_message(Event(SHOP), 5) == "event: shop\ndata: {}\n\n"
    assert client_message(Event("boshqa"), 5) is None
    assert client_message(Event(ORDER, order_id=7, customer_id=3, status="???"), 3) is None


async def test_stream_starts_with_ready_sends_events_and_heartbeats():
    hub = EventHub()
    stream = event_stream(hub.subscribe(customer_id=3), heartbeat=0.05)
    assert await anext(stream) == "event: ready\ndata: {}\n\n"
    hub.publish(Event(MENU))
    assert await anext(stream) == "event: menu\ndata: {}\n\n"
    hub.publish(Event(ORDER, order_id=1, customer_id=9, status="accepted"))  # begona buyurtma
    assert await anext(stream) == ": ping\n\n"
    hub.publish(Event(ORDER, order_id=2, customer_id=3, status="accepted"))
    assert (await anext(stream)).startswith("event: order\n")
    await stream.aclose()


async def test_heartbeat_is_not_starved_by_events_the_client_does_not_get():
    hub = EventHub()
    stream = event_stream(hub.subscribe(), heartbeat=0.2)
    assert await anext(stream) == "event: ready\ndata: {}\n\n"

    async def noise() -> None:
        while True:  # ilovaga yuborilmaydigan hodisalar "ping" oralig'idan tezroq kelib turibdi
            hub.publish(Event("boshqa"))
            await asyncio.sleep(0.02)

    task = asyncio.create_task(noise())
    try:
        # Sanoq har safar noldan boshlansa, "ping" hech qachon ketmas va ilova ulanishni uzar edi
        assert await asyncio.wait_for(anext(stream), timeout=1) == ": ping\n\n"
        assert await asyncio.wait_for(anext(stream), timeout=1) == ": ping\n\n"
    finally:
        task.cancel()
        await stream.aclose()


# ---------- Haqiqiy HTTP orqali, boshidan oxirigacha ----------


@asynccontextmanager
async def running_server(cfg, engine, notifier):
    """API'ni haqiqiy portda ishga tushiradi: oqim (stream) faqat shunday tekshiriladi."""
    app = create_app(cfg, engine=engine, notifier=notifier)
    config = uvicorn.Config(
        app, host="127.0.0.1", port=0, log_level="warning", timeout_graceful_shutdown=1
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    try:
        for _ in range(200):
            if server.started:
                break
            await asyncio.sleep(0.02)
        assert server.started
        port = server.servers[0].sockets[0].getsockname()[1]
        yield app, f"http://127.0.0.1:{port}/api/v1"
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, timeout=10)


class SseReader:
    def __init__(self, response: httpx.Response):
        self._lines = response.aiter_lines()

    async def next_message(self, timeout: float = 5.0) -> tuple[str, dict]:
        """Keyingi nomli xabar. Bo'sh "ping" satrlari o'tkazib yuboriladi."""

        async def read() -> tuple[str, dict]:
            name, data = None, None
            async for line in self._lines:
                if line.startswith("event: "):
                    name = line[len("event: ") :]
                elif line.startswith("data: "):
                    data = json.loads(line[len("data: ") :])
                elif line == "" and name is not None:
                    return name, data
            raise AssertionError("Oqim kutilmaganda yopildi")

        return await asyncio.wait_for(read(), timeout=timeout)


async def wait_ready(reader: SseReader) -> None:
    """Ulanish tayyor bo'lishini kutadi. PostgreSQL'da kanal tinglovchisi ishga tushganda
    bitta `resync` ham kelishi mumkin: sinov undan keyingi xabarlarni tekshiradi."""
    assert (await reader.next_message())[0] == "ready"
    if IS_POSTGRES:
        await asyncio.sleep(0.5)


async def next_named(reader: SseReader) -> tuple[str, dict]:
    while True:
        name, data = await reader.next_message()
        if name != "resync":
            return name, data


async def test_app_receives_menu_change_without_asking(cfg, engine, notifier, seed):
    async with running_server(cfg, engine, notifier) as (app, base):
        async with httpx.AsyncClient(base_url=base, timeout=10) as http:
            async with http.stream("GET", "/events") as response:
                assert response.status_code == 200
                assert response.headers["content-type"].startswith("text/event-stream")
                reader = SseReader(response)
                await wait_ready(reader)

                # Admin botda "tugadi" deb belgiladi (bot ham xuddi shunday sessiya orqali yozadi)
                factory = make_session_factory(engine) if IS_POSTGRES else app.state.session_factory
                async with factory() as session:
                    product = await session.get(Product, seed["osh"])
                    product.is_available = False
                    await session.commit()

                assert await next_named(reader) == ("menu", {})
                menu = (await http.get("/menu")).json()
                osh = next(p for p in menu["products"] if p["id"] == seed["osh"])
                assert osh["is_available"] is False


async def test_order_status_reaches_only_the_owner(cfg, engine, notifier, seed):
    async with running_server(cfg, engine, notifier) as (app, base):
        async with httpx.AsyncClient(base_url=base, timeout=10) as http:
            owner = await register(http, phone="90 111 11 11")
            stranger = await register(http, phone="90 222 22 22")
            created = await http.post(
                "/orders",
                headers=owner,
                json={"items": [{"product_id": seed["osh"], "quantity": 1}], **NEAR},
            )
            assert created.status_code == 201, created.text
            order_id = created.json()["id"]

            async with (
                http.stream("GET", "/events", headers=owner) as owner_response,
                http.stream("GET", "/events", headers=stranger) as stranger_response,
                http.stream("GET", "/events") as anonymous_response,
            ):
                owner_reader = SseReader(owner_response)
                stranger_reader = SseReader(stranger_response)
                anonymous_reader = SseReader(anonymous_response)
                for reader in (owner_reader, stranger_reader, anonymous_reader):
                    await wait_ready(reader)

                factory = make_session_factory(engine) if IS_POSTGRES else app.state.session_factory
                async with factory() as session:
                    await order_service.set_status_by_staff(
                        session, order_id, OrderStatus.ACCEPTED, "Vali"
                    )
                    # Keyin menyu o'zgaradi: begonalar aynan shuni birinchi bo'lib ko'rishi kerak
                    product = await session.get(Product, seed["lagmon"])
                    product.is_available = False
                    await session.commit()

                assert await next_named(owner_reader) == (
                    "order",
                    {"order_id": order_id, "status": "accepted", "status_label": "Tayyorlanmoqda"},
                )
                assert await next_named(owner_reader) == ("menu", {})
                assert await next_named(stranger_reader) == ("menu", {})
                assert await next_named(anonymous_reader) == ("menu", {})


async def test_stream_with_unknown_token_still_gets_public_events(cfg, engine, notifier, seed):
    async with running_server(cfg, engine, notifier) as (_, base):
        async with httpx.AsyncClient(base_url=base, timeout=10) as http:
            headers = {"Authorization": "Bearer eskirgan-kalit"}
            async with http.stream("GET", "/events", headers=headers) as response:
                assert response.status_code == 200
                assert (await SseReader(response).next_message())[0] == "ready"


async def wait_for_subscribers(hub: EventHub, count: int) -> None:
    for _ in range(200):
        if hub.subscriber_count == count:
            return
        await asyncio.sleep(0.02)
    raise AssertionError(f"{hub.subscriber_count} ta ulanish ochiq, {count} ta kutilgan edi")


async def test_closed_connection_frees_its_place(cfg, engine, notifier, seed):
    async with running_server(cfg, engine, notifier) as (app, base):
        hub: EventHub = app.state.events
        async with httpx.AsyncClient(base_url=base, timeout=10) as http:
            async with http.stream("GET", "/events") as response:
                assert (await SseReader(response).next_message())[0] == "ready"
                assert hub.subscriber_count == 1
            await wait_for_subscribers(hub, 0)


async def test_too_many_anonymous_streams_from_one_address_are_refused(
    cfg, engine, notifier, seed
):
    async with running_server(cfg, engine, notifier) as (app, base):
        hub: EventHub = app.state.events
        hub._max_per_address = 2
        async with httpx.AsyncClient(base_url=base, timeout=10) as http:
            async with (
                http.stream("GET", "/events") as first,
                http.stream("GET", "/events") as second,
            ):
                assert first.status_code == second.status_code == 200
                refused = await http.get("/events")
                assert refused.status_code == 429
                assert refused.json()["error"]["code"] == "too_many_streams"
                assert hub.subscriber_count == 2  # rad etilgan so'rov joy egallamadi

                # Kirgan mijoz manzil hisobiga kirmaydi
                owner = await register(http, phone="90 111 11 11")
                async with http.stream("GET", "/events", headers=owner) as third:
                    assert third.status_code == 200
            await wait_for_subscribers(hub, 0)


async def test_stop_signal_ends_open_streams_at_once(cfg, engine, notifier, seed):
    """`docker stop`: ochiq ulanishlar darhol yopiladi, server kutib o'tirmaydi."""
    seen: list[int] = []
    # uvicorn to'xtagach signalni avvalgi ishlovchiga qayta yuboradi: sinov jarayonini
    # o'ldirmasligi uchun avval zararsiz ishlovchi o'rnatiladi
    original = signal.signal(signal.SIGTERM, lambda signum, frame: seen.append(signum))
    try:
        app = create_app(cfg, engine=engine, notifier=notifier)
        config = uvicorn.Config(
            app, host="127.0.0.1", port=0, log_level="warning", timeout_graceful_shutdown=30
        )
        server = uvicorn.Server(config)
        task = asyncio.create_task(server.serve())
        for _ in range(200):
            if server.started:
                break
            await asyncio.sleep(0.02)
        assert server.started
        port = server.servers[0].sockets[0].getsockname()[1]
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}/api/v1") as http:
            async with http.stream("GET", "/events") as response:
                lines = response.aiter_lines()
                assert await asyncio.wait_for(anext(lines), timeout=5) == "event: ready"
                signal.raise_signal(signal.SIGTERM)

                async def read_to_end() -> None:
                    async for _ in lines:
                        pass

                await asyncio.wait_for(read_to_end(), timeout=3)  # oqim toza yopildi
        await asyncio.wait_for(task, timeout=3)  # 30 soniyalik kutish kerak bo'lmadi
        assert seen == [signal.SIGTERM]
    finally:
        signal.signal(signal.SIGTERM, original)
