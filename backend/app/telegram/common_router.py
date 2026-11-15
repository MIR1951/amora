"""Hamma uchun ochiq buyruqlar: sozlashda kerak bo'ladigan ID'larni ko'rsatish."""

from aiogram import F, Router
from aiogram.filters import JOIN_TRANSITION, ChatMemberUpdatedFilter, Command, CommandStart
from aiogram.types import ChatMemberUpdated, Message

from app.config import Settings
from app.telegram.filters import IsAdmin

router = Router(name="common")


@router.message(Command("id"))
async def cmd_id(message: Message):
    lines = [f"Chat ID: <code>{message.chat.id}</code>"]
    if message.from_user is not None:
        lines.append(f"Sizning ID: <code>{message.from_user.id}</code>")
    await message.answer("\n".join(lines))


@router.message(CommandStart(), F.chat.type == "private", ~IsAdmin())
async def cmd_start_stranger(message: Message):
    await message.answer(
        "Bu bot Amora kafe xodimlari uchun.\n\n"
        f"Sizning Telegram ID raqamingiz: <code>{message.from_user.id}</code>\n"
        "Admin bo'lish uchun shu raqamni bot egasiga yuboring."
    )


@router.my_chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def on_added_to_chat(event: ChatMemberUpdated, cfg: Settings):
    """Bot guruhga qo'shilganda guruh ID'sini aytadi: uni sozlamaga yozish kerak."""
    if event.chat.type == "private" or event.chat.id == cfg.orders_chat_id:
        return
    await event.answer(
        "Salom! Buyurtmalar shu guruhga kelishi uchun quyidagi raqamni serverdagi "
        f"<code>AMORA_ORDERS_CHAT_ID</code> sozlamasiga yozing:\n\n<code>{event.chat.id}</code>"
    )
