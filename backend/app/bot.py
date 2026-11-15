"""Telegram botni ishga tushirish: `python -m app.bot`."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from app.config import Settings, get_settings
from app.db import make_engine, make_session_factory
from app.telegram import admin_router, common_router, orders_router
from app.telegram.publisher import SessionFactory, make_bot, sweep_forever

log = logging.getLogger(__name__)


def build_dispatcher(cfg: Settings, session_factory: SessionFactory) -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    # Bu qiymatlar handler'larga nomi bo'yicha uzatiladi
    dispatcher["cfg"] = cfg
    dispatcher["session_factory"] = session_factory
    dispatcher.include_router(orders_router.router)
    # common admin'dan oldin turadi: aks holda adminning /id buyrug'i bosh menyuga tushib qoladi
    dispatcher.include_router(common_router.router)
    dispatcher.include_router(admin_router.router)
    return dispatcher


async def set_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Boshqaruv menyusi"),
            BotCommand(command="help", description="Buyruqlar ro'yxati"),
            BotCommand(command="id", description="Chat va foydalanuvchi ID"),
        ]
    )


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
    dispatcher = build_dispatcher(cfg, session_factory)

    if not cfg.admin_id_set:
        log.warning("AMORA_ADMIN_IDS bo'sh: admin bo'limiga hech kim kira olmaydi")

    sweeper = None
    if cfg.orders_chat_id is not None:
        sweeper = asyncio.create_task(
            sweep_forever(session_factory, bot, cfg.orders_chat_id, cfg.timezone)
        )
    else:
        log.warning("AMORA_ORDERS_CHAT_ID yozilmagan: buyurtmalar guruhga yuborilmaydi")

    try:
        try:
            await set_commands(bot)
        except Exception:  # noqa: BLE001
            # Buyruqlar ro'yxati shunchaki qulaylik: usiz ham bot ishlayveradi
            log.warning("Buyruqlar ro'yxatini o'rnatib bo'lmadi", exc_info=True)
        await dispatcher.start_polling(
            bot, allowed_updates=dispatcher.resolve_used_update_types()
        )
    finally:
        if sweeper is not None:
            sweeper.cancel()
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
