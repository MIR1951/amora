"""Mijoz raqamini tasdiqlash: ilova botni `?start=v_<kod>` bilan ochadi, mijoz raqamini yuboradi.

Bu router hamma uchun ochiq (mijozlar admin emas) va boshqa router'lardan oldin turadi.
"""

from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from app.services import customers as customer_service
from app.services import verify
from app.telegram import keyboards as kb
from app.telegram import texts
from app.telegram.publisher import SessionFactory

router = Router(name="verify")
router.message.filter(F.chat.type == "private")


@router.message(CommandStart(deep_link=True, magic=F.args.startswith(verify.START_PREFIX)))
async def start_verification(message: Message, command: CommandObject, session_factory: SessionFactory):
    code = command.args[len(verify.START_PREFIX):]
    user = message.from_user
    async with session_factory() as session:
        result = await verify.attach_telegram(session, code, user.id, user.full_name)
    if result == verify.AttachResult.OK:
        await message.answer(texts.VERIFY_ASK, reply_markup=kb.share_contact_keyboard())
    elif result == verify.AttachResult.OTHER_USER:
        await message.answer(texts.VERIFY_OTHER_USER, reply_markup=ReplyKeyboardRemove())
    else:
        await message.answer(texts.VERIFY_EXPIRED, reply_markup=ReplyKeyboardRemove())


@router.message(F.contact)
async def on_contact(message: Message, session_factory: SessionFactory):
    contact = message.contact
    # Kontaktlar ro'yxatidan boshqa odamning raqami yuborilgan bo'lsa, u bu hisobniki emas
    if contact.user_id != message.from_user.id:
        await message.answer(texts.VERIFY_NOT_OWN, reply_markup=kb.share_contact_keyboard())
        return
    async with session_factory() as session:
        result, phone = await verify.confirm_contact(
            session, message.from_user.id, contact.phone_number
        )
    if result == verify.ContactResult.OK:
        await message.answer(texts.verify_done(phone), reply_markup=ReplyKeyboardRemove())
    elif result == verify.ContactResult.BAD_PHONE:
        await message.answer(texts.VERIFY_BAD_PHONE, reply_markup=ReplyKeyboardRemove())
    else:
        await message.answer(texts.VERIFY_NO_REQUEST, reply_markup=ReplyKeyboardRemove())


@router.callback_query(kb.VerifyCb.filter(F.action == "revoke"))
async def on_revoke(callback: CallbackQuery, session_factory: SessionFactory):
    """"Bu men emas": shu Telegram hisobiga bog'langan mijozning barcha telefonlari chiqariladi."""
    async with session_factory() as session:
        count = await customer_service.sign_out_telegram_account(session, callback.from_user.id)
    await callback.answer()
    if callback.message is not None:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            texts.VERIFY_REVOKED if count else texts.VERIFY_NOTHING_TO_REVOKE
        )
