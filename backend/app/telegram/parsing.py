"""Admin yozgan qiymatlarni tushunish: summa, masofa, ish vaqti."""

import re
from datetime import time

MAX_AMOUNT = 100_000_000

_AMOUNT_NOISE = re.compile(r"(so['’`ʻ]?m|sum|uzs|[\s.,_'’`ʻ])", re.IGNORECASE)
_UNIT = re.compile(r"(so['’`ʻ]?m|sum|uzs)", re.IGNORECASE)
# Oxirida 1 yoki 2 xonali kasr: "35000.00", "12,5" (minglik ajratuvchidan keyin doim 3 ta raqam keladi)
_DECIMAL_TAIL = re.compile(r"[.,]\d{1,2}$")
_HOURS = re.compile(r"^\s*(\d{1,2})(?:[:.](\d{2}))?\s*[-–—]\s*(\d{1,2})(?:[:.](\d{2}))?\s*$")


def parse_amount(raw: str) -> int:
    """ "35 000", "35.000 so'm", "35000" -> 35000. Noto'g'ri bo'lsa ValueError."""
    text = (raw or "").strip()
    # "35000.00" yoki "12,5": nuqta va vergul minglik ajratuvchi deb olib tashlansa, summa 100 baravar
    # oshib ketar edi. So'mda tiyin yo'q, shuning uchun bunday yozuv rad etiladi
    if _DECIMAL_TAIL.search(_UNIT.sub("", text).strip()):
        raise ValueError("Summani tiyinsiz, butun son bilan yozing, masalan: 35000")
    cleaned = _AMOUNT_NOISE.sub("", text)
    if not cleaned.isascii() or not cleaned.isdecimal():
        raise ValueError("Summani faqat raqam bilan yozing, masalan: 35000")
    amount = int(cleaned)
    if amount > MAX_AMOUNT:
        raise ValueError("Summa juda katta")
    return amount


def parse_km(raw: str) -> float:
    """ "5", "3.5", "3,5 km" -> kilometr. Noto'g'ri bo'lsa ValueError."""
    cleaned = re.sub(r"\s*km\s*$", "", (raw or "").strip(), flags=re.IGNORECASE).replace(",", ".")
    try:
        value = float(cleaned)
    except ValueError:
        raise ValueError("Masofani kilometrda yozing, masalan: 5 yoki 3.5") from None
    # `not (0 <= value <= 200)`: "nan" ham shu yerda ushlanadi (u hech narsa bilan taqqoslanmaydi)
    if not (0 <= value <= 200):
        raise ValueError("Masofa 0 dan 200 km gacha bo'lishi kerak")
    return value


def parse_hours(raw: str) -> tuple[time, time]:
    """ "09:00-23:00", "9-23", "18.00 – 02.00" -> (ochilish, yopilish)."""
    match = _HOURS.match(raw or "")
    if not match:
        raise ValueError("Ish vaqtini shunday yozing: 09:00-23:00")
    open_hour, open_minute, close_hour, close_minute = (int(part or 0) for part in match.groups())
    if close_hour == 24 and close_minute == 0:
        close_hour = 0  # "9-24" yarim tungacha degani
    if open_hour > 23 or close_hour > 23 or open_minute > 59 or close_minute > 59:
        raise ValueError("Bunday vaqt yo'q. Namuna: 09:00-23:00")
    return time(open_hour, open_minute), time(close_hour, close_minute)


def parse_discount(raw: str) -> tuple[str, int, int | None]:
    """ "15%" -> foiz; "15% 30000" -> foiz, ko'pi bilan 30 000; "20000" -> so'mda.

    (turi, qiymati, eng ko'p chegirma) qaytaradi. Noto'g'ri bo'lsa ValueError.
    """
    text = (raw or "").strip()
    if "%" in text:
        left, right = text.split("%", 1)
        if not (left.strip().isascii() and left.strip().isdecimal()):
            raise ValueError("Foizni shunday yozing: 15% yoki 15% 30000")
        percent = int(left.strip())
        if not 1 <= percent <= 100:
            raise ValueError("Foiz 1 dan 100 gacha bo'lishi kerak")
        cap = parse_amount(right) if right.strip() else None
        return "percent", percent, cap or None
    try:
        amount = parse_amount(text)
    except ValueError:
        raise ValueError("Chegirmani shunday yozing: 15% yoki 20000") from None
    if amount <= 0:
        raise ValueError("Chegirma 0 dan katta bo'lishi kerak")
    return "amount", amount, None


def parse_count(raw: str, maximum: int, example: str) -> int:
    """Butun son: "0", "100". Noto'g'ri bo'lsa ValueError."""
    cleaned = re.sub(r"[\s_]", "", raw or "")
    if not (cleaned.isascii() and cleaned.isdecimal()) or int(cleaned) > maximum:
        raise ValueError(f"Faqat son yozing, masalan: {example}")
    return int(cleaned)
