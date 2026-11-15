import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api import customers, menu, orders
from app.api.deps import SessionDep
from app.config import Settings, get_settings
from app.db import make_engine, make_session_factory
from app.errors import install_error_handlers
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

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        if engine is None:  # o'zimiz yaratgan bo'lsak, o'zimiz yopamiz
            await db_engine.dispose()

    app = FastAPI(
        title="Amora API",
        version="0.1.0",
        description="Amora kafe yetkazib berish xizmati uchun mobil ilova API'si.",
        lifespan=lifespan,
    )
    app.state.settings = cfg
    app.state.engine = db_engine
    app.state.session_factory = make_session_factory(db_engine)
    app.state.notifier = notifier or NullNotifier()
    app.state.register_limiter = RateLimiter(cfg.register_limit_per_hour)

    install_error_handlers(app)

    api = APIRouter(prefix=API_PREFIX)

    @api.get("/health", tags=["xizmat"], summary="Server ishlayaptimi")
    async def health(session: SessionDep) -> dict:
        await session.execute(text("SELECT 1"))
        return {"status": "ok"}

    api.include_router(menu.router)
    api.include_router(customers.router)
    api.include_router(orders.router)
    app.include_router(api)

    cfg.media_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=cfg.media_dir), name="media")

    return app


def app_factory() -> FastAPI:
    """uvicorn uchun: `uvicorn app.main:app_factory --factory`."""
    return create_app()
