[app]

# ПолинаGram — Android сборка
title = PolinaGram
package.name = polinagram
package.domain = org.polinagram

source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.1.0

# Иконки и заставка при запуске (сгенерированы, лежат в mobile/icons/)
icon.filename = icons/icon.png
presplash.filename = icons/presplash.png

requirements = python3,kivy==2.3.0,requests,websockets,PyJWT,urllib3,chardet,idna,certifi

orientation = portrait
fullscreen = 0

android.api = 33
android.minapi = 24
android.ndk = 25c
android.accept_sdk_license = True

# Разрешения: интернет обязателен, POST_NOTIFICATIONS — для пушей (API 33+)
android.permissions = INTERNET,ACCESS_NETWORK_STATE,POST_NOTIFICATIONS,WAKE_LOCK

# Архитектуры: arm64-v8a (современные телефоны) + armeabi-v7a (старые, до 2019)
android.archs = arm64-v8a, armeabi-v7a

# Для GitHub Release собираем именно APK (по умолчанию p4a может дать AAB)
android.release_artifact = apk

# Релизная подпись через GitHub Actions (см. README, раздел «Подпись APK»):
# android.keystore = release.keystore
# android.keystore.alias = polinagram

[buildozer]

log_level = 2
warn_on_root = 0
