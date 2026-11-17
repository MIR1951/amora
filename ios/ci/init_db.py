#!/usr/bin/env python3
"""iOS sinovi uchun SQLite sinov bazasida jadvallarni yaratadi.

    cd backend && python ../ios/ci/init_db.py

macOS runner'da docker yo'q, shuning uchun PostgreSQL o'rniga SQLite fayli ishlatiladi.
Alembic migratsiyalari SQLite'da ishlamaydi (0003 va 0004 cheklovlarni ALTER bilan o'zgartiradi,
0004 PostgreSQL'ning md5(random()::text) ifodasini ishlatadi). Shuning uchun jadvallar
backend testlari (tests/conftest.py) kabi to'g'ridan-to'g'ri modellardan yaratiladi.
Baza manzili AMORA_DATABASE_URL dan olinadi va u faqat sqlite bo'lishi kerak.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app import models  # noqa: E402,F401  (jadvallar Base.metadata'ga yozilishi uchun)
from app.config import get_settings  # noqa: E402
from app.db import Base, make_engine  # noqa: E402


async def main() -> None:
    url = get_settings().database_url
    if not url.startswith("sqlite"):
        raise SystemExit(f"Bu skript faqat SQLite sinov bazasi uchun: {url}")
    engine = make_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print(f"Jadvallar yaratildi: {', '.join(sorted(Base.metadata.tables))}")


if __name__ == "__main__":
    asyncio.run(main())
