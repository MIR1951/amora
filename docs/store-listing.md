# Do'kon sahifalari uchun materiallar

Google Play Console va App Store Connect'ga ko'chirib qo'yiladigan matnlar va shakllar uchun javoblar.

## Umumiy

| Maydon | Qiymat |
|---|---|
| Ilova nomi | Amora |
| Paket / Bundle ID | `uz.amora.app` |
| Toifa | Food & Drink (Taom va ichimliklar) |
| Maxfiylik siyosati | https://amora.mirjoy.uz/privacy |
| Hisobni o'chirish havolasi (Play) | https://amora.mirjoy.uz/delete-account |
| Aloqa | Amora kafe, +998 77 223 19 51 |
| Narx | Bepul, ilova ichida xarid yo'q, reklama yo'q |

Do'konlar aloqa uchun email ham so'raydi: uni o'zingiz kiritasiz.

## Tavsif (o'zbekcha)

**Qisqa tavsif (80 belgigacha):**
Amora kafesidan taom buyurtma qiling: tez yetkazamiz, to'lov kuryerga naqd.

**To'liq tavsif:**
Amora — Amora kafesining taom yetkazib berish ilovasi.

• Menyu: taomlar, pitsalar, shirinliklar va ichimliklar rasm va narxlari bilan
• Manzilni xaritadan belgilang, yetkazish narxi darhol ko'rinadi
• Buyurtma holatini jonli kuzating: qabul qilindi, tayyorlanmoqda, kuryer yo'lda
• Holat o'zgarganda bildirishnoma keladi
• To'lov kuryerga naqd: karta ma'lumotlari so'ralmaydi
• Promokod va aksiyalar
• Buyurtmalar tarixi va bir bosishda qayta buyurtma

Raqamingiz Telegram orqali bir marta tasdiqlanadi, SMS kutish shart emas.

## Description (English)

**Short:** Order food from Amora cafe: fast delivery, pay the courier in cash.

**Full:**
Amora is the food delivery app of Amora cafe.

• Menu with photos and prices: meals, pizzas, desserts and drinks
• Pick your address on the map and see the delivery fee right away
• Track your order live: accepted, being prepared, courier on the way
• Notifications when the status changes
• Cash on delivery: no card details needed
• Promo codes and offers
• Order history and one-tap reorder

Your phone number is verified once through Telegram, no SMS needed.

## Tekshiruvchi uchun izoh (App Review notes / Play "App access")

Avval serverda `.env` ga `AMORA_REVIEW_CODE=<kod>` yozib, `docker compose up -d` qiling. Quyidagi matndagi `<KOD>` o'rniga o'sha kodni qo'ying.

```
The app normally signs users in by verifying their phone number through a Telegram bot.
For review, use this demo access instead (no Telegram account needed):

1. Add any dish to the cart, open the cart and tap "Manzilni tanlang" to pick a delivery
   point on the map (any point near the suggested location).
2. Tap "Raqamni tasdiqlang". In the "Ism" (Name) field type exactly: <KOD>
3. Tap "Telegram orqali tasdiqlash". Telegram or a browser opens; just return to the app.
   You are now signed in to a demo account.
4. Tap "Buyurtma berish" to place an order. Demo orders are marked as test orders for the
   cafe staff and are not prepared or delivered.

Account deletion: Profil → Hisobni o'chirish.
Payment is cash on delivery; there are no in-app purchases.
The app's language is Uzbek.
```

## Google Play: Data safety

- Ma'lumot to'planadimi: **Ha**. Uzatishda shifrlanadimi: **Ha**. O'chirishni so'rash mumkinmi: **Ha** (havola yuqorida).
- Uchinchi tomonga reklama yoki tahlil uchun beriladimi: **Yo'q**.

| Ma'lumot turi | To'planadi | Maqsad | Majburiymi |
|---|---|---|---|
| Name | Ha | App functionality, Account management | Ha |
| Phone number | Ha | App functionality, Account management, Fraud prevention | Ha |
| User IDs (Telegram hisobi ID) | Ha | Account management, Fraud prevention | Ha |
| Address (manzil izohi) | Ha | App functionality | Ixtiyoriy |
| Precise location (xaritadagi nuqta) | Ha | App functionality | Ha |
| Purchase history (buyurtmalar) | Ha | App functionality | Ha |
| Other user-generated content (kafe uchun izoh) | Ha | App functionality | Ixtiyoriy |
| Device or other IDs (push-token) | Ha | App functionality | Ixtiyoriy |

Qolgan turlar (to'lov ma'lumoti, kontaktlar, rasm, fayl, sog'liq, brauzer tarixi va h.k.): **to'planmaydi**.

## App Store: App Privacy

"Data Used to Track You": **yo'q**. Quyidagilarning hammasi "Data Linked to You", maqsadi "App Functionality":

Name, Phone Number, Physical Address, Precise Location, User ID, Device ID, Purchase History, Other User Content.

## Yosh reytingi

Zo'ravonlik, qimor, spirtli ichimlik, foydalanuvchilar o'rtasida muloqot: **yo'q**. Kutilgan natija: Play'da "Everyone / 3+", App Store'da "4+".

## Ekran rasmlari

CI har yig'ishda ilova ekranlarini suratga oladi: `ci-artifacts` shoxida `screenshots/` (Android) va `ci-artifacts-ios` shoxida `screenshots/` (iPhone). Do'kon uchun `haqiqiy-server` papkasidagilari mos (haqiqiy menyu bilan): menyu, taom oynasi, savat, xarita. Play kamida 2 ta, App Store 6.9 dyuymli iPhone uchun kamida 1 ta rasm so'raydi; o'lcham mos kelmasa, shu ekranlarni telefonda qayta suratga oling.
