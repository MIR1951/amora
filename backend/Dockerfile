FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv/amora

# Aniq versiyalar va xeshlar `requirements.lock`da: serverda ham, testlarda ham bir xil kutubxonalar
# o'rnatiladi. Yangilash: README, "Kutubxonalarni yangilash".
COPY requirements.lock .
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

COPY alembic.ini .
COPY migrations ./migrations
COPY app ./app
# Menyu uchun namunaviy rasmlar (python -m app.menu_content)
COPY menu_assets ./menu_assets

RUN useradd --create-home --uid 1000 amora && mkdir -p /srv/amora/media && chown -R amora /srv/amora
USER amora

EXPOSE 8000

# Avval baza sxemasi yangilanadi, keyin server ishga tushadi. `exec`: server konteynerning asosiy
# jarayoni bo'ladi va `docker stop` signalini o'zi oladi (aks holda signal qobiqda qolib ketadi,
# server toza to'xtamaydi va Docker uni 10 soniyadan keyin majburan o'chiradi).
#
# `--workers` qo'shmang: so'rovlar cheklovi va jonli ulanishlar soni jarayon xotirasida sanaladi,
# bir nechta jarayonda har biri alohida sanaydi.
#
# AMORA_FORWARDED_ALLOW_IPS: X-Forwarded-For sarlavhasiga qaysi manzildan kelganda ishoniladi.
# Port faqat 127.0.0.1 da ochiq bo'lsa `*` xavfsiz. Konteyner umumiy Docker tarmog'iga (masalan,
# Caddy bilan) ulangan bo'lsa, .env da proksining manzilini yoki tarmog'ini yozing.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app_factory --factory --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=\"${AMORA_FORWARDED_ALLOW_IPS:-*}\" --timeout-graceful-shutdown 5"]
