#!/usr/bin/env python3
"""Emulyator sinovi uchun CI ichida ishlayotgan SINOV serverini boshqaradi.

    backend_ctl.py prepare                    namuna menyu, kecha-kunduz ish vaqti, yetkazish shartlari
    backend_ctl.py status latest accepted     oxirgi buyurtmani keyingi holatga o'tkazadi
    backend_ctl.py status latest rejected "Sabab"

Kafe xodimi Telegram'da bosadigan tugmalar o'rnini bosadi. Faqat sinov bazasi bilan ishlatiladi:
AMORA_DATABASE_URL sinov bazasini ko'rsatib turishi kerak.
"""

import asyncio
import sys
from datetime import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from sqlalchemy import select  # noqa: E402

from app import seed  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import make_engine, make_session_factory  # noqa: E402
from app.models import Order, OrderStatus  # noqa: E402
from app.services.orders import set_status_by_staff  # noqa: E402
from app.services.shop import get_shop  # noqa: E402

# Ilovaning yuqori satrida ko'rinadi. smoke_test.py buyurtma berishdan oldin shu nomni tekshiradi:
# ilova sinov serveriga ulanganiga ishonch hosil qilish uchun.
TEST_CAFE_NAME = "Amora sinov serveri"

# Samarqand markazi: emulyatorning joylashuvi ham shu yerga qo'yiladi
CAFE_LATITUDE = 39.6547
CAFE_LONGITUDE = 66.9758


def guard() -> str:
    url = get_settings().database_url
    if "localhost" not in url and "127.0.0.1" not in url:
        raise SystemExit("Bu skript faqat mahalliy sinov bazasi bilan ishlaydi")
    return url


async def prepare() -> None:
    url = guard()
    await seed.main()
    engine = make_engine(url)
    async with make_session_factory(engine)() as session:
        shop = await get_shop(session)
        shop.cafe_name = TEST_CAFE_NAME
        shop.open_time = time(0, 0)
        shop.close_time = time(0, 0)  # kecha-kunduz ochiq
        shop.is_accepting_orders = True
        shop.phone = "+998901112233"
        shop.cafe_latitude = CAFE_LATITUDE
        shop.cafe_longitude = CAFE_LONGITUDE
        shop.max_delivery_km = 15
        shop.delivery_fee = 10_000
        shop.free_delivery_from = 100_000
        shop.min_order_amount = 20_000
        await session.commit()
    await engine.dispose()
    print("Sinov serveri tayyor")


async def set_status(target: str, status: str, reason: str | None) -> None:
    engine = make_engine(guard())
    async with make_session_factory(engine)() as session:
        if target == "latest":
            order_id = await session.scalar(select(Order.id).order_by(Order.id.desc()).limit(1))
            if order_id is None:
                raise SystemExit("Bazada buyurtma yo'q")
        else:
            order_id = int(target)
        order, changed = await set_status_by_staff(
            session, order_id, OrderStatus(status), actor="CI sinovi", reason=reason
        )
        print(f"Buyurtma #{order.id}: {order.status} (o'zgardi: {changed})")
    await engine.dispose()


def main() -> None:
    args = sys.argv[1:]
    if args[:1] == ["prepare"]:
        asyncio.run(prepare())
    elif args[:1] == ["status"] and len(args) >= 3:
        asyncio.run(set_status(args[1], args[2], args[3] if len(args) > 3 else None))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
