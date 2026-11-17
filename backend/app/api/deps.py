from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.config import Settings
from app.errors import ApiError
from app.models import Customer, CustomerDevice
from app.notifier import Notifier
from app.security import hash_token

_bearer = HTTPBearer(auto_error=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        yield session


def get_cfg(request: Request) -> Settings:
    return request.app.state.settings


def get_notifier(request: Request) -> Notifier:
    return request.app.state.notifier


SessionDep = Annotated[AsyncSession, Depends(get_session)]
CfgDep = Annotated[Settings, Depends(get_cfg)]
NotifierDep = Annotated[Notifier, Depends(get_notifier)]


async def get_optional_device(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CustomerDevice | None:
    """So'rov yuborgan telefon (kirish kaliti bo'yicha) va uning mijozi."""
    if credentials is None or not credentials.credentials:
        return None
    return await session.scalar(
        select(CustomerDevice)
        .options(joinedload(CustomerDevice.customer))
        .where(CustomerDevice.token_hash == hash_token(credentials.credentials))
    )


async def get_optional_customer(
    device: Annotated[CustomerDevice | None, Depends(get_optional_device)],
) -> Customer | None:
    return device.customer if device is not None else None


async def get_current_customer(
    customer: Annotated[Customer | None, Depends(get_optional_customer)],
) -> Customer:
    if customer is None:
        raise ApiError(401, "unauthorized", "Avval ro'yxatdan o'ting")
    return customer


async def get_current_device(
    device: Annotated[CustomerDevice | None, Depends(get_optional_device)],
) -> CustomerDevice:
    if device is None:
        raise ApiError(401, "unauthorized", "Avval ro'yxatdan o'ting")
    return device


CustomerDep = Annotated[Customer, Depends(get_current_customer)]
DeviceDep = Annotated[CustomerDevice, Depends(get_current_device)]
OptionalDeviceDep = Annotated[CustomerDevice | None, Depends(get_optional_device)]
# Ro'yxatdan o'tmagan mijoz ham ishlata oladigan so'rovlar uchun (savatni hisoblash)
OptionalCustomerDep = Annotated[Customer | None, Depends(get_optional_customer)]
