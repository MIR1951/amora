"""Do'konlar (App Store, Google Play) talab qiladigan ochiq sahifalar: maxfiylik siyosati va
hisobni o'chirish yo'riqnomasi. Oddiy HTML, tashqi fayl va skriptlarsiz."""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

OWNER = "Amora kafe"
CONTACT_PHONE = "+998 77 223 19 51"
CONTACT_TEL = "+998772231951"
UPDATED = "2026-11-27"

router = APIRouter(include_in_schema=False)

_STYLE = """
:root { color-scheme: light dark; }
body { margin: 0; font: 17px/1.6 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
       background: #f6f2ec; color: #1d1a17; }
main { max-width: 720px; margin: 0 auto; padding: 32px 16px 64px; }
h1 { font-size: 28px; line-height: 1.2; margin: 0 0 4px; }
h2 { font-size: 20px; margin: 32px 0 8px; }
p, li { margin: 8px 0; }
ul, ol { padding-left: 22px; }
.muted { color: #6b635b; font-size: 15px; }
a { color: #c2410c; }
hr { border: 0; border-top: 1px solid #d9d2c8; margin: 40px 0; }
@media (prefers-color-scheme: dark) {
  body { background: #12100e; color: #f1ece6; }
  .muted { color: #a59c92; }
  a { color: #fb923c; }
  hr { border-top-color: #3a342e; }
}
"""


def _page(title: str, body: str) -> HTMLResponse:
    html = (
        '<!doctype html><html lang="uz"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{title}</title><style>{_STYLE}</style></head><body><main>{body}</main></body></html>"
    )
    return HTMLResponse(html)


_CONTACT = f'{OWNER}, telefon: <a href="tel:{CONTACT_TEL}">{CONTACT_PHONE}</a>'

PRIVACY = f"""
<h1>Maxfiylik siyosati</h1>
<p class="muted">Amora ilovasi · {OWNER} · yangilangan: {UPDATED} · <a href="#en">English</a></p>

<p>Amora — {OWNER}ning taom yetkazib berish ilovasi. Bu sahifada ilova qanday ma'lumotlarni
to'plashi, ulardan nima uchun foydalanishi va ularni qanday o'chirish mumkinligi yozilgan.</p>

<h2>Qanday ma'lumotlar to'planadi</h2>
<ul>
<li><b>Ism va telefon raqami.</b> Raqam Telegram orqali tasdiqlanadi: siz botga o'z raqamingizni
yuborasiz. Shu bilan birga Telegram hisobingizning raqami (ID) va ko'rinadigan ismi saqlanadi.</li>
<li><b>Yetkazish manzili.</b> Xaritada belgilagan nuqtangiz (koordinatalar) va manzil izohi.
Joylashuv faqat manzilni tanlash paytida, ruxsatingiz bilan so'raladi; fonda kuzatilmaydi.</li>
<li><b>Buyurtmalar.</b> Taomlar, summa, vaqt, buyurtma holati va kafe uchun yozgan izohingiz.</li>
<li><b>Bildirishnoma manzili.</b> Buyurtma holati haqida xabar yuborish uchun qurilmangizning
push-tokeni.</li>
</ul>
<p>Ilova reklama ko'rsatmaydi, sizni boshqa ilova va saytlarda kuzatmaydi, tahlil (analytics)
xizmatlaridan foydalanmaydi. To'lov kuryerga naqd beriladi: ilova karta ma'lumotlarini so'ramaydi.</p>

<h2>Ma'lumotlar nima uchun kerak</h2>
<ul>
<li>buyurtmani qabul qilish, tayyorlash va manzilingizga yetkazish;</li>
<li>buyurtma bo'yicha siz bilan bog'lanish (kuryer qo'ng'iroq qilishi mumkin);</li>
<li>buyurtma holati haqida bildirishnoma yuborish;</li>
<li>soxta buyurtmalarning oldini olish.</li>
</ul>

<h2>Ma'lumotlar kimga beriladi</h2>
<ul>
<li><b>Kafe xodimlari va kuryer.</b> Buyurtmangiz (ism, raqam, manzil, taomlar) kafening yopiq
Telegram guruhiga yuboriladi.</li>
<li><b>Telegram.</b> Raqamni tasdiqlash va xodimlar guruhi Telegram orqali ishlaydi.</li>
<li><b>Google Firebase Cloud Messaging va Apple Push Notification service.</b> Bildirishnomalar
shu xizmatlar orqali yetkaziladi.</li>
<li><b>Xarita xizmatlari.</b> Xarita ko'rsatilganda xarita bo'laklari OpenStreetMap (Android) yoki
Apple Maps (iPhone) serverlaridan yuklanadi.</li>
</ul>
<p>Ma'lumotlaringiz sotilmaydi va reklama maqsadida hech kimga berilmaydi.</p>

<h2>Saqlash va himoya</h2>
<p>Ma'lumotlar kafe serverida saqlanadi, ilova server bilan faqat shifrlangan (HTTPS) aloqa orqali
ishlaydi. Kirish kaliti telefoningizda himoyalangan xotirada turadi. Ma'lumotlar hisobingiz mavjud
bo'lgan vaqt davomida saqlanadi.</p>

<h2>Hisobni va ma'lumotlarni o'chirish</h2>
<p>Hisobingizni istalgan vaqtda ilovaning o'zidan o'chirishingiz mumkin: <b>Profil → Hisobni
o'chirish</b>. Batafsil: <a href="/delete-account">hisobni o'chirish</a>. O'chirilganda hisobingiz,
ismingiz, Telegram hisobingiz bilan bog'lanish, manzillaringiz va izohlaringiz o'chiriladi. Eski
buyurtmalarning taomlari, summasi, vaqti va buyurtmada ko'rsatilgan telefon raqami kafening
hisob-kitobi va soxta buyurtmalarning oldini olish uchun saqlanadi.</p>

<h2>Bolalar</h2>
<p>Ilova 13 yoshdan kichik bolalar uchun mo'ljallanmagan va ulardan bila turib ma'lumot to'plamaydi.</p>

<h2>O'zgarishlar va aloqa</h2>
<p>Siyosat o'zgarsa, yangi matn shu sahifada e'lon qilinadi. Savollar uchun: {_CONTACT}.</p>

<hr>

<h1 id="en">Privacy Policy</h1>
<p class="muted">Amora app · {OWNER} (Amora cafe), Uzbekistan · updated: {UPDATED}</p>

<p>Amora is the food delivery app of Amora cafe. This page explains what data the app collects,
why, and how you can delete it.</p>

<h2>Data we collect</h2>
<ul>
<li><b>Name and phone number.</b> The phone number is verified through Telegram: you share your
own number with our bot. We also store your Telegram account ID and display name.</li>
<li><b>Delivery address.</b> The point you choose on the map (coordinates) and your address note.
Location is requested only while you choose an address, with your permission, and is never tracked
in the background.</li>
<li><b>Orders.</b> Items, totals, time, order status and the comment you write for the cafe.</li>
<li><b>Push token.</b> Your device's push token, used to notify you about your order status.</li>
</ul>
<p>The app shows no ads, does not track you across other apps or websites and uses no analytics
services. Payment is made in cash to the courier; the app never asks for card details.</p>

<h2>Why we use it</h2>
<ul>
<li>to accept, prepare and deliver your order;</li>
<li>to contact you about your order (the courier may call you);</li>
<li>to send order status notifications;</li>
<li>to prevent fake orders.</li>
</ul>

<h2>Who receives it</h2>
<ul>
<li><b>Cafe staff and couriers:</b> your order (name, phone, address, items) is sent to the cafe's
private Telegram group.</li>
<li><b>Telegram:</b> phone verification and the staff group run on Telegram.</li>
<li><b>Google Firebase Cloud Messaging and Apple Push Notification service:</b> deliver
notifications.</li>
<li><b>Map providers:</b> map tiles are loaded from OpenStreetMap (Android) or Apple Maps (iPhone).</li>
</ul>
<p>We do not sell your data or share it for advertising.</p>

<h2>Storage and security</h2>
<p>Data is stored on the cafe's server and is sent only over encrypted (HTTPS) connections. Your
sign-in key is kept in protected storage on your phone. Data is kept for as long as your account
exists.</p>

<h2>Deleting your account and data</h2>
<p>You can delete your account at any time inside the app: <b>Profil → Hisobni o'chirish</b>
(Profile → Delete account). See <a href="/delete-account#en">account deletion</a>. Deleting removes
your account, name, Telegram link, addresses and comments. The items, totals, time and the phone
number of past orders are kept for the cafe's bookkeeping and to prevent fake orders.</p>

<h2>Children</h2>
<p>The app is not directed at children under 13 and does not knowingly collect their data.</p>

<h2>Changes and contact</h2>
<p>Changes to this policy are published on this page. Contact: {_CONTACT}.</p>
"""

DELETE_ACCOUNT = f"""
<h1>Hisobni o'chirish</h1>
<p class="muted">Amora ilovasi · {OWNER} · <a href="#en">English</a></p>

<h2>Ilovadan o'chirish</h2>
<ol>
<li>Amora ilovasini oching va yuqoridagi <b>Profil</b> tugmasini bosing.</li>
<li>Sahifaning pastidagi <b>Hisobni o'chirish</b> tugmasini bosing va tasdiqlang.</li>
</ol>
<p>Tugallanmagan buyurtmangiz bo'lsa, avval u yetkazilishi yoki bekor qilinishi kerak.</p>

<h2>Ilovasiz o'chirish</h2>
<p>Ilova o'rnatilmagan bo'lsa, kafega qo'ng'iroq qiling: {_CONTACT}. Hisobingiz ro'yxatdan o'tgan
raqamdan murojaat qiling, hisob 7 kun ichida o'chiriladi.</p>

<h2>Nima o'chiriladi</h2>
<ul>
<li><b>O'chiriladi:</b> hisobingiz, ism, Telegram hisobi bilan bog'lanish, yetkazish manzillari
va izohlar, barcha qurilmalardagi kirish kalitlari va bildirishnoma manzillari.</li>
<li><b>Qoladi:</b> eski buyurtmalarning taomlari, summasi, vaqti va buyurtmada ko'rsatilgan telefon
raqami. Ular kafening hisob-kitobi va soxta buyurtmalarning oldini olish uchun saqlanadi va endi
hech qaysi hisobda ko'rinmaydi.</li>
</ul>
<p>Batafsil: <a href="/privacy">maxfiylik siyosati</a>.</p>

<hr>

<h1 id="en">Delete your account</h1>
<p class="muted">Amora app · {OWNER} (Amora cafe)</p>

<h2>In the app</h2>
<ol>
<li>Open the Amora app and tap <b>Profil</b> (Profile) at the top.</li>
<li>Tap <b>Hisobni o'chirish</b> (Delete account) at the bottom of the page and confirm.</li>
</ol>
<p>If you have an unfinished order, it must be delivered or cancelled first.</p>

<h2>Without the app</h2>
<p>If you no longer have the app, call the cafe: {_CONTACT}. Please call from the phone number of
your account; the account is deleted within 7 days.</p>

<h2>What is deleted</h2>
<ul>
<li><b>Deleted:</b> your account, name, Telegram link, delivery addresses and notes, sign-in keys
and push tokens on all devices.</li>
<li><b>Kept:</b> the items, totals, time and phone number of past orders. They are kept for the
cafe's bookkeeping and to prevent fake orders, and are no longer visible in any account.</li>
</ul>
<p>More: <a href="/privacy#en">privacy policy</a>.</p>
"""


@router.get("/privacy", response_class=HTMLResponse)
async def privacy() -> HTMLResponse:
    return _page("Amora: maxfiylik siyosati", PRIVACY)


@router.get("/delete-account", response_class=HTMLResponse)
async def delete_account() -> HTMLResponse:
    return _page("Amora: hisobni o'chirish", DELETE_ACCOUNT)
