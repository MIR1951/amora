# Amora iOS ilovasi

Amora kafe yetkazib berish xizmatining iPhone uchun ilovasi. Android ilovasining (`android/`) Swift va
SwiftUI'dagi aynan o'xshashi: bir xil ekranlar, bir xil o'zbekcha matnlar, bir xil dizayn (ranglar,
shriftlar, "shisha" panellar, ikonkalar) va bir xil server (`backend/`, `/api/v1/...`).

- Menyu, taom haqida ma'lumot, savat, promokod va birinchi buyurtma chegirmasi
- Yetkazish manzilini xaritada tanlash (MapKit), yetkazish hududini tekshirish
- Raqamni Telegram bot orqali tasdiqlash
- Buyurtma berish, holatini jonli kuzatish, bekor qilish, buyurtmalar tarixi, qayta buyurtma
- Ilova ochiq paytda buyurtma holati haqida bildirishnomalar

Uchinchi tomon kutubxonalari ishlatilmaydi. Eng past versiya: iOS 17. Loyiha fayli (`Amora.xcodeproj`)
repoda saqlanmaydi: u `project.yml` dan [XcodeGen](https://github.com/yonaskolb/XcodeGen) bilan yaratiladi.

## Papkalar

```
ios/
  project.yml          XcodeGen loyihasi: Amora (ilova) va AmoraUITests (UI sinovi)
  Amora/               ilova kodi (App, Theme, Components, Data, Util, Features/...)
  AmoraUITests/        SmokeTests.swift: buyurtmaning butun yo'lini simulyatorda bosib chiqadi
  ci/                  CI yordamchilari
    control_server.py    UI sinovi sinov serverini shu orqali boshqaradi (kafe xodimi o'rnida)
    init_db.py           SQLite sinov bazasida jadvallarni yaratadi
    pick_simulator.py    sinov uchun iPhone simulyatorini tanlaydi
    customer_location.py simulyator joylashuvi: kafedan 150 metrcha narida
```

## CI qanday yig'adi va sinaydi

`.github/workflows/ios.yml` `ios/` papkasida o'zgarish bo'lganda (va qo'lda, "Run workflow" orqali)
GitHub'ning macOS runner'ida ishlaydi:

1. Runner'dagi eng yangi Xcode 16.x tanlanadi, `xcodegen generate` loyihani yaratadi.
2. Ikki xil ilova yig'iladi:
   - **sinov uchun** (Debug): shu ishning ichida ko'tariladigan sinov serveriga qaratilgan
     (`AMORA_API_BASE_URL=http://127.0.0.1:8000`);
   - **mijozlar uchun simulyator ilovasi** (Release): haqiqiy serverga qaratilgan,
     `amora-ios-simulator.zip` bo'lib saqlanadi.
3. Sinov serveri ko'tariladi. macOS'da docker yo'q, shuning uchun PostgreSQL o'rniga SQLite fayli
   ishlatiladi: jadvallar `ios/ci/init_db.py` bilan yaratiladi (Alembic migratsiyalari SQLite'da
   ishlamaydi), namuna menyu, aksiya va promokodlar `android/ci/backend_ctl.py prepare` bilan qo'shiladi.
4. `ios/ci/control_server.py` 127.0.0.1:8099 da ishga tushadi. UI sinovi simulyator ichida ishlaydi va
   kompyuterdagi skriptni chaqira olmaydi, shuning uchun kafe xodimining tugmalari ("qabul qilish",
   "yo'lga chiqdi", "yetkazildi") va mijozning Telegram'da raqam yuborishi shu server orqali bajariladi.
5. Simulyator joylashuvi kafedan 150 metrcha nariga qo'yiladi, joylashuv ruxsati oldindan beriladi,
   ekran videoga yoziladi va `AmoraUITests` ishga tushadi: menyu, taom oynasi, savat, manzil,
   raqamni tasdiqlash, buyurtma berish, holatlar (qabul qilindi, kuryer yo'lda, yetkazildi),
   buyurtmalar tarixi va profil. Har qadam rasmga olinadi.
6. Natijalar ishning "Artifacts" bo'limida: `ios-smoke` (rasmlar va video), `ios-logs`
   (xcodebuild, sinov serveri va simulyator jurnallari, `UITests.xcresult`), `amora-ios-simulator`.
   Bundan tashqari `ci-artifacts-ios` shoxiga oxirgi yig'ilgan versiya yoziladi: `amora-ios-simulator.zip`,
   `screenshots/`, `video.mp4` va `BUILD.txt` (run raqami, commit, sinov natijasi).

Kompilyatsiya xatosi bo'lsa, ish jurnalidagi "Kompilyatsiya xatolari" guruhida `error:` qatorlari
ko'rinadi, to'liq jurnal esa `ios-logs` ichida.

## Simulyator ilovasini ochish (Mac kerak)

1. `ci-artifacts-ios` shoxidan yoki ishning "Artifacts" bo'limidan `amora-ios-simulator.zip` ni yuklab oling va oching.
2. Xcode bilan birga keladigan Simulator'ni oching (Xcode → Open Developer Tool → Simulator).
3. `Amora.app` ni simulyator oynasiga sudrab tashlang: ilova o'rnatiladi va bosh ekranda paydo bo'ladi.

Bu ilova faqat simulyatorda ishlaydi. Haqiqiy iPhone uchun Apple imzosi kerak (pastda).

## Mac'da ishga tushirish

Kerak: macOS, Xcode 16 (App Store'dan) va [Homebrew](https://brew.sh).

```bash
brew install xcodegen
cd ios
xcodegen generate
open Amora.xcodeproj
```

Xcode'da yuqoridan `Amora` sxemasini va biror iPhone simulyatorini tanlab, ▶ (Cmd+R) bosing.
Ilova standart holatda haqiqiy serverga ulanadi. Mahalliy serverga ulash uchun loyihaning
Build Settings bo'limida `AMORA_API_BASE_URL` ni o'zgartiring (masalan `http://127.0.0.1:8000`)
yoki buyruq qatoridan yig'ing:

```bash
xcodebuild build -project ios/Amora.xcodeproj -scheme Amora \
  -destination "platform=iOS Simulator,name=iPhone 16" \
  AMORA_API_BASE_URL=http://127.0.0.1:8000
```

`project.yml` o'zgartirilgandan keyin `xcodegen generate` ni qayta ishga tushiring.
`Amora.xcodeproj` ni qo'lda tahrirlamang: keyingi `xcodegen generate` uni qayta yozadi.

### UI sinovini Mac'da ishga tushirish

Sinov faqat SINOV serveri bilan ishlaydi (kafe nomi "Amora sinov serveri" bo'lishi shart, aks holda
sinov buyurtma bermasdan to'xtaydi). Repo ildizidan:

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements.txt aiosqlite
mkdir -p /tmp/localhost
export AMORA_DATABASE_URL=sqlite+aiosqlite:////tmp/localhost/amora.db
export AMORA_PUBLIC_BASE_URL=http://127.0.0.1:8000 AMORA_MEDIA_DIR=/tmp/amora-media
export AMORA_BOT_USERNAME=amora_test_bot
(cd backend && python ../ios/ci/init_db.py && python ../android/ci/backend_ctl.py prepare)
(cd backend && uvicorn app.main:app_factory --factory --host 127.0.0.1 --port 8000) &
python ios/ci/control_server.py &

TEST_RUNNER_SCREENSHOT_DIR=/tmp/amora-shots TEST_RUNNER_CONTROL_URL=http://127.0.0.1:8099 \
xcodebuild test -project ios/Amora.xcodeproj -scheme Amora \
  -destination "platform=iOS Simulator,name=iPhone 16" \
  -only-testing:AmoraUITests AMORA_API_BASE_URL=http://127.0.0.1:8000
```

## Keyingi qadam: haqiqiy iPhone va TestFlight

Hozircha CI imzosiz (`CODE_SIGNING_ALLOWED=NO`) faqat simulyator uchun yig'adi. Ilovani haqiqiy
iPhone'larga TestFlight orqali tarqatish uchun:

1. **Apple Developer Program** a'zoligi (yiliga 99 $) — kafe nomidan (tashkilot) yoki shaxsiy hisob.
   Tashkilot uchun D-U-N-S raqami kerak bo'ladi.
2. **App Store Connect**'da yangi ilova yaratish: bundle id `uz.amora.app`, nomi `Amora`.
3. `project.yml` da `DEVELOPMENT_TEAM` ga jamoa ID'sini yozish (bu maxfiy emas).
4. **App Store Connect API kaliti**: App Store Connect → Users and Access → Integrations →
   App Store Connect API → yangi kalit ("App Manager" roli). Yuklab olingan `.p8` fayl faqat bir marta
   beriladi.
5. Kalitni **faqat GitHub Secrets**'ga qo'yish (Settings → Secrets and variables → Actions):
   `APP_STORE_CONNECT_KEY_ID`, `APP_STORE_CONNECT_ISSUER_ID`, `APP_STORE_CONNECT_KEY_P8`
   (fayl matni yoki base64). Kalitni, sertifikatni yoki parollarni hech qachon chatga, issue'ga,
   commit'ga yoki jurnalga yozmang: kim ko'rsa, ilovangiz nomidan yangi versiya chiqara oladi.
6. Workflow'ga alohida "TestFlight" ishini qo'shish: `xcodebuild archive` (Release, `generic/platform=iOS`,
   `-allowProvisioningUpdates` va API kaliti bilan avtomatik imzolash), `xcodebuild -exportArchive`
   (`method: app-store-connect`) va `xcrun altool --upload-app` bilan App Store Connect'ga yuklash.
   Kalit ish ichida secrets'dan vaqtinchalik faylga yoziladi va ish tugashi bilan o'chiriladi.
   Har yig'ishda `CURRENT_PROJECT_VERSION` = GitHub run raqami, shuning uchun versiyalar o'z-o'zidan o'sib boradi.
7. Push-bildirishnomalar (ilova yopiq paytda ham) uchun Apple Push Notification kaliti (`.p8`) kerak bo'ladi:
   u ham faqat server sozlamalarida yoki GitHub Secrets'da saqlanadi.

TestFlight'ga birinchi yuklashdan keyin Apple ilovani bir-ikki kun ichida tekshiradi, so'ng sinovchilarni
email orqali taklif qilish mumkin.
