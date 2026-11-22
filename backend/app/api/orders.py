from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Query, Response

from app.api.deps import CfgDep, CustomerDep, NotifierDep, OptionalCustomerDep, SessionDep
from app.errors import ApiError
from app.models import ACTIVE_STATUSES, STATUS_LABELS, Order, OrderStatus
from app.notifier import safe_notify
from app.schemas import (
    OrderIn,
    OrderItemOut,
    OrderListOut,
    OrderOut,
    ProblemOut,
    QuoteIn,
    QuoteLineOut,
    QuoteOut,
    StatusEventOut,
)
from app.services import orders as order_service

router = APIRouter(tags=["buyurtma"])


def order_out(order: Order) -> OrderOut:
    status = order.status_enum
    return OrderOut(
        id=order.id,
        client_order_id=order.client_order_id,
        status=status.value,
        status_label=STATUS_LABELS[status],
        is_active=status in ACTIVE_STATUSES,
        can_cancel=status == OrderStatus.NEW,
        items=[OrderItemOut.model_validate(item) for item in order.items],
        items_total=order.items_total,
        delivery_fee=order.delivery_fee,
        discount=order.discount,
        promo_code=order.promo_code,
        total=order.total,
        customer_name=order.customer_name,
        phone=order.phone,
        latitude=order.latitude,
        longitude=order.longitude,
        address_note=order.address_note,
        comment=order.comment,
        reject_reason=order.reject_reason,
        created_at=order.created_at,
        updated_at=order.updated_at,
        history=[
            StatusEventOut(
                status=event.status,
                status_label=STATUS_LABELS[OrderStatus(event.status)],
                created_at=event.created_at,
            )
            for event in order.history
        ],
    )


@router.post("/orders/quote", response_model=QuoteOut, summary="Savatni hisoblash")
async def quote(
    data: QuoteIn, session: SessionDep, cfg: CfgDep, customer: OptionalCustomerDep
) -> QuoteOut:
    """Savat summasi, yetkazish narxi va buyurtma berish mumkinligini qaytaradi.

    Buyurtma berib bo'lmasa `can_order: false` va sababi `problems` ichida bo'ladi
    (kafe yopiq, eng kam summa, taom tugagan, manzil hududdan tashqarida).
    Manzil hali tanlanmagan bo'lsa `latitude`/`longitude` yuborilmaydi.

    Chegirma: `promo_code` yuborilsa o'sha tekshiriladi (ishlamasa sababi `promo_error`da,
    buyurtma berishga xalaqit qilmaydi: ilova kodni olib tashlashni taklif qiladi).
    `apply_auto_promo: true` bo'lsa, birinchi buyurtma chegirmasi o'zi qo'llanadi.
    Token yuborilsa mijozning oldingi buyurtmalari hisobga olinadi.
    """
    result = await order_service.compute_quote(
        session,
        [(item.product_id, item.quantity) for item in data.items],
        data.latitude,
        data.longitude,
        cfg,
        promo_code=data.promo_code,
        apply_auto_promo=data.apply_auto_promo,
        # Token bo'lmasa telefon hisobga olinmaydi: aks holda begona raqam buyurtma berganmi,
        # shu so'rov orqali bilib olish mumkin edi. Buyurtmada raqam bo'yicha baribir tekshiriladi
        phone=customer.phone if customer else None,
    )
    await session.commit()
    return QuoteOut(
        lines=[
            QuoteLineOut(
                product_id=line.product_id,
                name=line.name,
                price=line.price,
                quantity=line.quantity,
                line_total=line.line_total,
            )
            for line in result.lines
        ],
        items_total=result.items_total,
        delivery_fee=result.delivery_fee,
        discount=result.discount,
        promo_title=result.promo.title,
        promo_error=result.promo.error,
        total=result.total,
        distance_km=result.distance_km,
        can_order=result.can_order,
        problems=[
            ProblemOut(code=p.code, message=p.message, product_id=p.product_id)
            for p in result.problems
        ],
    )


@router.post("/orders", response_model=OrderOut, status_code=201, summary="Buyurtma berish")
async def create_order(
    data: OrderIn,
    response: Response,
    background: BackgroundTasks,
    customer: CustomerDep,
    session: SessionDep,
    cfg: CfgDep,
    notifier: NotifierDep,
) -> OrderOut:
    """Yangi buyurtma. Summa serverda hisoblanadi, to'lov kuryerga naqd beriladi.

    `client_order_id` (UUID) yuborilsa, xuddi shu so'rov qayta kelganda yangi buyurtma
    yaratilmaydi, avvalgisi 200 kodi bilan qaytadi.
    """
    order, created = await order_service.create_order(session, customer, data, cfg)
    if created:
        background.add_task(safe_notify, notifier.order_created(order.id))
    else:
        response.status_code = 200
    return order_out(order)


@router.get("/orders", response_model=OrderListOut, summary="Buyurtmalarim")
async def list_orders(
    customer: CustomerDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> OrderListOut:
    orders, has_more = await order_service.list_orders(session, customer.id, limit, offset)
    return OrderListOut(orders=[order_out(order) for order in orders], has_more=has_more)


@router.get("/orders/{order_id}", response_model=OrderOut, summary="Buyurtma holati")
async def get_order(order_id: int, customer: CustomerDep, session: SessionDep) -> OrderOut:
    order = await order_service.get_order(session, order_id, customer_id=customer.id)
    if order is None:
        raise ApiError(404, "not_found", "Buyurtma topilmadi")
    return order_out(order)


@router.post("/orders/{order_id}/cancel", response_model=OrderOut, summary="Buyurtmani bekor qilish")
async def cancel_order(
    order_id: int,
    background: BackgroundTasks,
    customer: CustomerDep,
    session: SessionDep,
    notifier: NotifierDep,
) -> OrderOut:
    """Faqat kafe hali qabul qilmagan buyurtmani bekor qilish mumkin."""
    order, changed = await order_service.cancel_by_customer(session, customer.id, order_id)
    if changed:
        background.add_task(safe_notify, notifier.order_cancelled(order.id))
    return order_out(order)
