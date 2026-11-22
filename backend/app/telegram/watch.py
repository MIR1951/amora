"""Bot fonda kuzatib turadigan narsalar: kechikkan buyurtmalar va kunlik hisobot."""

import asyncio
import logging
import time
from contextlib import suppress
from datetime import datetime, timedelta
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramMigrateToChat,
    TelegramNotFound,
)
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.db import utcnow
from app.models import (
    ACTIVE_STATUSES,
    Order,
    OrderStatus,
    PhoneVerification,
    ShopSettings,
    Staff,
    StaffInvite,
    StaffRole,
)
from app.services.reports import build_report, business_day
from app.services.shop import SHOP_ID, get_shop
from app.telegram.publisher import SessionFactory, current_chat_id
from app.telegram.texts import delay_alert_text, report_text

log = logging.getLogger(__name__)

# Kechikish shu holatlarda kuzatiladi: qabul qilinmagan va yo'lda
WATCHED = (OrderStatus.NEW.value, OrderStatus.DELIVERING.value)
# Server uzoq o'chiq turgan bo'lsa, eskirgan hisobotni yubormaymiz
DAILY_REPORT_GRACE = timedelta(hours=6)
# Yopilish vaqtida hali yo'lda bo'lgan buyurtmalar yetkazilishini shuncha kutamiz
DAILY_REPORT_WAIT = timedelta(minutes=90)


def _waiting_since(order: Order) -> datetime:
    """Buyurtma hozirgi holatiga qachon o'tgan."""
    for event in reversed(order.history):
        if event.status == order.status:
            return event.created_at
    return order.created_at


async def check_delays(session_factory: SessionFactory, bot: Bot, now: datetime | None = None) -> int:
    """Uzoq kutib qolgan buyurtmalar haqida guruhga eslatma yuboradi. Nechtasi yuborilganini qaytaradi."""
    now = now or utcnow()
    async with session_factory() as session:
        shop = await get_shop(session)
        await session.commit()
        limits = {
            OrderStatus.NEW.value: shop.alert_accept_minutes,
            OrderStatus.DELIVERING.value: shop.alert_delivery_minutes,
        }
        if not any(limits.values()):
            return 0
        orders = list(
            await session.scalars(
                select(Order)
                .options(selectinload(Order.history))
                .where(
                    Order.status.in_(WATCHED),
                    Order.tg_message_id.is_not(None),
                    Order.created_at >= now - timedelta(days=2),
                    or_(Order.alerted_status.is_(None), Order.alerted_status != Order.status),
                )
                .order_by(Order.id)
            )
        )

    sent = 0
    for order in orders:
        minutes = limits[order.status]
        waited = now - _waiting_since(order)
        if not minutes or waited < timedelta(minutes=minutes):
            continue
        # Avval "eslatildi" deb belgilaymiz: bot ikki nusxada ishlasa ham eslatma bitta bo'ladi
        async with session_factory() as session:
            claimed = await session.execute(
                update(Order.__table__)
                .where(
                    Order.__table__.c.id == order.id,
                    Order.__table__.c.status == order.status,
                    or_(
                        Order.__table__.c.alerted_status.is_(None),
                        Order.__table__.c.alerted_status != order.status,
                    ),
                )
                .values(alerted_status=order.status)
            )
            await session.commit()
        if claimed.rowcount != 1:
            continue

        async def release_claim(order_id: int = order.id) -> None:
            async with session_factory() as session:  # keyingi tekshiruvda yana urinamiz
                await session.execute(
                    update(Order.__table__)
                    .where(Order.__table__.c.id == order_id)
                    .values(alerted_status=None)
                )
                await session.commit()

        try:
            await bot.send_message(
                order.tg_chat_id,
                delay_alert_text(order, int(waited.total_seconds() // 60)),
                reply_to_message_id=order.tg_message_id,
                allow_sending_without_reply=True,
            )
            sent += 1
        except (TelegramBadRequest, TelegramForbiddenError, TelegramMigrateToChat, TelegramNotFound):
            # Shu buyurtmaning chatiga yozib bo'lmaydi (bot guruhdan chiqarilgan, guruh
            # o'zgargan): qayta urinish foyda bermaydi, boshqa buyurtmalarni to'sib qo'ymasin
            log.warning("Buyurtma #%s haqida eslatma yuborilmadi", order.id, exc_info=True)
        except Exception:  # noqa: BLE001
            # Telegram yoki tarmoq ishlamayapti: belgini qaytaramiz va keyinroq urinamiz
            log.exception("Buyurtma #%s haqida eslatma yuborilmadi", order.id)
            await release_claim()
            break
        except BaseException:
            # Bot to'xtatilmoqda (yangilash): eslatma yo'qolmasin, keyingi ishga tushishda yuboriladi
            await asyncio.shield(release_claim())
            raise
    return sent


async def report_recipients(session_factory: SessionFactory, cfg: Settings, target: str) -> list[int]:
    if target == "group":
        if cfg.orders_chat_id is None:
            return []
        return [current_chat_id(cfg.orders_chat_id)]
    async with session_factory() as session:
        admins = await session.scalars(
            select(Staff.telegram_id).where(Staff.role == StaffRole.ADMIN.value)
        )
        return sorted(cfg.admin_id_set) + [admin for admin in admins if admin not in cfg.admin_id_set]


async def send_daily_report(
    session_factory: SessionFactory, bot: Bot, cfg: Settings, now: datetime | None = None
) -> bool:
    """Ish kuni tugaganda (kafe yopilganda) o'sha kunning hisobotini bir marta yuboradi.

    Yopilish paytida yo'lda bo'lgan buyurtmalar ham tushumga kirishi uchun ular tugashini
    kutadi (ko'pi bilan DAILY_REPORT_WAIT).
    """
    now = now or utcnow()
    table = ShopSettings.__table__
    async with session_factory() as session:
        shop = await get_shop(session)
        await session.commit()
        target = shop.daily_report_to
        if target not in ("group", "admins"):
            return False
        start, end = business_day(shop, cfg.timezone, now)
        if now - end > DAILY_REPORT_GRACE:
            return False
        previous = shop.daily_report_sent_until
        if previous is not None and previous >= end:
            return False
        if previous is not None and previous > start:
            # Ish vaqti hisobot yuborilgandan keyin uzaytirilgan: o'sha buyurtmalar ikki marta
            # sanalmasin, faqat qolgan qismi yuboriladi
            start = previous
        if now - end < DAILY_REPORT_WAIT:
            unfinished = await session.scalar(
                select(func.count())
                .select_from(Order)
                .where(
                    Order.created_at >= start,
                    Order.created_at < end,
                    Order.status.in_(ACTIVE_STATUSES),
                )
            )
            if unfinished:
                return False
        # Ikki nusxa bir vaqtda yubormasligi uchun avval belgilab olamiz
        claimed = await session.execute(
            update(table)
            .where(
                table.c.id == SHOP_ID,
                or_(table.c.daily_report_sent_until.is_(None), table.c.daily_report_sent_until < end),
            )
            .values(daily_report_sent_until=end)
        )
        await session.commit()
        if claimed.rowcount != 1:
            return False

    async def release_claim() -> None:
        # Yuborilmadi: keyingi tekshiruvda qayta urinamiz
        async with session_factory() as session:
            await session.execute(
                update(table)
                .where(table.c.id == SHOP_ID, table.c.daily_report_sent_until == end)
                .values(daily_report_sent_until=previous)
            )
            await session.commit()

    delivered = 0
    try:
        async with session_factory() as session:
            report = await build_report(
                session, "Kunlik hisobot", start, end, cfg.timezone, timedelta(days=1)
            )
        text = report_text(report, cfg.timezone, "oldingi kunga")
        recipients = await report_recipients(session_factory, cfg, target)
        for chat_id in recipients:
            try:
                await bot.send_message(chat_id, text)
                delivered += 1
            except Exception:  # noqa: BLE001
                log.warning("Kunlik hisobot %s ga yuborilmadi", chat_id, exc_info=True)
    except BaseException:
        if not delivered:
            await asyncio.shield(release_claim())
        raise
    if recipients and not delivered:
        await release_claim()
        return False
    return bool(delivered)


HEARTBEAT_FILE = Path("/tmp/amora-bot-heartbeat")
# Eskirgan tasdiqlash so'rovlari va taklif havolalari shuncha vaqtda bir marta tozalanadi
CLEANUP_EVERY = 3600.0
CLEANUP_OLDER_THAN = timedelta(days=7)


def touch_heartbeat() -> None:
    """Bot tirikligini bildiradi: Docker `healthcheck` shu faylning yoshiga qaraydi."""
    with suppress(OSError):
        HEARTBEAT_FILE.touch()


async def purge_expired(session_factory: SessionFactory, now: datetime | None = None) -> int:
    """Muddati ancha oldin o'tgan tasdiqlash so'rovlari va taklif havolalarini o'chiradi."""
    limit = (now or utcnow()) - CLEANUP_OLDER_THAN
    async with session_factory() as session:
        verifications = await session.execute(
            delete(PhoneVerification).where(PhoneVerification.expires_at < limit)
        )
        invites = await session.execute(delete(StaffInvite).where(StaffInvite.expires_at < limit))
        await session.commit()
    return (verifications.rowcount or 0) + (invites.rowcount or 0)


async def watch_forever(
    session_factory: SessionFactory, bot: Bot, cfg: Settings, interval: float = 30.0
) -> None:
    cleaned_at = 0.0
    while True:
        touch_heartbeat()
        # Har biri alohida: eslatmalardagi xato kunlik hisobotni to'sib qo'ymasligi kerak
        try:
            if cfg.orders_chat_id is not None:
                await check_delays(session_factory, bot)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("Kechikkan buyurtmalarni tekshirishda xato")
        try:
            await send_daily_report(session_factory, bot, cfg)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("Kunlik hisobotni yuborishda xato")
        if time.monotonic() - cleaned_at >= CLEANUP_EVERY:
            cleaned_at = time.monotonic()
            try:
                await purge_expired(session_factory)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                log.exception("Eskirgan yozuvlarni tozalashda xato")
        await asyncio.sleep(interval)
