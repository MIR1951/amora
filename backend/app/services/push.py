"""Telefonga push-bildirishnoma: Android'ga Firebase Cloud Messaging (HTTP v1), iPhone'ga APNs.

Ilova yopiq bo'lsa ham buyurtma holati haqida xabar yetib boradi. Kafe botdan barcha
mijozlarga aksiya haqida xabar yuborishi ham shu yerdan.

Firebase kaliti (service account JSON) faqat serverda turadi: AMORA_FIREBASE_CREDENTIALS shu faylga
yo'l. iPhone uchun APNs kaliti: app/services/apns.py. Qaysi biri yozilmagan bo'lsa, o'sha telefonlarga
push o'chiq, qolgan hamma narsa odatdagidek ishlaydi.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import aiohttp
import httpx
import jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import STATUS_LABELS, CustomerDevice, Order, OrderStatus
from app.services.apns import ApnsError, ApnsSender, looks_like_apns_token

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
    """FCM'ga (Android) va APNs'ga (iPhone, `apns`) xabar yuboradi. Ikkala kalit ham bo'lmasa,
    hech narsa qilmaydi (`enabled` False)."""

    def __init__(
        self, credentials_path: Path | None, timeout: float = 15.0, apns: ApnsSender | None = None
    ):
        self.apns = apns if apns is not None else ApnsSender(None)
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
        return self.fcm_enabled or self.apns_enabled

    @property
    def fcm_enabled(self) -> bool:
        return self._credentials is not None

    @property
    def apns_enabled(self) -> bool:
        return self.apns.enabled

    async def send_apns(self, device_token: str, payload: dict, **options) -> str | None:
        return await self.apns.send(device_token, payload, **options)

    async def close(self) -> None:
        if self._http is not None:
            await self._http.close()
            self._http = None
        await self.apns.close()

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
        """Bitta FCM xabari. Natija: None (yetkazildi), "dead" (token o'lgan) yoki xato."""
        if not self.fcm_enabled:
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


def order_notice(order: Order) -> tuple[str, str] | None:
    """iPhone bildirishnomasi matni: ilovaning o'zidagi (ios OrderNotifier.orderNotice) bilan bir xil."""
    status = OrderStatus(order.status)
    number = order.id
    if status == OrderStatus.ACCEPTED:
        return f"Buyurtma №{number} qabul qilindi", "Kafe buyurtmangizni tayyorlamoqda."
    if status == OrderStatus.DELIVERING:
        return "Kuryer yo'lda", f"Buyurtma №{number} ni kuryer olib yo'lga chiqdi."
    if status == OrderStatus.DELIVERED:
        return "Buyurtma yetkazildi", f"Buyurtma №{number} yetkazildi. Yoqimli ishtaha!"
    if status == OrderStatus.REJECTED:
        reason = (order.reject_reason or "").strip()
        text = f"Sabab: {reason}" if reason else "Afsuski, kafe buyurtmani qabul qila olmadi."
        return f"Buyurtma №{number} rad etildi", text
    return None


def apns_order_payload(order: Order) -> dict | None:
    """Ilova yopiq bo'lsa tizim ko'rsatadi. Ilova ochiq bo'lsa ilova uni ko'rsatmaydi (jonli ulanish
    o'zi ko'rsatadi). apns-collapse-id "order-<id>" ilovadagi bildirishnoma nomi bilan bir xil:
    biri ikkinchisining o'rnini egallaydi, ikkilanmaydi."""
    notice = order_notice(order)
    if notice is None:
        return None
    title, body = notice
    payload = {
        "aps": {
            "alert": {"title": title, "body": body},
            "sound": "default",
            "thread-id": f"order-{order.id}",
            "category": "orders",
        },
        "type": "order",
        "order_id": order.id,
        "status": OrderStatus(order.status).value,
    }
    if order.reject_reason:
        payload["reject_reason"] = order.reject_reason
    return payload


def apns_broadcast_payload(title: str, text: str) -> dict:
    return {
        "aps": {"alert": {"title": title, "body": text}, "sound": "default", "category": "promo"},
        "type": "promo",
    }


def _is_ios(platform: str | None, token: str) -> bool:
    if platform == "ios":
        return True
    # Eski yozuvlarda platforma yo'q: APNs manzili 64 belgili hex, FCM tokeni esa uzun va ":" li
    return platform is None and looks_like_apns_token(token)


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
    """Buyurtma holati o'zgardi: mijozning barcha telefonlariga xabar (Android FCM, iPhone APNs).
    Xato bo'lsa jurnalga yozadi, xolos. Kamida bittasiga yetkazilsa True."""
    if not sender.enabled:
        return False
    async with session_factory() as session:
        order = await session.get(Order, order_id)
        if order is None or order.status_enum not in NOTIFY_STATUSES:
            return False
        devices = (
            await session.execute(
                select(CustomerDevice.id, CustomerDevice.fcm_token, CustomerDevice.platform).where(
                    CustomerDevice.customer_id == order.customer_id,
                    CustomerDevice.fcm_token.is_not(None),
                )
            )
        ).all()
        apns_payload = apns_order_payload(order)
        jobs = []
        for device_id, token, platform in devices:
            if _is_ios(platform, token):
                if sender.apns_enabled and apns_payload is not None:
                    jobs.append((device_id, token, "apns", apns_payload))
            elif sender.fcm_enabled:
                jobs.append((device_id, token, "fcm", order_message(token, order)))
    delivered = False
    dead: list[tuple[int, str]] = []
    for device_id, token, kind, message in jobs:
        try:
            if kind == "apns":
                result = await sender.send_apns(token, message, collapse_id=f"order-{order_id}")
            else:
                result = await sender.send(message)
        except (PushError, ApnsError, aiohttp.ClientError, httpx.HTTPError, TimeoutError) as error:
            log.warning("Buyurtma #%s haqida push yuborilmadi: %s", order_id, error)
            continue
        except Exception:
            log.exception("Buyurtma #%s haqida push yuborishda kutilmagan xato", order_id)
            continue
        if result == "dead":
            dead.append((device_id, token))
        elif result is None:
            delivered = True
    if dead:
        await _forget_tokens(session_factory, dead)
    return delivered


async def _forget_tokens(session_factory: async_sessionmaker[AsyncSession], dead: list[tuple[int, str]]) -> None:
    async with session_factory() as session:
        for device_id, token in dead:
            await session.execute(
                update(CustomerDevice)
                .where(CustomerDevice.id == device_id, CustomerDevice.fcm_token == token)
                .values(fcm_token=None)
            )
        await session.commit()


async def broadcast(
    sender: PushSender,
    title: str,
    text: str,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Barcha mijozlarga: Android'ga bitta FCM mavzu xabari, iPhone'larga har biriga APNs.
    Hech kimga yuborib bo'lmasa PushError (bot adminga aytadi)."""
    if not sender.enabled:
        raise PushError("Push-bildirishnomalar sozlanmagan")
    errors: list[str] = []
    sent_any = False
    if sender.fcm_enabled:
        try:
            result = await sender.send(broadcast_message(title, text))
            if result is None:
                sent_any = True
            else:
                errors.append("Firebase sozlanmagan")
        except PushError as error:
            errors.append(str(error))
        except (aiohttp.ClientError, TimeoutError) as error:
            errors.append(f"Firebase'ga ulanib bo'lmadi: {error}")
        except Exception as error:
            log.exception("Aksiya xabarini yuborishda kutilmagan xato")
            errors.append(f"Kutilmagan xato: {error}")
    if sender.apns_enabled and session_factory is not None:
        ok, failed = await _broadcast_apns(sender, session_factory, title, text)
        sent_any = sent_any or ok > 0
        if failed and not ok:
            errors.append(f"iPhone'larga yuborilmadi ({failed} ta)")
    if not sent_any and errors:
        raise PushError("; ".join(errors))


async def _broadcast_apns(
    sender: PushSender, session_factory: async_sessionmaker[AsyncSession], title: str, text: str
) -> tuple[int, int]:
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(CustomerDevice.id, CustomerDevice.fcm_token, CustomerDevice.platform).where(
                    CustomerDevice.fcm_token.is_not(None)
                )
            )
        ).all()
    targets = [(device_id, token) for device_id, token, platform in rows if _is_ios(platform, token)]
    payload = apns_broadcast_payload(title, text)
    limit = asyncio.Semaphore(20)  # HTTP/2: bitta ulanishda bir nechta so'rov parallel
    dead: list[tuple[int, str]] = []
    counts = {"ok": 0, "failed": 0}

    async def one(device_id: int, token: str) -> None:
        async with limit:
            try:
                result = await sender.send_apns(token, payload, ttl=86400, priority=5)
            except (ApnsError, httpx.HTTPError, TimeoutError) as error:
                log.warning("Aksiya xabari iPhone'ga yuborilmadi: %s", error)
                counts["failed"] += 1
                return
            except Exception:
                log.exception("Aksiya xabarini iPhone'ga yuborishda kutilmagan xato")
                counts["failed"] += 1
                return
            if result == "dead":
                dead.append((device_id, token))
            elif result is None:
                counts["ok"] += 1

    await asyncio.gather(*(one(device_id, token) for device_id, token in targets))
    if dead:
        await _forget_tokens(session_factory, dead)
    return counts["ok"], counts["failed"]
