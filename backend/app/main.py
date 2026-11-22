import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api import customers, events, menu, orders
from app.api.deps import SessionDep
from app.config import Settings, get_settings
from app.db import make_engine, make_session_factory
from app.errors import install_error_handlers
from app.events import EventHub, close_on_stop_signal, listen_forever
from app.notifier import Notifier, NullNotifier
from app.security import RateLimiter

API_PREFIX = "/api/v1"


def create_app(
    settings: Settings | None = None,
    engine: AsyncEngine | None = None,
    notifier: Notifier | None = None,
) -> FastAPI:
    cfg = settings or get_settings()
    logging.basicConfig(
        level=logging.DEBUG if cfg.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    db_engine = engine or make_engine(cfg.database_url)
    hub = EventHub()
    session_factory = make_session_factory(db_engine, hub)

    telegram_notifier = None
    if notifier is None:
        if cfg.bot_token and cfg.orders_chat_id is not None:
            from app.telegram.publisher import TelegramNotifier

            telegram_notifier = TelegramNotifier.from_settings(cfg, session_factory)
            notifier = telegram_notifier
        else:
            logging.getLogger(__name__).warning(
                "Telegram sozlanmagan (AMORA_BOT_TOKEN, AMORA_ORDERS_CHAT_ID): "
                "buyurtmalar guruhga yuborilmaydi"
            )
            notifier = NullNotifier()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # Bot boshqa jarayonda ishlaydi: uning o'zgarishlari baza kanali orqali yetib keladi
        listener = None
        if db_engine.dialect.name == "postgresql":
            listener = asyncio.create_task(listen_forever(cfg.database_url, hub))
        with close_on_stop_signal(hub):
            yield
        if listener is not None:
            listener.cancel()
            with suppress(asyncio.CancelledError):
                await listener
        if telegram_notifier is not None:
            await telegram_notifier.close()
        if engine is None:  # o'zimiz yaratgan bo'lsak, o'zimiz yopamiz
            await db_engine.dispose()

    app = FastAPI(
        title="Amora API",
        version="0.1.0",
        description="Amora kafe yetkazib berish xizmati uchun mobil ilova API'si.",
        lifespan=lifespan,
        # Interaktiv hujjat faqat sinov rejimida ochiq (AMORA_DEBUG=true)
        docs_url="/docs" if cfg.debug else None,
        redoc_url=None,
        openapi_url="/openapi.json" if cfg.debug else None,
    )
    app.state.settings = cfg
    app.state.engine = db_engine
    app.state.session_factory = session_factory
    app.state.events = hub
    app.state.notifier = notifier
    app.state.register_limiter = RateLimiter(cfg.register_limit_per_hour)
    app.state.verify_limiter = RateLimiter(cfg.verify_limit_per_hour)
    app.state.bot_username = None

    install_error_handlers(app)

    api = APIRouter(prefix=API_PREFIX)

    @api.get("/health", tags=["xizmat"], summary="Server ishlayaptimi")
    async def health(session: SessionDep) -> dict:
        await session.execute(text("SELECT 1"))
        return {"status": "ok"}

    api.include_router(menu.router)
    api.include_router(customers.router)
    api.include_router(orders.router)
    api.include_router(events.router)
    app.include_router(api)

    cfg.media_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=cfg.media_dir), name="media")

    return app


def app_factory() -> FastAPI:
    """uvicorn uchun: `uvicorn app.main:app_factory --factory`."""
    return create_app()
