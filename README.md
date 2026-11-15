# Amora

Amora kafe uchun yetkazib berish xizmati. Mijoz mobil ilovada buyurtma beradi, buyurtma kafening Telegram guruhiga keladi, to'lov kuryerga naqd beriladi.

| Qism | Texnologiya | Holati |
|---|---|---|
| `backend/` server (API) | Python, FastAPI, PostgreSQL | tayyor |
| Telegram bot (buyurtmalar guruhi va admin bo'limi) | Python, aiogram | tayyor |
| Android ilova | Kotlin | rejada |
| iOS ilova | Swift | Android'dan keyin |

## Server qanday ishlaydi

- **Menyu.** Taomlar, narxlar va rasmlar bazada turadi. Tugab qolgan taom o'chirilmaydi, `is_available: false` bo'lib qoladi.
- **Mijoz.** SMS tasdiqlash yo'q: mijoz ism va raqamini yozadi, server qurilmaga maxfiy token beradi. Buyurtmalar tarixi raqamga emas, shu tokenga bog'langan, shuning uchun birovning raqamini yozgan odam uning manzillarini ko'ra olmaydi.
- **Buyurtma.** Summa har doim serverda bazadagi narxlar bo'yicha hisoblanadi. Ilova yuborgan narxga ishonilmaydi.
- **Holatlar.** `new` (kafe javobi kutilmoqda) → `accepted` (tayyorlanmoqda) → `delivering` (kuryer yo'lda) → `delivered`. Kafe istalgan bosqichda rad etishi mumkin (`rejected`), mijoz faqat kafe qabul qilguncha bekor qila oladi (`cancelled`).
- **Yetkazish narxi.** Belgilangan narx, ixtiyoriy "falon summadan bepul" chegarasi va ixtiyoriy masofa chegarasi (kafedan necha km gacha).
- **Soxta buyurtmalardan himoya.** Bitta mijozda bir vaqtda ko'pi bilan 2 ta tugallanmagan buyurtma, raqamni bloklash, ro'yxatdan o'tishga cheklov.

## Telegram bot

**Buyurtmalar guruhi.** Har bir yangi buyurtma guruhga bitta xabar bo'lib keladi: taomlar, summa, mijoz ismi va raqami, manzil. Xabar ostida tugmalar bor:

- `✅ Qabul qilish` → `🚗 Yo'lga chiqdi` → `✅ Yetkazildi`
- `❌ Rad etish`: avval sababini so'raydi, shuning uchun tasodifan bosib yuborilmaydi
- `📍 Google xarita` va `📍 Yandex xarita`: kuryer manzilni xaritada ochadi

Har bir bosishda xabar yangilanadi va kim, qachon bosgani yozib qo'yiladi. Mijozning ilovasida holat shu zahoti o'zgaradi. Mijoz buyurtmani bekor qilsa, guruhga alohida xabar keladi.

Telegram vaqtincha ishlamay qolsa ham buyurtma yo'qolmaydi: bot har 20 soniyada guruhga yetib bormagan buyurtmalarni qayta yuboradi.

**Admin bo'limi.** Adminlar botga shaxsiy yozishmada `/start` yozadi:

- **Menyu:** taom qo'shish, nomi, narxi, tavsifi, rasmi va kategoriyasini o'zgartirish, "tugadi" deb belgilash, o'chirish.
- **Kategoriyalar:** qo'shish, nomini o'zgartirish, o'chirish.
- **Sozlamalar:** yetkazish narxi, bepul yetkazish chegarasi, eng kam buyurtma, yetkazish masofasi, ish vaqti, kafe telefoni va joylashuvi.
- **Bugungi hisobot:** nechta buyurtma, qanchasi yetkazildi va qancha summaga.
- **Buyurtma qabul qilishni to'xtatish/yoqish:** kafe band bo'lganda bitta tugma.
- `/blok 901234567` va `/ochish 901234567`: soxta buyurtma bergan raqamni bloklash.

### Botni sozlash

1. Telegram'da [@BotFather](https://t.me/BotFather)'ga `/newbot` yozing, bot oching va bergan tokenini `.env` fayldagi `AMORA_BOT_TOKEN` ga yozing.
2. Botga shaxsiy yozishmada `/start` yozing. U sizning ID raqamingizni aytadi. Shu raqamni `AMORA_ADMIN_IDS` ga yozing (bir nechta admin bo'lsa vergul bilan).
3. Xodimlar uchun guruh oching va botni qo'shing. Bot guruh ID'sini o'zi yozib beradi. Uni `AMORA_ORDERS_CHAT_ID` ga yozing.
4. `docker compose up -d` bilan qayta ishga tushiring.

Token maxfiy: uni hech kimga yubormang va GitHub'ga yuklamang. Guruhdagi har bir a'zo buyurtma tugmalarini bosa oladi, shuning uchun guruhga faqat xodimlarni qo'shing.

## API

Barcha manzillar `/api/v1` bilan boshlanadi. To'liq interaktiv hujjat server ishga tushgach `/docs` sahifasida ochiladi.

| So'rov | Vazifasi |
|---|---|
| `GET /menu` | Kategoriyalar va taomlar |
| `GET /shop` | Ish vaqti, yetkazish narxi, kafe hozir ochiqmi |
| `POST /auth/register` | Ism va telefon bilan ro'yxatdan o'tish, token qaytaradi |
| `GET /me`, `PATCH /me` | Profil |
| `POST /orders/quote` | Savatni hisoblash: summa, yetkazish narxi, buyurtma berish mumkinmi |
| `POST /orders` | Buyurtma berish |
| `GET /orders` | Buyurtmalarim |
| `GET /orders/{id}` | Buyurtma holati |
| `POST /orders/{id}/cancel` | Bekor qilish |

Token kerak bo'lgan so'rovlarda `Authorization: Bearer <token>` sarlavhasi yuboriladi.

Xatolar bir xil ko'rinishda qaytadi. `message` mijozga to'g'ridan-to'g'ri ko'rsatish uchun o'zbekcha yozilgan:

```json
{"error": {"code": "shop_closed", "message": "Kafe hozir yopiq. Ish vaqti: 09:00 dan 23:00 gacha"}}
```

## Serverga o'rnatish

Serverda Docker o'rnatilgan bo'lishi kerak.

```bash
git clone <repo manzili> amora && cd amora
cp .env.example .env
nano .env                      # parol va server manzilini yozing
docker compose up -d --build
curl http://127.0.0.1:8000/api/v1/health     # {"status":"ok"} chiqishi kerak
```

Baza jadvallari birinchi ishga tushishda o'zi yaratiladi. Sinov uchun namuna menyu qo'shish:

```bash
docker compose exec api python -m app.seed
```

Server faqat `127.0.0.1:8000` da ochiladi. Tashqariga chiqarish uchun oldiga nginx qo'yib, HTTPS sertifikat (Let's Encrypt) ulash kerak. Mobil ilova faqat HTTPS manzil bilan ishlaydi.

Yangilash:

```bash
git pull && docker compose up -d --build
```

## Kompyuterda ishga tushirish va testlar

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest                                             # testlar (xotiradagi SQLite)

export AMORA_DATABASE_URL=postgresql+asyncpg://user:parol@localhost:5432/amora
alembic upgrade head                               # jadvallarni yaratish
uvicorn app.main:app_factory --factory --reload    # http://127.0.0.1:8000/docs
```

Testlarni haqiqiy PostgreSQL'da yurgizish:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://user:parol@localhost:5432/amora_test pytest
```

## Papkalar

```
backend/
  app/
    api/          so'rovlarni qabul qiluvchi qism
    services/     buyurtma qoidalari (API ham, bot ham shundan foydalanadi)
    models.py     baza jadvallari
    schemas.py    so'rov va javob ko'rinishi
    telegram/     bot: buyurtma xabari, tugmalar, admin bo'limi
    bot.py        botni ishga tushirish (python -m app.bot)
    notifier.py   yangi buyurtma haqida xabar berish
  migrations/     baza sxemasi o'zgarishlari
  tests/
docker-compose.yml
```
