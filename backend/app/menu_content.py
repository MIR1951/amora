"""Mavjud menyuni to'ldirish: tavsiflar, rasmlar va kategoriyalar tartibi.

    docker compose exec api python -m app.menu_content --dry-run   # nima o'zgarishini ko'rish
    docker compose exec api python -m app.menu_content             # qo'llash

Qoidalar:
- hech bir taom qo'shilmaydi va o'chirilmaydi, nom va narxlarga tegilmaydi;
- tavsif faqat bo'sh bo'lsa yoziladi, rasm faqat qo'yilmagan bo'lsa qo'yiladi: kafe botdan
  kiritgan matn va rasm ustiga yozilmaydi;
- taom raqami (id) va nomi ikkalasi ham mos kelsagina o'zgartiriladi: menyu bu fayl
  yozilgandan keyin o'zgargan bo'lsa, begona taomga tegib ketmaydi;
- qayta ishga tushirilsa, hech narsa ikkilanmaydi.

Rasmlar `menu_assets/` papkasida (manbalari va litsenziyasi: `menu_assets/SOURCES.md`). Bular
umumiy namunaviy rasmlar: kafening o'z taomlari suratga olingach, botdagi "Rasmi" tugmasi
orqali almashtiriladi.
"""

import argparse
import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import make_engine, make_session_factory
from app.models import Category, Product

ASSETS_DIR = Path(__file__).resolve().parent.parent / "menu_assets"

# Ilovada kategoriyalar shu tartibda chiqadi: avval taomlar, oxirida ichimliklar
CATEGORY_ORDER = ["Taomlar", "Pitsalar", "Shirinliklar", "Choylar"]
# Imlo xatosi bilan kiritilgan nomlar -> to'g'risi
CATEGORY_RENAMES = {"Toamlar": "Taomlar"}
# Shu so'z bilan boshlangan qator o'zgarish emas: nimadir topilmadi va unga tegilmadi
SKIPPED = "O'tkazib yuborildi"


@dataclass(frozen=True)
class Item:
    product_id: int
    name: str
    description: str = ""
    image: str | None = None
    # Kategoriyasiz qolgan taom shu kategoriyaga qo'yiladi (kategoriyasi bor taomga tegilmaydi)
    category: str | None = None


ITEMS = [
    Item(2, "Lavash", category="Taomlar"),
    Item(
        4,
        "Shovurma",
        "Go'sht, yangi sabzavotlar va maxsus sous yupqa lavashga o'ralgan.",
        "shovurma.jpg",
    ),
    Item(
        5,
        "Xodok",
        "Yumshoq bulochka ichida sosiska, sous va yangi sabzavotlar.",
        "xodok.jpg",
    ),
    Item(
        6,
        "Chizburgur",
        "Yumshoq bulochka, go'shtli kotlet, eritilgan pishloq, sabzavot va sous.",
        "chizburger.jpg",
    ),
    Item(
        12,
        "Margherita",
        "Klassik pitsa: pomidor sousi, mozzarella pishlog'i va rayhon.",
        "margherita.jpg",
    ),
    Item(
        13,
        "Pepperoni",
        "Pomidor sousi, mozzarella pishlog'i va achchiqroq pepperoni kolbasasi.",
        "pepperoni.jpg",
    ),
    Item(
        14,
        "Goʻshtli pizza",
        "Pomidor sousi, mozzarella pishlog'i va mo'l go'sht bilan to'yimli pitsa.",
        "goshtli-pizza.jpg",
    ),
    Item(
        11,
        "Shirinliklar",
        "Choy yoniga turli shirinliklar to'plami.",
        "shirinliklar.jpg",
    ),
    Item(
        3,
        "Limon choy",
        "Limon bo'laklari qo'shib damlangan xushbo'y issiq choy.",
        "limon-choy.jpg",
    ),
    Item(
        7,
        "Bardak choy",
        "Katta bardakda tortiladigan yangi damlangan issiq choy.",
        "bardak-choy.jpg",
    ),
    Item(
        8,
        "Stakan choy",
        "Bir stakan yangi damlangan issiq choy.",
        "stakan-choy.jpg",
    ),
    Item(9, "Koffee", "Yangi tayyorlangan xushbo'y issiq qahva.", "kofe-1.jpg"),
    Item(10, "Koffee", "Yangi tayyorlangan xushbo'y issiq qahva.", "kofe-2.jpg"),
]


def _same_name(left: str, right: str) -> bool:
    """Nomlarni solishtiradi: katta-kichik harf va tutuq belgisi turi (ʻ ' ’) farq qilmaydi."""

    def norm(value: str) -> str:
        for mark in "ʻʼ’‘`":
            value = value.replace(mark, "'")
        return " ".join(value.split()).casefold()

    return norm(left) == norm(right)


async def apply(session: AsyncSession, media_dir: Path, dry_run: bool = False) -> list[str]:
    """O'zgarishlarni qo'llaydi (yoki `dry_run`da faqat sanaydi). Nima qilingani ro'yxatini qaytaradi."""
    log: list[str] = []

    categories = list(await session.scalars(select(Category).order_by(Category.id)))
    for category in categories:
        fixed = CATEGORY_RENAMES.get(category.name)
        if fixed and not any(other.name == fixed for other in categories):
            log.append(f"Kategoriya nomi: «{category.name}» -> «{fixed}»")
            category.name = fixed
    by_name = {category.name: category for category in categories}
    # Ro'yxatda yo'q kategoriyalar (keyin qo'shilganlari) o'z tartibida, oxirida qoladi
    rest = [c for c in categories if c.name not in CATEGORY_ORDER]
    rest.sort(key=lambda c: (c.sort_order, c.id))
    ordered = [by_name[name] for name in CATEGORY_ORDER if name in by_name] + rest
    for position, category in enumerate(ordered):
        if category.sort_order != position:
            log.append(f"Kategoriya tartibi: «{category.name}» -> {position + 1}-o'rin")
            category.sort_order = position

    for item in ITEMS:
        product = await session.get(Product, item.product_id)
        if product is None or product.is_deleted or not _same_name(product.name, item.name):
            log.append(f"{SKIPPED} (menyuda topilmadi): #{item.product_id} «{item.name}»")
            continue
        label = f"#{product.id} «{product.name}»"
        if item.description and not (product.description or "").strip():
            log.append(f"Tavsif: {label}")
            product.description = item.description
        if item.image and not product.image_path:
            source = ASSETS_DIR / item.image
            if not source.is_file():
                log.append(f"{SKIPPED} (rasm fayli yo'q): {label} <- {item.image}")
            else:
                log.append(f"Rasm: {label} <- {item.image}")
                if not dry_run:
                    relative = f"products/{uuid4().hex}.jpg"
                    destination = media_dir / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, destination)
                    product.image_path = relative
                    # Bu rasm Telegram'ga yuklanmagan: bot uni keyin o'zi yuklab oladi
                    product.image_file_id = None
        if item.category and product.category_id is None and item.category in by_name:
            log.append(f"Kategoriya: {label} -> «{item.category}»")
            product.category_id = by_name[item.category].id

    if dry_run:
        await session.rollback()
    else:
        await session.commit()
    return log


async def main() -> None:
    parser = argparse.ArgumentParser(description="Mavjud menyuni tavsif va rasmlar bilan to'ldirish")
    parser.add_argument("--dry-run", action="store_true", help="hech narsani o'zgartirmasdan ko'rsatish")
    args = parser.parse_args()

    cfg = get_settings()
    engine = make_engine(cfg.database_url)
    try:
        async with make_session_factory(engine)() as session:
            changes = await apply(session, cfg.media_dir, dry_run=args.dry_run)
    finally:
        await engine.dispose()
    for line in changes:
        print(line)
    count = sum(not line.startswith(SKIPPED) for line in changes)
    if not count:
        print("\nO'zgartiradigan narsa yo'q.")
    elif args.dry_run:
        print(f"\nJami {count} ta o'zgarish (hali qo'llanmadi: --dry-run).")
    else:
        print(f"\nJami {count} ta o'zgarish qo'llandi.")


if __name__ == "__main__":
    asyncio.run(main())
