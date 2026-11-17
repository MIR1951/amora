"""Buyurtma qoidalari. API ham, Telegram bot ham shu funksiyalardan foydalanadi."""

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.errors import ApiError
from app.models import (
    ACTIVE_STATUSES,
    Customer,
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusEvent,
    Product,
)
from app.schemas import OrderIn
from app.services import promos
from app.services.shop import distance_km, format_sum, get_shop, is_open_now

CUSTOMER_ACTOR = "mijoz"


@dataclass(frozen=True)
class Problem:
    code: str
    message: str
    product_id: int | None = None


@dataclass(frozen=True)
class QuoteLine:
    product_id: int
    name: str
    price: int
    quantity: int

    @property
    def line_total(self) -> int:
        return self.price * self.quantity


@dataclass
class Quote:
    lines: list[QuoteLine] = field(default_factory=list)
    items_total: int = 0
    delivery_fee: int = 0
    distance_km: float | None = None
    problems: list[Problem] = field(default_factory=list)
    promo: promos.PromoResult = field(default_factory=promos.PromoResult)

    @property
    def discount(self) -> int:
        return self.promo.discount

    @property
    def total(self) -> int:
        return self.items_total - self.discount + self.delivery_fee

    @property
    def can_order(self) -> bool:
        return not self.problems


async def compute_quote(
    session: AsyncSession,
    items: list[tuple[int, int]],
    latitude: float | None,
    longitude: float | None,
    cfg: Settings,
    now: datetime | None = None,
    promo_code: str | None = None,
    apply_auto_promo: bool = False,
    phone: str | None = None,
) -> Quote:
    """Savatni hisoblaydi. Narxlar har doim bazadan olinadi, ilova yuborgan narxga ishonilmaydi."""
    quote = Quote()

    # Bir xil taom ikki marta kelsa, sonini qo'shamiz
    quantities: dict[int, int] = {}
    for product_id, quantity in items:
        quantities[product_id] = quantities.get(product_id, 0) + quantity

    rows = await session.scalars(select(Product).where(Product.id.in_(quantities)))
    products = {product.id: product for product in rows}

    for product_id, quantity in quantities.items():
        product = products.get(product_id)
        if product is None or product.is_deleted:
            quote.problems.append(
                Problem("product_not_found", "Taom menyudan olib tashlangan", product_id)
            )
            continue
        if not product.is_available:
            quote.problems.append(
                Problem(
                    "product_unavailable", f"«{product.name}» hozircha mavjud emas", product_id
                )
            )
            continue
        if quantity > 50:
            quote.problems.append(
                Problem("quantity_too_large", f"«{product.name}» soni juda ko'p", product_id)
            )
            continue
        quote.lines.append(QuoteLine(product.id, product.name, product.price, quantity))

    quote.items_total = sum(line.line_total for line in quote.lines)

    shop = await get_shop(session)

    if not is_open_now(shop, cfg.timezone, now):
        hours = f"{shop.open_time:%H:%M} dan {shop.close_time:%H:%M} gacha"
        message = (
            "Kafe hozir buyurtma qabul qilmayapti"
            if not shop.is_accepting_orders
            else f"Kafe hozir yopiq. Ish vaqti: {hours}"
        )
        quote.problems.append(Problem("shop_closed", message))

    if quote.lines and quote.items_total < shop.min_order_amount:
        quote.problems.append(
            Problem(
                "below_min_order",
                f"Eng kam buyurtma summasi {format_sum(shop.min_order_amount)}",
            )
        )

    if (
        latitude is not None
        and longitude is not None
        and shop.cafe_latitude is not None
        and shop.cafe_longitude is not None
    ):
        quote.distance_km = round(
            distance_km(shop.cafe_latitude, shop.cafe_longitude, latitude, longitude), 2
        )
        if shop.max_delivery_km is not None and quote.distance_km > shop.max_delivery_km:
            quote.problems.append(
                Problem("out_of_zone", "Afsuski, bu manzilga yetkazib bera olmaymiz")
            )

    free_from = shop.free_delivery_from
    if free_from is not None and quote.items_total >= free_from:
        quote.delivery_fee = 0
    else:
        quote.delivery_fee = shop.delivery_fee

    if quote.lines:
        quote.promo = await promos.evaluate(
            session, promo_code, apply_auto_promo, quote.items_total, phone, now
        )
    return quote


def _order_query():
    return select(Order).options(selectinload(Order.items), selectinload(Order.history))


async def get_order(
    session: AsyncSession,
    order_id: int,
    customer_id: int | None = None,
    for_update: bool = False,
) -> Order | None:
    query = _order_query().where(Order.id == order_id)
    if customer_id is not None:
        query = query.where(Order.customer_id == customer_id)
    if for_update:
        # Ikki xodim bir vaqtda tugma bossa, biri ikkinchisini kutadi
        query = query.with_for_update(of=Order)
    return await session.scalar(query.execution_options(populate_existing=True))


async def list_orders(
    session: AsyncSession, customer_id: int, limit: int, offset: int
) -> tuple[list[Order], bool]:
    rows = await session.scalars(
        _order_query()
        .where(Order.customer_id == customer_id)
        .order_by(Order.id.desc())
        .limit(limit + 1)
        .offset(offset)
    )
    orders = list(rows)
    return orders[:limit], len(orders) > limit


async def is_phone_blocked(session: AsyncSession, phone: str) -> bool:
    return bool(
        await session.scalar(
            select(exists().where(Customer.phone == phone, Customer.is_blocked.is_(True)))
        )
    )


async def _find_by_client_id(
    session: AsyncSession, customer_id: int, client_order_id: str
) -> Order | None:
    return await session.scalar(
        _order_query().where(
            Order.customer_id == customer_id, Order.client_order_id == client_order_id
        )
    )


async def create_order(
    session: AsyncSession, customer: Customer, data: OrderIn, cfg: Settings
) -> tuple[Order, bool]:
    """Buyurtma yaratadi. (buyurtma, yangi_yaratildimi) qaytaradi."""
    client_order_id = str(data.client_order_id) if data.client_order_id else None
    customer_id = customer.id  # rollback'dan keyin customer obyektiga murojaat qilib bo'lmaydi
    if not customer.phone_verified:
        raise ApiError(
            403,
            "phone_not_verified",
            "Buyurtma berish uchun raqamingizni Telegram orqali tasdiqlang. Ilovani yangilang",
        )
    # Kuryer tasdiqlangan raqamga qo'ng'iroq qiladi: ilova boshqa raqam yuborsa ham shu olinadi
    phone = customer.phone
    name = data.name or customer.name
    telegram_id = customer.telegram_user_id

    if customer.is_blocked or await is_phone_blocked(session, phone):
        raise ApiError(403, "blocked", "Buyurtma berish imkoni cheklangan. Kafe bilan bog'laning")

    # Internet uzilib, ilova xuddi shu buyurtmani qayta yuborgan bo'lsa
    if client_order_id:
        existing = await _find_by_client_id(session, customer_id, client_order_id)
        if existing is not None:
            return existing, False

    active = await session.scalar(
        select(func.count())
        .select_from(Order)
        .where(Order.customer_id == customer_id, Order.status.in_(ACTIVE_STATUSES))
    )
    if active >= cfg.max_active_orders:
        raise ApiError(
            409,
            "too_many_active_orders",
            "Sizda tugallanmagan buyurtmalar bor. Ular yetkazilgach, yana buyurtma bera olasiz",
        )

    quote = await compute_quote(
        session,
        [(item.product_id, item.quantity) for item in data.items],
        data.latitude,
        data.longitude,
        cfg,
        promo_code=data.promo_code,
        apply_auto_promo=data.apply_auto_promo,
        phone=phone,
    )
    if quote.problems:
        problem = quote.problems[0]
        extra = {"product_id": problem.product_id} if problem.product_id else {}
        raise ApiError(409, problem.code, problem.message, extra)

    if quote.promo.error:
        raise ApiError(409, "promo_invalid", quote.promo.error)

    if data.expected_total is not None and data.expected_total != quote.total:
        raise ApiError(
            409,
            "price_changed",
            f"Narxlar o'zgargan. Yangi summa: {format_sum(quote.total)}",
            {"total": quote.total},
        )

    previous_orders = await session.scalar(
        select(func.count()).select_from(Order).where(Order.phone == phone)
    )

    order = Order(
        customer_id=customer_id,
        customer_order_no=previous_orders + 1,
        client_order_id=client_order_id,
        status=OrderStatus.NEW.value,
        customer_name=name,
        phone=phone,
        customer_telegram_id=telegram_id,
        latitude=data.latitude,
        longitude=data.longitude,
        address_note=data.address_note,
        comment=data.comment,
        items_total=quote.items_total,
        delivery_fee=quote.delivery_fee,
        discount=quote.discount,
        promo_id=quote.promo.promo.id if quote.promo.promo else None,
        promo_code=(
            (quote.promo.promo.code or promos.AUTO_TITLE)[:30] if quote.promo.promo else None
        ),
        total=quote.total,
        distance_km=quote.distance_km,
        items=[
            OrderItem(
                product_id=line.product_id,
                name=line.name,
                price=line.price,
                quantity=line.quantity,
            )
            for line in quote.lines
        ],
        history=[OrderStatusEvent(status=OrderStatus.NEW.value, actor=CUSTOMER_ACTOR)],
    )
    if order.promo_id is not None and not await promos.take_use(session, order.promo_id):
        await session.rollback()
        raise ApiError(409, "promo_invalid", "Promokod tugab qolgan")
    session.add(order)
    try:
        await session.commit()
    except IntegrityError:
        # Ikki bir xil so'rov bir vaqtda keldi: birinchisi yaratgan buyurtmani qaytaramiz
        await session.rollback()
        if client_order_id:
            existing = await _find_by_client_id(session, customer_id, client_order_id)
            if existing is not None:
                return existing, False
        raise
    return order, True


# Xodim (Telegram guruhdagi tugmalar) qila oladigan o'tishlar
STAFF_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.NEW: {OrderStatus.ACCEPTED, OrderStatus.REJECTED},
    OrderStatus.ACCEPTED: {OrderStatus.DELIVERING, OrderStatus.REJECTED},
    OrderStatus.DELIVERING: {OrderStatus.DELIVERED, OrderStatus.REJECTED},
}


class StatusChangeError(Exception):
    """Buyurtma holatini bunday o'zgartirib bo'lmaydi."""

    def __init__(self, message: str, order: Order | None = None):
        super().__init__(message)
        self.message = message
        self.order = order


async def set_status_by_staff(
    session: AsyncSession,
    order_id: int,
    new_status: OrderStatus,
    actor: str,
    reason: str | None = None,
) -> tuple[Order, bool]:
    """Xodim holatni o'zgartiradi. (buyurtma, o'zgardimi) qaytaradi.

    Tugma ikki marta bosilsa xato bermaydi, shunchaki o'zgarmaganini bildiradi.
    """
    order = await get_order(session, order_id, for_update=True)
    if order is None:
        raise StatusChangeError("Buyurtma topilmadi")

    current = order.status_enum
    if current == new_status:
        await session.commit()  # hech narsa o'zgarmadi, faqat qator qulfini bo'shatamiz
        return order, False

    if new_status not in STAFF_TRANSITIONS.get(current, set()):
        await session.commit()
        if current == OrderStatus.CANCELLED:
            raise StatusChangeError("Mijoz bu buyurtmani bekor qilgan", order)
        raise StatusChangeError("Bu buyurtma holatini endi o'zgartirib bo'lmaydi", order)

    order.status = new_status.value
    if new_status == OrderStatus.REJECTED:
        order.reject_reason = (reason or "").strip()[:255] or None
        await promos.return_use(session, order)
    order.history.append(OrderStatusEvent(status=new_status.value, actor=actor[:100]))
    await session.commit()
    return order, True


async def cancel_by_customer(
    session: AsyncSession, customer_id: int, order_id: int
) -> tuple[Order, bool]:
    """Mijoz faqat kafe hali qabul qilmagan buyurtmani bekor qila oladi.

    (buyurtma, o'zgardimi) qaytaradi: allaqachon bekor qilingan bo'lsa False.
    """
    order = await get_order(session, order_id, customer_id=customer_id, for_update=True)
    if order is None:
        raise ApiError(404, "not_found", "Buyurtma topilmadi")

    current = order.status_enum
    if current == OrderStatus.CANCELLED:
        await session.commit()
        return order, False
    if current != OrderStatus.NEW:
        await session.commit()
        raise ApiError(
            409,
            "cannot_cancel",
            "Kafe buyurtmani qabul qilib bo'lgan. Bekor qilish uchun kafega qo'ng'iroq qiling",
        )

    order.status = OrderStatus.CANCELLED.value
    await promos.return_use(session, order)
    order.history.append(
        OrderStatusEvent(status=OrderStatus.CANCELLED.value, actor=CUSTOMER_ACTOR)
    )
    await session.commit()
    return order, True
