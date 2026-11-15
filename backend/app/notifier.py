"""Buyurtma hodisalari haqida xabar berish.

API buyurtma yaratilganda yoki mijoz bekor qilganda shu interfeysni chaqiradi.
Telegram guruhga xabar yuboruvchi haqiqiy amalga oshirish bot bilan birga qo'shiladi.
"""

import logging
from typing import Protocol

log = logging.getLogger(__name__)


class Notifier(Protocol):
    async def order_created(self, order_id: int) -> None: ...

    async def order_cancelled(self, order_id: int) -> None: ...


class NullNotifier:
    """Hech qayerga yubormaydi, faqat logga yozadi (testlar va bot sozlanmagan holat uchun)."""

    async def order_created(self, order_id: int) -> None:
        log.info("Yangi buyurtma #%s (xabar yuboruvchi sozlanmagan)", order_id)

    async def order_cancelled(self, order_id: int) -> None:
        log.info("Buyurtma #%s bekor qilindi (xabar yuboruvchi sozlanmagan)", order_id)


async def safe_notify(coro) -> None:
    """Telegram ishlamay qolsa ham mijozning so'rovi xato bilan tugamasligi kerak."""
    try:
        await coro
    except Exception:  # noqa: BLE001
        log.exception("Xabar yuborishda xato")
