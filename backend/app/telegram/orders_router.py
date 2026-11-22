"""Buyurtmalar guruhidagi tugmalar: Qabul qilish, Yo'lga chiqdi, Yetkazildi, Rad etish."""

import asyncio
import logging

from aiogram import Bot, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup

from app.config import Settings
from app.models import ACTIVE_STATUSES, OrderStatus
from app.services.orders import StatusChangeError, get_order, set_status_by_staff
from app.services.push import PushSender, notify_order_status
from app.telegram.keyboards import OrderCb, order_keyboard, reject_reasons_keyboard
from app.telegram.publisher import SessionFactory, current_chat_id, refresh_order_message
from app.telegram.texts import REJECT_REASONS, STATUS_TITLE

log = logging.getLogger(__name__)
router = Router(name="orders")

# Fonda yuborilayotgan push'lar: vazifa tugaguncha havola saqlanadi (aks holda yo'qolib qolishi mumkin)
_push_tasks: set[asyncio.Task] = set()


async def wait_for_pushes(timeout: float = 5.0) -> None:
    """Bot to'xtayotganda yo'ldagi push'lar tugashini kutadi (ko'pi bilan `timeout` soniya)."""
    if _push_tasks:
        await asyncio.wait(list(_push_tasks), timeout=timeout)


def push_in_background(push: PushSender | None, session_factory: SessionFactory, order_id: int) -> None:
    """Mijoz telefoniga xabar: tugma bosgan xodim kutib qolmasligi uchun fonda."""
    if push is None or not push.enabled:
        return
    task = asyncio.create_task(notify_order_status(push, session_factory, order_id))
    _push_tasks.add(task)
    task.add_done_callback(_push_tasks.discard)


ACTION_STATUS = {
    "accept": OrderStatus.ACCEPTED,
    "go": OrderStatus.DELIVERING,
    "done": OrderStatus.DELIVERED,
}


async def _set_keyboard(
    bot: Bot, callback: CallbackQuery, markup: InlineKeyboardMarkup | None
) -> None:
    try:
        await bot.edit_message_reply_markup(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            reply_markup=markup,
        )
    except TelegramBadRequest as error:
        if "message is not modified" not in str(error):
            raise


@router.callback_query(OrderCb.filter())
async def on_order_button(
    callback: CallbackQuery,
    callback_data: OrderCb,
    bot: Bot,
    session_factory: SessionFactory,
    cfg: Settings,
    push: PushSender | None = None,
) -> None:
    order_id = callback_data.id
    action = callback_data.action
    order = None
    if callback.message is not None:
        async with session_factory() as session:
            order = await get_order(session, order_id)

    # Guruh superguruhga aylangan bo'lsa, ID'si o'zgargan: yangisi (bot buyurtmani o'zi
    # yuborgan chat) ham qabul qilinadi
    allowed_chats = {cfg.orders_chat_id, current_chat_id(cfg.orders_chat_id or 0)}
    if order is not None and order.tg_chat_id is not None:
        allowed_chats.add(order.tg_chat_id)
    if callback.message is None or callback.message.chat.id not in allowed_chats:
        await callback.answer("Bu tugma faqat buyurtmalar guruhida ishlaydi", show_alert=True)
        return
    if order is None:
        await callback.answer("Buyurtma topilmadi", show_alert=True)
        return
    if order.tg_message_id is not None and order.tg_message_id != callback.message.message_id:
        # Buyurtma guruhga ikki marta tushib qolgan (Telegram javobi yo'qolgan): bu eski nusxa,
        # u yangilanmaydi. Tugmalari olib tashlanadi, ish asosiy xabarda davom etadi
        await _set_keyboard(bot, callback, None)
        await callback.answer(
            "Bu xabarning nusxasi. Asosiy xabardagi tugmalardan foydalaning", show_alert=True
        )
        return

    # "Rad etish" darhol rad etmaydi: avval sabab so'raydi, "Orqaga" esa tugmalarni qaytaradi
    if action in ("reject", "back"):
        if order.status_enum not in ACTIVE_STATUSES:
            await refresh_order_message(bot, order, cfg.timezone)
            await callback.answer("Bu buyurtma allaqachon yopilgan", show_alert=True)
            return
        if action == "reject":
            await _set_keyboard(bot, callback, reject_reasons_keyboard(order_id))
            await callback.answer("Rad etish sababini tanlang")
        else:
            await _set_keyboard(bot, callback, order_keyboard(order))
            await callback.answer()
        return

    reason = None
    if action == "reason":
        new_status = OrderStatus.REJECTED
        if 0 <= callback_data.reason < len(REJECT_REASONS):
            reason = REJECT_REASONS[callback_data.reason]
    elif action in ACTION_STATUS:
        new_status = ACTION_STATUS[action]
    else:
        await callback.answer()
        return

    actor = callback.from_user.full_name
    try:
        async with session_factory() as session:
            order, changed = await set_status_by_staff(
                session, order_id, new_status, actor, reason
            )
    except StatusChangeError as error:
        if error.order is not None:
            await refresh_order_message(bot, error.order, cfg.timezone)
        await callback.answer(error.message, show_alert=True)
        return

    if changed:
        push_in_background(push, session_factory, order_id)
    await refresh_order_message(bot, order, cfg.timezone)
    if changed:
        log.info("Buyurtma #%s: %s (%s)", order_id, new_status.value, actor)
        await callback.answer(f"№{order_id}: {STATUS_TITLE[new_status]}")
    else:
        await callback.answer("Bu allaqachon belgilangan")
