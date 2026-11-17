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
- **Mijoz.** Raqam Telegram orqali tasdiqlanadi (bepul, SMS kerak emas): ilova botni `t.me/<bot>?start=v_<kod>` havolasi bilan ochadi, mijoz botda "📱 Raqamni yuborish" ni bosadi. Telegram faqat hisob egasining o'z raqamini yuboradi, shuning uchun birovning raqamini yozib bo'lmaydi. Bitta raqam = bitta mijoz: u bir nechta telefondan kirishi mumkin, har bir telefonning o'z maxfiy kaliti bor, buyurtmalar tarixi hammasida bir xil. Raqam tasdiqlanganda shu raqam bilan avval (eski ilovada) ochilgan hisoblarning buyurtmalari ham unga qo'shiladi. Buyurtma faqat tasdiqlangan raqam bilan beriladi. Guruhdagi buyurtmada mijozning Telegram'iga havola bor, bloklash Telegram hisobi bo'yicha ham ishlaydi.
- **Buyurtma.** Summa har doim serverda bazadagi narxlar bo'yicha hisoblanadi. Ilova yuborgan narxga ishonilmaydi.
- **Holatlar.** `new` (kafe javobi kutilmoqda) → `accepted` (tayyorlanmoqda) → `delivering` (kuryer yo'lda) → `delivered`. Kafe istalgan bosqichda rad etishi mumkin (`rejected`), mijoz faqat kafe qabul qilguncha bekor qila oladi (`cancelled`).
- **Yetkazish narxi.** Belgilangan narx, ixtiyoriy "falon summadan bepul" chegarasi va ixtiyoriy masofa chegarasi (kafedan necha km gacha).
- **Soxta buyurtmalardan himoya.** Bitta mijozda bir vaqtda ko'pi bilan 2 ta tugallanmagan buyurtma, raqamni bloklash, ro'yxatdan o'tishga cheklov.

## Telegram bot

**Buyurtmalar guruhi.** Har bir yangi buyurtma guruhga bitta xabar bo'lib keladi: taomlar, summa, mijoz ismi va raqami, manzil. Xabar ostida tugmalar bor:

- `✅ Qabul qilish` → `🚗 Yo'lga chiqdi` → `✅ Yetkazildi`
- `❌ Rad etish`: avval sababini so'raydi, shuning uchun tasodifan bosib yuborilmaydi
- `📍 Google xarita` va `📍 Yandex xarita`: kuryer manzilni xaritada ochadi

Mijoz ismi yonida "🆕 yangi mijoz" yoki "5-buyurtmasi" yoziladi. Har bir bosishda xabar yangilanadi va kim, qachon bosgani yozib qo'yiladi. Mijozning ilovasida holat shu zahoti o'zgaradi. Mijoz buyurtmani bekor qilsa, guruhga alohida xabar keladi.

Telegram vaqtincha ishlamay qolsa ham buyurtma yo'qolmaydi: bot har 20 soniyada guruhga yetib bormagan buyurtmalarni qayta yuboradi.

**Kechikish eslatmasi.** Yangi buyurtma 5 daqiqa qabul qilinmasa yoki 45 daqiqadan ko'p yo'lda tursa, bot guruhdagi buyurtma xabariga javob qilib eslatma yozadi (har holat uchun bir marta). Daqiqalar sozlamalardan o'zgartiriladi, 0 yozilsa eslatma o'chadi.

**Kunlik hisobot.** Kafe yopilgach o'sha ish kunining hisoboti guruhga keladi. Yopilish paytida yo'lda bo'lgan buyurtmalar yetkazilishi kutiladi (ko'pi bilan 1,5 soat), shunda ular ham tushumga kiradi. Sozlamalardan adminlarga yuborish yoki o'chirish mumkin. Kecha-kunduz ishlaganda yarim tunda keladi.

**Admin bo'limi.** Egasi, adminlar va xodimlar botga shaxsiy yozishmada `/start` yozadi:

- **Menyu:** taom qo'shish, nomi, narxi, tavsifi, rasmi va kategoriyasini o'zgartirish, "tugadi" deb belgilash, o'chirish.
- **Kategoriyalar:** qo'shish, nomini o'zgartirish, o'chirish.
- **Sozlamalar:** yetkazish narxi, bepul yetkazish chegarasi, eng kam buyurtma, yetkazish masofasi, ish vaqti, kafe telefoni va joylashuvi, kechikish eslatmasi, kunlik hisobot.
- **Hisobot:** bugun, kecha, 7 kun, 30 kun va shu oy bo'yicha buyurtmalar, tushum, o'rtacha chek, oldingi davr bilan solishtirish, yangi va qaytgan mijozlar, eng band soat, ko'p sotilgan taomlar, rad etish sabablari.
- **Buyurtma qabul qilishni to'xtatish/yoqish:** kafe band bo'lganda bitta tugma.
- `/mijoz 901234567` (yoki `/mijoz 45`, buyurtma raqami bilan): mijoz kartasi. Buyurtmalari, jami xaridi, ko'p oladigan taomlari, soxta buyurtmalari va bloklash tugmasi.
- `/blok 901234567` va `/ochish 901234567`: soxta buyurtma bergan raqamni bloklash.
- **Aksiyalar** (egasi va adminlar): ilovadagi bosh sahifa bannerining sarlavhasi va matni; birinchi buyurtma chegirmasi (yangi mijozga kod kiritmasdan, telefon raqami bo'yicha bir marta); promokodlar (foiz yoki so'm, eng ko'p chegirma, eng kam buyurtma, nechta buyurtmaga, necha kun, faqat yangi mijozlar uchunmi). Har bir mijoz bitta promokodni bir marta ishlatadi; buyurtma bekor qilinsa yoki rad etilsa, promokod qaytadi. Chegirma taomlar summasidan olinadi, yetkazish narxiga tegmaydi. Guruhdagi xabarda va hisobotda chegirma alohida ko'rinadi.
- **Adminlar va xodimlar:** bot bir martalik taklif havolasini beradi (24 soat amal qiladi), yangi odam uni bosib qo'shiladi. Egasi (`AMORA_ADMIN_IDS`) admin va xodim qo'sha oladi, admin faqat xodim. Xodim faqat taomni bor/tugadi qiladi, qabulni to'xtatadi, hisobot va mijoz kartasini ko'radi.

### Botni sozlash

1. Telegram'da [@BotFather](https://t.me/BotFather)'ga `/newbot` yozing, bot oching va bergan tokenini `.env` fayldagi `AMORA_BOT_TOKEN` ga yozing.
2. Botga shaxsiy yozishmada `/start` yozing. U sizning ID raqamingizni aytadi. Shu raqamni `AMORA_ADMIN_IDS` ga yozing (bir nechta admin bo'lsa vergul bilan).
3. Xodimlar uchun guruh oching va botni qo'shing. Bot guruh ID'sini o'zi yozib beradi. Uni `AMORA_ORDERS_CHAT_ID` ga yozing.
4. `docker compose up -d` bilan qayta ishga tushiring.

Token maxfiy: uni hech kimga yubormang va GitHub'ga yuklamang. Guruhdagi har bir a'zo buyurtma tugmalarini bosa oladi, shuning uchun guruhga faqat xodimlarni qo'shing. Kimnidir botdan olib tashlasangiz, guruhdan ham chiqarib qo'ying.

## API

Barcha manzillar `/api/v1` bilan boshlanadi. To'liq interaktiv hujjat server ishga tushgach `/docs` sahifasida ochiladi.

| So'rov | Vazifasi |
|---|---|
| `GET /menu` | Kategoriyalar va taomlar |
| `GET /shop` | Ish vaqti, yetkazish narxi, kafe hozir ochiqmi |
| `POST /auth/telegram` | Raqamni Telegram orqali tasdiqlashni boshlash: kod va bot havolasi |
| `POST /auth/telegram/check` | Mijoz botda raqamini yubordimi: `pending` yoki `verified` + token |
| `POST /auth/register` | Eski ilovalar uchun: raqam tasdiqlanmaydi, bunday hisob buyurtma bera olmaydi |
| `GET /me`, `PATCH /me` | Profil |
| `POST /orders/quote` | Savatni hisoblash: summa, yetkazish narxi, chegirma (`promo_code`, `apply_auto_promo`), buyurtma berish mumkinmi |
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

**Push-bildirishnomalar (Firebase).** Firebase konsolidagi *Project settings → Service accounts → Generate new private key* faylini serverga `~/amora/secrets/firebase.json` qilib qo'ying (bu papka GitHub'ga yuklanmaydi). Bot uni o'zi topadi. Fayl yo'q bo'lsa push o'chiq, qolgan hamma narsa ishlaydi. Tekshirish: `docker compose logs bot | grep -i firebase`. "o'qilmadi" chiqsa, `chmod 644 ~/amora/secrets/firebase.json` qilib, `docker compose up -d` ni qayta ishga tushiring. Ilova tomoni `android/app/google-services.json` dan sozlanadi (u maxfiy emas).

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

- Mijoz menyuni ro'yxatdan o'tmasdan ko'radi. Birinchi buyurtma paytida ism so'raladi va raqam Telegram orqali tasdiqlanadi, server bergan kalit telefonda saqlanadi.
- Xarita OpenStreetMap: kalit ham, to'lov ham kerak emas. Joylashuv Google xizmatlarisiz, telefonning o'z GPS'i orqali aniqlanadi.
- Ilova ochiq turganda server bilan jonli ulanish ushlab turiladi (`data/Realtime.kt`, `data/LiveUpdates.kt`): menyu, kafe holati, faol buyurtmalar va ochiq turgan buyurtma ekrani serverdagi o'zgarishdan keyin o'zi yangilanadi. Ulanish uzilsa, ilova o'zi qayta ulanadi va shu orada avvalgidek vaqti-vaqti bilan so'rab turadi (buyurtma holati har 7 soniyada).
- Buyurtma holati o'zgarganda bildirishnoma chiqadi (`notify/OrderNotifier.kt`), bosilsa o'sha buyurtma ochiladi. Ruxsat birinchi buyurtmadan keyin so'raladi, keyin profil sahifasidagi "Bildirishnomalar" qatoridan boshqariladi. Ilova ochiq paytda bildirishnoma jonli ulanishdan keladi, yopiq paytda esa Firebase (FCM) orqali. Ikkala yo'l bitta joydan o'tadi, shuning uchun bitta o'zgarish uchun bitta bildirishnoma chiqadi. Kafe botdagi "📣 Mijozlarga xabar yuborish" orqali ilovani o'rnatgan hamma telefonga aksiya xabarini yuboradi (bepul).
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
