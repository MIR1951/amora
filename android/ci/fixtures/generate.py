"""CI sinov serveri uchun namuna taom rasmlari (chizilgan, fotosurat emas).

Shu papkadagi .jpg fayllar shu skript bilan yaratilgan:  python generate.py .
Pillow kerak. Rasmlar faqat emulyator sinovida, sinov serverining menyusida ishlatiladi
(android/ci/backend_ctl.py). Haqiqiy menyu rasmlari Telegram bot orqali yuklanadi.
"""
import math
import random
import sys
from PIL import Image, ImageDraw, ImageFilter

W, H, S = 800, 640, 2  # yakuniy o'lcham va chizishdagi kattalashtirish
CX, CY = W * S // 2, H * S // 2


def ell(d, x, y, a, b, ang, fill):
    pts = []
    for i in range(18):
        t = 2 * math.pi * i / 18
        pts.append((x + a * math.cos(t) * math.cos(ang) - b * math.sin(t) * math.sin(ang),
                    y + a * math.cos(t) * math.sin(ang) + b * math.sin(t) * math.cos(ang)))
    d.polygon(pts, fill=fill)


def disc_point(rnd, r, power=0.5):
    rr = r * rnd.random() ** power
    t = rnd.random() * 2 * math.pi
    return CX + rr * math.cos(t), CY + rr * math.sin(t)


def background(c1, c2):
    img = Image.new("RGB", (W * S, H * S), c1)
    px = img.load()
    for y in range(H * S):
        for x in range(0, W * S):
            k = (x / (W * S) * 0.55 + y / (H * S) * 0.45)
            px[x, y] = tuple(int(c1[i] + (c2[i] - c1[i]) * k) for i in range(3))
    return img


def shadow(img, r, dx=0, dy=26, alpha=95, blur=30):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse((CX - r + dx, CY - r + dy, CX + r + dx, CY + r + dy), fill=(60, 30, 10, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    img.paste(layer, (0, 0), layer)


def circle(d, r, fill, cx=None, cy=None):
    cx = CX if cx is None else cx
    cy = CY if cy is None else cy
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill)


def plate(img, r, body=(251, 249, 245), rim=(236, 231, 222), well=(246, 243, 237)):
    shadow(img, r)
    d = ImageDraw.Draw(img)
    circle(d, r, body)
    circle(d, r * 0.80, rim)
    circle(d, r * 0.77, well)
    return d


def herbs(d, rnd, r, n=40, color=(74, 140, 62)):
    for _ in range(n):
        x, y = disc_point(rnd, r)
        ell(d, x, y, rnd.uniform(5, 9), rnd.uniform(3, 5), rnd.random() * 3.14, color)


def osh(rnd):
    img = background((238, 206, 160), (224, 178, 124))
    d = plate(img, 520)
    grains = [(243, 204, 112), (236, 190, 94), (248, 218, 142), (229, 176, 80), (250, 226, 160)]
    for _ in range(2600):
        x, y = disc_point(rnd, 350, 0.55)
        ell(d, x, y, rnd.uniform(11, 15), rnd.uniform(4, 5.5), rnd.random() * 3.14, rnd.choice(grains))
    for _ in range(70):
        x, y = disc_point(rnd, 320)
        ell(d, x, y, rnd.uniform(26, 44), 6, rnd.random() * 3.14, rnd.choice([(232, 122, 40), (240, 140, 52), (222, 106, 30)]))
    for _ in range(9):
        x, y = disc_point(rnd, 230, 0.7)
        a = rnd.random() * 3.14
        ell(d, x, y, rnd.uniform(46, 62), rnd.uniform(34, 44), a, (104, 58, 36))
        ell(d, x - 6, y - 8, rnd.uniform(30, 40), rnd.uniform(20, 26), a, (136, 78, 48))
    for _ in range(16):
        x, y = disc_point(rnd, 300)
        circle(d, 15, (236, 208, 160), x, y)
        circle(d, 9, (246, 224, 184), x - 3, y - 3)
    herbs(d, rnd, 300, 30)
    return img


def lagmon(rnd):
    img = background((196, 214, 196), (160, 188, 168))
    shadow(img, 500)
    d = ImageDraw.Draw(img)
    circle(d, 500, (250, 248, 244))
    circle(d, 440, (232, 226, 216))
    circle(d, 420, (190, 76, 38))
    circle(d, 380, (206, 92, 44))
    for _ in range(46):
        pts = []
        x, y = disc_point(rnd, 300)
        ang = rnd.random() * 6.28
        for _ in range(26):
            pts.append((x, y))
            ang += rnd.uniform(-0.55, 0.55)
            x += math.cos(ang) * 24
            y += math.sin(ang) * 24
            dx, dy = x - CX, y - CY
            dist = math.hypot(dx, dy)
            if dist > 350:
                ang = math.atan2(-dy, -dx) + rnd.uniform(-0.6, 0.6)
        d.line(pts, fill=rnd.choice([(247, 228, 176), (242, 218, 160), (250, 236, 192)]), width=15, joint="curve")
    for _ in range(26):
        x, y = disc_point(rnd, 320)
        ell(d, x, y, rnd.uniform(16, 24), rnd.uniform(9, 13), rnd.random() * 3.14, rnd.choice([(214, 48, 40), (232, 70, 46), (240, 170, 50)]))
    for _ in range(10):
        x, y = disc_point(rnd, 280)
        ell(d, x, y, rnd.uniform(28, 38), rnd.uniform(22, 28), rnd.random() * 3.14, (112, 62, 38))
    herbs(d, rnd, 330, 70, (62, 140, 58))
    return img


def manti(rnd):
    img = background((214, 200, 226), (186, 170, 206))
    d = plate(img, 520)
    for i in range(6):
        if i == 5:
            x, y, r = CX, CY, 118
        else:
            t = 2 * math.pi * i / 5 - 1.2
            x, y, r = CX + 250 * math.cos(t), CY + 250 * math.sin(t), 124
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.ellipse((x - r, y - r + 16, x + r, y + r + 16), fill=(90, 60, 30, 70))
        layer = layer.filter(ImageFilter.GaussianBlur(14))
        img.paste(layer, (0, 0), layer)
        d = ImageDraw.Draw(img)
        circle(d, r, (242, 230, 204), x, y)
        circle(d, r * 0.86, (250, 242, 222), x - 6, y - 8)
        for k in range(4):
            a = math.pi * k / 4 + i * 0.4
            d.line((x - r * 0.62 * math.cos(a), y - r * 0.62 * math.sin(a), x + r * 0.62 * math.cos(a), y + r * 0.62 * math.sin(a)),
                   fill=(222, 204, 170), width=9)
        circle(d, r * 0.2, (232, 216, 186), x, y)
    for _ in range(90):
        x, y = disc_point(rnd, 380)
        ell(d, x, y, rnd.uniform(5, 8), 3, rnd.random() * 3.14, (70, 140, 64))
    for _ in range(26):
        x, y = disc_point(rnd, 380)
        circle(d, rnd.uniform(3, 5), (60, 44, 36), x, y)
    return img


def shashlik(rnd):
    img = background((226, 190, 170), (206, 150, 126))
    d = plate(img, 520)
    for _ in range(40):
        x, y = disc_point(rnd, 360)
        r = rnd.uniform(34, 58)
        a0 = rnd.uniform(0, 360)
        d.arc((x - r, y - r, x + r, y + r), a0, a0 + rnd.uniform(150, 330), fill=rnd.choice([(246, 238, 242), (232, 186, 208), (250, 244, 246)]), width=12)
    for row in range(3):
        y = CY - 190 + row * 190 + rnd.uniform(-10, 10)
        tilt = rnd.uniform(-0.06, 0.06)
        x0, x1 = CX - 470, CX + 470
        d.line((x0, y - tilt * 470, x1, y + tilt * 470), fill=(176, 178, 186), width=9)
        for k in range(5):
            x = CX - 300 + k * 150
            yy = y + tilt * (x - CX)
            a = tilt + rnd.uniform(-0.15, 0.15)
            ell(d, x, yy, 66, 54, a, (86, 44, 26))
            ell(d, x - 3, yy - 5, 58, 45, a, (142, 76, 42))
            ell(d, x - 14, yy - 14, 26, 15, a, (176, 104, 60))
            d.line((x - 30, yy + 18, x + 26, yy + 26), fill=(70, 34, 20), width=7)
    herbs(d, rnd, 380, 60)
    return img


def salat(rnd):
    img = background((246, 222, 150), (236, 196, 110))
    shadow(img, 500)
    d = ImageDraw.Draw(img)
    circle(d, 500, (250, 248, 244))
    circle(d, 430, (236, 231, 222))
    circle(d, 410, (244, 240, 232))
    for _ in range(34):
        x, y = disc_point(rnd, 320, 0.6)
        if rnd.random() < 0.5:
            r = rnd.uniform(62, 78)
            circle(d, r, (206, 44, 40), x, y)
            circle(d, r * 0.84, (232, 84, 66), x, y)
            for k in range(6):
                a = math.pi * k / 3 + rnd.random()
                ell(d, x + r * 0.42 * math.cos(a), y + r * 0.42 * math.sin(a), r * 0.2, r * 0.11, a, (248, 190, 130))
        else:
            r = rnd.uniform(54, 66)
            circle(d, r, (86, 150, 70), x, y)
            circle(d, r * 0.86, (196, 226, 156), x, y)
            for k in range(8):
                a = math.pi * k / 4
                ell(d, x + r * 0.34 * math.cos(a), y + r * 0.34 * math.sin(a), r * 0.13, r * 0.06, a, (232, 242, 204))
    for _ in range(22):
        x, y = disc_point(rnd, 330)
        r = rnd.uniform(40, 70)
        a0 = rnd.uniform(0, 360)
        d.arc((x - r, y - r, x + r, y + r), a0, a0 + rnd.uniform(120, 260), fill=(196, 120, 176), width=10)
    herbs(d, rnd, 340, 90, (58, 132, 56))
    return img


def choy(rnd):
    img = background((204, 222, 232), (170, 196, 214))
    d = plate(img, 470, well=(248, 246, 241))
    # dasta
    d.rounded_rectangle((CX + 250, CY - 46, CX + 430, CY + 46), radius=46, fill=(246, 243, 237))
    d.rounded_rectangle((CX + 280, CY - 20, CX + 400, CY + 20), radius=20, fill=(236, 231, 222))
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.ellipse((CX - 290, CY - 270, CX + 290, CY + 310), fill=(70, 40, 20, 80))
    layer = layer.filter(ImageFilter.GaussianBlur(20))
    img.paste(layer, (0, 0), layer)
    d = ImageDraw.Draw(img)
    circle(d, 290, (252, 250, 247))
    circle(d, 252, (150, 78, 26))
    circle(d, 232, (172, 96, 34))
    circle(d, 180, (186, 110, 44))
    ell(d, CX - 80, CY - 96, 96, 34, -0.6, (214, 150, 84))
    # limon bo'lagi
    lx, ly = CX - 330, CY + 300
    circle(d, 92, (238, 190, 40), lx, ly)
    circle(d, 80, (250, 226, 110), lx, ly)
    for k in range(8):
        a = 2 * math.pi * k / 8
        d.line((lx, ly, lx + 76 * math.cos(a), ly + 76 * math.sin(a)), fill=(252, 240, 170), width=7)
    circle(d, 10, (252, 240, 170), lx, ly)
    return img


def kompot(rnd):
    img = background((246, 204, 206), (232, 160, 170))
    shadow(img, 400, dy=30)
    d = ImageDraw.Draw(img)
    circle(d, 400, (236, 244, 248))
    circle(d, 372, (188, 34, 58))
    circle(d, 330, (206, 46, 70))
    for _ in range(11):
        x, y = disc_point(rnd, 250, 0.7)
        r = rnd.uniform(48, 66)
        circle(d, r, (140, 16, 40), x, y)
        circle(d, r * 0.8, (164, 24, 50), x - 5, y - 6)
        ell(d, x - r * 0.3, y - r * 0.34, r * 0.24, r * 0.12, -0.6, (226, 110, 130))
    for _ in range(6):
        x, y = disc_point(rnd, 270)
        ell(d, x, y, 60, 26, rnd.random() * 3.14, (244, 190, 96))
    ell(d, CX - 170, CY - 190, 150, 40, -0.7, (236, 120, 140))
    return img


DISHES = {"osh": osh, "lagmon": lagmon, "manti": manti, "shashlik": shashlik, "salat": salat, "choy": choy, "kompot": kompot}

if __name__ == "__main__":
    out = sys.argv[1]
    for index, (name, fn) in enumerate(DISHES.items()):
        img = fn(random.Random(1000 + index))
        img = img.resize((W, H), Image.LANCZOS)
        img.save(f"{out}/{name}.jpg", quality=84, optimize=True)
        print(name, img.size)
