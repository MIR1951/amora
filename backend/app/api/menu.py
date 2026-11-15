from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CfgDep, SessionDep
from app.models import Category, Product
from app.schemas import CategoryOut, MenuOut, ProductOut, ShopOut
from app.services.shop import get_shop, is_open_now

router = APIRouter(tags=["menyu"])


def image_url(base_url: str, image_path: str | None) -> str | None:
    return f"{base_url}/media/{image_path}" if image_path else None


@router.get("/menu", response_model=MenuOut, summary="Menyu")
async def get_menu(session: SessionDep, cfg: CfgDep) -> MenuOut:
    """Barcha taomlar. Tugab qolgan taom `is_available: false` bilan qaytadi,
    ilova uni kulrang qilib ko'rsatadi."""
    categories = await session.scalars(
        select(Category)
        .where(Category.is_active.is_(True))
        .order_by(Category.sort_order, Category.id)
    )
    category_list = list(categories)
    active_ids = {category.id for category in category_list}

    products = await session.scalars(
        select(Product)
        .where(Product.is_deleted.is_(False))
        .order_by(Product.sort_order, Product.id)
    )
    return MenuOut(
        categories=[CategoryOut(id=c.id, name=c.name) for c in category_list],
        products=[
            ProductOut(
                id=p.id,
                # O'chirilgan kategoriyadagi taom kategoriyasiz ko'rinadi
                category_id=p.category_id if p.category_id in active_ids else None,
                name=p.name,
                description=p.description,
                price=p.price,
                image_url=image_url(cfg.public_base_url, p.image_path),
                is_available=p.is_available,
            )
            for p in products
        ],
    )


@router.get("/shop", response_model=ShopOut, summary="Kafe ma'lumotlari")
async def get_shop_info(session: SessionDep, cfg: CfgDep) -> ShopOut:
    """Ish vaqti, yetkazish narxi va kafe hozir ochiqmi."""
    shop = await get_shop(session)
    await session.commit()  # birinchi marta chaqirilganda standart qator yaratiladi
    return ShopOut(
        cafe_name=shop.cafe_name,
        phone=shop.phone,
        is_open=is_open_now(shop, cfg.timezone),
        is_accepting_orders=shop.is_accepting_orders,
        open_time=f"{shop.open_time:%H:%M}",
        close_time=f"{shop.close_time:%H:%M}",
        delivery_fee=shop.delivery_fee,
        free_delivery_from=shop.free_delivery_from,
        min_order_amount=shop.min_order_amount,
        max_delivery_km=shop.max_delivery_km,
        cafe_latitude=shop.cafe_latitude,
        cafe_longitude=shop.cafe_longitude,
    )
