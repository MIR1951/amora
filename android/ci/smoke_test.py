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
          Jonli yangilanish ham shu yerda tekshiriladi: serverdagi o'zgarish ilovada hech
          narsa bosilmasdan ko'rinishi va buyurtma holati haqida bildirishnoma chiqishi kerak.
"""

import json
import re
import subprocess
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

PACKAGE = "uz.amora.app"
# backend_ctl.py sinov serverida kafe nomini shunga o'zgartiradi (TEST_CAFE_NAME)
TEST_CAFE_NAME = "Amora sinov serveri"
# Sinov serveri CI ichida shu manzilda ishlaydi (emulyator uni 10.0.2.2 orqali ko'radi)
TEST_SERVER = "http://127.0.0.1:8000"
# Kafe joylashuvi serverda kiritilmagan bo'lsa, emulyator shu yerga qo'yiladi: Samarqand markazi
DEFAULT_LOCATION = (39.6547, 66.9758)
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
            root = ET.fromstring(raw.decode("utf-8", "replace"))
        except ET.ParseError:
            time.sleep(1)
            continue
        if not dismiss_system_dialog(root):
            return root
    raise RuntimeError("Ekran tuzilishini o'qib bo'lmadi")


def dismiss_system_dialog(root):
    """Boshqa ilova haqidagi tizim oynasini yopadi. Yopgan bo'lsa True qaytaradi.

    CI emulyatori sekin ishlaganda Android "Pixel Launcher isn't responding" kabi oyna chiqaradi.
    U Amora'ga aloqador emas, lekin ekranni to'sib qo'yadi: sinov hech narsani ko'ra olmaydi,
    bosish va yozish ham ilovaga emas, shu oynaga ketadi.
    Oyna Amora'ning o'zi haqida bo'lsa, bu haqiqiy xato: sinov shu yerda to'xtaydi.
    """
    items = list(nodes(root))
    title = next(
        (node["text"] for node in items if "isn't responding" in node["text"] or "keeps stopping" in node["text"]),
        None,
    )
    if title is None:
        return False
    if "Amora" in title:
        raise RuntimeError(f"Ilova ishlamay qoldi: {title}")
    # "Wait" bosilsa, oyna bir necha soniyadan keyin yana chiqadi. "Close app" o'sha ilovani
    # (Amora'ni emas) yopadi, tizim uni orqa fonda o'zi qayta ishga tushiradi.
    button = next((node for node in items if node["text"] == "Close app"), None)
    if button is None:
        button = next((node for node in items if node["text"] == "Wait"), None)
    if button is None:
        raise RuntimeError(f"Tizim oynasini yopib bo'lmadi: {title}")
    print(f"[ogohlantirish] tizim oynasi yopildi: {title}", flush=True)
    adb("shell", "input", "tap", str(button["x"]), str(button["y"]))
    time.sleep(2)
    return True


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
            "id": node.get("resource-id") or "",
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


def find_id(resource_id):
    """Ilova kodidagi testTag bo'yicha izlaydi (masalan, taom nomi: "product-name")."""
    for node in nodes(dump()):
        if node["id"] == resource_id or node["id"].endswith("/" + resource_id):
            return node
    return None


def tap_field(index):
    """Ekrandagi matn kiritish maydonlaridan birini bosadi (0 dan boshlab)."""
    fields = [node for node in nodes(dump()) if node["class"].endswith("EditText")]
    if index >= len(fields):
        raise RuntimeError(f"{index}-maydon topilmadi (jami {len(fields)} ta)")
    tap_node(fields[index])


def type_text(text):
    adb("shell", "input", "text", text.replace(" ", "%s"))
    time.sleep(1)


def fill_field(index, text):
    """Maydonni bosib, matn yozadi va yozilganini tekshiradi.

    Yozish paytida tizim oynasi chiqib qolsa, harflar ilovaga yetib bormaydi: bunday holda
    maydon tozalanib, qayta yoziladi.
    """
    wanted = text.replace(" ", "")
    for _ in range(4):
        tap_field(index)
        type_text(text)
        fields = [node for node in nodes(dump()) if node["class"].endswith("EditText")]
        if index < len(fields) and wanted in fields[index]["text"].replace(" ", ""):
            return
        tap_field(index)
        adb("shell", "input", "keyevent", "KEYCODE_MOVE_END")
        adb("shell", "input", "keyevent", *(["KEYCODE_DEL"] * 40))
        time.sleep(1)
    raise RuntimeError(f"{index}-maydonga yozib bo'lmadi: {text!r}")


def shot(name):
    dump()  # ekranni tizim oynasi to'sib turgan bo'lsa, avval u yopiladi
    (OUT / f"{name}.png").write_bytes(adb("exec-out", "screencap", "-p"))
    print(f"[rasm] {name}.png", flush=True)


def back():
    dump()
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


def find_scrolling(needle, attempts=6):
    """Ekranni pastga surib, shu yozuv ko'ringuncha izlaydi."""
    for _ in range(attempts):
        node = find(needle)
        if node:
            return node
        adb("shell", "input", "swipe", "540", "1500", "540", "900", "400")
        time.sleep(1.5)
    raise RuntimeError(f"Ekranda topilmadi (surib ko'rilganda ham): {needle!r}")


def enter_promo(code):
    """Savatdagi promokod maydoniga kod yozib, "Qo'llash"ni bosadi."""
    find_scrolling("Qo'llash")
    fields = [node for node in nodes(dump()) if node["class"].endswith("EditText")]
    if not fields:
        raise RuntimeError("Promokod maydoni topilmadi")
    field = fields[-1]  # promokod izoh maydonidan pastda turadi
    tap_node(field)
    adb("shell", "input", "keyevent", "KEYCODE_MOVE_END")
    adb("shell", "input", "keyevent", *(["KEYCODE_DEL"] * 25))
    type_text(code)
    adb("shell", "input", "keyevent", "KEYCODE_BACK")  # klaviaturani yopamiz
    time.sleep(1)
    tap("Qo'llash")


def backend(*args):
    """Sinov serverida kafe xodimi yoki admin o'rnida biror ish qiladi (backend_ctl.py)."""
    command = [sys.executable, str(Path(__file__).with_name("backend_ctl.py")), *args]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    print(f"[kafe] {result.stdout.strip()}", flush=True)
    if result.returncode != 0:
        raise RuntimeError(f"backend_ctl: {result.stderr.strip()[-2000:]}")


def staff(status, reason=None):
    """Sinov serverida oxirgi buyurtmaning holatini o'zgartiradi (kafe xodimi o'rnida)."""
    backend("status", "latest", status, *([reason] if reason else []))


def wait_gone(needle, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if find(needle) is None:
            return
        time.sleep(1)
    raise RuntimeError(f"Ekrandan yo'qolmadi: {needle!r}")


def check_live_menu():
    """Jonli yangilanish: admin taomni "tugadi" deb belgilaydi, ilovada hech narsa bosilmaydi.

    Menyu ekrani serverdan o'zi qayta so'ramaydi, shuning uchun yozuv faqat server yuborgan
    xabar tufayli paydo bo'lishi mumkin.
    """
    if find("Tugagan"):
        raise RuntimeError("Sinov boshida ekranda tugagan taom bo'lmasligi kerak")
    backend("product", "Lag'mon", "off")
    wait_for("Tugagan", timeout=20)
    shot("01a-live-menu")
    backend("product", "Lag'mon", "on")
    wait_gone("Tugagan", timeout=20)
    print("Jonli yangilanish: menyu o'zi yangilandi", flush=True)


def notification_shown(text):
    """Tizimda shu matnli Amora bildirishnomasi turibdimi."""
    out = adb("shell", "dumpsys", "notification", "--noredact", check=False).decode(errors="replace")
    return f"pkg={PACKAGE}" in out and text in out


def wait_notification(text, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if notification_shown(text):
            return
        time.sleep(1)
    raise RuntimeError(f"Bildirishnoma chiqmadi: {text!r}")


def open_order_from_notification(title, on_screen):
    """Bildirishnomani bosib, buyurtma ekrani ochilishini tekshiradi.

    Bildirishnomalar pardasi tizimga tegishli va emulyatorda ba'zan sekin ochiladi: bu qadam
    o'xshamasa, sinov to'xtamaydi, buyurtma bosh sahifadagi belgi orqali ochiladi.
    """
    try:
        adb("shell", "cmd", "statusbar", "expand-notifications")
        time.sleep(2)
        shot("11b-notification")
        tap(title, timeout=15)
        wait_for(on_screen, timeout=20)
        print("Bildirishnoma bosildi: buyurtma ochildi", flush=True)
    except RuntimeError as error:
        print(f"[ogohlantirish] bildirishnomani bosib bo'lmadi: {error}", flush=True)
        adb("shell", "cmd", "statusbar", "collapse", check=False)
        time.sleep(2)
        tap("Buyurtma №")
        wait_for(on_screen, timeout=20)


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

    # Taom haqida ma'lumot oynasi: taom nomi bosilganda ochiladi (ochilmasa, sinov davom etaveradi)
    try:
        name = find_id("product-name")
        if name is None:
            raise RuntimeError("taom kartochkasi topilmadi")
        tap_node(name)
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
    fill_field(0, "Sinov")
    fill_field(1, "901234567")
    shot("07-profile")
    tap("Saqlash")

    wait_for("Buyurtma berish", timeout=60)
    time.sleep(3)
    shot("08-cart-ready")
    print("Savat:", visible_texts(), flush=True)


def open_from_home(label):
    """Bosh sahifaning yuqori satridagi tugmani bosadi: "Buyurtmalarim" yoki "Profil"."""
    tap(label)


def shot_profile(name):
    open_from_home("Profil")
    wait_for("Yetkazish manzili")
    shot(name)
    back()


def scenario_readonly():
    fill_cart()
    # "Buyurtma berish" tugmasi ATAYLAB bosilmaydi: haqiqiy kafega buyurtma ketmasin.
    back()
    open_from_home("Buyurtmalarim")
    wait_for("Hali buyurtma yo'q")
    shot("09-orders")
    back()
    shot_profile("10-profile")


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

    wait_for("so'm", timeout=90)
    time.sleep(3)  # jonli ulanish o'rnatilib ulgursin
    check_live_menu()

    fill_cart()

    # Birinchi buyurtma chegirmasi kod kiritmasdan qo'llanadi
    find_scrolling("Birinchi buyurtma: −10%")
    find("Chegirma") or find_scrolling("Chegirma")
    shot("08a-cart-first-order-discount")
    print("Birinchi buyurtma chegirmasi:", visible_texts(), flush=True)

    # 1-buyurtma: kafe qabul qiladi, kuryer yo'lga chiqadi, yetkazadi
    place_order()
    shot("09-order-new")
    # Ilova Firebase manzilini serverga yubordimi. Emulyatorda Google xizmatlari bo'lmasligi
    # mumkin: bu faqat jurnalga yoziladi, sinovni to'xtatmaydi
    time.sleep(3)
    backend("push-token")
    print("Buyurtma:", visible_texts(), flush=True)

    # Bu yerda ekran to'g'ri ko'rsatilishi tekshiriladi. Holat tez kelgani jonli ulanishni
    # isbotlamaydi (ulanish bo'lmasa, ekran serverdan har 7 soniyada o'zi so'raydi): jonli
    # yetkazish `check_live_menu` da isbotlanadi, chunki menyu o'zi qayta so'ramaydi.
    staff("accepted")
    wait_for("Tayyorlanmoqda", timeout=15)
    shot("10-order-accepted")

    # Menyudagi "faol buyurtma" belgisi
    back()
    wait_for("Buyurtma №", timeout=40)
    shot("11-menu-active-order")

    # Mijoz boshqa ekranda turganda holat o'zgaradi: belgi o'zi yangilanadi va bildirishnoma chiqadi
    staff("delivering")
    time.sleep(1.5)
    (OUT / "11a-notification-popup.png").write_bytes(adb("exec-out", "screencap", "-p"))
    wait_notification("Kuryer yo'lda")
    wait_for("Kuryer yo'lda", timeout=20)
    print("Jonli yangilanish: bosh sahifadagi buyurtma belgisi o'zi yangilandi", flush=True)
    open_order_from_notification("Kuryer yo'lda", "Kuryer buyurtmangizni olib")
    shot("12-order-delivering")

    staff("delivered")
    wait_for("Yoqimli ishtaha", timeout=15)
    shot("13-order-delivered")
    print("Yetkazilgan buyurtma:", visible_texts(), flush=True)

    # Buyurtmalar tarixi va undan buyurtmani ochish
    back()
    open_from_home("Buyurtmalarim")
    wait_for("Buyurtma №")
    wait_for("Yetkazildi")
    shot("14-orders")
    tap("Buyurtma №")
    wait_for("Yoqimli ishtaha")

    # 2-buyurtma: xuddi shu taomlar bilan, mijoz o'zi bekor qiladi
    tap_scrolling("Yana shunday buyurtma berish")
    wait_for("Buyurtma berish ·", timeout=60)  # savat ochildi
    shot("15-reorder-cart")
    # Ikkinchi buyurtmada avtomatik chegirma yo'q, promokod kiritiladi
    if find("Birinchi buyurtma: −"):
        raise RuntimeError("Birinchi buyurtma chegirmasi ikkinchi buyurtmada ham chiqdi")
    enter_promo("XATO")
    wait_for("Bunday promokod yo'q", timeout=20)
    shot("15a-promo-wrong")
    enter_promo("AMORA10")
    wait_for("AMORA10:", timeout=20)
    time.sleep(1)
    shot("15b-promo-applied")
    print("Promokod:", visible_texts(), flush=True)
    place_order()
    shot("15c-order-with-promo")
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
    wait_for("Rad etildi", timeout=15)
    wait_for("Mahsulot tugadi")
    shot("18-order-rejected")

    back()
    open_from_home("Buyurtmalarim")
    wait_for("Rad etildi")
    wait_for("Bekor qilindi")
    wait_for("Yetkazildi")
    shot("19-orders-all")
    print("Buyurtmalar:", visible_texts(), flush=True)
    back()

    shot_profile("20-profile")

    # Tungi rejim: ranglar qorong'i mavzuda ham to'g'ri ko'rinishini rasmga olamiz
    adb("shell", "cmd", "uimode", "night", "yes")
    time.sleep(4)
    wait_for(TEST_CAFE_NAME)
    shot("21-menu-dark")
    open_from_home("Buyurtmalarim")
    wait_for("Rad etildi")
    shot("22-orders-dark")
    tap("Buyurtma №")
    wait_for("Jami · naqd")
    shot("23-order-dark")
    adb("shell", "cmd", "uimode", "night", "no")
    time.sleep(3)


def live_server():
    """Haqiqiy server manzili: ilova yig'ilganda ishlatilgan android/gradle.properties dan."""
    properties = Path(__file__).resolve().parents[1] / "gradle.properties"
    for line in properties.read_text(encoding="utf-8").splitlines():
        if line.startswith("amora.apiBaseUrl="):
            return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("gradle.properties da amora.apiBaseUrl topilmadi")


def customer_location(server):
    """Emulyator turadigan joy: kafedan 150 metrcha narida, ya'ni yetkazish hududi ichida.

    Kafe joylashuvi serverdan o'qiladi (faqat o'qish so'rovi). Kafe o'z manzilini va yetkazish
    hududini o'zgartirsa ham, sinovdagi "mijoz" hudud ichida qoladi.
    """
    try:
        with urllib.request.urlopen(f"{server}/api/v1/shop", timeout=20) as response:
            shop = json.load(response)
        latitude, longitude = shop.get("cafe_latitude"), shop.get("cafe_longitude")
        if latitude is not None and longitude is not None:
            return float(latitude) + 0.0015, float(longitude)
        print("[ogohlantirish] serverda kafe joylashuvi kiritilmagan", flush=True)
    except Exception as error:
        print(f"[ogohlantirish] kafe joylashuvini o'qib bo'lmadi: {error}", flush=True)
    return DEFAULT_LOCATION


def save_diagnostics():
    """Emulyator holati: "javob bermayapti" (ANR) yozuvlari, protsessor yuklamasi, chizilgan kadrlar.

    Tizim oynasi chiqqan bo'lsa, sababi shu yerdan ko'rinadi: emulyator shunchaki sekinmi yoki
    ilova protsessorni band qilib qo'yganmi.
    """
    parts = []
    log = adb("logcat", "-d", "ActivityManager:E", "*:S", check=False).decode(errors="replace")
    anr = [line for line in log.splitlines() if "ANR in" in line or "Reason:" in line or "CPU usage" in line
           or "% TOTAL" in line or "uz.amora" in line or "nexuslauncher" in line]
    parts.append("== ANR yozuvlari ==\n" + "\n".join(anr[-80:]))
    cpu = adb("shell", "dumpsys", "cpuinfo", check=False).decode(errors="replace")
    parts.append("== Protsessor ==\n" + "\n".join(cpu.splitlines()[:25]))
    gfx = adb("shell", "dumpsys", "gfxinfo", PACKAGE, check=False).decode(errors="replace")
    parts.append("== Kadrlar ==\n" + "\n".join(gfx.splitlines()[:30]))
    (OUT / "diagnostics.txt").write_text("\n\n".join(parts), encoding="utf-8")


def main():
    global OUT
    if len(sys.argv) != 4 or sys.argv[1] not in ("readonly", "full"):
        raise SystemExit(__doc__)
    mode, apk = sys.argv[1], sys.argv[2]
    OUT = Path(sys.argv[3])
    OUT.mkdir(parents=True, exist_ok=True)

    adb("install", "-r", apk)
    # Bildirishnoma ruxsati oldindan beriladi: tizimning ruxsat oynasi sinovni to'sib qo'ymasin
    for permission in ("ACCESS_FINE_LOCATION", "ACCESS_COARSE_LOCATION", "POST_NOTIFICATIONS"):
        adb("shell", "pm", "grant", PACKAGE, f"android.permission.{permission}")
    latitude, longitude = customer_location(TEST_SERVER if mode == "full" else live_server())
    adb("emu", "geo", "fix", f"{longitude:.5f}", f"{latitude:.5f}", check=False)  # avval uzunlik, keyin kenglik
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
    finally:
        try:
            save_diagnostics()
        except Exception as error:
            print(f"[ogohlantirish] tashxisni saqlab bo'lmadi: {error}", flush=True)
    print(f"Sinov muvaffaqiyatli o'tdi ({mode})", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
