"""Hisobot va mijoz kartasi: egasi, admin va xodimlar uchun."""

from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import Customer, Order, OrderItem, OrderStatus
from app.security import normalize_phone
from app.services import customers as customer_service
from app.services.reports import (
    COMPARE_SHIFT,
    COMPARE_TITLE,
    PERIODS,
    build_report,
    period_bounds,
)
from app.telegram import keyboards as kb
from app.telegram import texts
from app.telegram.admin_router import show
from app.telegram.filters import is_admin, protect
from app.telegram.keyboards import AdminCb
from app.telegram.publisher import SessionFactory

router = protect(Router(name="insights"))


# ---------- Hisobot ----------


async def show_report(event: Message | CallbackQuery, period: str, session_factory, cfg: Settings):
    if period not in PERIODS:
        period = "today"
    start, end = period_bounds(period, cfg.timezone, datetime.now(ZoneInfo(cfg.timezone)))
    async with session_factory() as session:
        report = await build_report(
            session, PERIODS[period], start, end, cfg.timezone, COMPARE_SHIFT.get(period)
        )
    text = texts.report_text(report, cfg.timezone, COMPARE_TITLE.get(period))
    await show(event, text, kb.report_keyboard(period))


@router.callback_query(AdminCb.filter(F.action == "report"))
async def cb_report(callback: CallbackQuery, session_factory: SessionFactory, cfg: Settings):
    await show_report(callback, "today", session_factory, cfg)


@router.callback_query(AdminCb.filter(F.action == "rep"))
async def cb_report_period(
    callback: CallbackQuery, callback_data: AdminCb, session_factory: SessionFactory, cfg: Settings
):
    await show_report(callback, callback_data.value, session_factory, cfg)


# ---------- Mijoz kartasi ----------


async def find_phone(session: AsyncSession, query: str) -> str | None:
    """Raqam yoki buyurtma raqami (№) bo'yicha mijozning telefonini topadi."""
    digits = "".join(char for char in query if char.isdigit())
    if digits and len(digits) <= 7:
        order = await session.get(Order, int(digits))
        return order.phone if order is not None else None
    try:
        return normalize_phone(query)
    except ValueError:
        return None


async def customer_card(session: AsyncSession, phone: str, tz_name: str) -> tuple[str, bool]:
    """(kartaning matni, bloklanganmi)"""
    orders = list(
        await session.scalars(select(Order).where(Order.phone == phone).order_by(Order.id))
    )
    customers = list(await session.scalars(select(Customer).where(Customer.phone == phone)))
    blocked = any(customer.is_blocked for customer in customers)
    # Tasdiqlangan mijoz ismi birinchi: u bitta, qolganlari eski buyurtmalardagi ismlar
    customers.sort(key=lambda customer: not customer.phone_verified)
    telegram_id = next(
        (c.telegram_user_id for c in customers if c.phone_verified and c.telegram_user_id), None
    )
    names: list[str] = []
    for name in [c.name for c in customers if c.phone_verified] + [
        order.customer_name for order in reversed(orders)
    ] + [c.name for c in customers]:
        if name and name not in names:
            names.append(name)
    favourites = [
        (name, int(quantity))
        for name, quantity in await session.execute(
            select(OrderItem.name, func.sum(OrderItem.quantity))
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.phone == phone, Order.status == OrderStatus.DELIVERED.value)
            .group_by(OrderItem.name)
            .order_by(func.sum(OrderItem.quantity).desc(), OrderItem.name)
            .limit(3)
        )
    ]
    text = texts.customer_card(
        phone, names[:3], orders, favourites, blocked, tz_name, telegram_id=telegram_id
    )
    return text, blocked


async def show_customer(event, session: AsyncSession, phone: str, cfg: Settings, role: str, notice=None):
    text, blocked = await customer_card(session, phone, cfg.timezone)
    await show(event, text, kb.customer_keyboard(phone, blocked, is_admin(role)), notice)


@router.message(Command("mijoz", "client"))
async def cmd_customer(
    message: Message,
    command: CommandObject,
    session_factory: SessionFactory,
    cfg: Settings,
    role: str,
):
    query = (command.args or "").strip()
    if not query:
        await message.answer(
            "Raqamni yoki buyurtma raqamini buyruqdan keyin yozing, masalan:\n"
            "/mijoz 901234567\n/mijoz 45"
        )
        return
    async with session_factory() as session:
        phone = await find_phone(session, query)
        if phone is None:
            await message.answer("Mijoz topilmadi. Raqamni shunday yozing: /mijoz 901234567")
            return
        await show_customer(message, session, phone, cfg, role)


@router.callback_query(AdminCb.filter(F.action.in_({"cust_block", "cust_unblock"})))
async def cb_customer_block(
    callback: CallbackQuery,
    callback_data: AdminCb,
    session_factory: SessionFactory,
    cfg: Settings,
    role: str,
):
    blocked = callback_data.action == "cust_block"
    phone = callback_data.value
    async with session_factory() as session:
        changed = await customer_service.set_blocked(session, phone, blocked)
        if changed == 0:
            notice = "Bu raqam bilan ro'yxatdan o'tgan mijoz yo'q"
        else:
            notice = "Bloklandi" if blocked else "Blokdan chiqarildi"
        await show_customer(callback, session, phone, cfg, role, notice)
