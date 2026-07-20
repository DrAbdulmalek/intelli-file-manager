[app]
title = IntelliFile Manager
package.name = intellifile
package.domain = org.intellifile
source.dir = mobile
source.include_exts = py,png,jpg,kv,atlas,json,ttf,otf
version = 2.0.0
requirements = python3==3.11.6,kivy==2.3.0,pillow,pytesseract,httpx,pydantic,chromadb,rank-bm25,rapidfuzz,networkx,pdfplumber,python-docx,openpyxl,rich
orientation = portrait
fullscreen = 1
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,CAMERA,RECORD_AUDIO
android.api = 33
android.minapi = 24
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a
android.allow_backup = True
p4a.branch = master
log_level = 2
warn_on_root = 1

[buildozer]
log_level = 2
warn_on_root = 1
