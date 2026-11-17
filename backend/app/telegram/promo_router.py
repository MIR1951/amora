"""Aksiyalar: bosh sahifadagi banner, birinchi buyurtma chegirmasi va promokodlar.

Faqat egasi va adminlar uchun (xodimga StaffLimits yopib qo'yadi).
"""

import logging
from datetime import timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db import utcnow
from app.models import Customer, Order, OrderStatus, PromoCode
from app.services import promos
from app.services.push import PushError, PushSender, broadcast
from app.services.shop import get_shop
from app.telegram import keyboards as kb
from app.telegram import texts
from app.telegram.admin_router import clean_text, show
from app.telegram.filters import protect
from app.telegram.keyboards import AdminCb
from app.telegram.parsing import parse_amount, parse_count, parse_discount
from app.telegram.publisher import SessionFactory

log = logging.getLogger(__name__)

router = protect(Router(name="promo"))

MAX_CODES_SHOWN = 30
# Holatdagi xabar buyruq bo'lsa (/bekor, /start), uni admin bo'limi ushlaydi
NOT_COMMAND = ~F.text.startswith("/")
_VOID = (OrderStatus.CANCELLED.value, OrderStatus.REJECTED.value)


class PromoInput(StatesGroup):
    banner = State()
    auto = State()


class Broadcast(StatesGroup):
    title = State()
    text = State()
    confirm = State()


class NewPromo(StatesGroup):
    code = State()
    discount = State()
    min_order = State()
    limit = State()
    days = State()
    audience = State()


# ---------- Yordamchi ----------


async def load_auto(session: AsyncSession) -> PromoCode | None:
    return await session.scalar(
        select(PromoCode).where(PromoCode.is_auto.is_(True)).order_by(PromoCode.id).limit(1)
    )


async def load_codes(session: AsyncSession) -> list[PromoCode]:
    rows = await session.scalars(
        select(PromoCode)
        .where(PromoCode.is_auto.is_(False))
        .order_by(PromoCode.is_active.desc(), PromoCode.id.desc())
        .limit(MAX_CODES_SHOWN)
    )
    return list(rows)


async def usage(session: AsyncSession, promo_id: int) -> tuple[int, int]:
    """(nechta buyurtmada, jami qancha chegirma) — bekor qilingan va rad etilganlarsiz."""
    row = (
        await session.execute(
            select(func.count(), func.coalesce(func.sum(Order.discount), 0)).where(
                Order.promo_id == promo_id, Order.status.not_in(_VOID)
            )
        )
    ).one()
    return int(row[0]), int(row[1])


async def show_promo_menu(event, session: AsyncSession, notice=None):
    shop = await get_shop(session)
    await session.commit()
    codes = await load_codes(session)
    await show(
        event,
        texts.promo_menu_text(shop, await load_auto(session), codes, utcnow()),
        kb.promo_menu_keyboard(codes),
        notice,
    )


async def show_banner(event, session: AsyncSession, notice=None):
    shop = await get_shop(session)
    await session.commit()
    await show(
        event,
        texts.banner_screen_text(shop),
        kb.banner_keyboard(bool(shop.banner_title or shop.banner_text)),
        notice,
    )


async def show_auto(event, session: AsyncSession, notice=None):
    auto = await load_auto(session)
    given, total = await usage(session, auto.id) if auto is not None else (0, 0)
    active = auto is not None and auto.is_active
    await show(event, texts.auto_promo_text(auto, given, total), kb.auto_promo_keyboard(active), notice)


async def show_card(event, session: AsyncSession, promo: PromoCode, cfg: Settings, notice=None):
    given, total = await usage(session, promo.id)
    await show(
        event,
        texts.promo_card_text(promo, given, total, utcnow(), cfg.timezone),
        kb.promo_card_keyboard(promo),
        notice,
    )


CANCEL = kb.cancel_keyboard(AdminCb(action="promo"))


# ---------- Bosh ekran ----------


@router.callback_query(AdminCb.filter(F.action == "promo"))
async def cb_promo(callback: CallbackQuery, state: FSMContext, session_factory: SessionFactory):
    await state.clear()
    async with session_factory() as session:
        await show_promo_menu(callback, session)


# ---------- Banner ----------


@router.callback_query(AdminCb.filter(F.action == "ban"))
async def cb_banner(callback: CallbackQuery, state: FSMContext, session_factory: SessionFactory):
    await state.clear()
    async with session_factory() as session:
        await show_banner(callback, session)


@router.callback_query(AdminCb.filter(F.action == "ban_edit"))
async def cb_banner_edit(callback: CallbackQuery, callback_data: AdminCb, state: FSMContext):
    field = "title" if callback_data.value == "title" else "text"
    await state.set_state(PromoInput.banner)
    await state.update_data(field=field)
    await show(callback, texts.banner_prompt(field), kb.cancel_keyboard(AdminCb(action="ban")))


@router.message(PromoInput.banner, NOT_COMMAND)
async def msg_banner(message: Message, state: FSMContext, session_factory: SessionFactory):
    field = (await state.get_data()).get("field", "title")
    if field == "title":
        # Sarlavhada qator ko'chirish mumkin (ilovada ikki qator), ortiqcha bo'shliqlar olib tashlanadi
        lines = [" ".join(line.split()) for line in (message.text or "").splitlines()]
        value = "\n".join(line for line in lines if line)[: texts.BANNER_TITLE_MAX + 1]
        limit = texts.BANNER_TITLE_MAX
        if value.count("\n") > 1:
            await message.answer("Sarlavha ko'pi bilan 2 qator bo'lsin.")
            return
    else:
        value = clean_text(message)
        limit = texts.BANNER_TEXT_MAX
    if not value:
        await message.answer("Matn yozing yoki standartga qaytarish uchun - yuboring.")
        return
    if len(value) > limit:
        await message.answer(f"Juda uzun: ko'pi bilan {limit} ta harf bo'lsin.")
        return
    async with session_factory() as session:
        shop = await get_shop(session)
        new_value = None if value == "-" else value
        if field == "title":
            shop.banner_title = new_value
        else:
            shop.banner_text = new_value
        await session.commit()
        await state.clear()
        await show_banner(message, session, "Saqlandi")


@router.callback_query(AdminCb.filter(F.action == "ban_reset"))
async def cb_banner_reset(callback: CallbackQuery, session_factory: SessionFactory):
    async with session_factory() as session:
        shop = await get_shop(session)
        shop.banner_title = None
        shop.banner_text = None
        await session.commit()
        await show_banner(callback, session, "Standart matn qaytdi")


# ---------- Birinchi buyurtma chegirmasi ----------


@router.callback_query(AdminCb.filter(F.action == "auto"))
async def cb_auto(callback: CallbackQuery, state: FSMContext, session_factory: SessionFactory):
    await state.clear()
    async with session_factory() as session:
        await show_auto(callback, session)


@router.callback_query(AdminCb.filter(F.action == "auto_edit"))
async def cb_auto_edit(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PromoInput.auto)
    await show(callback, texts.AUTO_PROMO_PROMPT, kb.cancel_keyboard(AdminCb(action="auto")))


@router.message(PromoInput.auto, NOT_COMMAND)
async def msg_auto(message: Message, state: FSMContext, session_factory: SessionFactory):
    text = clean_text(message)
    turn_off = text == "0"
    if not turn_off:
        try:
            kind, value, cap = parse_discount(text)
        except ValueError as error:
            await message.answer(str(error))
            return
    async with session_factory() as session:
        auto = await load_auto(session)
        if turn_off:
            if auto is not None:
                auto.is_active = False
        else:
            if auto is None:
                auto = PromoCode(is_auto=True, first_order_only=True, created_by=message.from_user.id)
                session.add(auto)
            auto.kind, auto.value, auto.max_discount = kind, value, cap
            auto.is_active = True
        await session.commit()
        await state.clear()
        log.info("Birinchi buyurtma chegirmasi o'zgardi: %s (%s)", text, message.from_user.id)
        await show_auto(message, session, "Saqlandi")


@router.callback_query(AdminCb.filter(F.action == "auto_off"))
async def cb_auto_off(callback: CallbackQuery, session_factory: SessionFactory):
    async with session_factory() as session:
        auto = await load_auto(session)
        if auto is not None:
            auto.is_active = False
            await session.commit()
        await show_auto(callback, session, "O'chirildi")


# ---------- Promokod kartasi ----------


@router.callback_query(AdminCb.filter(F.action == "pc"))
async def cb_card(
    callback: CallbackQuery, callback_data: AdminCb, session_factory: SessionFactory, cfg: Settings
):
    async with session_factory() as session:
        promo = await session.get(PromoCode, callback_data.id)
        if promo is None or promo.is_auto:
            await show_promo_menu(callback, session, "Promokod topilmadi")
            return
        await show_card(callback, session, promo, cfg)


@router.callback_query(AdminCb.filter(F.action.in_({"pc_on", "pc_off"})))
async def cb_card_toggle(
    callback: CallbackQuery, callback_data: AdminCb, session_factory: SessionFactory, cfg: Settings
):
    async with session_factory() as session:
        promo = await session.get(PromoCode, callback_data.id)
        if promo is None or promo.is_auto:
            await show_promo_menu(callback, session, "Promokod topilmadi")
            return
        promo.is_active = callback_data.action == "pc_on"
        await session.commit()
        await show_card(callback, session, promo, cfg, "Yoqildi" if promo.is_active else "To'xtatildi")


@router.callback_query(AdminCb.filter(F.action == "pc_del"))
async def cb_card_delete(callback: CallbackQuery, callback_data: AdminCb, session_factory: SessionFactory):
    async with session_factory() as session:
        promo = await session.get(PromoCode, callback_data.id)
        if promo is None or promo.is_auto:
            await show_promo_menu(callback, session, "Promokod topilmadi")
            return
        await show(
            callback,
            f"<b>{promo.code}</b> promokodi o'chirilsinmi? Berilgan buyurtmalar o'zgarmaydi.",
            kb.confirm_promo_delete_keyboard(promo.id),
        )


@router.callback_query(AdminCb.filter(F.action == "pc_del_yes"))
async def cb_card_delete_yes(
    callback: CallbackQuery, callback_data: AdminCb, session_factory: SessionFactory
):
    async with session_factory() as session:
        promo = await session.get(PromoCode, callback_data.id)
        notice = "Allaqachon o'chirilgan"
        if promo is not None and not promo.is_auto:
            await session.delete(promo)
            await session.commit()
            log.info("Promokod %s o'chirildi (%s)", promo.code, callback.from_user.id)
            notice = "O'chirildi"
        await show_promo_menu(callback, session, notice)


# ---------- Yangi promokod ----------


@router.callback_query(AdminCb.filter(F.action == "pc_add"))
async def cb_add(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(NewPromo.code)
    await show(callback, "🎟 <b>Yangi promokod</b>\n\n" + texts.PROMO_WIZARD["code"], CANCEL)


@router.message(NewPromo.code, NOT_COMMAND)
async def msg_add_code(message: Message, state: FSMContext, session_factory: SessionFactory):
    code = promos.normalize_code(message.text)
    if not promos.CODE_PATTERN.match(code):
        await message.answer(
            "Promokod faqat lotin harflari va raqamlardan iborat bo'lsin, 3–20 ta belgi. "
            "Masalan: AMORA10"
        )
        return
    async with session_factory() as session:
        exists = await session.scalar(select(PromoCode.id).where(PromoCode.code == code))
    if exists:
        await message.answer("Bunday promokod allaqachon bor. Boshqa nom yozing.")
        return
    await state.update_data(code=code)
    await state.set_state(NewPromo.discount)
    await message.answer(texts.PROMO_WIZARD["discount"], reply_markup=CANCEL)


@router.message(NewPromo.discount, NOT_COMMAND)
async def msg_add_discount(message: Message, state: FSMContext):
    try:
        kind, value, cap = parse_discount(clean_text(message))
    except ValueError as error:
        await message.answer(str(error))
        return
    await state.update_data(kind=kind, value=value, cap=cap)
    await state.set_state(NewPromo.min_order)
    await message.answer(texts.PROMO_WIZARD["min_order"], reply_markup=CANCEL)


@router.message(NewPromo.min_order, NOT_COMMAND)
async def msg_add_min_order(message: Message, state: FSMContext):
    try:
        min_order = parse_amount(clean_text(message))
    except ValueError as error:
        await message.answer(str(error))
        return
    await state.update_data(min_order=min_order)
    await state.set_state(NewPromo.limit)
    await message.answer(texts.PROMO_WIZARD["limit"], reply_markup=CANCEL)


@router.message(NewPromo.limit, NOT_COMMAND)
async def msg_add_limit(message: Message, state: FSMContext):
    try:
        limit = parse_count(clean_text(message), 1_000_000, "100")
    except ValueError as error:
        await message.answer(str(error))
        return
    await state.update_data(limit=limit or None)
    await state.set_state(NewPromo.days)
    await message.answer(texts.PROMO_WIZARD["days"], reply_markup=CANCEL)


@router.message(NewPromo.days, NOT_COMMAND)
async def msg_add_days(message: Message, state: FSMContext):
    try:
        days = parse_count(clean_text(message), 3650, "7")
    except ValueError as error:
        await message.answer(str(error))
        return
    await state.update_data(days=days)
    await state.set_state(NewPromo.audience)
    await message.answer(texts.PROMO_WIZARD["audience"], reply_markup=kb.promo_audience_keyboard())


@router.callback_query(AdminCb.filter(F.action == "pc_new"), NewPromo.audience)
async def cb_add_finish(
    callback: CallbackQuery,
    callback_data: AdminCb,
    state: FSMContext,
    session_factory: SessionFactory,
    cfg: Settings,
):
    data = await state.get_data()
    await state.clear()
    promo = PromoCode(
        code=data["code"],
        kind=data["kind"],
        value=data["value"],
        max_discount=data.get("cap"),
        min_order=data.get("min_order", 0),
        usage_limit=data.get("limit"),
        expires_at=utcnow() + timedelta(days=data["days"]) if data.get("days") else None,
        first_order_only=callback_data.value == "1",
        created_by=callback.from_user.id,
    )
    async with session_factory() as session:
        session.add(promo)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            await show_promo_menu(callback, session, "Bunday promokod allaqachon bor")
            return
        log.info("Promokod %s qo'shildi (%s)", promo.code, callback.from_user.id)
        await show_card(callback, session, promo, cfg, "Promokod qo'shildi")


@router.message(NewPromo.audience, NOT_COMMAND)
async def msg_add_audience(message: Message):
    await message.answer("Pastdagi tugmalardan birini bosing.", reply_markup=kb.promo_audience_keyboard())


# ---------- Mijozlarga xabar (push) ----------


@router.callback_query(AdminCb.filter(F.action == "bc"))
async def cb_broadcast(callback: CallbackQuery, state: FSMContext, push: PushSender):
    if not push.enabled:
        await callback.answer(
            "Bildirishnomalar hali sozlanmagan: serverda Firebase kaliti yo'q", show_alert=True
        )
        return
    await state.clear()
    await state.set_state(Broadcast.title)
    await show(callback, texts.BROADCAST_TITLE_PROMPT, CANCEL)


@router.message(Broadcast.title, NOT_COMMAND)
async def msg_broadcast_title(message: Message, state: FSMContext):
    title = clean_text(message)
    if not title:
        await message.answer("Sarlavhani matn bilan yozing.")
        return
    if len(title) > texts.BROADCAST_TITLE_MAX:
        await message.answer(f"Juda uzun: ko'pi bilan {texts.BROADCAST_TITLE_MAX} ta harf bo'lsin.")
        return
    await state.update_data(title=title)
    await state.set_state(Broadcast.text)
    await message.answer(texts.BROADCAST_TEXT_PROMPT, reply_markup=CANCEL)


@router.message(Broadcast.text, NOT_COMMAND)
async def msg_broadcast_text(message: Message, state: FSMContext, session_factory: SessionFactory):
    text = " ".join((message.text or "").split())
    if not text:
        await message.answer("Xabar matnini yozing.")
        return
    if len(text) > texts.BROADCAST_TEXT_MAX:
        await message.answer(f"Juda uzun: ko'pi bilan {texts.BROADCAST_TEXT_MAX} ta harf bo'lsin.")
        return
    await state.update_data(text=text)
    await state.set_state(Broadcast.confirm)
    async with session_factory() as session:
        known = await session.scalar(
            select(func.count()).select_from(Customer).where(Customer.fcm_token.is_not(None))
        )
    title = (await state.get_data())["title"]
    await message.answer(
        texts.broadcast_preview(title, text, known), reply_markup=kb.broadcast_confirm_keyboard()
    )


@router.callback_query(AdminCb.filter(F.action == "bc_send"), Broadcast.confirm)
async def cb_broadcast_send(
    callback: CallbackQuery, state: FSMContext, push: PushSender, session_factory: SessionFactory
):
    data = await state.get_data()
    await state.clear()  # ikki marta bosilsa ikki marta ketmasin
    try:
        await broadcast(push, data["title"], data["text"])
    except PushError as error:
        log.warning("Xabar yuborilmadi: %s", error)
        async with session_factory() as session:
            await show_promo_menu(callback, session, "Yuborilmadi, birozdan keyin qayta urining")
        return
    log.info("Mijozlarga xabar yuborildi: %r (%s)", data["title"], callback.from_user.id)
    async with session_factory() as session:
        await show_promo_menu(callback, session, "📣 Xabar yuborildi")


@router.callback_query(AdminCb.filter(F.action == "bc_send"))
async def cb_broadcast_stale(callback: CallbackQuery, session_factory: SessionFactory):
    async with session_factory() as session:
        await show_promo_menu(callback, session, "Bu xabar allaqachon yuborilgan yoki bekor qilingan")
