"""Admin bo'limi: botga shaxsiy yozishmada, faqat AMORA_ADMIN_IDS ro'yxatidagilar uchun."""

import logging
from pathlib import Path
from uuid import uuid4

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import Category, Product
from app.security import normalize_phone
from app.services import customers as customer_service
from app.services.shop import get_shop, is_open_now
from app.telegram import keyboards as kb
from app.telegram import texts
from app.telegram.filters import STAFF, protect
from app.telegram.keyboards import AdminCb
from app.telegram.texts import escape
from app.telegram.parsing import parse_amount, parse_hours, parse_km
from app.telegram.publisher import SessionFactory

log = logging.getLogger(__name__)


router = protect(Router(name="admin"))


class AddProduct(StatesGroup):
    name = State()
    price = State()
    description = State()
    photo = State()
    category = State()


class EditProduct(StatesGroup):
    value = State()


class EditCategory(StatesGroup):
    name = State()


class EditSetting(StatesGroup):
    value = State()


# ---------- Yordamchi funksiyalar ----------


async def show(
    event: Message | CallbackQuery,
    text: str,
    markup: InlineKeyboardMarkup | None = None,
    notice: str | None = None,
) -> None:
    """Tugma bosilgan bo'lsa o'sha xabarni almashtiradi, aks holda yangi xabar yuboradi."""
    if isinstance(event, Message):
        await event.answer(text, reply_markup=markup)
        return
    message = event.message
    try:
        await event.bot.edit_message_text(
            text, chat_id=message.chat.id, message_id=message.message_id, reply_markup=markup
        )
    except TelegramBadRequest as error:
        if "message is not modified" not in str(error):
            # Eski xabarni tahrirlab bo'lmasa, yangisini yuboramiz
            await event.bot.send_message(message.chat.id, text, reply_markup=markup)
    await event.answer(notice)


async def load_products(session: AsyncSession) -> list[Product]:
    rows = await session.scalars(
        select(Product)
        .where(Product.is_deleted.is_(False))
        .order_by(Product.sort_order, Product.id)
    )
    return list(rows)


async def load_categories(session: AsyncSession) -> list[Category]:
    rows = await session.scalars(
        select(Category)
        .where(Category.is_active.is_(True))
        .order_by(Category.sort_order, Category.id)
    )
    return list(rows)


async def load_product(session: AsyncSession, product_id: int) -> Product | None:
    product = await session.get(Product, product_id)
    return None if product is None or product.is_deleted else product


async def category_name(session: AsyncSession, category_id: int | None) -> str | None:
    if category_id is None:
        return None
    category = await session.get(Category, category_id)
    return category.name if category is not None and category.is_active else None


async def show_main(
    event: Message | CallbackQuery, session: AsyncSession, cfg: Settings, role: str, notice=None
):
    shop = await get_shop(session)
    await session.commit()
    await show(
        event,
        texts.main_menu_text(shop, is_open_now(shop, cfg.timezone), role),
        kb.main_menu_keyboard(shop, role),
        notice,
    )


async def show_menu(
    event: Message | CallbackQuery, session: AsyncSession, notice=None, role: str | None = None
):
    products = await load_products(session)
    full = role != STAFF
    if full:
        text = "🍽 <b>Menyu</b>\n\nTaomni tanlang yoki yangisini qo'shing."
        if not products:
            text = "🍽 <b>Menyu</b>\n\nHozircha taom yo'q. Birinchisini qo'shing."
    else:
        text = "🍽 <b>Menyu</b>\n\nTugagan yoki yana paydo bo'lgan taomni tanlang."
    await show(event, text, kb.menu_keyboard(products, full=full), notice)


async def show_product(
    event: Message | CallbackQuery,
    session: AsyncSession,
    product: Product,
    notice=None,
    role: str | None = None,
):
    await show(
        event,
        texts.product_card(product, await category_name(session, product.category_id)),
        kb.product_keyboard(product, full=role != STAFF),
        notice,
    )


async def show_categories(event: Message | CallbackQuery, session: AsyncSession, notice=None):
    categories = await load_categories(session)
    text = "📂 <b>Kategoriyalar</b>\n\nMasalan: Taomlar, Ichimliklar, Shirinliklar."
    await show(event, text, kb.categories_keyboard(categories), notice)


async def show_settings(event: Message | CallbackQuery, session: AsyncSession, notice=None):
    shop = await get_shop(session)
    await session.commit()
    await show(event, texts.settings_text(shop), kb.settings_keyboard(), notice)


def clean_text(message: Message) -> str:
    return " ".join((message.text or "").split())


async def save_photo(bot: Bot, message: Message, media_dir: Path) -> tuple[str, str]:
    """Rasmni serverga saqlaydi. (media ichidagi yo'l, Telegram file_id) qaytaradi."""
    photo = message.photo[-1]  # eng katta o'lchami
    relative = f"products/{uuid4().hex}.jpg"
    destination = media_dir / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    await bot.download(photo.file_id, destination=destination)
    return relative, photo.file_id


def remove_photo_file(media_dir: Path, relative: str | None) -> None:
    if relative:
        (media_dir / relative).unlink(missing_ok=True)


# ---------- Bosh menyu ----------


@router.message(CommandStart())
@router.message(Command("menu", "bekor", "cancel"))
async def cmd_start(
    message: Message, state: FSMContext, session_factory: SessionFactory, cfg: Settings, role: str
):
    await state.clear()
    async with session_factory() as session:
        await show_main(message, session, cfg, role)


@router.message(Command("help", "yordam"))
async def cmd_help(message: Message, role: str):
    await message.answer(texts.help_text(role))


# ---------- Raqamni bloklash ----------


async def _set_blocked(message: Message, command: CommandObject, session_factory, blocked: bool):
    try:
        phone = normalize_phone(command.args or "")
    except ValueError:
        name = "blok" if blocked else "ochish"
        await message.answer(f"Raqamni buyruqdan keyin yozing, masalan:\n/{name} 901234567")
        return
    async with session_factory() as session:
        changed = await customer_service.set_blocked(session, phone, blocked)
    if changed == 0:
        await message.answer(f"{phone} raqamli mijoz topilmadi.")
    elif blocked:
        await message.answer(f"🚫 {phone} bloklandi. Bu raqamdan endi buyurtma berib bo'lmaydi.")
    else:
        await message.answer(f"✅ {phone} blokdan chiqarildi.")


@router.message(Command("blok", "block"))
async def cmd_block(message: Message, command: CommandObject, session_factory: SessionFactory):
    await _set_blocked(message, command, session_factory, True)


@router.message(Command("ochish", "unblock"))
async def cmd_unblock(message: Message, command: CommandObject, session_factory: SessionFactory):
    await _set_blocked(message, command, session_factory, False)


@router.callback_query(AdminCb.filter(F.action == "main"))
async def cb_main(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: SessionFactory,
    cfg: Settings,
    role: str,
):
    await state.clear()
    async with session_factory() as session:
        await show_main(callback, session, cfg, role)


@router.callback_query(AdminCb.filter(F.action.in_({"pause", "resume"})))
async def cb_toggle_accepting(
    callback: CallbackQuery,
    callback_data: AdminCb,
    session_factory: SessionFactory,
    cfg: Settings,
    role: str,
):
    accepting = callback_data.action == "resume"
    async with session_factory() as session:
        shop = await get_shop(session)
        shop.is_accepting_orders = accepting
        await session.commit()
        notice = "Buyurtmalar yana qabul qilinadi" if accepting else "Buyurtma qabul qilish to'xtatildi"
        await show_main(callback, session, cfg, role, notice)


# ---------- Menyu: taomlar ----------


@router.callback_query(AdminCb.filter(F.action == "menu"))
async def cb_menu(
    callback: CallbackQuery, state: FSMContext, session_factory: SessionFactory, role: str
):
    await state.clear()
    async with session_factory() as session:
        await show_menu(callback, session, role=role)


@router.callback_query(AdminCb.filter(F.action == "prod"))
async def cb_product(
    callback: CallbackQuery,
    callback_data: AdminCb,
    state: FSMContext,
    session_factory: SessionFactory,
    role: str,
):
    await state.clear()
    async with session_factory() as session:
        product = await load_product(session, callback_data.id)
        if product is None:
            await show_menu(callback, session, "Bu taom o'chirilgan", role=role)
            return
        await show_product(callback, session, product, role=role)


@router.callback_query(AdminCb.filter(F.action.in_({"prod_on", "prod_off"})))
async def cb_product_toggle(
    callback: CallbackQuery, callback_data: AdminCb, session_factory: SessionFactory, role: str
):
    available = callback_data.action == "prod_on"
    async with session_factory() as session:
        product = await load_product(session, callback_data.id)
        if product is None:
            await show_menu(callback, session, "Bu taom o'chirilgan", role=role)
            return
        product.is_available = available
        await session.commit()
        notice = "Taom yana sotuvda" if available else "Taom tugagan deb belgilandi"
        await show_product(callback, session, product, notice, role=role)


PRODUCT_PROMPTS = {
    "name": "Taomning yangi nomini yozing.",
    "price": "Yangi narxni so'mda yozing, masalan: 35000",
    "description": "Yangi tavsifni yozing. O'chirish uchun bitta chiziqcha (-) yuboring.",
    "photo": "Taomning rasmini yuboring. Rasmni olib tashlash uchun bitta chiziqcha (-) yuboring.",
}


@router.callback_query(AdminCb.filter(F.action == "prod_edit"))
async def cb_product_edit(callback: CallbackQuery, callback_data: AdminCb, state: FSMContext):
    field = callback_data.value
    if field not in PRODUCT_PROMPTS:
        await callback.answer()
        return
    await state.set_state(EditProduct.value)
    await state.update_data(product_id=callback_data.id, field=field)
    await show(
        callback,
        PRODUCT_PROMPTS[field],
        kb.cancel_keyboard(AdminCb(action="prod", id=callback_data.id)),
    )


@router.message(EditProduct.value)
async def msg_product_edit(
    message: Message, state: FSMContext, bot: Bot, session_factory: SessionFactory, cfg: Settings
):
    data = await state.get_data()
    field = data["field"]
    text = clean_text(message)
    async with session_factory() as session:
        product = await load_product(session, data["product_id"])
        if product is None:
            await state.clear()
            await show_menu(message, session)
            return

        if field == "photo":
            if message.photo:
                old_path = product.image_path
                product.image_path, product.image_file_id = await save_photo(
                    bot, message, cfg.media_dir
                )
                remove_photo_file(cfg.media_dir, old_path)
            elif text == "-":
                remove_photo_file(cfg.media_dir, product.image_path)
                product.image_path = product.image_file_id = None
            else:
                await message.answer("Rasmni fayl emas, oddiy rasm sifatida yuboring.")
                return
        elif field == "name":
            if not text or len(text) > 100:
                await message.answer("Nom 1 dan 100 belgigacha bo'lishi kerak.")
                return
            product.name = text
        elif field == "price":
            try:
                price = parse_amount(text)
            except ValueError as error:
                await message.answer(str(error))
                return
            if price <= 0:
                await message.answer("Narx 0 dan katta bo'lishi kerak.")
                return
            product.price = price
        elif field == "description":
            description = (message.text or "").strip()
            if len(description) > 1000:
                await message.answer("Tavsif 1000 belgidan oshmasin.")
                return
            product.description = "" if description == "-" else description

        await session.commit()
        await state.clear()
        await show_product(message, session, product)


@router.callback_query(AdminCb.filter(F.action == "prod_cat"))
async def cb_product_category(
    callback: CallbackQuery, callback_data: AdminCb, session_factory: SessionFactory
):
    async with session_factory() as session:
        categories = await load_categories(session)
    if not categories:
        await callback.answer("Avval bosh menyudan kategoriya qo'shing", show_alert=True)
        return
    await show(
        callback,
        "Taom qaysi kategoriyada bo'lsin?",
        kb.choose_category_keyboard(categories, "prod_setcat", callback_data.id),
    )


@router.callback_query(AdminCb.filter(F.action == "prod_setcat"))
async def cb_product_set_category(
    callback: CallbackQuery, callback_data: AdminCb, session_factory: SessionFactory
):
    async with session_factory() as session:
        product = await load_product(session, callback_data.id)
        if product is None:
            await show_menu(callback, session, "Bu taom o'chirilgan")
            return
        product.category_id = int(callback_data.value) or None
        await session.commit()
        await show_product(callback, session, product, "Kategoriya o'zgartirildi")


@router.callback_query(AdminCb.filter(F.action == "prod_del"))
async def cb_product_delete(
    callback: CallbackQuery, callback_data: AdminCb, session_factory: SessionFactory
):
    async with session_factory() as session:
        product = await load_product(session, callback_data.id)
    if product is None:
        await callback.answer("Bu taom allaqachon o'chirilgan", show_alert=True)
        return
    await show(
        callback,
        f"«{escape(product.name)}» menyudan butunlay o'chirilsinmi?\n\n"
        "Taom vaqtincha tugagan bo'lsa, o'chirmasdan «Tugadi deb belgilash»ni bosing.",
        kb.confirm_delete_keyboard(product.id),
    )


@router.callback_query(AdminCb.filter(F.action == "prod_del_yes"))
async def cb_product_delete_confirmed(
    callback: CallbackQuery, callback_data: AdminCb, session_factory: SessionFactory
):
    async with session_factory() as session:
        product = await load_product(session, callback_data.id)
        if product is not None:
            # Eski buyurtmalar tarixi buzilmasligi uchun qator bazada qoladi
            product.is_deleted = True
            await session.commit()
        await show_menu(callback, session, "Taom o'chirildi")


# ---------- Menyu: yangi taom ----------


@router.callback_query(AdminCb.filter(F.action == "prod_add"))
async def cb_add_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(AddProduct.name)
    await show(callback, "Yangi taomning nomini yozing.", kb.cancel_keyboard(AdminCb(action="menu")))


@router.message(AddProduct.name)
async def msg_add_name(message: Message, state: FSMContext):
    name = clean_text(message)
    if not name or len(name) > 100:
        await message.answer("Nom 1 dan 100 belgigacha bo'lishi kerak.")
        return
    await state.update_data(name=name)
    await state.set_state(AddProduct.price)
    await message.answer(
        "Narxini so'mda yozing, masalan: 35000",
        reply_markup=kb.cancel_keyboard(AdminCb(action="menu")),
    )


@router.message(AddProduct.price)
async def msg_add_price(message: Message, state: FSMContext):
    try:
        price = parse_amount(clean_text(message))
    except ValueError as error:
        await message.answer(str(error))
        return
    if price <= 0:
        await message.answer("Narx 0 dan katta bo'lishi kerak.")
        return
    await state.update_data(price=price)
    await state.set_state(AddProduct.description)
    await message.answer(
        "Qisqa tavsif yozing (tarkibi, og'irligi).", reply_markup=kb.skip_keyboard("add_skip_desc")
    )


async def ask_photo(event: Message | CallbackQuery, state: FSMContext):
    await state.set_state(AddProduct.photo)
    await show(event, "Taomning rasmini yuboring.", kb.skip_keyboard("add_skip_photo"))


@router.message(AddProduct.description)
async def msg_add_description(message: Message, state: FSMContext):
    description = (message.text or "").strip()
    if not description or len(description) > 1000:
        await message.answer("Tavsifni matn bilan yozing (1000 belgigacha).")
        return
    await state.update_data(description=description)
    await ask_photo(message, state)


@router.callback_query(AdminCb.filter(F.action == "add_skip_desc"), AddProduct.description)
async def cb_add_skip_description(callback: CallbackQuery, state: FSMContext):
    await state.update_data(description="")
    await ask_photo(callback, state)


async def ask_category_or_finish(
    event: Message | CallbackQuery, state: FSMContext, session_factory: SessionFactory
):
    async with session_factory() as session:
        categories = await load_categories(session)
        if categories:
            await state.set_state(AddProduct.category)
            await show(
                event,
                "Taom qaysi kategoriyada bo'lsin?",
                kb.choose_category_keyboard(categories, "add_cat"),
            )
            return
        await finish_add(event, state, session, None)


async def finish_add(
    event: Message | CallbackQuery, state: FSMContext, session: AsyncSession, category_id: int | None
):
    data = await state.get_data()
    last_order = await session.scalar(select(func.max(Product.sort_order)))
    product = Product(
        name=data["name"],
        price=data["price"],
        description=data.get("description", ""),
        image_path=data.get("image_path"),
        image_file_id=data.get("image_file_id"),
        category_id=category_id,
        sort_order=(last_order or 0) + 1,
    )
    session.add(product)
    await session.commit()
    await state.clear()
    await show_product(event, session, product, "Taom qo'shildi")


@router.message(AddProduct.photo, F.photo)
async def msg_add_photo(
    message: Message, state: FSMContext, bot: Bot, session_factory: SessionFactory, cfg: Settings
):
    image_path, file_id = await save_photo(bot, message, cfg.media_dir)
    await state.update_data(image_path=image_path, image_file_id=file_id)
    await ask_category_or_finish(message, state, session_factory)


@router.message(AddProduct.photo)
async def msg_add_photo_wrong(message: Message):
    await message.answer(
        "Rasmni fayl emas, oddiy rasm sifatida yuboring.",
        reply_markup=kb.skip_keyboard("add_skip_photo"),
    )


@router.callback_query(AdminCb.filter(F.action == "add_skip_photo"), AddProduct.photo)
async def cb_add_skip_photo(callback: CallbackQuery, state: FSMContext, session_factory: SessionFactory):
    await ask_category_or_finish(callback, state, session_factory)


@router.callback_query(AdminCb.filter(F.action == "add_cat"), AddProduct.category)
async def cb_add_category(
    callback: CallbackQuery, callback_data: AdminCb, state: FSMContext, session_factory: SessionFactory
):
    async with session_factory() as session:
        await finish_add(callback, state, session, int(callback_data.value) or None)


# ---------- Kategoriyalar ----------


@router.callback_query(AdminCb.filter(F.action == "cats"))
async def cb_categories(callback: CallbackQuery, state: FSMContext, session_factory: SessionFactory):
    await state.clear()
    async with session_factory() as session:
        await show_categories(callback, session)


@router.callback_query(AdminCb.filter(F.action == "cat"))
async def cb_category(callback: CallbackQuery, callback_data: AdminCb, session_factory: SessionFactory):
    async with session_factory() as session:
        category = await session.get(Category, callback_data.id)
        if category is None or not category.is_active:
            await show_categories(callback, session, "Bu kategoriya o'chirilgan")
            return
        count = await session.scalar(
            select(func.count())
            .select_from(Product)
            .where(Product.category_id == category.id, Product.is_deleted.is_(False))
        )
        await show(
            callback,
            f"📂 <b>{escape(category.name)}</b>\nTaomlar soni: {count}",
            kb.category_keyboard(category.id),
        )


@router.callback_query(AdminCb.filter(F.action.in_({"cat_add", "cat_rename"})))
async def cb_category_name(callback: CallbackQuery, callback_data: AdminCb, state: FSMContext):
    await state.set_state(EditCategory.name)
    await state.update_data(category_id=callback_data.id)
    prompt = "Kategoriyaning yangi nomini yozing." if callback_data.id else "Yangi kategoriya nomini yozing."
    await show(callback, prompt, kb.cancel_keyboard(AdminCb(action="cats")))


@router.message(EditCategory.name)
async def msg_category_name(message: Message, state: FSMContext, session_factory: SessionFactory):
    name = clean_text(message)
    if not name or len(name) > 60:
        await message.answer("Nom 1 dan 60 belgigacha bo'lishi kerak.")
        return
    data = await state.get_data()
    async with session_factory() as session:
        category = await session.get(Category, data["category_id"]) if data["category_id"] else None
        if category is not None:
            category.name = name
        else:
            last_order = await session.scalar(select(func.max(Category.sort_order)))
            session.add(Category(name=name, sort_order=(last_order or 0) + 1))
        await session.commit()
        await state.clear()
        await show_categories(message, session)


@router.callback_query(AdminCb.filter(F.action == "cat_del"))
async def cb_category_delete(
    callback: CallbackQuery, callback_data: AdminCb, session_factory: SessionFactory
):
    async with session_factory() as session:
        category = await session.get(Category, callback_data.id)
        if category is not None:
            category.is_active = False
            # Taomlar o'chmaydi, faqat kategoriyasiz qoladi
            await session.execute(
                update(Product).where(Product.category_id == category.id).values(category_id=None)
            )
            await session.commit()
        await show_categories(callback, session, "Kategoriya o'chirildi, taomlari saqlab qolindi")


# ---------- Sozlamalar ----------

SETTING_PROMPTS = {
    "delivery_fee": "Yetkazish narxini so'mda yozing, masalan: 10000\nBepul bo'lsa 0 yozing.",
    "free_delivery_from": (
        "Qancha summadan boshlab yetkazish bepul bo'lsin? Masalan: 100000\n"
        "Bunday chegara kerak bo'lmasa 0 yozing."
    ),
    "min_order_amount": "Eng kam buyurtma summasini yozing, masalan: 30000\nCheklov kerak bo'lmasa 0 yozing.",
    "max_delivery_km": (
        "Kafedan necha kilometrgacha yetkazasiz? Masalan: 5\nCheklov kerak bo'lmasa 0 yozing."
    ),
    "hours": "Ish vaqtini yozing, masalan: 09:00-23:00\nKecha-kunduz ishlasangiz: 00:00-00:00",
    "phone": "Mijozlar qo'ng'iroq qiladigan raqamni yozing, masalan: 90 123 45 67",
    "location": "Kafe joylashuvini yuboring: 📎 tugmasi → Joylashuv (Location).",
    "alert_accept": (
        "Yangi buyurtma necha daqiqa qabul qilinmasa, guruhga eslatma kelsin? Masalan: 5\n"
        "Eslatma kerak bo'lmasa 0 yozing."
    ),
    "alert_delivery": (
        "Buyurtma necha daqiqa yo'lda tursa, guruhga eslatma kelsin? Masalan: 45\n"
        "Eslatma kerak bo'lmasa 0 yozing."
    ),
}


def parse_minutes(raw: str) -> int:
    cleaned = raw.lower().replace("daqiqa", "").replace("min", "").strip()
    if not cleaned.isdigit() or int(cleaned) > 24 * 60:
        raise ValueError("Daqiqani raqam bilan yozing, masalan: 5. O'chirish uchun 0.")
    return int(cleaned)


@router.callback_query(AdminCb.filter(F.action == "settings"))
async def cb_settings(callback: CallbackQuery, state: FSMContext, session_factory: SessionFactory):
    await state.clear()
    async with session_factory() as session:
        await show_settings(callback, session)


@router.callback_query(AdminCb.filter(F.action == "set"))
async def cb_setting_edit(
    callback: CallbackQuery, callback_data: AdminCb, state: FSMContext, session_factory: SessionFactory
):
    key = callback_data.value
    if key == "daily_report":
        async with session_factory() as session:
            shop = await get_shop(session)
            await session.commit()
        await show(
            callback,
            "📊 <b>Kunlik hisobot</b>\n\nKafe yopilganda o'sha kun hisoboti qayerga kelsin?",
            kb.daily_report_keyboard(shop.daily_report_to),
        )
        return
    if key not in SETTING_PROMPTS:
        await callback.answer()
        return
    await state.set_state(EditSetting.value)
    await state.update_data(key=key)
    await show(callback, SETTING_PROMPTS[key], kb.cancel_keyboard(AdminCb(action="settings")))


@router.message(EditSetting.value)
async def msg_setting_value(message: Message, state: FSMContext, session_factory: SessionFactory):
    key = (await state.get_data())["key"]
    text = clean_text(message)
    async with session_factory() as session:
        shop = await get_shop(session)
        try:
            if key == "delivery_fee":
                shop.delivery_fee = parse_amount(text)
            elif key == "free_delivery_from":
                shop.free_delivery_from = parse_amount(text) or None
            elif key == "min_order_amount":
                shop.min_order_amount = parse_amount(text)
            elif key == "max_delivery_km":
                shop.max_delivery_km = parse_km(text) or None
            elif key == "hours":
                shop.open_time, shop.close_time = parse_hours(text)
            elif key == "phone":
                shop.phone = normalize_phone(text)
            elif key == "alert_accept":
                shop.alert_accept_minutes = parse_minutes(text)
            elif key == "alert_delivery":
                shop.alert_delivery_minutes = parse_minutes(text)
            elif key == "location":
                if message.location is None:
                    raise ValueError(SETTING_PROMPTS["location"])
                shop.cafe_latitude = message.location.latitude
                shop.cafe_longitude = message.location.longitude
        except ValueError as error:
            await message.answer(str(error))
            return
        await session.commit()
        await state.clear()
        await show_settings(message, session)


# ---------- Kunlik hisobot sozlamasi ----------


@router.callback_query(AdminCb.filter(F.action == "set_report"))
async def cb_set_daily_report(
    callback: CallbackQuery, callback_data: AdminCb, session_factory: SessionFactory
):
    if callback_data.value not in texts.DAILY_REPORT_TARGETS:
        await callback.answer()
        return
    async with session_factory() as session:
        shop = await get_shop(session)
        shop.daily_report_to = callback_data.value
        await session.commit()
        await show_settings(callback, session, "Saqlandi")


@router.message()
async def msg_unknown(
    message: Message, state: FSMContext, session_factory: SessionFactory, cfg: Settings, role: str
):
    """Tushunarsiz xabar: bosh menyuni ko'rsatamiz."""
    await state.clear()
    async with session_factory() as session:
        await show_main(message, session, cfg, role)
