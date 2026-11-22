import logging

from fastapi import APIRouter, BackgroundTasks, Request, Response
from sqlalchemy import update

from app.api.deps import (
    CfgDep,
    CustomerDep,
    DeviceDep,
    NotifierDep,
    OptionalDeviceDep,
    SessionDep,
)
from app.errors import ApiError
from app.models import Customer, CustomerDevice
from app.schemas import (
    CustomerOut,
    CustomerUpdate,
    RegisterIn,
    RegisterOut,
    TelegramCheckIn,
    TelegramCheckOut,
    TelegramStartIn,
    TelegramStartOut,
)
from app.notifier import safe_notify
from app.security import hash_token, new_token
from app.services import customers as customer_service
from app.services import verify
from app.services.orders import is_phone_blocked

log = logging.getLogger(__name__)
router = APIRouter(tags=["mijoz"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post(
    "/auth/register",
    response_model=RegisterOut,
    status_code=201,
    summary="Ro'yxatdan o'tish (eski usul, raqam tasdiqlanmaydi)",
)
async def register(data: RegisterIn, request: Request, session: SessionDep, cfg: CfgDep) -> RegisterOut:
    """Eski ilovalar uchun: ism va telefon bilan, raqamni tekshirmasdan. Bunday mijoz buyurtma
    bera olmaydi, avval `/auth/telegram` orqali raqamini tasdiqlashi kerak.

    Standart holatda o'chiq (`AMORA_ALLOW_LEGACY_REGISTER`): hozirgi ilovalar buni ishlatmaydi."""
    if not cfg.allow_legacy_register:
        raise ApiError(
            410, "update_required", "Ilovaning bu versiyasi eskirgan. Iltimos, ilovani yangilang"
        )
    if not request.app.state.register_limiter.allow(_client_ip(request)):
        raise ApiError(429, "too_many_requests", "Juda ko'p urinish. Birozdan keyin qayta urinib ko'ring")

    token = new_token()
    customer = Customer(
        name=data.name,
        phone=data.phone,
        is_blocked=await is_phone_blocked(session, data.phone),
    )
    customer.devices.append(CustomerDevice(token_hash=hash_token(token), platform=data.platform))
    session.add(customer)
    await session.commit()
    return RegisterOut(token=token, customer=CustomerOut.model_validate(customer))


async def resolve_bot_username(request: Request) -> str | None:
    """Botning @nomi: sozlamada yozilgan bo'lsa o'sha, aks holda Telegram'dan bir marta so'raladi."""
    cfg = request.app.state.settings
    if cfg.bot_username:
        return cfg.bot_username.lstrip("@")
    if request.app.state.bot_username:
        return request.app.state.bot_username
    if not cfg.bot_token:
        return None
    from aiogram import Bot

    bot = Bot(cfg.bot_token)
    try:
        me = await bot.get_me()
    except Exception as error:  # Telegram'ga ulanib bo'lmadi: keyingi so'rovda yana urinamiz
        log.warning("Bot nomini olib bo'lmadi: %s", error)
        return None
    finally:
        await bot.session.close()
    request.app.state.bot_username = me.username
    return me.username


@router.post(
    "/auth/telegram",
    response_model=TelegramStartOut,
    status_code=201,
    summary="Raqamni Telegram orqali tasdiqlashni boshlash",
)
async def telegram_start(
    data: TelegramStartIn, request: Request, session: SessionDep, device: OptionalDeviceDep
) -> TelegramStartOut:
    """Ilova `app_url` (yoki Telegram o'rnatilmagan bo'lsa `bot_url`) havolasini ochadi. Mijoz
    botda "Start" va "📱 Raqamni yuborish" ni bosadi. Ilova shu orada `/auth/telegram/check` ni
    so'rab turadi. Ilovada kirish kaliti bo'lsa, u yuboriladi: shu telefondagi eski buyurtmalar
    tasdiqlangan hisobga o'tadi."""
    if not request.app.state.verify_limiter.allow(_client_ip(request)):
        raise ApiError(429, "too_many_requests", "Juda ko'p urinish. Birozdan keyin qayta urinib ko'ring")
    username = await resolve_bot_username(request)
    if not username:
        raise ApiError(
            503, "verify_unavailable", "Tasdiqlash hozir ishlamayapti. Birozdan keyin qayta urinib ko'ring"
        )
    code = await verify.start(session, data.name, data.platform, device)
    start = f"{verify.START_PREFIX}{code}"
    return TelegramStartOut(
        code=code,
        app_url=f"tg://resolve?domain={username}&start={start}",
        bot_url=f"https://t.me/{username}?start={start}",
        expires_in=int(verify.CODE_TTL.total_seconds()),
    )


@router.post(
    "/auth/telegram/check",
    response_model=TelegramCheckOut,
    summary="Raqam tasdiqlandimi",
)
async def telegram_check(
    data: TelegramCheckIn, session: SessionDep, background: BackgroundTasks, notifier: NotifierDep
) -> TelegramCheckOut:
    """`pending`: mijoz hali botda raqamini yubormadi, bir-ikki soniyadan keyin yana so'rang.
    `verified`: `token` endi shu telefonning kirish kaliti, `customer` mijozning ma'lumotlari.
    Kod eskirgan yoki ishlatib bo'lingan bo'lsa 410."""
    result = await verify.complete(session, data.code)
    if result.status in (verify.CheckStatus.EXPIRED, verify.CheckStatus.UNKNOWN):
        raise ApiError(410, "verification_expired", "Tasdiqlash muddati o'tdi. Qaytadan urinib ko'ring")
    if result.status == verify.CheckStatus.PENDING:
        return TelegramCheckOut(status="pending")
    if result.fresh and result.customer.telegram_user_id is not None:
        # Havolani begona odam yuborgan bo'lsa, hisob egasi bilib qoladi va botdagi tugma bilan
        # barcha telefonlarni hisobdan chiqara oladi
        background.add_task(safe_notify, notifier.signed_in(result.customer.telegram_user_id))
    return TelegramCheckOut(
        status="verified",
        token=result.token,
        customer=CustomerOut.model_validate(result.customer),
    )


@router.get("/me", response_model=CustomerOut, summary="Mening profilim")
async def get_me(customer: CustomerDep) -> Customer:
    return customer


@router.patch("/me", response_model=CustomerOut, summary="Profilni o'zgartirish")
async def update_me(data: CustomerUpdate, device: DeviceDep, session: SessionDep) -> Customer:
    """Ism, telefon yoki shu telefonning push-xabar manzilini (`fcm_token`) yangilaydi.

    Tasdiqlangan raqamni bu yerda o'zgartirib bo'lmaydi: yangi raqam Telegram orqali tasdiqlanadi."""
    customer = device.customer
    if data.name is not None:
        customer.name = data.name
    if data.phone is not None and data.phone != customer.phone:
        if customer.phone_verified:
            raise ApiError(
                409, "phone_locked", "Raqamni almashtirish uchun yangi raqamni Telegram orqali tasdiqlang"
            )
        customer.phone = data.phone
        if await is_phone_blocked(session, data.phone):
            customer.is_blocked = True
    if "fcm_token" in data.model_fields_set:
        token = data.fcm_token or None
        if token is not None:
            # Telefonda boshqa hisob bilan kirilgan: eski hisobga xabar ketmasin
            await session.execute(
                update(CustomerDevice)
                .where(CustomerDevice.fcm_token == token, CustomerDevice.id != device.id)
                .values(fcm_token=None)
            )
        device.fcm_token = token
    await session.commit()
    return customer


@router.post("/auth/logout", status_code=204, summary="Hisobdan chiqish")
async def logout(device: DeviceDep, session: SessionDep) -> Response:
    """Shu telefonning kirish kaliti bekor qilinadi va unga push-xabar yuborilmaydi.
    Mijozning boshqa telefonlari va buyurtmalari joyida qoladi."""
    await customer_service.sign_out_device(session, device.id)
    return Response(status_code=204)


@router.delete("/me", status_code=204, summary="Hisobni o'chirish")
async def delete_me(device: DeviceDep, session: SessionDep) -> Response:
    """Hisob butunlay o'chiriladi: barcha telefonlar chiqariladi, ism, Telegram hisobi, manzillar
    va izohlar o'chadi. Tugallanmagan buyurtma bo'lsa 409 `has_active_orders`."""
    if not await customer_service.delete_account(session, device.customer_id):
        raise ApiError(
            409,
            "has_active_orders",
            "Tugallanmagan buyurtmangiz bor. U yetkazilgach yoki bekor qilingach, hisobni "
            "o'chirishingiz mumkin",
        )
    return Response(status_code=204)
