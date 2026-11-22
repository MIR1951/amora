# Amora: R8 (release) uchun qoidalar.
# OkHttp, Okio, Coil, Firebase, AndroidX va kotlinx.coroutines o'z qoidalarini kutubxona ichida
# olib keladi (consumer rules). Bu yerda faqat ular qamramaydigan narsalar turadi.

# Xato hisobotlarida satr raqamlari saqlansin (mapping.txt bilan asl nomlarga qaytariladi)
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile

# ---------- kotlinx.serialization ----------
# @Serializable klasslarining serializer'lari (kutubxonaning tavsiya etilgan qoidalari).
-keepattributes RuntimeVisibleAnnotations,AnnotationDefault,InnerClasses

-if @kotlinx.serialization.Serializable class **
-keepclassmembers class <1> {
    static <1>$Companion Companion;
}

-if @kotlinx.serialization.Serializable class ** {
    static **$* *;
}
-keepclassmembers class <2>$<3> {
    kotlinx.serialization.KSerializer serializer(...);
}

-if @kotlinx.serialization.Serializable class ** {
    public static ** INSTANCE;
}
-keepclassmembers class <1> {
    public static <1> INSTANCE;
    kotlinx.serialization.KSerializer serializer(...);
}

-keepclassmembers class uz.amora.app.**$$serializer {
    *** INSTANCE;
}

-dontnote kotlinx.serialization.**
-dontwarn kotlinx.serialization.internal.ClassValueReferences

# ---------- OkHttp / Okio ----------
# Ixtiyoriy platformalar (Android'da yo'q): ular haqidagi ogohlantirishlar kerak emas
-dontwarn okhttp3.internal.platform.**
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**

# ---------- osmdroid ----------
# Xarita kutubxonasi o'z qoidalarini olib kelmaydi; ba'zi klasslari nomi bo'yicha (reflection)
# chaqiriladi: xarita manbalari, kesh (SQLite) va sozlamalar
-keep class org.osmdroid.** { *; }
-dontwarn org.osmdroid.**

# ---------- Firebase Messaging ----------
# Manifestda yozilgan xizmat (AAPT qoidasi ham saqlaydi, bu yerda aniqlik uchun)
-keep class uz.amora.app.notify.PushService { *; }
