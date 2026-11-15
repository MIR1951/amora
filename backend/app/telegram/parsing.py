"""Admin yozgan qiymatlarni tushunish: summa, masofa, ish vaqti."""

import re
from datetime import time

MAX_AMOUNT = 100_000_000

_AMOUNT_NOISE = re.compile(r"(so['’`ʻ]?m|sum|uzs|[\s.,_'’`ʻ])", re.IGNORECASE)
_HOURS = re.compile(r"^\s*(\d{1,2})(?:[:.](\d{2}))?\s*[-–—]\s*(\d{1,2})(?:[:.](\d{2}))?\s*$")


def parse_amount(raw: str) -> int:
    """ "35 000", "35.000 so'm", "35000" -> 35000. Noto'g'ri bo'lsa ValueError."""
    cleaned = _AMOUNT_NOISE.sub("", raw or "")
    if not cleaned.isdigit():
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
    if value < 0 or value > 200:
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
