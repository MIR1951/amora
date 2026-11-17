"""Kim botning boshqaruv qismiga kira oladi va nima qila oladi.

Uch daraja bor:
- egasi: serverdagi AMORA_ADMIN_IDS ro'yxati, hech kim uni botdan o'chira olmaydi;
- admin: botdan taklif qilingan, egasi bilan deyarli bir xil huquqlarga ega;
- xodim: faqat kundalik ish (taom bor/tugadi, qabulni to'xtatish, hisobot, mijoz kartasi).
"""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, F, Router
from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy import select

from app.config import Settings
from app.models import Staff, StaffRole

OWNER = "owner"
ADMIN = StaffRole.ADMIN.value
STAFF = StaffRole.STAFF.value

ROLE_TITLES = {OWNER: "Egasi", ADMIN: "Admin", STAFF: "Xodim"}

# Xodim bosishi mumkin bo'lgan tugmalar (AdminCb.action)
STAFF_ACTIONS = frozenset(
    {"main", "menu", "prod", "prod_on", "prod_off", "pause", "resume", "report", "rep"}
)
# Xodim yozishi mumkin bo'lgan buyruqlar
STAFF_COMMANDS = frozenset({"start", "menu", "bekor", "cancel", "help", "yordam", "mijoz"})


async def resolve_role(user_id: int, cfg: Settings, session_factory) -> str | None:
    if user_id in cfg.admin_id_set:
        return OWNER
    async with session_factory() as session:
        return await session.scalar(select(Staff.role).where(Staff.telegram_id == user_id))


def is_admin(role: str | None) -> bool:
    return role in (OWNER, ADMIN)


class HasAccess(BaseFilter):
    """Foydalanuvchi egasi, admin yoki xodimmi. Ha bo'lsa, handler'ga `role` beriladi."""

    async def __call__(self, event: TelegramObject, cfg: Settings, session_factory) -> bool | dict:
        user = getattr(event, "from_user", None)
        if user is None:
            return False
        role = await resolve_role(user.id, cfg, session_factory)
        return {"role": role} if role else False


# Eski nom: boshqa joylarda shunday ishlatilgan
IsAdmin = HasAccess


def _command_name(text: str | None) -> str | None:
    if not text or not text.startswith("/"):
        return None
    return text[1:].split(maxsplit=1)[0].split("@", 1)[0].lower()


class StaffLimits(BaseMiddleware):
    """Xodimga faqat ruxsat etilgan tugma va buyruqlarni o'tkazadi."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if data.get("role") != STAFF:
            return await handler(event, data)
        if isinstance(event, CallbackQuery):
            from app.telegram.keyboards import AdminCb

            try:
                action = AdminCb.unpack(event.data or "").action
            except (TypeError, ValueError):
                action = None
            if action in STAFF_ACTIONS:
                return await handler(event, data)
            await event.answer("Bu amal faqat admin uchun", show_alert=True)
            return None
        if isinstance(event, Message):
            # Rasm ostidagi izohdagi buyruq ham buyruq (aiogram ikkalasini ham qabul qiladi)
            command = _command_name(event.text or event.caption)
            state = data.get("raw_state")
            if command is None and state is None:
                return await handler(event, data)  # tushunarsiz matn: bosh menyu ko'rsatiladi
            if command in STAFF_COMMANDS:
                return await handler(event, data)
            await event.answer("Bu amal faqat admin uchun.")
            return None
        return await handler(event, data)


def protect(router: Router) -> Router:
    """Router'ni faqat egasi, admin va xodimlar uchun ochadi, xodimga cheklov qo'yadi."""
    router.message.filter(F.chat.type == "private", HasAccess())
    router.callback_query.filter(HasAccess())
    router.message.middleware(StaffLimits())
    router.callback_query.middleware(StaffLimits())
    return router
