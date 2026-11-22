"""Buyurtmalarni Telegram guruhga yuborish va xabarni yangilab turish."""

import asyncio
import logging
import time
from collections.abc import Iterable
from datetime import timedelta

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramMigrateToChat,
    TelegramNotFound,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.db import utcnow
from app.models import Order, OrderStatus
from app.services.orders import get_order
from app.telegram.keyboards import order_keyboard, revoke_sign_in_keyboard
from app.telegram.texts import (
    VERIFY_SIGNED_IN,
    cancelled_notice,
    chat_migrated_alert,
    order_text,
    unsent_alert,
)

log = logging.getLogger(__name__)

SessionFactory = async_sessionmaker[AsyncSession]


# Telegram javob bermasa 60 emas, 20 soniyada voz kechamiz va qayta urinamiz
REQUEST_TIMEOUT = 20

# Buyurtma shuncha vaqt guruhga yetib bormasa, egalarga shaxsiy xabar yuboriladi
UNSENT_ALERT_AFTER = timedelta(minutes=2)
# ...va muammo davom etsa, shuncha soniyada bir marta takrorlanadi
UNSENT_ALERT_EVERY = 30 * 60.0

# Guruh superguruhga aylantirilsa, Telegram uning ID'sini almashtiradi: eski ID -> yangi ID.
# Sozlamadagi ID yangilanguncha (qayta ishga tushirishgacha) shu jadval ishlatiladi
_migrated_chats: dict[int, int] = {}


def current_chat_id(chat_id: int) -> int:
    """Sozlamadagi guruh ID'si, guruh ko'chgan bo'lsa yangisi."""
    return _migrated_chats.get(chat_id, chat_id)


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
    chat_id = current_chat_id(chat_id)
    async with session_factory() as session:
        order = await get_order(session, order_id, for_update=True)
        if order is None or order.tg_message_id is not None:
            return False
        if order.status_enum != OrderStatus.NEW:
            return False  # guruhga yetib bormasidan mijoz bekor qilgan
        text = order_text(order, tz_name)
        markup = order_keyboard(order)
        try:
            message = await bot.send_message(
                chat_id, text, reply_markup=markup, request_timeout=15
            )
        except TelegramMigrateToChat as error:
            # Guruh superguruhga aylantirilgan: yangi ID bilan shu zahoti qayta yuboramiz
            new_chat_id = error.migrate_to_chat_id
            log.error(
                "Buyurtmalar guruhining ID'si o'zgargan: %s -> %s. AMORA_ORDERS_CHAT_ID ni yangilang",
                chat_id,
                new_chat_id,
            )
            _migrated_chats[chat_id] = new_chat_id
            for old, new in list(_migrated_chats.items()):
                if new == chat_id:
                    _migrated_chats[old] = new_chat_id
            chat_id = new_chat_id
            message = await bot.send_message(
                chat_id, text, reply_markup=markup, request_timeout=15
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


# Qayta urinish foyda bermaydigan xatolar: boshqa buyurtmalarni to'sib qo'ymasligi kerak
_PERMANENT_ERRORS = (TelegramBadRequest, TelegramForbiddenError, TelegramNotFound)


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
        except _PERMANENT_ERRORS:
            # Shu buyurtmaning o'zida muammo (yoki bot guruhga yoza olmaydi): keyingisiga o'tamiz
            log.exception("Buyurtma #%s guruhga yuborilmadi", order_id)
        except Exception:  # noqa: BLE001
            log.exception("Buyurtma #%s guruhga yuborilmadi", order_id)
            break  # Telegram ishlamayapti: keyingi tekshiruvda yana urinamiz
    return sent


async def unsent_orders(session_factory: SessionFactory) -> tuple[int, int | None, int]:
    """Uzoq vaqt guruhga yetib bormagan buyurtmalar: (soni, eng eskisining raqami, necha daqiqa)."""
    now = utcnow()
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(Order.id, Order.created_at)
                .where(
                    Order.status == OrderStatus.NEW.value,
                    Order.tg_message_id.is_(None),
                    Order.created_at <= now - UNSENT_ALERT_AFTER,
                )
                .order_by(Order.id)
            )
        ).all()
    if not rows:
        return 0, None, 0
    oldest_id, created_at = rows[0]
    return len(rows), oldest_id, int((now - created_at).total_seconds() // 60)


async def tell_owners(bot: Bot, owner_ids: Iterable[int], text: str) -> int:
    """Egalarga shaxsiy xabar. Nechtasiga yetib borganini qaytaradi."""
    delivered = 0
    for owner_id in owner_ids:
        try:
            await bot.send_message(owner_id, text)
            delivered += 1
        except Exception:  # noqa: BLE001
            log.warning("Egaga (%s) xabar yuborilmadi", owner_id, exc_info=True)
    return delivered


class UnsentWatch:
    """Guruhga yuborish to'xtab qolganini egalarga aytadi (bot guruhdan chiqarilgan, guruh
    o'chirilgan, token bekor qilingan). Aks holda mijozlar buyurtma beraveradi, xodimlar esa
    hech narsa ko'rmaydi va buni faqat server jurnalidan bilish mumkin bo'lar edi."""

    def __init__(self, owner_ids: Iterable[int], chat_id: int):
        self.owner_ids = sorted(owner_ids)
        self.chat_id = chat_id
        self._alerted_at: float | None = None
        self._told_chat: int | None = None

    async def check(self, session_factory: SessionFactory, bot: Bot) -> bool:
        """Xabar yuborilgan bo'lsa True."""
        if not self.owner_ids:
            return False
        told = False
        migrated = current_chat_id(self.chat_id)
        if migrated != self.chat_id and migrated != self._told_chat:
            if await tell_owners(bot, self.owner_ids, chat_migrated_alert(migrated)):
                self._told_chat = migrated
                told = True
        count, oldest_id, minutes = await unsent_orders(session_factory)
        if not count:
            self._alerted_at = None
            return told
        now = time.monotonic()
        if self._alerted_at is not None and now - self._alerted_at < UNSENT_ALERT_EVERY:
            return told
        reason = "Telegram guruhga yuborishni rad etmoqda yoki javob bermayapti"
        if await tell_owners(bot, self.owner_ids, unsent_alert(count, oldest_id, minutes, reason)):
            self._alerted_at = now
            told = True
        return told


async def sweep_forever(
    session_factory: SessionFactory,
    bot: Bot,
    chat_id: int,
    tz_name: str,
    interval: float = 20.0,
    owner_ids: Iterable[int] = (),
) -> None:
    watch = UnsentWatch(owner_ids, chat_id)
    while True:
        try:
            sent = await sweep_unsent(session_factory, bot, chat_id, tz_name)
            if sent:
                log.warning("Kechikkan %s ta buyurtma guruhga yuborildi", sent)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("Zaxira tekshiruvida xato")
        try:
            await watch.check(session_factory, bot)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("Yetib bormagan buyurtmalarni tekshirishda xato")
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

    async def signed_in(self, telegram_user_id: int) -> None:
        await self.bot.send_message(
            telegram_user_id, VERIFY_SIGNED_IN, reply_markup=revoke_sign_in_keyboard()
        )

    async def close(self) -> None:
        await self.bot.session.close()
