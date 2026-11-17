"""Savdo hisobotlari: davr bo'yicha buyurtmalar, tushum, taomlar va mijozlar."""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ACTIVE_STATUSES, Order, OrderItem, OrderStatus, ShopSettings

# Hisobot davrlari: tugma kaliti -> sarlavha
PERIODS = {
    "today": "Bugun",
    "yesterday": "Kecha",
    "week": "So'nggi 7 kun",
    "month": "So'nggi 30 kun",
    "this_month": "Shu oy",
}

# Qaysi oldingi davr bilan solishtiriladi: bugun kechaning shu vaqtigacha bo'lgani bilan va hokazo
COMPARE_SHIFT = {
    "today": timedelta(days=1),
    "yesterday": timedelta(days=1),
    "week": timedelta(days=7),
    "month": timedelta(days=30),
}

COMPARE_TITLE = {
    "today": "kechaning shu vaqtiga",
    "yesterday": "undan oldingi kunga",
    "week": "oldingi 7 kunga",
    "month": "oldingi 30 kunga",
}


@dataclass
class Report:
    title: str
    start: datetime
    end: datetime
    orders: int = 0
    by_status: Counter = field(default_factory=Counter)
    delivered: int = 0
    revenue: int = 0  # yetkazilganlarning jami summasi (kuryer olib kelgan naqd pul)
    items_revenue: int = 0
    delivery_revenue: int = 0
    new_customers: int = 0
    returning_customers: int = 0
    top_products: list[tuple[str, int, int]] = field(default_factory=list)  # nom, soni, summa
    reject_reasons: list[tuple[str, int]] = field(default_factory=list)
    busiest_hour: tuple[int, int] | None = None  # soat, buyurtmalar soni
    previous_revenue: int | None = None
    previous_delivered: int | None = None

    @property
    def average_check(self) -> int:
        return round(self.revenue / self.delivered) if self.delivered else 0

    @property
    def in_progress(self) -> int:
        return sum(self.by_status[status] for status in ACTIVE_STATUSES)


def period_bounds(kind: str, tz_name: str, now: datetime) -> tuple[datetime, datetime]:
    """Davr boshi va oxiri (mahalliy vaqt bilan)."""
    zone = ZoneInfo(tz_name)
    local_now = now.astimezone(zone)
    midnight = datetime.combine(local_now.date(), time.min, tzinfo=zone)
    if kind == "yesterday":
        return midnight - timedelta(days=1), midnight
    if kind == "week":
        return midnight - timedelta(days=6), local_now
    if kind == "month":
        return midnight - timedelta(days=29), local_now
    if kind == "this_month":
        return midnight.replace(day=1), local_now
    return midnight, local_now


def business_day(shop: ShopSettings, tz_name: str, now: datetime) -> tuple[datetime, datetime]:
    """Oxirgi tugagan ish kuni: (ochilish, yopilish). Kecha-kunduz ishlasa, 24 soatlik oraliq.

    Yarim tundan o'tadigan ish vaqti (18:00-02:00) ham bitta ish kuni hisoblanadi.
    """
    zone = ZoneInfo(tz_name)
    local_now = now.astimezone(zone)
    end = datetime.combine(local_now.date(), shop.close_time, tzinfo=zone)
    if end > local_now:
        end -= timedelta(days=1)
    open_dt = datetime.combine(end.date(), shop.open_time, tzinfo=zone)
    if shop.open_time == shop.close_time:
        length = timedelta(days=1)
    else:
        length = (end - open_dt) % timedelta(days=1)
    return end - length, end


async def build_report(
    session: AsyncSession,
    title: str,
    start: datetime,
    end: datetime,
    tz_name: str,
    compare_shift: timedelta | None = None,
) -> Report:
    report = Report(title=title, start=start, end=end)
    in_period = (Order.created_at >= start, Order.created_at < end)

    rows = (
        await session.execute(
            select(
                Order.status,
                Order.total,
                Order.items_total,
                Order.delivery_fee,
                Order.phone,
                Order.reject_reason,
                Order.created_at,
            ).where(*in_period)
        )
    ).all()

    zone = ZoneInfo(tz_name)
    hours: Counter = Counter()
    reasons: Counter = Counter()
    phones: set[str] = set()
    for status, total, items_total, delivery_fee, phone, reason, created_at in rows:
        report.orders += 1
        report.by_status[OrderStatus(status)] += 1
        phones.add(phone)
        hours[created_at.astimezone(zone).hour] += 1
        if status == OrderStatus.DELIVERED.value:
            report.delivered += 1
            report.revenue += total
            report.items_revenue += items_total
            report.delivery_revenue += delivery_fee
        elif status == OrderStatus.REJECTED.value:
            reasons[reason or "Sababsiz"] += 1

    report.reject_reasons = reasons.most_common()
    if hours:
        report.busiest_hour = max(hours.items(), key=lambda item: (item[1], -item[0]))

    if phones:
        # Raqamning birinchi buyurtmasi shu davrga to'g'ri kelsa, u yangi mijoz
        first_orders = await session.execute(
            select(Order.phone, func.min(Order.created_at))
            .where(Order.phone.in_(phones))
            .group_by(Order.phone)
        )
        for _, first in first_orders:
            if first >= start:
                report.new_customers += 1
            else:
                report.returning_customers += 1

    top = await session.execute(
        select(
            OrderItem.name,
            func.sum(OrderItem.quantity),
            func.sum(OrderItem.quantity * OrderItem.price),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .where(*in_period, Order.status == OrderStatus.DELIVERED.value)
        .group_by(OrderItem.name)
        .order_by(
            func.sum(OrderItem.quantity).desc(),
            func.sum(OrderItem.quantity * OrderItem.price).desc(),
            OrderItem.name,
        )
        .limit(5)
    )
    report.top_products = [(name, int(qty), int(amount)) for name, qty, amount in top]

    if compare_shift is not None:
        previous = (
            await session.execute(
                select(func.count(), func.coalesce(func.sum(Order.total), 0)).where(
                    Order.created_at >= start - compare_shift,
                    Order.created_at < end - compare_shift,
                    Order.status == OrderStatus.DELIVERED.value,
                )
            )
        ).one()
        report.previous_delivered, report.previous_revenue = int(previous[0]), int(previous[1])
    return report
