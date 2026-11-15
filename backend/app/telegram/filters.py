from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject

from app.config import Settings


class IsAdmin(BaseFilter):
    """Foydalanuvchi AMORA_ADMIN_IDS ro'yxatida bormi."""

    async def __call__(self, event: TelegramObject, cfg: Settings) -> bool:
        user = getattr(event, "from_user", None)
        return user is not None and user.id in cfg.admin_id_set
