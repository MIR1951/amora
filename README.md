# Amora

Amora kafe uchun yetkazib berish xizmati. Mijoz mobil ilovada buyurtma beradi, buyurtma kafening Telegram guruhiga keladi, to'lov kuryerga naqd beriladi.

| Qism | Texnologiya | Holati |
|---|---|---|
| `backend/` server (API) | Python, FastAPI, PostgreSQL | tayyor |
| Telegram bot (buyurtmalar guruhi va admin bo'limi) | Python, aiogram | tayyor |
| `android/` Android ilova | Kotlin, Jetpack Compose | sinovda |
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
| `GET /events` | Jonli yangilanishlar oqimi (Server-Sent Events) |

Token kerak bo'lgan so'rovlarda `Authorization: Bearer <token>` sarlavhasi yuboriladi.

### Jonli yangilanishlar

Ilova ochiq turganda `GET /events` ga bitta doimiy ulanish ushlab turadi. Bazada biror narsa o'zgarsa (admin botda taomni "tugadi" deb belgiladi, narxni o'zgartirdi, kafeni to'xtatdi, xodim buyurtmani qabul qildi), server shu ulanish orqali qisqa xabar yuboradi va ilova kerakli ma'lumotni o'zi qayta o'qiydi: sahifani yangilash shart emas.

| Xabar | Ma'nosi |
|---|---|
| `ready` | Ulanish o'rnatildi |
| `menu` | Menyu o'zgardi: `GET /menu` qayta o'qiladi |
| `shop` | Kafe sozlamalari o'zgardi: `GET /shop` qayta o'qiladi |
| `order` | Mijozning buyurtmasi holati o'zgardi (`order_id`, `status`, `status_label`). Faqat token yuborilgan bo'lsa va faqat buyurtma egasiga keladi |
| `resync` | Ba'zi xabarlar o'tkazib yuborilgan bo'lishi mumkin: hammasi qayta o'qiladi |

Qanday ishlaydi (`backend/app/events.py`): API ham, bot ham bazaga bitta umumiy joydan yozadi va har bir yozuv o'zi hodisaga aylanadi, kodda buni alohida chaqirish shart emas. Bot va API alohida jarayonlar bo'lgani uchun hodisa PostgreSQL'ning `NOTIFY` kanali orqali uzatiladi: tranzaksiya saqlansa yetib boradi, bekor bo'lsa yo'qoladi. Har 20 soniyada ulanishga bo'sh "ping" satri yuboriladi. Ulanishlar soni cheklangan: jami 2000 ta, bitta mijozga 4 ta (ortig'i ochilsa, eng eskisi yopiladi), ro'yxatdan o'tmagan ilovalar uchun bitta manzildan 60 ta (ortig'iga `429`). Server to'xtatilganda (`docker stop`) ochiq ulanishlar darhol yopiladi va ilovalar o'zi qayta ulanadi. Oldinda turgan proksi (Caddy, nginx) bu javobni ushlab turmasligi kerak; Caddy buni o'zi biladi, nginx uchun `X-Accel-Buffering: no` sarlavhasi yuboriladi.

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

Server faqat `127.0.0.1:8000` da ochiladi. Tashqariga chiqarish uchun oldiga proksi (Caddy yoki nginx) qo'yib, HTTPS sertifikat (Let's Encrypt) ulash kerak. Mobil ilova faqat HTTPS manzil bilan ishlaydi.

Server mijozning manzilini proksi yuborgan `X-Forwarded-For` sarlavhasining birinchi yozuvidan oladi: ro'yxatdan o'tish va jonli ulanishlar soni shu manzil bo'yicha cheklanadi. Shuning uchun proksi bu sarlavhani mijoz yuborganiga qo'shib emas, o'zi qaytadan yozishi kerak. Caddy (2.5 va keyingi) buni o'zi qiladi. nginx'da `proxy_set_header X-Forwarded-For $remote_addr;` yozilishi kerak (`$proxy_add_x_forwarded_for` emas): aks holda bitta kompyuter sarlavhani soxtalashtirib, cheklovni chetlab o'tishi mumkin.

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

## Android ilova

`android/` papkasida. Kotlin va Jetpack Compose'da yozilgan, Android 7.0 va undan yuqorisida ishlaydi.

Ekranlar: menyu (kafe satri, banner, qidiruv, bo'limlar, taom oynasi, suzuvchi savat paneli), savat (summa serverda hisoblanadi), xaritadan manzil tanlash, buyurtma holati, buyurtmalar tarixi, profil (ism va telefon). Bosh sahifa: menyu. Buyurtmalar va profil uning yuqori satridagi ikki tugmadan ochiladi, pastki menyu yo'q. Ekranlar bir-biriga o'ngdan sirpanib o'tadi, ma'lumot yuklanayotganda sahifa shaklidagi skelet ko'rinadi.

Dizayn asosi `android/app/src/main/java/uz/amora/app/ui/theme/Theme.kt` da (ranglar, shrift, burchaklar), umumiy tugma va kartochkalar `ui/components/Components.kt` da, harakatlar (ekran o'tishlari, bosilgandagi siqilish, skelet) `ui/components/Motion.kt` da. Kafe o'z logotipi va ranglarini bersa, asosan `Theme.kt` o'zgaradi. Shriftlar: sarlavha va narxlar Bricolage Grotesque, matn Instrument Sans (ikkalasi ochiq litsenziyali, matni `android/licenses/` da).

"Suyuq shisha" (liquid glass) panellar `ui/components/Glass.kt` da: yuqori satr, pastki tugma joyi, savat paneli va xarita ustidagi tugmalar ortidagi kontentni xira shisha orqali ko'rsatadi ([Haze](https://github.com/chrisbanes/haze) kutubxonasi). Haqiqiy xiralashtirish Android 12L va undan yangi telefonlarda ishlaydi, eskiroqlarida o'rniga deyarli shaffof bo'lmagan rang chiziladi. Shisha panel har doim suriladigan kontentning yonida turishi kerak, ichida emas.

Qanday ishlaydi:

- Mijoz menyuni ro'yxatdan o'tmasdan ko'radi. Birinchi buyurtma paytida ism va telefon so'raladi, server bergan kalit telefonda saqlanadi.
- Xarita OpenStreetMap: kalit ham, to'lov ham kerak emas. Joylashuv Google xizmatlarisiz, telefonning o'z GPS'i orqali aniqlanadi.
- Ilova ochiq turganda server bilan jonli ulanish ushlab turiladi (`data/Realtime.kt`, `data/LiveUpdates.kt`): menyu, kafe holati, faol buyurtmalar va ochiq turgan buyurtma ekrani serverdagi o'zgarishdan keyin o'zi yangilanadi. Ulanish uzilsa, ilova o'zi qayta ulanadi va shu orada avvalgidek vaqti-vaqti bilan so'rab turadi (buyurtma holati har 7 soniyada).
- Buyurtma holati o'zgarganda bildirishnoma chiqadi (`notify/OrderNotifier.kt`), bosilsa o'sha buyurtma ochiladi. Ruxsat birinchi buyurtmadan keyin so'raladi, keyin profil sahifasidagi "Bildirishnomalar" qatoridan boshqariladi. Bildirishnoma jonli ulanishga tayanadi: ilova ochiq yoki yaqinda orqa fonga o'tgan bo'lsa keladi. Ilova butunlay yopiq paytda ham kelishi uchun Firebase (FCM) kerak, u hali ulanmagan.
- Har bir buyurtmaga takrorlanmas raqam biriktiriladi: internet uzilib, buyurtma qayta yuborilsa ham u ikkilanmaydi.

Server manzili bitta joyda turadi: `android/gradle.properties` dagi `amora.apiBaseUrl`. Domen o'zgarsa faqat shu qator almashtiriladi.

### APK yig'ish

APK GitHub Actions'da yig'iladi (`.github/workflows/android.yml`): testlar o'tadi, APK tayyorlanadi, so'ng ilova emulyatorda ikki marta sinaladi (`android/ci/smoke_test.py`):

- mijozlar oladigan APK haqiqiy server bilan ochiladi: menyu, savat, xarita, profil. Bu sinov serverga faqat o'qish so'rovlarini yuboradi, buyurtma bermaydi;
- sinov APK'si shu ishning o'zida ko'tarilgan sinov serveri bilan buyurtmaning butun yo'lini bosib o'tadi: buyurtma berish, kafe qabul qilishi, kuryer yo'lga chiqishi, yetkazilishi, mijoz bekor qilishi, kafe rad etishi, qayta buyurtma berish. Kafe xodimining tugmalari o'rnini `android/ci/backend_ctl.py` bosadi. Haqiqiy kafega hech narsa yuborilmaydi.

Tayyor APK va ekran rasmlari har bir ishga tushirishning "Artifacts" bo'limida va `ci-artifacts` shoxida turadi (shoxda faqat oxirgi yig'ilgan versiya).

Kompyuterda yig'ish uchun Android SDK va JDK 17 kerak:

```bash
cd android
./gradlew testReleaseUnitTest assembleRelease
# natija: app/build/outputs/apk/release/app-release.apk
```

APK `android/keystore/amora-test.jks` sinov kaliti bilan imzolanadi. Bu kalit repoda ochiq turadi va faqat sinov uchun. Do'konga (Google Play) chiqariladigan versiya alohida, maxfiy kalit bilan imzolanadi.

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
    events.py     jonli yangilanishlar: bazadagi o'zgarishni ilovalarga yetkazish
  migrations/     baza sxemasi o'zgarishlari
  tests/
android/
  app/src/main/java/uz/amora/app/
    data/         server bilan aloqa, savat, telefonda saqlanadigan ma'lumotlar
    ui/           ekranlar (menu, cart, address, profile, order, orders)
    util/         summa, telefon va vaqtni ko'rsatish
  ci/             emulyatordagi sinov
  gradle.properties   server manzili va ilova versiyasi
docker-compose.yml
```
