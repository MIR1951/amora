FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv/amora

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY migrations ./migrations
COPY app ./app

RUN useradd --create-home --uid 1000 amora && mkdir -p /srv/amora/media && chown -R amora /srv/amora
USER amora

EXPOSE 8000

# Avval baza sxemasi yangilanadi, keyin server ishga tushadi. `exec`: server konteynerning asosiy
# jarayoni bo'ladi va `docker stop` signalini o'zi oladi (aks holda signal qobiqda qolib ketadi,
# server toza to'xtamaydi va Docker uni 10 soniyadan keyin majburan o'chiradi).
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app_factory --factory --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*' --timeout-graceful-shutdown 5"]
