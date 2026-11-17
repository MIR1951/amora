from fastapi import APIRouter, Request
from sqlalchemy import update

from app.api.deps import CfgDep, CustomerDep, SessionDep
from app.errors import ApiError
from app.models import Customer
from app.schemas import CustomerOut, CustomerUpdate, RegisterIn, RegisterOut
from app.security import hash_token, new_token
from app.services.orders import is_phone_blocked

router = APIRouter(tags=["mijoz"])


@router.post("/auth/register", response_model=RegisterOut, status_code=201, summary="Ro'yxatdan o'tish")
async def register(data: RegisterIn, request: Request, session: SessionDep, cfg: CfgDep) -> RegisterOut:
    """Ism va telefon raqam bilan ro'yxatdan o'tadi. Qaytgan `token` qurilmada saqlanadi
    va keyingi so'rovlarda `Authorization: Bearer <token>` sarlavhasida yuboriladi."""
    ip = request.client.host if request.client else "unknown"
    if not request.app.state.register_limiter.allow(ip):
        raise ApiError(429, "too_many_requests", "Juda ko'p urinish. Birozdan keyin qayta urinib ko'ring")

    token = new_token()
    customer = Customer(
        name=data.name,
        phone=data.phone,
        platform=data.platform,
        token_hash=hash_token(token),
        is_blocked=await is_phone_blocked(session, data.phone),
    )
    session.add(customer)
    await session.commit()
    return RegisterOut(token=token, customer=CustomerOut.model_validate(customer))


@router.get("/me", response_model=CustomerOut, summary="Mening profilim")
async def get_me(customer: CustomerDep) -> Customer:
    return customer


@router.patch("/me", response_model=CustomerOut, summary="Profilni o'zgartirish")
async def update_me(data: CustomerUpdate, customer: CustomerDep, session: SessionDep) -> Customer:
    """Ism, telefon yoki push-xabar tokenini (`fcm_token`) yangilaydi."""
    if data.name is not None:
        customer.name = data.name
    if data.phone is not None and data.phone != customer.phone:
        customer.phone = data.phone
        if await is_phone_blocked(session, data.phone):
            customer.is_blocked = True
    if "fcm_token" in data.model_fields_set:
        token = data.fcm_token or None
        if token is not None:
            # Telefonda boshqa raqam bilan qayta ro'yxatdan o'tilgan: eski mijozga xabar ketmasin
            await session.execute(
                update(Customer)
                .where(Customer.fcm_token == token, Customer.id != customer.id)
                .values(fcm_token=None)
            )
        customer.fcm_token = token
    await session.commit()
    return customer
