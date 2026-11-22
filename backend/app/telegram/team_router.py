"""Adminlar va xodimlar: taklif havolasi orqali qo'shish va olib tashlash."""

import logging
import secrets
from datetime import timedelta

from aiogram import Bot, F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db import utcnow
from app.models import Staff, StaffInvite, StaffRole
from app.telegram import keyboards as kb
from app.telegram import texts
from app.telegram.admin_router import show
from app.telegram.filters import ADMIN, OWNER, ROLE_TITLES, protect, resolve_role
from app.telegram.keyboards import AdminCb
from app.telegram.publisher import SessionFactory

log = logging.getLogger(__name__)

INVITE_HOURS = 24
INVITE_PREFIX = "inv_"

router = protect(Router(name="team"))
# Taklif havolasini hali hech kim bo'lmagan odam bosadi, shuning uchun alohida, ochiq router
invite_router = Router(name="invites")


def can_manage(actor_role: str, target_role: str) -> bool:
    """Egasi hammani, admin esa faqat xodimlarni qo'sha va olib tashlay oladi."""
    if actor_role == OWNER:
        return True
    return actor_role == ADMIN and target_role == StaffRole.STAFF.value


async def load_members(session: AsyncSession) -> list[Staff]:
    rows = await session.scalars(select(Staff).order_by(Staff.role, Staff.created_at, Staff.id))
    return list(rows)


async def show_team(event, session: AsyncSession, cfg: Settings, role: str, notice=None):
    members = await load_members(session)
    await show(
        event,
        texts.team_text(sorted(cfg.admin_id_set), members),
        kb.team_keyboard(members, can_manage_admins=role == OWNER),
        notice,
    )


@router.callback_query(AdminCb.filter(F.action == "team"))
async def cb_team(
    callback: CallbackQuery, session_factory: SessionFactory, cfg: Settings, role: str
):
    async with session_factory() as session:
        await show_team(callback, session, cfg, role)


@router.callback_query(AdminCb.filter(F.action == "team_inv"))
async def cb_team_invite(
    callback: CallbackQuery,
    callback_data: AdminCb,
    bot: Bot,
    session_factory: SessionFactory,
    role: str,
):
    target = callback_data.value
    if target not in (StaffRole.ADMIN.value, StaffRole.STAFF.value) or not can_manage(role, target):
        await callback.answer("Admin qo'shishni faqat egasi qila oladi", show_alert=True)
        return
    token = secrets.token_urlsafe(16)[:22]
    async with session_factory() as session:
        session.add(
            StaffInvite(
                token=token,
                role=target,
                created_by=callback.from_user.id,
                expires_at=utcnow() + timedelta(hours=INVITE_HOURS),
            )
        )
        await session.commit()
    me = await bot.me()
    link = f"https://t.me/{me.username}?start={INVITE_PREFIX}{token}"
    await show(
        callback,
        texts.invite_text(link, target, INVITE_HOURS),
        kb.invite_keyboard(link, texts.invite_share_text(target)),
    )


@router.callback_query(AdminCb.filter(F.action == "team_del"))
async def cb_team_remove(
    callback: CallbackQuery,
    callback_data: AdminCb,
    session_factory: SessionFactory,
    cfg: Settings,
    role: str,
):
    async with session_factory() as session:
        member = await session.get(Staff, callback_data.id)
        if member is None:
            await show_team(callback, session, cfg, role, "Allaqachon olib tashlangan")
            return
        if not can_manage(role, member.role):
            await callback.answer("Adminni faqat egasi olib tashlay oladi", show_alert=True)
            return
        if member.telegram_id == callback.from_user.id:
            await callback.answer("O'zingizni olib tashlay olmaysiz", show_alert=True)
            return
        title = ROLE_TITLES[member.role].lower()
        await show(
            callback,
            f"{texts.escape(member.name)} ({title}) botdan olib tashlansinmi?",
            kb.confirm_remove_keyboard(member.id),
        )


@router.callback_query(AdminCb.filter(F.action == "team_del_yes"))
async def cb_team_remove_yes(
    callback: CallbackQuery,
    callback_data: AdminCb,
    session_factory: SessionFactory,
    cfg: Settings,
    role: str,
):
    async with session_factory() as session:
        member = await session.get(Staff, callback_data.id)
        notice = "Allaqachon olib tashlangan"
        if member is not None:
            if not can_manage(role, member.role) or member.telegram_id == callback.from_user.id:
                await callback.answer("Buni qila olmaysiz", show_alert=True)
                return
            await session.delete(member)
            # U yaratgan, hali ishlatilmagan taklif havolalari ham bekor bo'ladi
            await session.execute(
                update(StaffInvite)
                .where(StaffInvite.created_by == member.telegram_id, StaffInvite.used_by.is_(None))
                .values(expires_at=utcnow())
            )
            await session.commit()
            log.info("%s botdan olib tashlandi (%s)", member.name, callback.from_user.id)
            notice = "Olib tashlandi"
        await show_team(callback, session, cfg, role, notice)


# ---------- Taklif havolasini qabul qilish ----------


@invite_router.message(
    CommandStart(deep_link=True, magic=F.args.startswith(INVITE_PREFIX)),
    F.chat.type == "private",
)
async def accept_invite(
    message: Message,
    command: CommandObject,
    bot: Bot,
    session_factory: SessionFactory,
    cfg: Settings,
):
    user = message.from_user
    token = command.args[len(INVITE_PREFIX) :]
    current = await resolve_role(user.id, cfg, session_factory)
    async with session_factory() as session:
        invite = await session.scalar(
            select(StaffInvite).where(StaffInvite.token == token).with_for_update()
        )
        if invite is None or invite.used_by is not None or invite.expires_at < utcnow():
            await session.commit()
            await message.answer(
                "Bu taklif havolasi eskirgan yoki allaqachon ishlatilgan. "
                "Admindan yangi havola so'rang."
            )
            return
        if user.id == invite.created_by:
            # Havolani yaratgan odam uni tekshirib bosib ko'rsa, havola yonib ketmasin
            await session.commit()
            await message.answer(
                "Bu havolani o'zingiz yaratgansiz. Uni yangi odamga yuboring: "
                "u bosgandagina ishlaydi."
            )
            return
        if current == OWNER:
            await session.commit()
            await message.answer("Siz botning egasisiz, taklif kerak emas. /start ni bosing.")
            return
        # Havolani yaratgan odam hali ham shu huquqqa egami (uni olib tashlagan bo'lishlari mumkin)
        inviter_role = await resolve_role(invite.created_by, cfg, session_factory)
        if inviter_role is None or not can_manage(inviter_role, invite.role):
            await session.commit()
            await message.answer(
                "Bu taklif havolasi endi ishlamaydi. Admindan yangi havola so'rang."
            )
            return
        if current == ADMIN and invite.role == StaffRole.STAFF.value:
            # Taklif hech qachon huquqni kamaytirmaydi: buni faqat egasi qila oladi
            await session.commit()
            await message.answer("Siz allaqachon adminsiz. Boshqaruv menyusi: /start")
            return
        invite.used_by = user.id
        invite.used_at = utcnow()
        member = await session.scalar(select(Staff).where(Staff.telegram_id == user.id))
        name = (user.full_name or user.username or str(user.id))[:100]
        if member is None:
            session.add(
                Staff(telegram_id=user.id, name=name, role=invite.role, added_by=invite.created_by)
            )
        else:
            member.role = invite.role
            member.name = name
        await session.commit()
        role = invite.role
        inviter = invite.created_by

    title = ROLE_TITLES[role].lower()
    log.info("%s (%s) %s bo'lib qo'shildi", name, user.id, role)
    await message.answer(
        f"✅ Siz Amora botiga <b>{title}</b> bo'lib qo'shildingiz. Boshqaruv menyusi: /start"
    )
    try:
        await bot.send_message(inviter, f"✅ {texts.escape(name)} {title} bo'lib qo'shildi.")
    except Exception:  # noqa: BLE001
        log.warning("Taklif qilgan odamga xabar yuborilmadi")
