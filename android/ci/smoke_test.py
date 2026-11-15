#!/usr/bin/env python3
"""Ilovani emulyatorda ochib, asosiy ekranlarni bosib chiqadi va rasmga oladi.

Ishlatilishi:  smoke_test.py <apk fayl> <natijalar papkasi>

Haqiqiy serverga faqat o'qish so'rovlari ketadi (menyu, kafe ma'lumoti, summa hisobi).
Buyurtma BERILMAYDI va serverda mijoz yaratilmaydi: ism va telefon faqat emulyatorda saqlanadi.
"""

import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

PACKAGE = "uz.amora.app"
BOUNDS = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")
OUT = Path(".")


def adb(*args, check=True):
    result = subprocess.run(["adb", *args], capture_output=True, timeout=180)
    if check and result.returncode != 0:
        raise RuntimeError(f"adb {' '.join(args)}: {result.stderr.decode(errors='replace').strip()}")
    return result.stdout


def dump():
    """Ekrandagi elementlar ro'yxati. Ekran harakatda bo'lsa (yuklanish belgisi), qayta urinadi."""
    for _ in range(25):
        adb("shell", "rm", "-f", "/sdcard/ui.xml", check=False)
        adb("shell", "uiautomator", "dump", "/sdcard/ui.xml", check=False)
        raw = adb("exec-out", "cat", "/sdcard/ui.xml", check=False)
        try:
            return ET.fromstring(raw.decode("utf-8", "replace"))
        except ET.ParseError:
            time.sleep(1)
    raise RuntimeError("Ekran tuzilishini o'qib bo'lmadi")


def nodes(root):
    for node in root.iter("node"):
        match = BOUNDS.match(node.get("bounds", ""))
        if not match:
            continue
        x1, y1, x2, y2 = map(int, match.groups())
        if x2 <= x1 or y2 <= y1:
            continue
        yield {
            "text": node.get("text") or "",
            "desc": node.get("content-desc") or "",
            "class": node.get("class") or "",
            "x": (x1 + x2) // 2,
            "y": (y1 + y2) // 2,
        }


def find(needle, exclude=()):
    for node in nodes(dump()):
        label = node["text"] + " | " + node["desc"]
        if needle in label and not any(word in label for word in exclude):
            return node
    return None


def wait_for(needle, timeout=45, exclude=()):
    deadline = time.time() + timeout
    while time.time() < deadline:
        node = find(needle, exclude)
        if node:
            return node
        time.sleep(1)
    raise RuntimeError(f"Ekranda topilmadi: {needle!r}")


def tap_node(node):
    adb("shell", "input", "tap", str(node["x"]), str(node["y"]))
    time.sleep(1.5)


def tap(needle, timeout=45, exclude=()):
    tap_node(wait_for(needle, timeout, exclude))


def tap_field(index):
    """Ekrandagi matn kiritish maydonlaridan birini bosadi (0 dan boshlab)."""
    fields = [node for node in nodes(dump()) if node["class"].endswith("EditText")]
    if index >= len(fields):
        raise RuntimeError(f"{index}-maydon topilmadi (jami {len(fields)} ta)")
    tap_node(fields[index])


def type_text(text):
    adb("shell", "input", "text", text.replace(" ", "%s"))
    time.sleep(1)


def shot(name):
    (OUT / f"{name}.png").write_bytes(adb("exec-out", "screencap", "-p"))
    print(f"[rasm] {name}.png", flush=True)


def visible_texts():
    labels = []
    for node in nodes(dump()):
        label = (node["text"] or node["desc"]).strip()
        if label:
            labels.append(label)
    return labels


def scenario():
    wait_for("so'm", timeout=90)
    time.sleep(6)  # taom rasmlari yuklanib ulgursin
    shot("01-menu")
    print("Menyu:", visible_texts(), flush=True)

    # Taom haqida ma'lumot oynasi (ochilmasa, sinov davom etaveradi)
    try:
        tap("so'm", exclude=("Yetkazish", "buyurtma", "Savat"))
        wait_for("Savatga qo'shish", timeout=15)
        shot("02-product")
        adb("shell", "input", "keyevent", "BACK")
        time.sleep(2)
    except RuntimeError as error:
        print(f"[ogohlantirish] taom oynasi: {error}", flush=True)
        shot("02-product-failed")

    tap("Qo'shish", exclude=("Savatga",))
    wait_for("Savat")
    shot("03-added")

    tap("Savat")
    wait_for("Jami")
    time.sleep(2)
    shot("04-cart")

    tap("Manzilni tanlang")
    wait_for("Shu manzilga yetkazish", timeout=60)
    time.sleep(15)  # joylashuv aniqlanib, xarita bo'laklari yuklansin
    shot("05-address")
    tap("Shu manzilga yetkazish")

    wait_for("Ism va telefonni kiriting")
    shot("06-cart-address")
    tap("Ism va telefonni kiriting")

    wait_for("Saqlash")
    tap_field(0)
    type_text("Sinov")
    tap_field(1)
    type_text("901234567")
    shot("07-profile")
    tap("Saqlash")

    wait_for("Buyurtma berish", timeout=60)
    time.sleep(3)
    shot("08-cart-ready")
    print("Savat:", visible_texts(), flush=True)
    # "Buyurtma berish" tugmasi ATAYLAB bosilmaydi: haqiqiy kafega buyurtma ketmasin.

    adb("shell", "input", "keyevent", "BACK")
    time.sleep(2)
    tap("Buyurtmalarim")
    wait_for("Hali buyurtma yo'q")
    shot("09-orders")


def main():
    global OUT
    apk = sys.argv[1]
    OUT = Path(sys.argv[2])
    OUT.mkdir(parents=True, exist_ok=True)

    adb("install", "-r", apk)
    for permission in ("ACCESS_FINE_LOCATION", "ACCESS_COARSE_LOCATION"):
        adb("shell", "pm", "grant", PACKAGE, f"android.permission.{permission}")
    adb("emu", "geo", "fix", "66.9758", "39.6547", check=False)  # Samarqand markazi
    adb("logcat", "-c", check=False)
    adb("shell", "am", "start", "-W", "-n", f"{PACKAGE}/.MainActivity")

    try:
        scenario()
    except Exception as error:
        print(f"[XATO] {error}", flush=True)
        try:
            shot("failure")
            print("Ekranda:", visible_texts(), flush=True)
        except Exception as inner:
            print(f"[XATO] ekranni saqlab bo'lmadi: {inner}", flush=True)
        log = adb("logcat", "-d", "-t", "400", "AndroidRuntime:E", "System.err:W", "*:S", check=False)
        (OUT / "logcat.txt").write_bytes(log)
        print(log.decode(errors="replace")[-6000:], flush=True)
        return 1
    print("Sinov muvaffaqiyatli o'tdi", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
