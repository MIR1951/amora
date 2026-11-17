"""Telefonga push-bildirishnoma: Firebase Cloud Messaging (HTTP v1).

Ilova yopiq bo'lsa ham buyurtma holati haqida xabar yetib boradi. Kafe botdan barcha
mijozlarga aksiya haqida xabar yuborishi ham shu yerdan.

Kalit (service account JSON) faqat serverda turadi: AMORA_FIREBASE_CREDENTIALS shu faylga
yo'l. Yozilmagan bo'lsa push o'chiq, qolgan hamma narsa odatdagidek ishlaydi.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import aiohttp
import jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import STATUS_LABELS, Customer, Order, OrderStatus

log = logging.getLogger(__name__)

SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
SEND_URL = "https://fcm.googleapis.com/v1/projects/{project}/messages:send"
# Ilova o'rnatilgan har bir telefon shu mavzuga yoziladi: aksiya xabari hammaga bitta so'rov
BROADCAST_TOPIC = "all"
# Mijozga xabar beriladigan holatlar (yangi va bekor qilingan buyurtmani mijoz o'zi biladi)
NOTIFY_STATUSES = {
    OrderStatus.ACCEPTED,
    OrderStatus.DELIVERING,
    OrderStatus.DELIVERED,
    OrderStatus.REJECTED,
}
# Token endi ishlamaydi: ilova o'chirilgan yoki qayta o'rnatilgan
_DEAD_TOKEN_CODES = {"UNREGISTERED", "INVALID_ARGUMENT", "NOT_FOUND", "SENDER_ID_MISMATCH"}


class PushError(Exception):
    pass


@dataclass
class _Credentials:
    project_id: str
    client_email: str
    private_key: str
    private_key_id: str
    token_uri: str


def load_credentials(path: Path) -> _Credentials:
    data = json.loads(path.read_text(encoding="utf-8"))
    return _Credentials(
        project_id=data["project_id"],
        client_email=data["client_email"],
        private_key=data["private_key"],
        private_key_id=data.get("private_key_id", ""),
        token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
    )


class PushSender:
    """FCM'ga xabar yuboradi. Kalit fayli bo'lmasa, hech narsa qilmaydi (`enabled` False)."""

    def __init__(self, credentials_path: Path | None, timeout: float = 15.0):
        self._credentials: _Credentials | None = None
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._http: aiohttp.ClientSession | None = None
        self._access_token: str | None = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()
        if credentials_path is None:
            log.info("AMORA_FIREBASE_CREDENTIALS yozilmagan: push-bildirishnomalar o'chiq")
            return
        try:
            credentials = load_credentials(Path(credentials_path))
            _sign(credentials)  # kalit buzuq bo'lsa (masalan nusxalashda qatorlar buzilgan), darhol bilinadi
            self._credentials = credentials
        except (OSError, ValueError, KeyError, TypeError, PushError) as error:
            log.error(
                "Firebase kaliti o'qilmadi (%s): %s. Push-bildirishnomalar o'chiq. "
                "Fayl bormi va konteyner uni o'qiy oladimi (chmod 644) tekshiring.",
                credentials_path,
                error,
            )

    @property
    def enabled(self) -> bool:
        return self._credentials is not None

    async def close(self) -> None:
        if self._http is not None:
            await self._http.close()
            self._http = None

    def _session(self) -> aiohttp.ClientSession:
        if self._http is None or self._http.closed:
            self._http = aiohttp.ClientSession(timeout=self._timeout)
        return self._http

    async def _token(self) -> str:
        async with self._lock:
            if self._access_token and time.time() < self._expires_at - 300:
                return self._access_token
            creds = self._credentials
            now = int(time.time())
            assertion = _sign(creds, now)
            async with self._session().post(
                creds.token_uri,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion,
                },
            ) as response:
                body = await _read_body(response)
                if response.status != 200 or "access_token" not in body:
                    raise PushError(f"Google kirish kaliti berilmadi ({response.status}): {body}")
            self._access_token = body["access_token"]
            self._expires_at = now + int(body.get("expires_in", 3600))
            return self._access_token

    async def send(self, message: dict) -> str | None:
        """Bitta xabar yuboradi. Natija: None (yetkazildi), "dead" (token o'lgan) yoki xato."""
        if not self.enabled:
            return "disabled"
        url = SEND_URL.format(project=self._credentials.project_id)
        for attempt in range(2):
            token = await self._token()
            async with self._session().post(
                url,
                json={"message": message},
                headers={"Authorization": f"Bearer {token}"},
            ) as response:
                if response.status == 200:
                    return None
                body = await _read_body(response)
            if response.status == 401 and attempt == 0:
                self._access_token = None  # kalit muddatidan oldin bekor qilingan: yangisini olamiz
                continue
            if _is_dead_token(response.status, body) and "token" in message:
                return "dead"
            raise PushError(f"FCM xatosi ({response.status}): {body}")
        raise PushError("FCM kirish kaliti qabul qilinmadi")


def _sign(creds: _Credentials, now: int | None = None) -> str:
    """Google'ga o'zimizni tanitadigan imzolangan so'rov (service account JWT)."""
    now = int(time.time()) if now is None else now
    try:
        return jwt.encode(
            {
                "iss": creds.client_email,
                "scope": SCOPE,
                "aud": creds.token_uri,
                "iat": now,
                "exp": now + 3600,
            },
            creds.private_key,
            algorithm="RS256",
            headers={"kid": creds.private_key_id} if creds.private_key_id else None,
        )
    except (jwt.PyJWTError, ValueError, TypeError) as error:
        raise PushError(f"Firebase kaliti yaroqsiz: {error}") from error


async def _read_body(response: aiohttp.ClientResponse) -> dict:
    """Javob tanasi. Google ba'zan (502/503) JSON o'rniga HTML sahifa qaytaradi."""
    text = await response.text()
    try:
        body = json.loads(text) if text else {}
    except ValueError:
        return {"raw": text[:300]}
    return body if isinstance(body, dict) else {"raw": text[:300]}


def _is_dead_token(status: int, body: dict) -> bool:
    error = (body or {}).get("error", {}) if isinstance(body, dict) else {}
    codes = {error.get("status")}
    for detail in error.get("details", []) or []:
        codes.add(detail.get("errorCode"))
    return status in (400, 404) and bool(codes & _DEAD_TOKEN_CODES)


def order_message(token: str, order: Order) -> dict:
    """Buyurtma holati: faqat ma'lumot (data). Bildirishnomani ilovaning o'zi ko'rsatadi,
    shunda jonli ulanish orqali kelgan xuddi shu xabar bilan ikkilanmaydi."""
    status = OrderStatus(order.status)
    data = {
        "type": "order",
        "order_id": str(order.id),
        "status": status.value,
        "status_label": STATUS_LABELS[status],
    }
    if order.reject_reason:
        data["reject_reason"] = order.reject_reason
    return {
        "token": token,
        "data": data,
        # Telefon uxlab yotgan bo'lsa ham darhol uyg'otadi; bir soatdan keyin ahamiyati yo'q
        "android": {"priority": "HIGH", "ttl": "3600s"},
    }


def broadcast_message(title: str, text: str) -> dict:
    """Aksiya xabari: tizim o'zi ko'rsatadi (ilova yopiq bo'lsa ham), "promo" kanalida."""
    return {
        "topic": BROADCAST_TOPIC,
        "notification": {"title": title, "body": text},
        "data": {"type": "promo", "title": title, "body": text},
        "android": {
            "priority": "HIGH",
            "ttl": "86400s",
            "notification": {"channel_id": "promo"},
        },
    }


async def notify_order_status(
    sender: PushSender, session_factory: async_sessionmaker[AsyncSession], order_id: int
) -> bool:
    """Buyurtma holati o'zgardi: mijoz telefoniga xabar. Xato bo'lsa jurnalga yozadi, xolos."""
    if not sender.enabled:
        return False
    async with session_factory() as session:
        row = (
            await session.execute(
                select(Order, Customer.fcm_token)
                .join(Customer, Customer.id == Order.customer_id)
                .where(Order.id == order_id)
            )
        ).first()
        if row is None:
            return False
        order, token = row
        if not token or order.status_enum not in NOTIFY_STATUSES:
            return False
        message = order_message(token, order)
        customer_id = order.customer_id
    try:
        result = await sender.send(message)
    except (PushError, aiohttp.ClientError, TimeoutError) as error:
        log.warning("Buyurtma #%s haqida push yuborilmadi: %s", order_id, error)
        return False
    except Exception:
        log.exception("Buyurtma #%s haqida push yuborishda kutilmagan xato", order_id)
        return False
    if result == "dead":
        async with session_factory() as session:
            await session.execute(
                update(Customer)
                .where(Customer.id == customer_id, Customer.fcm_token == token)
                .values(fcm_token=None)
            )
            await session.commit()
        return False
    return result is None


async def broadcast(sender: PushSender, title: str, text: str) -> None:
    """Barcha mijozlarga. Xato bo'lsa PushError (bot adminga aytadi)."""
    try:
        result = await sender.send(broadcast_message(title, text))
    except PushError:
        raise
    except (aiohttp.ClientError, TimeoutError) as error:
        raise PushError(f"Firebase'ga ulanib bo'lmadi: {error}") from error
    except Exception as error:
        log.exception("Aksiya xabarini yuborishda kutilmagan xato")
        raise PushError(f"Kutilmagan xato: {error}") from error
    if result is not None:
        raise PushError("Push-bildirishnomalar sozlanmagan")
