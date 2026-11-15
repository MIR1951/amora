"""Sinov uchun namuna menyu: `python -m app.seed`.

Faqat menyu bo'sh bo'lsa ishlaydi. Haqiqiy menyu Telegram botdagi admin bo'limidan kiritiladi.
"""

import asyncio

from sqlalchemy import func, select

from app.config import get_settings
from app.db import make_engine, make_session_factory
from app.models import Category, Product
from app.services.shop import get_shop

SAMPLE = {
    "Taomlar": [
        ("Namuna: Osh", "Sinov uchun namuna taom", 35_000),
        ("Namuna: Lag'mon", "Sinov uchun namuna taom", 30_000),
        ("Namuna: Manti", "Sinov uchun namuna taom", 28_000),
    ],
    "Ichimliklar": [
        ("Namuna: Choy", "Sinov uchun namuna ichimlik", 5_000),
        ("Namuna: Kompot", "Sinov uchun namuna ichimlik", 8_000),
    ],
}


async def main() -> None:
    engine = make_engine(get_settings().database_url)
    async with make_session_factory(engine)() as session:
        await get_shop(session)
        if await session.scalar(select(func.count()).select_from(Product)):
            print("Menyu bo'sh emas, hech narsa qo'shilmadi.")
        else:
            for order, (category_name, dishes) in enumerate(SAMPLE.items()):
                category = Category(name=category_name, sort_order=order)
                session.add(category)
                for position, (name, description, price) in enumerate(dishes):
                    session.add(
                        Product(
                            category=category,
                            name=name,
                            description=description,
                            price=price,
                            sort_order=position,
                        )
                    )
            print("Namuna menyu qo'shildi.")
        await session.commit()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
