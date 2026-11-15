import os
from datetime import time

import httpx
import pytest

from app.config import Settings
from app.db import Base, make_engine, make_session_factory
from app.main import create_app
from app.models import Category, Product, ShopSettings

# Standart holatda xotiradagi SQLite. Haqiqiy PostgreSQL'da tekshirish uchun:
#   TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost/amora_test pytest
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")


class RecordingNotifier:
    def __init__(self):
        self.created: list[int] = []
        self.cancelled: list[int] = []

    async def order_created(self, order_id: int) -> None:
        self.created.append(order_id)

    async def order_cancelled(self, order_id: int) -> None:
        self.cancelled.append(order_id)


@pytest.fixture
def cfg(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=TEST_DATABASE_URL,
        public_base_url="https://api.test",
        media_dir=tmp_path / "media",
        max_active_orders=2,
        register_limit_per_hour=1000,
    )


@pytest.fixture
async def engine():
    engine = make_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(engine):
    return make_session_factory(engine)


@pytest.fixture
async def seed(session_factory) -> dict:
    """Kecha-kunduz ochiq kafe, 3 ta taom: ikkitasi bor, bittasi tugagan."""
    async with session_factory() as session:
        shop = ShopSettings(
            id=1,
            open_time=time(0, 0),
            close_time=time(0, 0),
            delivery_fee=10_000,
            cafe_latitude=39.6542,
            cafe_longitude=66.9597,
        )
        category = Category(name="Asosiy taomlar")
        osh = Product(name="Osh", price=35_000, category=category, image_path="products/osh.jpg")
        lagmon = Product(name="Lag'mon", price=30_000, category=category, sort_order=1)
        somsa = Product(name="Somsa", price=8_000, is_available=False, sort_order=2)
        deleted = Product(name="Eski taom", price=1_000, is_deleted=True)
        session.add_all([shop, category, osh, lagmon, somsa, deleted])
        await session.commit()
        return {
            "osh": osh.id,
            "lagmon": lagmon.id,
            "somsa": somsa.id,
            "deleted": deleted.id,
            "category": category.id,
        }


@pytest.fixture
def notifier() -> RecordingNotifier:
    return RecordingNotifier()


@pytest.fixture
async def client(cfg, engine, notifier):
    app = create_app(cfg, engine=engine, notifier=notifier)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        yield client


async def register(client: httpx.AsyncClient, name="Ali", phone="90 123 45 67") -> dict:
    response = await client.post("/auth/register", json={"name": name, "phone": phone})
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.fixture
async def auth(client) -> dict:
    return await register(client)


# Kafedan taxminan 1 km uzoqlikdagi manzil
NEAR = {"latitude": 39.6600, "longitude": 66.9680}
