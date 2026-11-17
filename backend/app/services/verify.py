"""Telefon raqamini Telegram orqali tasdiqlash.

1. Ilova kod so'raydi (`start`) va botni `t.me/<bot>?start=v_<kod>` havolasi bilan ochadi.
2. Mijoz botda "Start" bosadi (`attach_telegram`): kod shu Telegram hisobiga bog'lanadi.
3. Mijoz "📱 Raqamni yuborish" tugmasini bosadi (`confirm_contact`). Telegram faqat hisobning
   o'z raqamini yuboradi, uni qo'lda yozib yoki soxtalashtirib bo'lmaydi.
4. Ilova kodni tekshiradi (`complete`): shu raqamli mijoz topiladi (yoki yaratiladi), qurilma
   unga ulanadi va yangi kirish kaliti beriladi. Bitta raqam = bitta mijoz: shu raqam bilan
   avval tasdiqlanmasdan ochilgan hisoblarning buyurtmalari ham unga o'tadi.
"""

import secrets
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from sqlalchemy import delete, exists, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import utcnow
from app.models import Customer, CustomerDevice, Order, PhoneVerification, VerificationStatus
from app.security import hash_token, new_token, normalize_phone

CODE_TTL = timedelta(minutes=10)
# Raqam botda tasdiqlangach, ilova uni shu vaqt ichida olib ketishi kerak
CONFIRMED_TTL = timedelta(minutes=30)
START_PREFIX = "v_"
DEFAULT_NAME = "Mijoz"


class AttachResult(StrEnum):
    OK = "ok"
    EXPIRED = "expired"  # eskirgan, ishlatilgan yoki topilmadi
    OTHER_USER = "other_user"  # havola boshqa Telegram hisobida ochilgan


class ContactResult(StrEnum):
    OK = "ok"
    NO_REQUEST = "no_request"  # ilovadan so'rov yo'q yoki eskirgan
    BAD_PHONE = "bad_phone"  # O'zbekiston raqami emas


class CheckStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


@dataclass
class CheckResult:
    status: CheckStatus
    token: str | None = None
    customer: Customer | None = None


def _aware(value):
    # SQLite vaqt mintaqasini saqlamaydi: taqqoslash uchun UTC deb olamiz
    from datetime import timezone

    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


async def start(
    session: AsyncSession,
    name: str | None,
    platform: str | None,
    device: CustomerDevice | None,
) -> str:
    """Yangi so'rov. Kodni qaytaradi: u faqat ilovada va bot havolasida bo'ladi."""
    code = secrets.token_urlsafe(16)
    session.add(
        PhoneVerification(
            code_hash=hash_token(code),
            device_id=device.id if device is not None else None,
            name=name or None,
            platform=platform,
            expires_at=utcnow() + CODE_TTL,
        )
    )
    await session.commit()
    return code


async def _by_code(session: AsyncSession, code: str, for_update: bool = False):
    query = select(PhoneVerification).where(PhoneVerification.code_hash == hash_token(code))
    if for_update:
        query = query.with_for_update()
    return await session.scalar(query)


async def attach_telegram(
    session: AsyncSession, code: str, telegram_user_id: int, telegram_name: str
) -> AttachResult:
    """Mijoz botda "Start" bosdi: so'rov shu Telegram hisobiga bog'lanadi."""
    verification = await _by_code(session, code, for_update=True)
    if (
        verification is None
        or verification.status != VerificationStatus.PENDING
        or _aware(verification.expires_at) <= utcnow()
    ):
        await session.rollback()
        return AttachResult.EXPIRED
    if verification.telegram_user_id not in (None, telegram_user_id):
        await session.rollback()
        return AttachResult.OTHER_USER
    verification.telegram_user_id = telegram_user_id
    verification.telegram_name = (telegram_name or "").strip()[:60] or None
    await session.commit()
    return AttachResult.OK


async def confirm_contact(
    session: AsyncSession, telegram_user_id: int, raw_phone: str
) -> tuple[ContactResult, str | None]:
    """Mijoz botda o'z raqamini yubordi. Chaqiruvchi raqam shu hisobniki ekanini tekshirgan."""
    verification = await session.scalar(
        select(PhoneVerification)
        .where(
            PhoneVerification.telegram_user_id == telegram_user_id,
            PhoneVerification.status == VerificationStatus.PENDING.value,
            PhoneVerification.expires_at > utcnow(),
        )
        .order_by(PhoneVerification.id.desc())
        .limit(1)
        .with_for_update()
    )
    if verification is None:
        await session.rollback()
        return ContactResult.NO_REQUEST, None
    try:
        phone = normalize_phone(raw_phone)
    except ValueError:
        await session.rollback()
        return ContactResult.BAD_PHONE, None
    verification.phone = phone
    verification.status = VerificationStatus.CONFIRMED.value
    # Ilova uni olib ketguncha muddat yangilanadi: mijoz Telegram'da biroz qolib ketishi mumkin
    verification.expires_at = utcnow() + CONFIRMED_TTL
    await session.commit()
    return ContactResult.OK, phone


async def complete(session: AsyncSession, code: str) -> CheckResult:
    """Ilova natijani so'raydi. Tasdiqlangan bo'lsa, qurilmani mijozga ulaydi va kalit beradi."""
    verification = await _by_code(session, code, for_update=True)
    if verification is None:
        await session.rollback()
        return CheckResult(CheckStatus.UNKNOWN)
    expired = _aware(verification.expires_at) <= utcnow()
    if verification.status == VerificationStatus.USED or expired:
        await session.rollback()
        return CheckResult(CheckStatus.EXPIRED)
    if verification.status == VerificationStatus.PENDING:
        await session.rollback()
        return CheckResult(CheckStatus.PENDING)

    phone = verification.phone
    telegram_user_id = verification.telegram_user_id
    device = None
    if verification.device_id is not None:
        device = await session.get(CustomerDevice, verification.device_id)
    previous = await session.get(Customer, device.customer_id) if device is not None else None

    # Kim bo'lishidan qat'i nazar, shu raqam yoki shu Telegram hisobi bloklangan bo'lsa, blok qoladi
    blocked = bool(
        await session.scalar(
            select(
                exists().where(
                    Customer.is_blocked.is_(True),
                    or_(Customer.phone == phone, Customer.telegram_user_id == telegram_user_id),
                )
            )
        )
    )

    customer = await session.scalar(
        select(Customer)
        .where(Customer.phone == phone, Customer.phone_verified.is_(True))
        .order_by(Customer.id)
        .limit(1)
    )
    if customer is None:
        # Shu Telegram hisobi avval boshqa raqam bilan tasdiqlangan: raqamini almashtirgan
        customer = await session.scalar(
            select(Customer)
            .where(Customer.telegram_user_id == telegram_user_id, Customer.phone_verified.is_(True))
            .order_by(Customer.id)
            .limit(1)
        )
    if customer is None and previous is not None and not previous.phone_verified:
        customer = previous  # shu telefondagi eski hisob tasdiqlangan hisobga aylanadi
    if customer is None:
        customer = Customer(
            name=verification.name or verification.telegram_name or DEFAULT_NAME, phone=phone
        )
        session.add(customer)
        await session.flush()

    customer.phone = phone
    customer.phone_verified = True
    customer.telegram_user_id = telegram_user_id
    customer.is_blocked = customer.is_blocked or blocked
    await session.execute(
        update(Customer)
        .where(Customer.telegram_user_id == telegram_user_id, Customer.id != customer.id)
        .values(telegram_user_id=None)
    )

    # Shu raqam bilan tasdiqlanmasdan ochilgan hisoblar va shu telefondagi eski hisob birlashadi:
    # buyurtmalari tasdiqlangan mijozga o'tadi, ularning boshqa qurilmalari chiqib ketadi
    merged = set(
        await session.scalars(
            select(Customer.id).where(
                Customer.phone == phone,
                Customer.phone_verified.is_(False),
                Customer.id != customer.id,
            )
        )
    )
    if previous is not None and not previous.phone_verified and previous.id != customer.id:
        merged.add(previous.id)
    if merged:
        await session.execute(
            update(Order).where(Order.customer_id.in_(merged)).values(customer_id=customer.id)
        )
        stale_devices = select(CustomerDevice.id).where(
            CustomerDevice.customer_id.in_(merged),
            CustomerDevice.id != (device.id if device is not None else -1),
        )
        await session.execute(
            update(PhoneVerification)
            .where(PhoneVerification.device_id.in_(stale_devices))
            .values(device_id=None)
        )
        await session.execute(
            delete(CustomerDevice).where(CustomerDevice.id.in_(stale_devices))
        )

    token = new_token()
    if device is None:
        device = CustomerDevice(customer_id=customer.id, token_hash=hash_token(token))
        session.add(device)
    else:
        device.customer_id = customer.id
        device.token_hash = hash_token(token)
    if verification.platform:
        device.platform = verification.platform
    verification.status = VerificationStatus.USED.value
    await session.flush()
    if merged:
        await session.execute(delete(Customer).where(Customer.id.in_(merged)))
    await session.commit()
    await session.refresh(customer)
    return CheckResult(CheckStatus.VERIFIED, token=token, customer=customer)
