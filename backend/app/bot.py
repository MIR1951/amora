"""Telegram botni ishga tushirish: `python -m app.bot`."""

import asyncio
import logging
import signal
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramNetworkError, TelegramServerError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from app.config import Settings, get_settings
from app.db import make_engine, make_session_factory
from app.telegram import (
    admin_router,
    common_router,
    insights_router,
    orders_router,
    promo_router,
    team_router,
)
from app.services.push import PushSender
from app.telegram.publisher import SessionFactory, make_bot, sweep_forever
from app.telegram.watch import watch_forever

log = logging.getLogger(__name__)


def build_dispatcher(
    cfg: Settings, session_factory: SessionFactory, push: PushSender | None = None
) -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    # Bu qiymatlar handler'larga nomi bo'yicha uzatiladi
    dispatcher["cfg"] = cfg
    dispatcher["session_factory"] = session_factory
    dispatcher["push"] = push or PushSender(None)
    dispatcher.include_router(orders_router.router)
    # Taklif havolasi /start bilan keladi: u boshqa /start'lardan oldin tekshiriladi
    dispatcher.include_router(team_router.invite_router)
    # common admin'dan oldin turadi: aks holda adminning /id buyrug'i bosh menyuga tushib qoladi
    dispatcher.include_router(common_router.router)
    dispatcher.include_router(insights_router.router)
    dispatcher.include_router(team_router.router)
    dispatcher.include_router(promo_router.router)
    # admin oxirida: unda tushunarsiz xabarlarni ushlaydigan handler bor
    dispatcher.include_router(admin_router.router)
    return dispatcher


COMMANDS = [
    BotCommand(command="start", description="Boshqaruv menyusi"),
    BotCommand(command="mijoz", description="Mijoz kartasi: /mijoz 901234567"),
    BotCommand(command="help", description="Buyruqlar ro'yxati"),
    BotCommand(command="id", description="Chat va foydalanuvchi ID"),
]

# Telegram'ga ulanib bo'lmaganda necha soniyadan keyin qayta urinish
RETRY_DELAYS = (2, 5, 10, 20, 30)


async def set_commands_in_background(bot: Bot) -> None:
    """Buyruqlar ro'yxati shunchaki qulaylik: bot ishga tushishini kutdirmasligi kerak."""
    for delay in (0, 30, 120, 600):
        await asyncio.sleep(delay)
        try:
            await bot.set_my_commands(COMMANDS)
            return
        except Exception as error:  # noqa: BLE001
            log.warning("Buyruqlar ro'yxati o'rnatilmadi (%s), keyinroq qayta urinamiz", error)


async def pause(stop: asyncio.Event, seconds: float) -> None:
    """`seconds` soniya kutadi, lekin to'xtatish so'ralsa darhol qaytadi."""
    with suppress(TimeoutError):
        await asyncio.wait_for(stop.wait(), timeout=seconds)


async def poll_forever(dispatcher: Dispatcher, bot: Bot, stop: asyncio.Event) -> None:
    """Xabarlarni tinglaydi. Telegram vaqtincha javob bermasa, jarayon yiqilmaydi, qayta urinadi."""
    attempt = 0
    while not stop.is_set():
        try:
            await dispatcher.start_polling(
                bot,
                allowed_updates=dispatcher.resolve_used_update_types(),
                handle_signals=False,  # to'xtatish signalini o'zimiz boshqaramiz (main ichida)
            )
            return
        except (TelegramNetworkError, TelegramServerError) as error:
            delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
            attempt += 1
            log.warning(
                "Telegram'ga ulanib bo'lmadi (%s). %s soniyadan keyin qayta urinamiz", error, delay
            )
            await pause(stop, delay)


def install_stop_handlers(dispatcher: Dispatcher, stop: asyncio.Event) -> None:
    """SIGTERM/SIGINT kelganda (masalan `docker compose stop`) bot toza to'xtaydi,
    qayta ulanishni kutayotgan paytda ham."""

    async def stop_polling() -> None:
        with suppress(RuntimeError):  # polling hali boshlanmagan bo'lishi mumkin
            await dispatcher.stop_polling()

    def on_signal() -> None:
        stop.set()
        asyncio.ensure_future(stop_polling())

    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        with suppress(NotImplementedError):  # Windows'da bunday imkoniyat yo'q
            loop.add_signal_handler(signum, on_signal)


async def main() -> None:
    cfg = get_settings()
    logging.basicConfig(
        level=logging.DEBUG if cfg.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if not cfg.bot_token:
        # Xato bilan chiqsak, Docker botni to'xtovsiz qayta ishga tushiraveradi.
        # Shuning uchun token yozilguncha jim kutib turamiz.
        log.warning(
            "AMORA_BOT_TOKEN yozilmagan: bot ishlamayapti. Tokenni @BotFather'dan olib "
            ".env fayliga yozing va `docker compose up -d` ni qayta ishga tushiring."
        )
        await asyncio.Event().wait()

    engine = make_engine(cfg.database_url)
    session_factory = make_session_factory(engine)
    bot = make_bot(cfg.bot_token)
    push = PushSender(cfg.firebase_credentials)
    dispatcher = build_dispatcher(cfg, session_factory, push)

    if not cfg.admin_id_set:
        log.warning("AMORA_ADMIN_IDS bo'sh: admin bo'limiga hech kim kira olmaydi")

    sweeper = None
    if cfg.orders_chat_id is not None:
        sweeper = asyncio.create_task(
            sweep_forever(session_factory, bot, cfg.orders_chat_id, cfg.timezone)
        )
    else:
        log.warning("AMORA_ORDERS_CHAT_ID yozilmagan: buyurtmalar guruhga yuborilmaydi")

    # Kechikkan buyurtmalar haqida eslatma va kunlik hisobot
    watcher = asyncio.create_task(watch_forever(session_factory, bot, cfg))

    stop = asyncio.Event()
    install_stop_handlers(dispatcher, stop)
    commands_task = asyncio.create_task(set_commands_in_background(bot))
    try:
        await poll_forever(dispatcher, bot, stop)
    finally:
        commands_task.cancel()
        watcher.cancel()
        if sweeper is not None:
            sweeper.cancel()
        await bot.session.close()
        await push.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
