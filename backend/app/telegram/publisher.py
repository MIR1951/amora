"""Buyurtmalarni Telegram guruhga yuborish va xabarni yangilab turish."""

import asyncio
import logging
from datetime import timedelta

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.db import utcnow
from app.models import Order, OrderStatus
from app.services.orders import get_order
from app.telegram.keyboards import order_keyboard
from app.telegram.texts import cancelled_notice, order_text

log = logging.getLogger(__name__)

SessionFactory = async_sessionmaker[AsyncSession]


# Telegram javob bermasa 60 emas, 20 soniyada voz kechamiz va qayta urinamiz
REQUEST_TIMEOUT = 20


def make_bot(token: str) -> Bot:
    return Bot(
        token,
        session=AiohttpSession(timeout=REQUEST_TIMEOUT),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )


async def publish_order(
    session_factory: SessionFactory, bot: Bot, chat_id: int, order_id: int, tz_name: str
) -> bool:
    """Yangi buyurtmani guruhga yuboradi. Yuborilgan bo'lsa True.

    Buyurtma qatori qulflanadi: API va botning zaxira tekshiruvi bir vaqtda
    ishga tushsa ham xabar ikki marta yuborilmaydi.
    """
    async with session_factory() as session:
        order = await get_order(session, order_id, for_update=True)
        if order is None or order.tg_message_id is not None:
            return False
        if order.status_enum != OrderStatus.NEW:
            return False  # guruhga yetib bormasidan mijoz bekor qilgan
        message = await bot.send_message(
            chat_id,
            order_text(order, tz_name),
            reply_markup=order_keyboard(order),
            request_timeout=15,
        )
        order.tg_chat_id = chat_id
        order.tg_message_id = message.message_id
        await session.commit()
        return True


async def refresh_order_message(bot: Bot, order: Order, tz_name: str) -> None:
    """Guruhdagi xabarni buyurtmaning hozirgi holatiga moslaydi."""
    if order.tg_chat_id is None or order.tg_message_id is None:
        return
    try:
        await bot.edit_message_text(
            order_text(order, tz_name),
            chat_id=order.tg_chat_id,
            message_id=order.tg_message_id,
            reply_markup=order_keyboard(order),
        )
    except TelegramBadRequest as error:
        # Ikki xodim ketma-ket bosganda matn o'zgarmagan bo'lishi mumkin: bu xato emas
        if "message is not modified" not in str(error):
            raise


async def sweep_unsent(
    session_factory: SessionFactory, bot: Bot, chat_id: int, tz_name: str, min_age: float = 15.0
) -> int:
    """Guruhga yetib bormagan yangi buyurtmalarni qayta yuboradi (Telegram uzilib qolgan holat)."""
    async with session_factory() as session:
        rows = await session.scalars(
            select(Order.id)
            .where(
                Order.status == OrderStatus.NEW.value,
                Order.tg_message_id.is_(None),
                Order.created_at <= utcnow() - timedelta(seconds=min_age),
            )
            .order_by(Order.id)
            .limit(20)
        )
        order_ids = list(rows)
    sent = 0
    for order_id in order_ids:
        try:
            if await publish_order(session_factory, bot, chat_id, order_id, tz_name):
                sent += 1
        except Exception:  # noqa: BLE001
            log.exception("Buyurtma #%s guruhga yuborilmadi", order_id)
            break  # Telegram ishlamayapti: keyingi tekshiruvda yana urinamiz
    return sent


async def sweep_forever(
    session_factory: SessionFactory, bot: Bot, chat_id: int, tz_name: str, interval: float = 20.0
) -> None:
    while True:
        try:
            sent = await sweep_unsent(session_factory, bot, chat_id, tz_name)
            if sent:
                log.warning("Kechikkan %s ta buyurtma guruhga yuborildi", sent)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("Zaxira tekshiruvida xato")
        await asyncio.sleep(interval)


class TelegramNotifier:
    """API tomonidan chaqiriladi: yangi buyurtma va mijoz bekor qilgani haqida guruhga xabar."""

    def __init__(self, bot: Bot, chat_id: int, session_factory: SessionFactory, tz_name: str):
        self.bot = bot
        self.chat_id = chat_id
        self.session_factory = session_factory
        self.tz_name = tz_name

    @classmethod
    def from_settings(cls, cfg: Settings, session_factory: SessionFactory) -> "TelegramNotifier":
        return cls(make_bot(cfg.bot_token), cfg.orders_chat_id, session_factory, cfg.timezone)

    async def order_created(self, order_id: int) -> None:
        await publish_order(self.session_factory, self.bot, self.chat_id, order_id, self.tz_name)

    async def order_cancelled(self, order_id: int) -> None:
        async with self.session_factory() as session:
            order = await get_order(session, order_id)
        if order is None or order.tg_message_id is None:
            return  # guruhga hali yuborilmagan edi: xodimlarni bezovta qilmaymiz
        await refresh_order_message(self.bot, order, self.tz_name)
        # Xabarni tahrirlash ovozsiz bo'ladi, shuning uchun alohida javob ham yuboramiz
        await self.bot.send_message(
            order.tg_chat_id,
            cancelled_notice(order),
            reply_to_message_id=order.tg_message_id,
            allow_sending_without_reply=True,
        )

    async def close(self) -> None:
        await self.bot.session.close()
