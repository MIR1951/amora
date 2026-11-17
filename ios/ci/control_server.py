#!/usr/bin/env python3
"""iOS UI sinovi sinov serverini shu kichik HTTP server orqali boshqaradi.

    python ios/ci/control_server.py [--host 127.0.0.1] [--port 8099]

Android sinovida smoke_test.py `android/ci/backend_ctl.py` ni o'zi chaqiradi. iOS sinovi esa
simulyator ichidagi XCUITest jarayonida ishlaydi va kompyuterdagi skriptni ishga tushira olmaydi,
lekin 127.0.0.1 ga HTTP so'rov yubora oladi. Shuning uchun kafe xodimi va mijozning Telegram'dagi
harakatlari shu server orqali bajariladi:

    GET /health                                       server ishlayaptimi
    GET /verify?phone=%2B998901234567                 mijoz botda raqamini yubordi
    GET /status?order=latest&to=accepted              buyurtma holati (accepted|delivering|delivered|rejected)
    GET /status?order=12&to=rejected&reason=Sabab     rad etish sababi bilan
    GET /product?name=Lag%27mon&available=off         taom "tugadi" (on: yana sotuvda)

Har bir so'rov `backend_ctl.py` ni alohida jarayon sifatida backend/ papkasidan, shu serverning
muhit o'zgaruvchilari bilan (AMORA_DATABASE_URL va boshqalar) ishga tushiradi. Natija: muvaffaqiyatda
200 va skript chiqishi, xatoda 500 va xato matni. Har bir chaqiruv jurnalga yoziladi.
Faqat CI ichidagi SINOV bazasi bilan ishlatiladi (backend_ctl.py ham buni tekshiradi).
"""

import argparse
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
BACKEND_CTL = ROOT / "android" / "ci" / "backend_ctl.py"
STATUSES = ("accepted", "delivering", "delivered", "rejected")

# SQLite bitta yozuvchini yaxshi ko'radi: buyruqlar navbat bilan bajariladi
LOCK = threading.Lock()


def log(message: str) -> None:
    stamp = time.strftime("%H:%M:%S")
    print(f"[{stamp}] {message}", file=sys.stderr, flush=True)


def run_ctl(*args: str) -> tuple[bool, str]:
    command = [sys.executable, str(BACKEND_CTL), *args]
    with LOCK:
        try:
            result = subprocess.run(
                command, cwd=BACKEND_DIR, capture_output=True, text=True, timeout=90
            )
        except subprocess.TimeoutExpired:
            return False, "backend_ctl.py 90 soniyada tugamadi"
    if result.returncode == 0:
        return True, result.stdout.strip()
    # SystemExit("matn") xabari stderr'ga yoziladi
    return False, (result.stderr.strip() or result.stdout.strip())[-4000:]


def normalize_phone(raw: str) -> str:
    """So'rovda "+" kodlanmasdan yuborilsa, u bo'sh joyga aylanadi: qaytarib qo'yamiz."""
    phone = raw.strip()
    if phone and phone[0].isdigit():
        phone = "+" + phone
    return phone


def first(query: dict, key: str) -> str | None:
    values = query.get(key)
    return values[0] if values else None


class Handler(BaseHTTPRequestHandler):
    server_version = "AmoraControl/1.0"

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        log(f"{self.address_string()} {format % args}")

    def reply(self, code: int, text: str) -> None:
        body = (text + "\n").encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        url = urlsplit(self.path)
        query = parse_qs(url.query, keep_blank_values=True)
        args: tuple[str, ...]
        if url.path == "/health":
            self.reply(200, "ok")
            return
        if url.path == "/verify":
            phone = normalize_phone(first(query, "phone") or "")
            if not phone:
                self.reply(400, "phone kerak: /verify?phone=%2B998901234567")
                return
            args = ("verify", phone)
        elif url.path == "/status":
            order = (first(query, "order") or "latest").strip()
            status = (first(query, "to") or "").strip()
            if status not in STATUSES:
                self.reply(400, f"to quyidagilardan biri bo'lishi kerak: {', '.join(STATUSES)}")
                return
            if order != "latest" and not order.isdigit():
                self.reply(400, "order: buyurtma raqami yoki latest")
                return
            reason = (first(query, "reason") or "").strip()
            args = ("status", order, status, *([reason] if reason else []))
        elif url.path == "/product":
            name = (first(query, "name") or "").strip()
            available = (first(query, "available") or "").strip()
            if not name or available not in ("on", "off"):
                self.reply(400, "kerak: /product?name=...&available=on|off")
                return
            args = ("product", name, available)
        else:
            self.reply(404, "Noma'lum buyruq. /verify, /status, /product")
            return

        log(f"backend_ctl.py {' '.join(args)}")
        ok, output = run_ctl(*args)
        log(("OK: " if ok else "XATO: ") + output.replace("\n", " | "))
        self.reply(200 if ok else 500, output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8099)
    options = parser.parse_args()
    server = HTTPServer((options.host, options.port), Handler)
    log(f"Boshqaruv serveri: http://{options.host}:{options.port} (backend: {BACKEND_DIR})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
