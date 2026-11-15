import hashlib
import re
import secrets
import time
from collections import defaultdict, deque


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Bazada tokenning o'zi emas, xeshi saqlanadi: baza o'g'irlansa ham tokenlar ishlamaydi."""
    return hashlib.sha256(token.encode()).hexdigest()


_NON_DIGITS = re.compile(r"\D+")


def normalize_phone(raw: str) -> str:
    """O'zbekiston raqamini +998XXXXXXXXX ko'rinishiga keltiradi.

    Qabul qilinadi: "90 123 45 67", "998901234567", "+998 (90) 123-45-67".
    Noto'g'ri bo'lsa ValueError.
    """
    digits = _NON_DIGITS.sub("", raw or "")
    if len(digits) == 9:
        digits = "998" + digits
    if len(digits) != 12 or not digits.startswith("998"):
        raise ValueError("Telefon raqam noto'g'ri. Namuna: +998 90 123 45 67")
    return "+" + digits


class RateLimiter:
    """Xotiradagi oddiy cheklov: `window` soniya ichida `limit` ta urinish.

    Bitta jarayon uchun yetarli. Bir nechta worker ishlatilsa, har birida alohida hisoblanadi.
    """

    def __init__(self, limit: int, window: float = 3600.0):
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        if len(self._hits) > 10_000:  # xotira o'sib ketmasligi uchun
            self._prune(now)
        return True

    def _prune(self, now: float) -> None:
        for key in [k for k, v in self._hits.items() if not v or now - v[-1] > self.window]:
            del self._hits[key]
