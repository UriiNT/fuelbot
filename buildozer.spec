# -*- mode: python ; coding: utf-8 -*-

[app]

# ---------- Источник ----------
source.filename = %(source.dir)s/kivy_app.py
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ico

# ---------- Мета ----------
title = Наличие топлива на АЗС
package.name = fuelbot
package.domain = org.fuelbot
version = 1.0.0
version.filename = %(source.dir)s/version.txt

# ---------- Иконка / заставка ----------
icon.filename = %(source.dir)s/app_icon_preview.png
presplash.filename = %(source.dir)s/app_icon_preview.png
presplash_color = #0f1522

# ---------- Зависимости ----------
requirements = python3,kivy,requests,urllib3,certifi

# ---------- Android ----------
# Целевой SDK 33, минимальный — 26 (Android 8.0+)
android.api = 33
android.minapi = 26
android.ndk = 25b
# Поддержка большинства смартфонов (x86_64 не добавляем, чтобы APK был компактнее)
android.arch = arm64-v8a, armeabi-v7a
android.permissions = INTERNET, ACCESS_NETWORK_STATE
android.accept_sdk_license = True

# ---------- Gradle ----------
android.enable_androidx = True
android.add_users_java = True
#android.gradle_dependencies = androidx.appcompat:appcompat:1.6.1

# ---------- Интерфейс ----------
fullscreen = 0
orientation = portrait

# ---------- Пакетирование ----------
# debug-версия: обычный APK; релиз — AAB
#android.release_artifact = aab
android.skip_update = False

# ---------- Логи ----------
log_level = 2
warn_on_root = 0
#android.logcat_filters = *:S python:I
