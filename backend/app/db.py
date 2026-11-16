from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator


class Base(DeclarativeBase):
    pass


class UTCDateTime(TypeDecorator):
    """Vaqt har doim UTC'da saqlanadi va vaqt mintaqasi bilan qaytariladi.

    SQLite vaqt mintaqasini saqlamaydi, shuning uchun o'qishda UTC deb belgilaymiz.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Vaqt mintaqasiz datetime saqlab bo'lmaydi")
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def make_engine(url: str) -> AsyncEngine:
    if url.startswith("sqlite"):
        # Faqat testlar uchun: bitta ulanish, xotiradagi baza
        return create_async_engine(
            url, poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
    return create_async_engine(url, pool_pre_ping=True)


def make_session_factory(engine: AsyncEngine, hub=None) -> async_sessionmaker[AsyncSession]:
    """Sessiyalar fabrikasi. Har bir yozuv jonli yangilanish hodisasiga aylanadi (`app/events.py`).

    `hub` (`EventHub`) faqat API jarayonida beriladi; bot hodisalarni baza orqali jo'natadi.
    """
    from app.events import attach_event_hooks  # modellar shu fayldan `Base`ni oladi

    sync_maker = sessionmaker(expire_on_commit=False)
    attach_event_hooks(sync_maker, hub)
    return async_sessionmaker(engine, expire_on_commit=False, sync_session_class=sync_maker)
