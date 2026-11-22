"""`python -m app.menu_content`: hozirgi menyuni to'ldiradi, taom qo'shmaydi va o'chirmaydi."""

from sqlalchemy import select

from app.menu_content import ASSETS_DIR, ITEMS, apply
from app.models import Category, Product

# Serverdagi menyuning nusxasi (2026-11-22): id, kategoriya, nom, tavsif, narx, rasm
LIVE_CATEGORIES = [(1, "Choylar"), (2, "Toamlar"), (3, "Pitsalar"), (4, "Shirinliklar")]
LIVE_PRODUCTS = [
    (2, None, "Lavash", "mol go'shtli lavash , 450 gram", 45000, "products/real-lavash.jpg"),
    (3, 1, "Limon choy", "", 25000, None),
    (4, 2, "Shovurma", "", 30000, None),
    (5, 2, "Xodok", "", 20000, None),
    (6, 2, "Chizburgur", "", 30000, None),
    (7, 1, "Bardak choy", "", 25000, None),
    (8, 1, "Stakan choy", "", 5000, None),
    (9, 1, "Koffee", "", 10000, None),
    (10, 1, "Koffee", "", 20000, None),
    (11, 4, "Shirinliklar", "", 20000, None),
    (12, 3, "Margherita", "", 60000, None),
    (13, 3, "Pepperoni", "", 60000, None),
    (14, 3, "Goʻshtli pizza", "", 60000, None),
]


async def load_live_menu(session_factory) -> None:
    async with session_factory() as session:
        for category_id, name in LIVE_CATEGORIES:
            session.add(Category(id=category_id, name=name, sort_order=0))
        for product_id, category_id, name, description, price, image in LIVE_PRODUCTS:
            session.add(
                Product(
                    id=product_id, category_id=category_id, name=name,
                    description=description, price=price, image_path=image,
                )
            )
        await session.commit()


async def snapshot(session_factory) -> dict:
    async with session_factory() as session:
        products = list(await session.scalars(select(Product).order_by(Product.id)))
        categories = list(
            await session.scalars(select(Category).order_by(Category.sort_order, Category.id))
        )
        return {
            "products": {p.id: (p.name, p.price, p.description, p.image_path, p.category_id) for p in products},
            "categories": [c.name for c in categories],
        }


def test_every_listed_photo_exists():
    for item in ITEMS:
        if item.image:
            assert (ASSETS_DIR / item.image).is_file(), item.image


async def test_fills_menu_without_adding_or_removing_dishes(engine, session_factory, tmp_path):
    await load_live_menu(session_factory)
    before = await snapshot(session_factory)
    async with session_factory() as session:
        changes = await apply(session, tmp_path)
    after = await snapshot(session_factory)

    assert not any("O'tkazib yuborildi" in line for line in changes)
    # Taomlar soni, nomlari va narxlari o'sha-o'sha
    assert set(after["products"]) == set(before["products"]) and len(after["products"]) == 13
    for product_id, (name, price, *_rest) in before["products"].items():
        assert after["products"][product_id][:2] == (name, price)
    # Avval taomlar, oxirida choylar; imlo xatosi tuzatilgan
    assert after["categories"] == ["Taomlar", "Pitsalar", "Shirinliklar", "Choylar"]
    # Kafe o'zi kiritgan tavsif va rasmga tegilmagan, faqat kategoriyasi qo'yilgan
    name, _, description, image, category_id = after["products"][2]
    assert (description, image) == ("mol go'shtli lavash , 450 gram", "products/real-lavash.jpg")
    assert category_id == 2
    # Qolgan hammasida tavsif va rasm bor, rasm fayli joyida
    for product_id, (_, _, description, image, category_id) in after["products"].items():
        assert description and image and category_id, product_id
        if product_id != 2:
            assert (tmp_path / image).is_file()


async def test_second_run_changes_nothing(engine, session_factory, tmp_path):
    await load_live_menu(session_factory)
    async with session_factory() as session:
        assert await apply(session, tmp_path)
    async with session_factory() as session:
        assert await apply(session, tmp_path) == []


async def test_dry_run_touches_nothing(engine, session_factory, tmp_path):
    await load_live_menu(session_factory)
    before = await snapshot(session_factory)
    async with session_factory() as session:
        assert await apply(session, tmp_path, dry_run=True)
    assert await snapshot(session_factory) == before
    assert not list(tmp_path.iterdir())


async def test_renamed_dish_is_left_alone(engine, session_factory, tmp_path):
    await load_live_menu(session_factory)
    async with session_factory() as session:
        (await session.get(Product, 5)).name = "Burger"  # id 5 endi boshqa taom
        await session.commit()
    async with session_factory() as session:
        changes = await apply(session, tmp_path)
    assert any("#5" in line and "O'tkazib yuborildi" in line for line in changes)
    assert (await snapshot(session_factory))["products"][5][2:4] == ("", None)
