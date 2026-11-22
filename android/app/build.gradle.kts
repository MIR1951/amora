plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("org.jetbrains.kotlin.plugin.serialization")
    id("com.google.gms.google-services")
}

val apiBaseUrl = providers.gradleProperty("amora.apiBaseUrl").get().trimEnd('/')
// Sinov (debug) yig'ilishini boshqa serverga qaratish mumkin, masalan CI ichidagi sinov serveriga:
// -Pamora.debugApiBaseUrl=http://10.0.2.2:8000. Berilmasa, asosiy server ishlatiladi.
val debugApiBaseUrl = providers.gradleProperty("amora.debugApiBaseUrl").orNull?.trimEnd('/') ?: apiBaseUrl
val appVersionName = providers.gradleProperty("amora.versionName").get()
val appVersionCode = providers.gradleProperty("amora.versionCode").get().toInt()

// Do'konga chiqariladigan versiya maxfiy kalit bilan imzolanadi. U repoda turmaydi: yo'li va
// parollari muhit o'zgaruvchilaridan olinadi (AMORA_KEYSTORE, AMORA_KEYSTORE_PASSWORD,
// AMORA_KEY_ALIAS, AMORA_KEY_PASSWORD). AMORA_KEYSTORE berilmasa, sinov kaliti ishlatiladi.
val releaseKeystore = providers.environmentVariable("AMORA_KEYSTORE").orNull?.takeIf { it.isNotBlank() }

android {
    namespace = "uz.amora.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "uz.amora.app"
        minSdk = 24
        targetSdk = 35
        versionCode = appVersionCode
        versionName = appVersionName
        buildConfigField("String", "API_BASE_URL", "\"$apiBaseUrl\"")
    }

    signingConfigs {
        // Sinov uchun kalit: repoda ochiq turadi, faqat sinov APK'larini imzolaydi.
        // Do'konga chiqariladigan versiya boshqa, maxfiy kalit bilan imzolanadi.
        create("testing") {
            storeFile = rootProject.file("keystore/amora-test.jks")
            storePassword = "amora-test"
            keyAlias = "amora-test"
            keyPassword = "amora-test"
        }
        if (releaseKeystore != null) {
            create("release") {
                storeFile = file(releaseKeystore)
                // Kalit berilgan-u, paroli yoki nomi yo'q: tushunarsiz imzo xatosidan oldin aniq aytiladi
                fun requiredEnv(name: String): String =
                    providers.environmentVariable(name).orNull?.takeIf { it.isNotEmpty() }
                        ?: throw GradleException("AMORA_KEYSTORE berilgan, lekin $name yo'q: release'ni imzolab bo'lmaydi")
                storePassword = requiredEnv("AMORA_KEYSTORE_PASSWORD")
                keyAlias = requiredEnv("AMORA_KEY_ALIAS")
                keyPassword = requiredEnv("AMORA_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        debug {
            signingConfig = signingConfigs.getByName("testing")
            buildConfigField("String", "API_BASE_URL", "\"$debugApiBaseUrl\"")
        }
        release {
            // R8: ishlatilmagan kod va resurslar olib tashlanadi, qolgani qisqartiriladi
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.getByName(if (releaseKeystore != null) "release" else "testing")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
        freeCompilerArgs += listOf(
            "-opt-in=androidx.compose.material3.ExperimentalMaterial3Api",
        )
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }

    // Release yig'ilganda jiddiy lint xatolari (lintVital) yig'ishni to'xtatadi
    lint {
        checkReleaseBuilds = true
        abortOnError = true
    }
}

// Sinov kaliti bilan imzolangan release'ni do'konga chiqarib bo'lmaydi: yig'ishda eslatiladi
gradle.taskGraph.whenReady {
    val buildsRelease = allTasks.any { it.project == project && it.name.startsWith("package") && it.name.contains("Release") }
    if (releaseKeystore == null && buildsRelease) {
        logger.warn(
            "WARNING: AMORA_KEYSTORE berilmagan, release SINOV kaliti (keystore/amora-test.jks) bilan " +
                "imzolanmoqda. Bu yig'ilma do'konga chiqarish uchun yaramaydi.",
        )
    }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2026.11.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")

    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    // Ilova ekranda turganini bilish uchun: jonli ulanish shunga qarab ochiladi va yopiladi
    implementation("androidx.lifecycle:lifecycle-process:2.8.7")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.navigation:navigation-compose:2.8.5")

    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.7.3")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("io.coil-kt:coil-compose:2.7.0")
    implementation("org.osmdroid:osmdroid-android:6.1.20")
    // Shisha (glass) panellar ortidagi kontentni xiralashtirish uchun
    implementation("dev.chrisbanes.haze:haze:1.1.1")

    // Push-bildirishnomalar: ilova butunlay yopiq bo'lsa ham buyurtma holati va aksiyalar haqida
    implementation(platform("com.google.firebase:firebase-bom:33.7.0"))
    implementation("com.google.firebase:firebase-messaging")

    testImplementation("junit:junit:4.13.2")
}
