#!/usr/bin/env python3
"""Ilovani emulyatorda ochib, ekranlarni bosib chiqadi va rasmga oladi.

Ishlatilishi:  smoke_test.py readonly|full <apk fayl> <natijalar papkasi>

readonly  Haqiqiy serverga qaratilgan APK uchun. Serverga faqat o'qish so'rovlari ketadi
          (menyu, kafe ma'lumoti, summa hisobi). Buyurtma BERILMAYDI va serverda mijoz
          yaratilmaydi: ism va telefon faqat emulyatorda saqlanadi.
full      CI ichida ishlayotgan SINOV serveriga qaratilgan APK uchun. Buyurtma beriladi,
          kafe xodimining tugmalari o'rnini backend_ctl.py bosadi: qabul qilish, yo'lga
          chiqish, yetkazish, rad etish. Mijoz tomonidan bekor qilish va qayta buyurtma
          berish ham tekshiriladi. Haqiqiy serverga qaratilgan APK bilan ISHLATILMAYDI.
"""

import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

PACKAGE = "uz.amora.app"
# backend_ctl.py sinov serverida kafe nomini shunga o'zgartiradi (TEST_CAFE_NAME)
TEST_CAFE_NAME = "Amora sinov serveri"
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


def back():
    adb("shell", "input", "keyevent", "BACK")
    time.sleep(2)


def tap_scrolling(needle, attempts=6):
    """Element ko'rinmasa, ekranni pastga surib izlaydi."""
    for _ in range(attempts):
        node = find(needle)
        if node:
            tap_node(node)
            return
        adb("shell", "input", "swipe", "540", "1700", "540", "800", "400")
        time.sleep(1.5)
    raise RuntimeError(f"Ekranda topilmadi (surib ko'rilganda ham): {needle!r}")


def staff(status, reason=None):
    """Sinov serverida oxirgi buyurtmaning holatini o'zgartiradi (kafe xodimi o'rnida)."""
    command = [sys.executable, str(Path(__file__).with_name("backend_ctl.py")), "status", "latest", status]
    if reason:
        command.append(reason)
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    print(f"[kafe] {result.stdout.strip()}", flush=True)
    if result.returncode != 0:
        raise RuntimeError(f"backend_ctl: {result.stderr.strip()[-2000:]}")


def visible_texts():
    labels = []
    for node in nodes(dump()):
        label = (node["text"] or node["desc"]).strip()
        if label:
            labels.append(label)
    return labels


def fill_cart():
    """Menyudan savatgacha: taom qo'shish, manzil va profil. Oxirida buyurtma berishga tayyor savat."""
    wait_for("so'm", timeout=90)
    time.sleep(6)  # taom rasmlari yuklanib ulgursin
    shot("01-menu")
    print("Menyu:", visible_texts(), flush=True)

    # Taom haqida ma'lumot oynasi (ochilmasa, sinov davom etaveradi)
    try:
        tap("so'm", exclude=("Yetkazish", "buyurtma", "Savat"))
        wait_for("Savatga qo'shish", timeout=15)
        shot("02-product")
        back()
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


def scenario_readonly():
    fill_cart()
    # "Buyurtma berish" tugmasi ATAYLAB bosilmaydi: haqiqiy kafega buyurtma ketmasin.
    back()
    tap("Buyurtmalarim")
    wait_for("Hali buyurtma yo'q")
    shot("09-orders")


def place_order():
    """Savatdagi buyurtmani yuboradi va buyurtma ekrani ochilishini kutadi."""
    button = "Buyurtma berish ·"  # summa serverdan kelgach tugmada summa ko'rinadi va u yoqiladi
    wait_for(button, timeout=60)
    for _ in range(4):
        time.sleep(2)
        tap(button)
        if find("Buyurtmani tasdiqlaysizmi?"):
            break
    else:
        raise RuntimeError("Tasdiqlash oynasi ochilmadi")
    tap("Tasdiqlash")
    wait_for("Kafe javobi kutilmoqda", timeout=60)
    time.sleep(1)


def scenario_full():
    # Himoya: ilova sinov serveriga ulangan bo'lsagina davom etamiz. Aks holda buyurtma
    # haqiqiy kafega ketib qolishi mumkin.
    try:
        wait_for(TEST_CAFE_NAME, timeout=90)
    except RuntimeError:
        raise RuntimeError("Ilova sinov serveriga ulanmagan: buyurtma berilmaydi") from None

    fill_cart()

    # 1-buyurtma: kafe qabul qiladi, kuryer yo'lga chiqadi, yetkazadi
    place_order()
    shot("09-order-new")
    print("Buyurtma:", visible_texts(), flush=True)

    staff("accepted")
    wait_for("Tayyorlanmoqda", timeout=40)  # ilova holatni 7 soniyada bir so'raydi
    shot("10-order-accepted")

    # Menyudagi "faol buyurtma" belgisi va undan buyurtmaga qaytish
    back()
    wait_for("Buyurtma №", timeout=40)
    shot("11-menu-active-order")
    tap("Buyurtma №")
    wait_for("Kafe qabul qildi")

    staff("delivering")
    wait_for("Kuryer yo'lda", timeout=40)
    shot("12-order-delivering")

    staff("delivered")
    wait_for("Yoqimli ishtaha", timeout=40)
    shot("13-order-delivered")
    print("Yetkazilgan buyurtma:", visible_texts(), flush=True)

    # Buyurtmalar tarixi va undan buyurtmani ochish
    back()
    tap("Buyurtmalarim")
    wait_for("Buyurtma №")
    wait_for("Yetkazildi")
    shot("14-orders")
    tap("Buyurtma №")
    wait_for("Yoqimli ishtaha")

    # 2-buyurtma: xuddi shu taomlar bilan, mijoz o'zi bekor qiladi
    tap_scrolling("Yana shunday buyurtma berish")
    wait_for("Buyurtma berish ·", timeout=60)  # savat ochildi
    shot("15-reorder-cart")
    place_order()
    tap("Buyurtmani bekor qilish")
    wait_for("Buyurtmani bekor qilasizmi?")
    shot("16-cancel-dialog")
    tap("Bekor qilish")  # katta "B" bilan: faqat oynadagi tugma
    wait_for("bekor qilgansiz", timeout=40)
    shot("17-order-cancelled")

    # 3-buyurtma: kafe sababini yozib rad etadi
    tap_scrolling("Yana shunday buyurtma berish")
    wait_for("Buyurtma berish ·", timeout=60)  # savat ochildi
    place_order()
    staff("rejected", "Mahsulot tugadi")
    wait_for("Rad etildi", timeout=40)
    wait_for("Mahsulot tugadi")
    shot("18-order-rejected")

    back()
    tap("Buyurtmalarim")
    wait_for("Rad etildi")
    wait_for("Bekor qilindi")
    wait_for("Yetkazildi")
    shot("19-orders-all")
    print("Buyurtmalar:", visible_texts(), flush=True)


def main():
    global OUT
    if len(sys.argv) != 4 or sys.argv[1] not in ("readonly", "full"):
        raise SystemExit(__doc__)
    mode, apk = sys.argv[1], sys.argv[2]
    OUT = Path(sys.argv[3])
    OUT.mkdir(parents=True, exist_ok=True)

    adb("install", "-r", apk)
    for permission in ("ACCESS_FINE_LOCATION", "ACCESS_COARSE_LOCATION"):
        adb("shell", "pm", "grant", PACKAGE, f"android.permission.{permission}")
    adb("emu", "geo", "fix", "66.9758", "39.6547", check=False)  # Samarqand markazi
    adb("logcat", "-c", check=False)
    adb("shell", "am", "start", "-W", "-n", f"{PACKAGE}/.MainActivity")

    try:
        if mode == "full":
            scenario_full()
        else:
            scenario_readonly()
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
    print(f"Sinov muvaffaqiyatli o'tdi ({mode})", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
