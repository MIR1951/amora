#!/usr/bin/env python3
"""Emulyator sinovi uchun CI ichida ishlayotgan SINOV serverini boshqaradi.

    backend_ctl.py prepare                    rasmli namuna menyu, kecha-kunduz ish vaqti, yetkazish shartlari
    backend_ctl.py status latest accepted     oxirgi buyurtmani keyingi holatga o'tkazadi
    backend_ctl.py status latest rejected "Sabab"

Kafe xodimi Telegram'da bosadigan tugmalar o'rnini bosadi. Faqat sinov bazasi bilan ishlatiladi:
AMORA_DATABASE_URL sinov bazasini ko'rsatib turishi kerak.
"""

import asyncio
import shutil
import sys
from datetime import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from sqlalchemy import func, select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import make_engine, make_session_factory  # noqa: E402
from app.models import Category, Order, OrderStatus, Product  # noqa: E402
from app.services.orders import set_status_by_staff  # noqa: E402
from app.services.shop import get_shop  # noqa: E402

# Ilovaning yuqori satrida ko'rinadi. smoke_test.py buyurtma berishdan oldin shu nomni tekshiradi:
# ilova sinov serveriga ulanganiga ishonch hosil qilish uchun.
TEST_CAFE_NAME = "Amora sinov serveri"

# Samarqand markazi: emulyatorning joylashuvi ham shu yerga qo'yiladi
CAFE_LATITUDE = 39.6547
CAFE_LONGITUDE = 66.9758


# Namuna menyu: (taom, tavsif, narx, rasm fayli, sotuvda bormi). Rasmlar fixtures/ papkasida:
# ular chizilgan namunalar (fixtures/generate.py), fotosurat emas. Bitta taom ataylab rasmsiz,
# bittasi "tugagan": ilovada bu holatlar ham ko'rinishi kerak.
FIXTURES = Path(__file__).with_name("fixtures")
MEDIA_FOLDER = "ci"
TEST_MENU = {
    "Milliy taomlar": [
        ("Osh", "Devzira guruch, mol go'shti, sariq sabzi va no'xat", 35_000, "osh.jpg", True),
        ("Lag'mon", "Qo'lda cho'zilgan xamir, go'sht va sabzavotli qayla", 30_000, "lagmon.jpg", True),
        ("Manti", "Bug'da pishirilgan, 5 dona. Qatiq bilan beriladi", 28_000, "manti.jpg", True),
        ("Shashlik", "Mol go'shtidan, 3 six. Piyoz va ko'kat bilan", 45_000, "shashlik.jpg", True),
    ],
    "Salat va non": [
        ("Achchiq-chuchuk", "Pomidor, bodring, piyoz va ko'katlar", 12_000, "salat.jpg", True),
        ("Tandir non", "Tandirda yopilgan issiq non", 4_000, None, True),
    ],
    "Ichimliklar": [
        ("Limonli choy", "Choynakda, 0,5 litr", 5_000, "choy.jpg", True),
        ("Olcha kompoti", "Uy usulida, 0,4 litr", 8_000, "kompot.jpg", False),
    ],
}


def guard() -> str:
    url = get_settings().database_url
    if "localhost" not in url and "127.0.0.1" not in url:
        raise SystemExit("Bu skript faqat mahalliy sinov bazasi bilan ishlaydi")
    return url


async def add_menu(session) -> None:
    """Menyu bo'sh bo'lsa, namuna menyuni rasmlari bilan qo'shadi."""
    if await session.scalar(select(func.count()).select_from(Product)):
        print("Menyu bo'sh emas, hech narsa qo'shilmadi")
        return
    media = get_settings().media_dir / MEDIA_FOLDER
    media.mkdir(parents=True, exist_ok=True)
    for order, (category_name, dishes) in enumerate(TEST_MENU.items()):
        category = Category(name=category_name, sort_order=order)
        session.add(category)
        for position, (name, description, price, image, available) in enumerate(dishes):
            if image:
                shutil.copyfile(FIXTURES / image, media / image)
            session.add(
                Product(
                    category=category,
                    name=name,
                    description=description,
                    price=price,
                    image_path=f"{MEDIA_FOLDER}/{image}" if image else None,
                    is_available=available,
                    sort_order=position,
                )
            )
    print("Namuna menyu qo'shildi")


async def prepare() -> None:
    url = guard()
    engine = make_engine(url)
    async with make_session_factory(engine)() as session:
        await add_menu(session)
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
