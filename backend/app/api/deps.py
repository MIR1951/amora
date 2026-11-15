from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.errors import ApiError
from app.models import Customer
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


async def get_current_customer(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Customer:
    if credentials is None or not credentials.credentials:
        raise ApiError(401, "unauthorized", "Avval ro'yxatdan o'ting")
    customer = await session.scalar(
        select(Customer).where(Customer.token_hash == hash_token(credentials.credentials))
    )
    if customer is None:
        raise ApiError(401, "unauthorized", "Avval ro'yxatdan o'ting")
    return customer


CustomerDep = Annotated[Customer, Depends(get_current_customer)]
