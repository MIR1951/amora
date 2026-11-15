import math
from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ShopSettings

SHOP_ID = 1


async def get_shop(session: AsyncSession) -> ShopSettings:
    """Sozlamalar qatorini qaytaradi, yo'q bo'lsa standart qiymatlar bilan yaratadi."""
    shop = await session.get(ShopSettings, SHOP_ID)
    if shop is None:
        try:
            async with session.begin_nested():
                shop = ShopSettings(id=SHOP_ID)
                session.add(shop)
        except IntegrityError:  # boshqa so'rov bir vaqtda yaratib ulgurdi
            shop = await session.get(ShopSettings, SHOP_ID)
    return shop


def is_within_hours(open_time: time, close_time: time, now: time) -> bool:
    """Ish vaqti ichidami. Yarim tundan o'tadigan vaqt (masalan 18:00-02:00) ham ishlaydi."""
    if open_time == close_time:
        return True  # kecha-kunduz
    if open_time < close_time:
        return open_time <= now < close_time
    return now >= open_time or now < close_time


def is_open_now(shop: ShopSettings, tz_name: str, now: datetime | None = None) -> bool:
    if not shop.is_accepting_orders:
        return False
    local = (now or datetime.now(ZoneInfo(tz_name))).astimezone(ZoneInfo(tz_name))
    return is_within_hours(shop.open_time, shop.close_time, local.time())


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Ikki nuqta orasidagi to'g'ri chiziq masofasi (haversine)."""
    radius = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def format_sum(amount: int) -> str:
    """25000 -> "25 000 so'm"."""
    return f"{amount:,}".replace(",", " ") + " so'm"
