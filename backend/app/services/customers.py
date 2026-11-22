"""Mijozlar bilan bot va server birga ishlatadigan amallar."""

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ACTIVE_STATUSES, Customer, CustomerDevice, Order, PhoneVerification


async def set_blocked(session: AsyncSession, phone: str, blocked: bool) -> int:
    """Raqamni bloklaydi (yoki blokdan chiqaradi). Raqam Telegram orqali tasdiqlangan bo'lsa,
    o'sha Telegram hisobi ham bloklanadi: odam boshqa raqam bilan qaytib kela olmaydi.
    Nechta mijoz o'zgargani qaytadi (0: bu raqamli mijoz yo'q)."""
    telegram_ids = select(Customer.telegram_user_id).where(
        Customer.phone == phone, Customer.telegram_user_id.is_not(None)
    )
    result = await session.execute(
        update(Customer)
        .where(or_(Customer.phone == phone, Customer.telegram_user_id.in_(telegram_ids)))
        .values(is_blocked=blocked)
        .execution_options(synchronize_session=False)
    )
    await session.commit()
    return result.rowcount


DELETED_NAME = "O'chirilgan mijoz"


async def _drop_devices(session: AsyncSession, device_ids) -> None:
    """Qurilmalarni o'chiradi (kirish kalitlari va push manzillari bilan birga)."""
    await session.execute(
        update(PhoneVerification)
        .where(PhoneVerification.device_id.in_(device_ids))
        .values(device_id=None)
    )
    await session.execute(delete(CustomerDevice).where(CustomerDevice.id.in_(device_ids)))


async def sign_out_device(session: AsyncSession, device_id: int) -> None:
    """Shu telefon hisobdan chiqadi: kaliti endi ishlamaydi, unga push ham ketmaydi."""
    await _drop_devices(session, [device_id])
    await session.commit()


async def sign_out_telegram_account(session: AsyncSession, telegram_user_id: int) -> int:
    """Shu Telegram hisobiga bog'langan mijozning barcha telefonlari chiqariladi. Nechtaligini qaytaradi."""
    device_ids = list(
        await session.scalars(
            select(CustomerDevice.id)
            .join(Customer, Customer.id == CustomerDevice.customer_id)
            .where(Customer.telegram_user_id == telegram_user_id)
        )
    )
    if device_ids:
        await _drop_devices(session, device_ids)
    await session.commit()
    return len(device_ids)


async def delete_account(session: AsyncSession, customer_id: int) -> bool:
    """Hisobni o'chiradi. Tugallanmagan buyurtma bo'lsa False (avval ular yopilishi kerak).

    Barcha telefonlar chiqariladi, ism, Telegram hisobi, manzillar va izohlar o'chiriladi.
    Buyurtmalarning o'zi (taomlar, summa, raqam) kafe hisob-kitobi va soxta buyurtmalardan
    himoya uchun qoladi, lekin endi hech qaysi hisobga ko'rinmaydi.
    """
    customer = await session.scalar(
        select(Customer).where(Customer.id == customer_id).with_for_update()
    )
    if customer is None:
        return True
    active = await session.scalar(
        select(func.count())
        .select_from(Order)
        .where(Order.customer_id == customer_id, Order.status.in_(ACTIVE_STATUSES))
    )
    if active:
        await session.rollback()
        return False
    device_ids = list(
        await session.scalars(
            select(CustomerDevice.id).where(CustomerDevice.customer_id == customer_id)
        )
    )
    if device_ids:
        await _drop_devices(session, device_ids)
    await session.execute(
        update(PhoneVerification)
        .where(
            PhoneVerification.phone == customer.phone,
            PhoneVerification.telegram_user_id == customer.telegram_user_id,
        )
        .values(name=None, telegram_name=None)
    )
    await session.execute(
        update(Order)
        .where(Order.customer_id == customer_id)
        .values(
            customer_name=DELETED_NAME,
            customer_telegram_id=None,
            address_note="",
            comment="",
            latitude=0.0,
            longitude=0.0,
        )
    )
    customer.name = DELETED_NAME
    customer.phone_verified = False
    customer.telegram_user_id = None
    if not customer.is_blocked:
        # Raqam bo'shatiladi: shu raqam bilan qayta ro'yxatdan o'tilsa, eski buyurtmalar
        # yangi hisobga qo'shilib qolmaydi. Bloklangan raqamda blok saqlanib qoladi
        customer.phone = ""
    await session.commit()
    return True
