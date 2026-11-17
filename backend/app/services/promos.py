"""Promokodlar va birinchi buyurtma chegirmasi: tekshirish va hisoblash."""

import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import utcnow
from app.models import Order, OrderStatus, PromoCode, PromoKind
from app.services.shop import format_sum

# Bekor qilingan va rad etilgan buyurtmalar "haqiqiy" hisoblanmaydi
_VOID = (OrderStatus.CANCELLED.value, OrderStatus.REJECTED.value)
CODE_PATTERN = re.compile(r"^[A-Z0-9_-]{3,20}$")
AUTO_TITLE = "Birinchi buyurtma"


def normalize_code(raw: str | None) -> str:
    return "".join((raw or "").split()).upper()


def describe(promo: PromoCode) -> str:
    """ "−15%" yoki "−20 000 so'm" (foizda eng ko'pi bilan qancha bo'lishi ham)."""
    if promo.kind == PromoKind.PERCENT.value:
        text = f"−{promo.value}%"
        if promo.max_discount:
            text += f" (ko'pi bilan {format_sum(promo.max_discount)})"
        return text
    return f"−{format_sum(promo.value)}"


@dataclass
class PromoResult:
    promo: PromoCode | None = None
    discount: int = 0
    title: str | None = None  # ilovada ko'rsatiladi: "AMORA10: −10%"
    error: str | None = None  # kiritilgan kod nega ishlamadi


async def _real_orders(session: AsyncSession, phone: str, promo: PromoCode | None = None) -> int:
    query = select(func.count()).select_from(Order).where(
        Order.phone == phone, Order.status.not_in(_VOID)
    )
    if promo is not None:
        # Kod nomi bo'yicha ham: o'chirib, xuddi shu nom bilan qayta qo'shilgan kod
        # mijozga ikkinchi marta berilmasin
        query = query.where(or_(Order.promo_id == promo.id, Order.promo_code == promo.code))
    return await session.scalar(query)


def _usable(promo: PromoCode, now: datetime) -> str | None:
    if not promo.is_active:
        return "Bu promokod hozir ishlamaydi"
    if promo.expires_at is not None and promo.expires_at <= now:
        return "Promokod muddati tugagan"
    if promo.usage_limit is not None and promo.used_count >= promo.usage_limit:
        return "Promokod tugab qolgan"
    return None


async def evaluate(
    session: AsyncSession,
    code: str | None,
    apply_auto: bool,
    items_total: int,
    phone: str | None,
    now: datetime | None = None,
) -> PromoResult:
    """Savatga qaysi chegirma tushishini aniqlaydi.

    Kod kiritilgan bo'lsa o'sha tekshiriladi. Kiritilmagan bo'lsa (va ilova buni tushunsa)
    birinchi buyurtma chegirmasi o'zi qo'llanadi. Kiritilgan kod ishlamasa ham birinchi
    buyurtma chegirmasi hisoblanadi (xato bilan birga): ilova ishlamagan kodni buyurtmaga
    qo'shmaydi, shunda savatdagi summa buyurtmadagi bilan bir xil bo'ladi.
    Telefon noma'lum bo'lsa, mijoz yangi deb hisoblanadi: buyurtmada raqam bo'yicha yana
    tekshiriladi.
    """
    now = now or utcnow()
    code = normalize_code(code)
    if code:
        result = await _evaluate_code(session, code, items_total, phone, now)
        if result.error is not None and apply_auto:
            fallback = await _evaluate_auto(session, items_total, phone, now)
            fallback.error = result.error
            return fallback
        return result
    if not apply_auto:
        return PromoResult()
    return await _evaluate_auto(session, items_total, phone, now)


async def _evaluate_code(
    session: AsyncSession, code: str, items_total: int, phone: str | None, now: datetime
) -> PromoResult:
    promo = await session.scalar(
        select(PromoCode).where(PromoCode.code == code, PromoCode.is_auto.is_(False))
    )
    if promo is None:
        return PromoResult(error="Bunday promokod yo'q")
    problem = _usable(promo, now)
    if problem is None and items_total < promo.min_order:
        problem = f"Promokod {format_sum(promo.min_order)}dan boshlab amal qiladi"
    if problem is None and phone:
        if promo.first_order_only and await _real_orders(session, phone):
            problem = "Bu promokod faqat birinchi buyurtma uchun"
        elif await _real_orders(session, phone, promo):
            problem = "Siz bu promokoddan foydalangansiz"
    if problem is not None:
        return PromoResult(error=problem)
    return PromoResult(promo, promo.discount_for(items_total), f"{code}: {describe(promo)}")


async def _evaluate_auto(
    session: AsyncSession, items_total: int, phone: str | None, now: datetime
) -> PromoResult:
    promo = await session.scalar(
        select(PromoCode).where(PromoCode.is_auto.is_(True)).order_by(PromoCode.id).limit(1)
    )
    if promo is None or _usable(promo, now) is not None or items_total < promo.min_order:
        return PromoResult()
    if phone and await _real_orders(session, phone):
        return PromoResult()
    return PromoResult(promo, promo.discount_for(items_total), f"{AUTO_TITLE}: {describe(promo)}")


async def take_use(session: AsyncSession, promo_id: int) -> bool:
    """Promokoddan bitta foydalanishni band qiladi. Soni tugagan bo'lsa False."""
    table = PromoCode.__table__
    result = await session.execute(
        update(table)
        .where(
            table.c.id == promo_id,
            (table.c.usage_limit.is_(None)) | (table.c.used_count < table.c.usage_limit),
        )
        .values(used_count=table.c.used_count + 1)
    )
    return result.rowcount == 1


async def return_use(session: AsyncSession, order: Order) -> None:
    """Buyurtma bekor qilinsa yoki rad etilsa, promokod qaytariladi: uni yana ishlatish mumkin."""
    if order.promo_id is None:
        return
    table = PromoCode.__table__
    await session.execute(
        update(table)
        .where(table.c.id == order.promo_id, table.c.used_count > 0)
        .values(used_count=table.c.used_count - 1)
    )


async def total_discount(session: AsyncSession, promo_id: int) -> int:
    return await session.scalar(
        select(func.coalesce(func.sum(Order.discount), 0)).where(
            Order.promo_id == promo_id, Order.status.not_in(_VOID)
        )
    )
