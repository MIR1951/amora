plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("org.jetbrains.kotlin.plugin.serialization")
}

val apiBaseUrl = providers.gradleProperty("amora.apiBaseUrl").get().trimEnd('/')
// Sinov (debug) yig'ilishini boshqa serverga qaratish mumkin, masalan CI ichidagi sinov serveriga:
// -Pamora.debugApiBaseUrl=http://10.0.2.2:8000. Berilmasa, asosiy server ishlatiladi.
val debugApiBaseUrl = providers.gradleProperty("amora.debugApiBaseUrl").orNull?.trimEnd('/') ?: apiBaseUrl
val appVersionName = providers.gradleProperty("amora.versionName").get()
val appVersionCode = providers.gradleProperty("amora.versionCode").get().toInt()

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
    }

    buildTypes {
        debug {
            signingConfig = signingConfigs.getByName("testing")
            buildConfigField("String", "API_BASE_URL", "\"$debugApiBaseUrl\"")
        }
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("testing")
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

    lint {
        checkReleaseBuilds = false
        abortOnError = false
    }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2024.12.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")

    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
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

    testImplementation("junit:junit:4.13.2")
}
