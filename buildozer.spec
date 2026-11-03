[app]
title = KosSplit
package.name = kossplit
package.domain = id.kossplit
source.dir = .
source.include_exts = py,png,jpg,kv,ttf
source.exclude_dirs = tests,bin,.buildozer,.venv
version = 0.2.1
requirements = python3,kivy==2.3.1,pyjnius,android,openpyxl,et_xmlfile,fpdf2==2.8.2,pillow,fonttools,defusedxml,plyer
orientation = portrait
fullscreen = 0

# ML Kit runs on the device. The document scanner opens its own camera UI
# through Google Play services, so KosSplit needs no CAMERA or storage permission.
android.gradle_dependencies = com.google.mlkit:text-recognition:16.0.1,com.google.android.gms:play-services-mlkit-document-scanner:16.0.0-beta1
android.enable_androidx = True

android.api = 35
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
