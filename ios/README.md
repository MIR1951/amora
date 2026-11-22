# Amora iOS ilovasi

Amora kafe yetkazib berish xizmatining iPhone uchun ilovasi. Android ilovasining (`android/`) Swift va
SwiftUI'dagi aynan o'xshashi: bir xil ekranlar, bir xil o'zbekcha matnlar, bir xil dizayn (ranglar,
shriftlar, "shisha" panellar, ikonkalar) va bir xil server (`backend/`, `/api/v1/...`).

- Menyu, taom haqida ma'lumot, savat, promokod va birinchi buyurtma chegirmasi
- Yetkazish manzilini xaritada tanlash (MapKit), yetkazish hududini tekshirish
- Raqamni Telegram bot orqali tasdiqlash
- Buyurtma berish, holatini jonli kuzatish, bekor qilish, buyurtmalar tarixi, qayta buyurtma
- Buyurtma holati haqida bildirishnomalar: ilova ochiq paytda jonli ulanish orqali, yopiq paytda
  server yuboradigan push (APNs) orqali
- Hisobdan chiqish va hisobni o'chirish (profil sahifasida)

Uchinchi tomon kutubxonalari ishlatilmaydi. Eng past versiya: iOS 17. Loyiha fayli (`Amora.xcodeproj`)
repoda saqlanmaydi: u `project.yml` dan [XcodeGen](https://github.com/yonaskolb/XcodeGen) bilan yaratiladi.

## Papkalar

```
ios/
  project.yml          XcodeGen loyihasi: Amora (ilova), AmoraTests (birlik sinovlari), AmoraUITests (UI sinovi)
  Amora/               ilova kodi (App, Theme, Components, Data, Util, Features/...)
  AmoraTests/          server kerak bo'lmagan tez sinovlar (SSE, holatlar tartibi, JSON o'qish, qidiruv)
  AmoraUITests/        SmokeTests.swift: buyurtmaning butun yo'lini simulyatorda bosib chiqadi
  ci/                  CI yordamchilari
    asc.py               TestFlight uchun vaqtinchalik imzo (App Store Connect API)
    select_xcode.sh      runner'dagi eng yangi Xcode 26.x ni tanlaydi
    control_server.py    UI sinovi sinov serverini shu orqali boshqaradi (kafe xodimi o'rnida)
    init_db.py           SQLite sinov bazasida jadvallarni yaratadi
    pick_simulator.py    sinov uchun iPhone simulyatorini tanlaydi
    customer_location.py simulyator joylashuvi: kafedan 150 metrcha narida
```

## CI qanday yig'adi va sinaydi

`.github/workflows/ios.yml` `ios/` papkasida o'zgarish bo'lganda (va qo'lda, "Run workflow" orqali)
GitHub'ning macOS runner'ida ishlaydi:

1. Runner'dagi eng yangi Xcode 26.x tanlanadi (`ios/ci/select_xcode.sh`), `xcodegen generate` loyihani yaratadi.
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

Kerak: macOS, Xcode 26 yoki yangirog'i (App Store'dan) va [Homebrew](https://brew.sh).

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

Mahalliy server (shifrlanmagan `http://127.0.0.1`) faqat Debug yig'ishda ishlaydi: Release ilovasidan
`NSAllowsLocalNetworking` istisnosi olib tashlanadi va `AMORA_API_BASE_URL` muhit o'zgaruvchisi o'qilmaydi.

### Birlik sinovlari

Server kerak emas, bir necha soniyada o'tadi:

```bash
xcodebuild test -project ios/Amora.xcodeproj -scheme Amora \
  -destination "platform=iOS Simulator,name=iPhone 16" \
  -only-testing:AmoraTests CODE_SIGNING_ALLOWED=NO
```

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

## TestFlight'ga yuklash (haqiqiy iPhone)

`.github/workflows/ios-testflight.yml` imzolangan ilovani yig'ib, App Store Connect'ga yuklaydi.
Mac kerak emas. Faqat qo'lda ishga tushadi: GitHub → Actions → **iOS TestFlight** → **Run workflow**.

### Bir martalik tayyorgarlik

1. developer.apple.com → Identifiers: App ID `uz.amora.app`, **Push Notifications** yoqilgan
   (yo'q bo'lsa, workflow o'zi yaratadi va push'ni yoqadi).
2. appstoreconnect.apple.com → Apps → **+** → New App: Bundle ID `uz.amora.app`, SKU `amora-ios`.
3. App Store Connect → Users and Access → Integrations → App Store Connect API → Team Keys → **+**,
   Access: **Admin** (sertifikat va profil yaratish uchun kerak). `.p8` faqat bir marta yuklanadi.
4. GitHub → Settings → Secrets and variables → Actions → **New repository secret**:
   - `APPLE_TEAM_ID`: Team ID (developer.apple.com → Membership, 10 belgi)
   - `ASC_KEY_ID`: API kalitining Key ID si
   - `ASC_ISSUER_ID`: Issuer ID (API kalitlari sahifasining tepasida)
   - `ASC_KEY_P8`: `.p8` faylning to'liq matni, BEGIN/END qatorlari bilan

   Kalitni hech qachon chatga, issue'ga, commit'ga yozmang: kim ko'rsa, ilova nomidan versiya chiqara oladi.
   Repo ochiq bo'lsa ham sirlar boshqalarga ko'rinmaydi va begona PR'larga berilmaydi.

### Workflow nima qiladi

1. `ios/ci/asc.py check`: kalitni tekshiradi, bundle ID va push imkoniyatini, ilova yozuvini topadi,
   yangi build raqamini tanlaydi (avval yuklanganlarning eng kattasidan +1, kamida run raqami).
2. Xcode 26 tanlanadi (App Store 2026 aprelidan iOS 26 SDK talab qiladi), `xcodegen generate`.
3. `asc.py signing`: runner ichida yangi kalit yaratib, App Store Connect API orqali vaqtinchalik
   **Apple Distribution** sertifikati va **App Store** profili ("Amora CI <run id> <sertifikat ID>") oladi. Kalit faqat
   vaqtinchalik keychain'da turadi.
4. `xcodebuild archive` (Release, qo'lda imzo), so'ng tekshiruv: server manzili `https://amora.mirjoy.uz`,
   build raqami to'g'ri, `aps-environment = production`.
5. `xcodebuild -exportArchive` (`app-store-connect`) → `.ipa`, `xcrun altool --upload-app` bilan yuklash.
6. Har doim (xato bo'lsa ham) `asc.py cleanup`: vaqtinchalik sertifikat va profil o'chiriladi,
   keychain va kalit fayli o'chiriladi. Akkauntdagi boshqa sertifikatlarga tegilmaydi: oldingi uzilib
   qolgan ishlardan qolgan "Amora CI ..." profillaridan faqat nomida ID si yozilgan (ya'ni shu skript
   o'zi yaratgan) sertifikat bekor qilinadi, profilga shunchaki biriktirilgan boshqa sertifikat emas. Apple TestFlight va
   App Store ilovalarini o'zi qayta imzolaydi, shuning uchun sertifikatni o'chirish yuklangan build'ga ta'sir qilmaydi.

Yuklangandan keyin Apple build'ni 5–30 daqiqada qayta ishlaydi va u App Store Connect → TestFlight'da
ko'rinadi. **Internal Testing** guruhiga jamoa a'zolarini qo'shsangiz, ular iPhone'dagi TestFlight ilovasi
orqali darhol o'rnatadi (Apple tekshiruvisiz). Jamoadan tashqaridagilar (External Testing) uchun birinchi
build Apple'ning qisqa beta tekshiruvidan o'tadi.

Agar akkauntda Apple Distribution sertifikatlari chegarasi to'lgan bo'lsa (3 ta), workflow buni aytib to'xtaydi:
developer.apple.com → Certificates bo'limida keraksizini o'chirish kerak.
