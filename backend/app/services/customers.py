"""Mijozlar bilan bot va server birga ishlatadigan amallar."""

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Customer


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
