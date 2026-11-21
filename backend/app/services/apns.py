"""iPhone'ga push-bildirishnoma: Apple Push Notification service (APNs) ga to'g'ridan-to'g'ri.

iOS ilovada Firebase yo'q: ilova Apple'dan olgan qurilma manzilini (64 belgili hex) serverga
yuboradi (`PATCH /me {"fcm_token": ...}`, qurilma `platform="ios"`), server esa shu yerdan
APNs'ga HTTP/2 orqali yuboradi. Android avvalgidek Firebase (push.py) orqali.

Kalit (.p8, Apple Developer → Keys → "Apple Push Notifications service") faqat serverda turadi:
    AMORA_APNS_KEY      .p8 fayl yo'li (masalan /srv/amora/secrets/apns.p8)
    AMORA_APNS_KEY_ID   kalitning Key ID si (10 belgi)
    AMORA_APNS_TEAM_ID  Apple Developer Team ID (10 belgi)
    AMORA_APNS_TOPIC    ilovaning bundle ID si (standart: uz.amora.app)
    AMORA_APNS_SANDBOX  true faqat Xcode'dan o'rnatilgan sinov ilovalari uchun; TestFlight va
                        App Store ilovalari asosiy (production) serverdan oladi
Yozilmagan bo'lsa iPhone'ga push o'chiq, qolgan hamma narsa odatdagidek ishlaydi.
"""

import asyncio
import json
import logging
import re
import time
from pathlib import Path

import httpx
import jwt

log = logging.getLogger(__name__)

PRODUCTION_URL = "https://api.push.apple.com"
SANDBOX_URL = "https://api.sandbox.push.apple.com"
# Apple: kalit (JWT) 20 daqiqadan tez-tez almashtirilmasin va 60 daqiqadan eski bo'lmasin
_TOKEN_TTL = 40 * 60
# Qurilma manzili endi ishlamaydi: ilova o'chirilgan yoki manzil boshqa muhitniki (sinov ilovasi).
# DeviceTokenNotForTopic bu ro'yxatda yo'q: u server sozlamasi xatosi (AMORA_APNS_TOPIC), manzillar o'chirilmasin
_DEAD_REASONS = {"BadDeviceToken", "Unregistered"}
_HEX_TOKEN = re.compile(r"^[0-9a-fA-F]{64}$")


class ApnsError(Exception):
    pass


def looks_like_apns_token(token: str | None) -> bool:
    return bool(token) and bool(_HEX_TOKEN.match(token))


class ApnsSender:
    """APNs'ga xabar yuboradi. Kalit bo'lmasa `enabled` False."""

    def __init__(
        self,
        key_path: Path | None,
        key_id: str = "",
        team_id: str = "",
        topic: str = "uz.amora.app",
        sandbox: bool = False,
        timeout: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._key: str | None = None
        self.key_id = (key_id or "").strip()
        self.team_id = (team_id or "").strip()
        self.topic = topic
        self.base_url = SANDBOX_URL if sandbox else PRODUCTION_URL
        self._timeout = timeout
        self._transport = transport
        self._http: httpx.AsyncClient | None = None
        self._token: str | None = None
        self._token_at = 0.0
        self._lock = asyncio.Lock()
        if key_path is None or not Path(key_path).exists():
            # Kalit hali serverga qo'yilmagan: oddiy holat, xato emas
            log.info("APNs kaliti yo'q (%s): iPhone'ga push-bildirishnomalar o'chiq", key_path)
            return
        try:
            if not self.key_id or not self.team_id:
                raise ValueError("AMORA_APNS_KEY_ID va AMORA_APNS_TEAM_ID ham yozilishi kerak")
            key = Path(key_path).read_text(encoding="utf-8")
            if "BEGIN PRIVATE KEY" not in key:
                raise ValueError(".p8 fayl emas")
            self._sign(key)  # kalit buzuq bo'lsa, bot ishga tushganda bilinadi
            self._key = key
        except (OSError, ValueError, ApnsError) as error:
            log.error(
                "APNs kaliti o'qilmadi (%s): %s. iPhone'ga push-bildirishnomalar o'chiq. "
                "Fayl bormi va konteyner uni o'qiy oladimi (chmod 644) tekshiring.",
                key_path,
                error,
            )

    @property
    def enabled(self) -> bool:
        return self._key is not None

    async def close(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            if self._transport is not None:
                self._http = httpx.AsyncClient(transport=self._transport, timeout=self._timeout)
            else:
                self._http = httpx.AsyncClient(http2=True, timeout=self._timeout)
        return self._http

    def _sign(self, key: str, now: int | None = None) -> str:
        now = int(time.time()) if now is None else now
        try:
            return jwt.encode(
                {"iss": self.team_id, "iat": now},
                key,
                algorithm="ES256",
                headers={"kid": self.key_id},
            )
        except (jwt.PyJWTError, ValueError, TypeError) as error:
            raise ApnsError(f"APNs kaliti yaroqsiz: {error}") from error

    async def _bearer(self, force: bool = False) -> str:
        async with self._lock:
            now = time.time()
            if force or not self._token or now - self._token_at > _TOKEN_TTL:
                self._token = self._sign(self._key, int(now))
                self._token_at = now
            return self._token

    async def send(
        self,
        device_token: str,
        payload: dict,
        *,
        collapse_id: str | None = None,
        ttl: int = 3600,
        priority: int = 10,
    ) -> str | None:
        """Bitta xabar. Natija: None (yetkazildi), "dead" (manzil o'lgan) yoki ApnsError."""
        if not self.enabled:
            return "disabled"
        headers = {
            "apns-topic": self.topic,
            "apns-push-type": "alert",
            "apns-priority": str(priority),
            "apns-expiration": str(int(time.time()) + ttl),
        }
        if collapse_id:
            headers["apns-collapse-id"] = collapse_id[:64]
        url = f"{self.base_url}/3/device/{device_token}"
        body = json.dumps(payload, ensure_ascii=False).encode()
        for attempt in range(2):
            headers["authorization"] = f"bearer {await self._bearer(force=attempt > 0)}"
            response = await self._client().post(url, content=body, headers=headers)
            if response.status_code == 200:
                return None
            reason = _reason(response)
            if response.status_code == 403 and reason == "ExpiredProviderToken" and attempt == 0:
                continue
            if response.status_code == 410 or reason in _DEAD_REASONS:
                return "dead"
            raise ApnsError(f"APNs xatosi ({response.status_code}): {reason or response.text[:200]}")
        raise ApnsError("APNs kalitni qabul qilmadi")


def _reason(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return ""
    return str(data.get("reason", "")) if isinstance(data, dict) else ""
