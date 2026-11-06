# ⚡ Faqih Downloader (FD) | فقيه التنزيلات
> **Ultra-Fast Multi-Threaded Download Manager with YouTube & Social Media Extraction, Live Stream Preview, Subtitle Dubbing, and Native Browser Integration**  
> *مدير تنزيلات فائق السرعة ومتعدد المسارات مع استخراج الوسائط ومنصات التواصل الاجتماعي، ومعاينة حية تفاعلية للفيديو والصوت والترجمة، وتكامل شامل مع المتصفحات*

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-0078D6.svg)](https://microsoft.com/windows)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-Passing%20100%25-brightgreen.svg)](#-test-suites--verification)
[![Release](https://img.shields.io/badge/release-v2.0.2-orange.svg)](https://github.com/hazoza90-hub/Faqih-Downloader-FD-/releases)

---

## 🌐 Language Navigation / تصفح اللغات
- [English Documentation](#-english-documentation)
  - [🌟 What's New in v2.0.2](#-whats-new-in-v202)
  - [🚀 Key Features](#-key-features)
  - [🏗️ System Architecture & Data Flow](#-system-architecture--data-flow)
  - [💻 Installation & Quick Start](#-installation--quick-start)
  - [🔌 Browser Extension Integration](#-browser-extension-integration)
  - [🔨 Build & Zero-Rebuild OTA Hot-Patch](#-build--zero-rebuild-ota-hot-patch)
  - [🧪 Test Suites & Verification](#-test-suites--verification)
- [التوثيق باللغة العربية](#-التوثيق-باللغة-العربية)
  - [🌟 جديد الإصدار v2.0.2](#-جديد-الإصدار-v202)
  - [🚀 الميزات الرئيسية](#-الميزات-الرئيسية)
  - [🏗️ الهندسة المعمارية وتدفق البيانات](#-الهندسة-المعمارية-وتدفق-البيانات)
  - [💻 طرق التثبيت والتشغيل السريع](#-طرق-التثبيت-والتشغيل-السريع)
  - [🔌 تكامل إضافة المتصفحات](#-تكامل-إضافة-المتصفحات)
  - [🔨 بناء الحزم والتحديث الفوري (CorePatch)](#-بناء-الحزم-والتحديث-الفوري-corepatch)
  - [🧪 الاختبارات الآلية والتحقق](#-الاختبارات-الآلية-والتحقق)

---

## 📖 English Documentation

### 🌟 What's New in v2.0.2

1. **🎨 3-Column Modern Responsive Kanban Workspace**
   - Clean, highly organized 3-column workflow layout: **Active Downloads**, **Completed Downloads**, and **Interactive Details / Analytics Panel**.
   - Live download segment visualization showing chunk activity, thread state, throughput meters, and ETA.
   - Smooth Acrylic glass transparency effect (Win32 backdrop) with custom neon cyan and electric blue styling.

2. **🎬 Built-in Real-time Live Preview (Video, Audio & Subtitles)**
   - Preview videos and audio in real-time *before* or *during* download without waiting for the entire file to finish.
   - In-memory HTTP streaming proxy with on-the-fly VTT subtitle generation and track switching.
   - Video thumbnail extraction with interactive play overlay and audio spectrum equalizer animations.

3. **⚡ Zero-Rebuild Atomic `CorePatch` OTA Updates**
   - Update the application engine instantly with lightweight (~120 KB) `FaqihDownloader-CorePatch.zip` packages.
   - Dynamic module loader injects core updates directly without having to compile or reinstall `FaqihDownloader.exe`.
   - Dynamic `yt-dlp` plugin self-updating directly in `%APPDATA%\SmartDownload\yt_dlp_plugin`.

4. **🔒 Hardened Security & Anti-Corruption Verification**
   - Cryptographic SHA-256 and MD5 file integrity verification with automatic archive inspection.
   - Domain whitelist enforcement for update downloads (`_is_trusted_update_url`).
   - Atomic multi-part writing preventing partial file corruption on unexpected shutdowns or network disconnects.

---

### 🚀 Key Features

- **⚡ Turbo Multi-Threaded Engine**:
  Splits files into up to **32 concurrent byte-range connections**. Features dynamic chunk stealing to reallocate idle connections to lagging streams. Resumes paused or broken downloads via persistent `.sd_parts` manifests.
- **🎥 Universal Media & Social Extraction**:
  Full-fidelity extraction from **YouTube, TikTok, Instagram, Facebook, X (formerly Twitter), and Reddit**. Select resolutions up to 4K UHD, audio bitrates, dubbing tracks, and embedded/burned subtitles.
- **🌐 Full Chromium & Edge Browser Integration**:
  Interception via the official Manifest V3 browser extension communicating through the native messaging protocol (`com.faqihdownloader.host`) and the local HTTP bridge (`127.0.0.1:9654`).
- **📋 Universal Real-Time Clipboard Sniffer**:
  Instantly captures downloadable file URLs and media links copied to your clipboard across all applications with immediate prompt confirmation.
- **🌐 Bilingual Arabic & English UI**:
  Seamless dynamic language toggle with 100% Arabic and English localization, proper Right-to-Left (RTL) text mirroring, and persistent preferences.
- **🚀 Zero-Elevation Windows Background Auto-Start**:
  Boots silently into the Windows system tray without UAC prompts using a robust 3-tier startup mechanism (Run key, Task Scheduler, and Startup directory).

---

### 🏗️ System Architecture & Data Flow

```text
┌─────────────────────────────────────────────────────────────┐
│ Browser Extension (Chrome / Edge / Brave / Opera)           │
└──────────────┬──────────────────────────────┬───────────────┘
               │ (stdio length-prefixed)      │ (HTTP POST port 9654)
               ▼                              ▼
  services/browser/native_host.py   services/browser/bridge_server.py
               │                              │
               └──────────────┬───────────────┘
                              ▼
              ui/controllers/browser_controller.py
                              │ (dispatch_to_main_thread)
                              ▼
              ui/controllers/download_controller.py
                     │                     │
         [Media / YouTube URL]        [Direct File URL]
                     ▼                     ▼
          services/youtube_service.py     core/engine.py
          (MediaResolver / yt-dlp)       (TurboDownloadEngine)
                     │                     │
                     ▼                     │
          core/stream_coordinator.py       │
          (FFmpeg Audio+Video Merge)       │
                     │                     │
                     └──────────┬──────────┘
                                ▼
               Real-time UI Event Dispatchers:
               - 3-Column Kanban Cards (kanban_panel.py)
               - Visual Chunk Segments (chunks_panel.py)
               - Live Streaming Preview (preview_stream_bridge.py)
               - Windows System Tray & Toasts (system_tray.py)
```

---

### 💻 Installation & Quick Start

#### Option 1: Standalone Windows Installer (Recommended)
Download `FaqihDownloader-Setup.exe` from the [GitHub Releases](https://github.com/hazoza90-hub/Faqih-Downloader-FD-/releases) page. The installer bundles `ffmpeg`, configures desktop and start menu shortcuts, sets up zero-elevation auto-startup, and requires no Python installation.

#### Option 2: Run from Source
1. **Clone the repository:**
   ```bash
   git clone https://github.com/hazoza90-hub/Faqih-Downloader-FD-.git
   cd Faqih-Downloader-FD-
   ```

2. **Install dependencies:**
   ```bash
   pip install pillow yt-dlp pystray pywebview
   ```

3. **Launch Faqih Downloader:**
   ```bash
   python faqih_downloader.py
   ```

---

### 🔌 Browser Extension Integration

1. Open your Chromium-based browser (**Chrome**, **Edge**, or **Brave**).
2. Navigate to `chrome://extensions` or `edge://extensions`.
3. Enable **Developer mode** toggle.
4. Click **Load unpacked** and select the `extension/` directory.
5. Register the Native Messaging Host (`com.faqihdownloader.host`) in the Windows Registry:
   ```bash
   python register_browser.py --register
   ```
6. Check registration status at any time:
   ```bash
   python register_browser.py --status
   ```

---

### 🔨 Build & Zero-Rebuild OTA Hot-Patch

```bash
# 1. Produce lightweight OTA hot-patch (~120 KB in <0.5s)
python -c "from updater import build_core_patch_zip; build_core_patch_zip('dist/FaqihDownloader-CorePatch.zip')"

# 2. Build standalone executable (dist/FaqihDownloader.exe)
pyinstaller FaqihDownloader.spec

# 3. Build standalone Windows Setup Installer (dist/FaqihDownloader-Setup.exe)
python build_installer.py --rebuild-all
```

---

### 🧪 Test Suites & Verification

Faqih Downloader maintains a rigorous suite of automated unit and integration tests:

```bash
# Verify App and Plugin Auto-Updaters (3.5s)
python -m unittest tests/test_updater.py

# Verify Rebranding, Transparency, and Media Enhancements (12s)
python -m unittest tests/test_rebranding_and_improvements.py

# Verify Dynamic Core Hot-Patch Loader (0.5s)
python -m unittest tests/test_core_patch_updater.py

# Verify Strict Single Responsibility Principle (<550 lines per file)
python -m unittest tests/test_stage4_srp_decomposition.py

# Verify Architecture Map Synchronization
python scripts/update_arch_map.py --check
```

---

## 🌍 التوثيق باللغة العربية

### 🌟 جديد الإصدار v2.0.2

1. **🎨 مساحة عمل عصرية ثلاثية الأعمدة (3-Column Kanban Workspace)**
   - تنظيم بصري تفاعلي مقسم إلى 3 أعمدة ذكية: **التنزيلات النشطة**، **التنزيلات المكتملة**، و**لوحة التفاصيل والإحصائيات التفاعلية**.
   - خريطة مرئية متطورة لمسارات وتجزئة الملف تُظهر حالة المسارات وسرعتها والوقت المتبقي بدقة متناهية.
   - تأثير شفافية زجاجي فاخر (Acrylic Glass Win32) مع نظام ألوان داكن وإضاءات نيون عصرية مريحة للعين.

2. **🎬 مشغل ومعاينة حية وفورية قبل وأثناء التحميل (Live Streaming Preview)**
   - إمكانية تشغيل ومعاينة مقاطع الفيديو والصوت أثناء التحميل مباشرة دون انتظار اكتمال التنزيل.
   - خادم وسيط محلي (Proxy) لتوليد مسارات الترجمة الفورية (VTT) والتبديل السريع بين مسارات الدبلجة الصوتية واللغات.
   - استخراج وتوليد صور مصغرة واقعية للفيديوهات (Real Thumbnails) مع تأثير أمواج طيف الصوت لمقاطع MP3.

3. **⚡ نظام التحديث الفوري الذري (CorePatch OTA)**
   - تحديث محرك البرنامج خلال أجزاء من الثانية بحزمة خفيفة جداً (~120 كيلوبايت) تحمل اسم `FaqihDownloader-CorePatch.zip`.
   - محمل ديناميكي ذكي يحدّث الملفات البرمجية دون الحاجة لإعادة تجميع أو تنزيل ملف `FaqihDownloader.exe` الكامل.
   - تحديث ذاتي تلقائي ومستقل لمستخرجات `yt-dlp` في مسار `%APPDATA%\SmartDownload\yt_dlp_plugin`.

4. **🔒 أمان فائق وحماية متقدمة ضد تلف الملفات**
   - فحص سلامة الملفات عبر خوارزميات التشفير التلقائية (SHA-256 و MD5) وفك ضغط الأرشيفات تلقائياً.
   - حماية أمنية مشددة تمنع تحميل أي تحديثات من نطاقات غير موثوقة.
   - كتابة ذرية آمنة للملفات تمنع فقدان أو تلف التنزيلات عند انقطاع الاتصال أو إغلاق النظام المفاجئ.

---

### 🚀 الميزات الرئيسية

- **⚡ محرك تحميل فائق السرعة متعدد المسارات**:
  تقسيم ديناميكي للملف حتى **32 اتصالاً متزامناً**، مع ميزة سرقة المقاطع الذكية (Dynamic Chunk Stealing) لإعادة توزيع الأجزاء على المسارات الأسرع، واستئناف موثوق للتنزيلات عبر ملفات `.sd_parts`.
- **🎥 استخراج شامل للوسائط وشبكات التواصل**:
  دعم متكامل لأشهر المنصات العالمية: **يوتيوب (YouTube)، تيك توك (TikTok)، إنستغرام (Instagram)، فيسبوك (Facebook)، إكس / تويتر (X)، وريديت (Reddit)** بدقة تصل إلى 4K مع إمكانية استخراج الصوت بشكل منفصل.
- **🌐 تكامل تام مع كافة متصفحات كروميوم وإيدج**:
  إضافة رسمية حديثة (Manifest V3) تتواصل عبر بروتوكول الرسائل الأصلي `com.faqihdownloader.host` والجسر المحلي `127.0.0.1:9654`.
- **📋 مراقبة ذكية وفورية للحافظة (Clipboard Sniffer)**:
  التقاط فوري لروابط الملفات والفيديوهات فور نسخها من أي برنامج دون الحاجة لتثبيت أي إضافات خارجية.
- **🌐 واجهة ثنائية اللغة متكاملة (عربي / إنجليزي)**:
  تبديل ديناميكي فوري للغة الواجهة بضغطة زر مع دعم الاتجاه من اليمين إلى اليسار (RTL) وحفظ اللغة المفضلة.
- **🚀 بدء تشغيل تلقائي صامت بدون صلاحيات مسؤول**:
  إقلاع فوري مع نظام ويندوز في صينية النظام (System Tray) دون أي نوافذ UAC مزعجة عبر منظومة ثلاثية متكاملة.

---

### 🏗️ الهندسة المعمارية وتدفق البيانات

```text
┌─────────────────────────────────────────────────────────────┐
│ إضافة المتصفح (Chrome / Edge / Brave / Opera)               │
└──────────────┬──────────────────────────────┬───────────────┘
               │ (stdio length-prefixed)      │ (HTTP POST port 9654)
               ▼                              ▼
  services/browser/native_host.py   services/browser/bridge_server.py
               │                              │
               └──────────────┬───────────────┘
                              ▼
              ui/controllers/browser_controller.py
                              │ (إرسال آمن لخيط الواجهة الرئيسي)
                              ▼
              ui/controllers/download_controller.py
                     │                     │
           [رابط وسائط / فيديو]          [رابط ملف مباشر]
                     ▼                     ▼
          services/youtube_service.py     core/engine.py
          (MediaResolver / yt-dlp)       (TurboDownloadEngine)
                     │                     │
                     ▼                     │
          core/stream_coordinator.py       │
          (دمج الصوت والفيديو عبر FFmpeg)  │
                     │                     │
                     └──────────┬──────────┘
                                ▼
               موزعات أحداث الواجهة الفورية:
               - بطاقات كانبان ثلاثية الأعمدة (kanban_panel.py)
               - خريطة المقاطع المرئية (chunks_panel.py)
               - جسر المعاينة المباشرة (preview_stream_bridge.py)
               - أيقونة شريط المهام والإشعارات (system_tray.py)
```

---

### 💻 طرق التثبيت والتشغيل السريع

#### الخيار الأول: استخدام برنامج التثبيت الرسمي (موصى به)
حمّل ملف التثبيت السلس `FaqihDownloader-Setup.exe` مباشرة من صفحة [إصدارات GitHub](https://github.com/hazoza90-hub/Faqih-Downloader-FD-/releases). يحتوي المثبت على حزمة `ffmpeg` المدمجة، وينشئ الاختصارات اللازمة، ويفعّل البدء التلقائي دون الحاجة لأي متطلبات مسبقة.

#### الخيار الثاني: التشغيل من الكود المصدري
1. **استنساخ المستودع:**
   ```bash
   git clone https://github.com/hazoza90-hub/Faqih-Downloader-FD-.git
   cd Faqih-Downloader-FD-
   ```

2. **تثبيت حزم بايثون:**
   ```bash
   pip install pillow yt-dlp pystray pywebview
   ```

3. **تشغيل البرنامج:**
   ```bash
   python faqih_downloader.py
   ```

---

### 🔌 تكامل إضافة المتصفحات

1. افتح متصفحك المفضل (Google Chrome أو Microsoft Edge أو Brave).
2. انتقل إلى إدارة الإضافات `chrome://extensions` أو `edge://extensions`.
3. فعّل **وضع المطور (Developer Mode)**.
4. انقر فوق **تحميل حزمة غير مضغوطة (Load unpacked)** وحدد مجلد `extension/` من داخل المستودع.
5. سجّل مضيف الاتصال الأصلي (`com.faqihdownloader.host`) في سجلات ويندوز:
   ```bash
   python register_browser.py --register
   ```
6. يمكنك التحقق من حالة التسجيل بتشغيل:
   ```bash
   python register_browser.py --status
   ```

---

### 🔨 بناء الحزم والتحديث الفوري (CorePatch)

```bash
# 1. إنشاء حزمة التحديث الفوري OTA السريعة (~120 كيلوبايت خلال 0.5 ثانية)
python -c "from updater import build_core_patch_zip; build_core_patch_zip('dist/FaqihDownloader-CorePatch.zip')"

# 2. بناء الملف التنفيذي المباشر (dist/FaqihDownloader.exe)
pyinstaller FaqihDownloader.spec

# 3. بناء مثبت التثبيت الشامل (dist/FaqihDownloader-Setup.exe)
python build_installer.py --rebuild-all
```

---

### 🧪 الاختبارات الآلية والتحقق

يحتوي المستودع على منظومة متكاملة من الاختبارات الآلية لضمان الجودة والأداء:

```bash
# فحص نظام التحديث التلقائي للتطبيق و yt-dlp (3.5 ثوانٍ)
python -m unittest tests/test_updater.py

# فحص الهوية الجديدة والشفافية واستخراج الوسائط (12 ثانية)
python -m unittest tests/test_rebranding_and_improvements.py

# فحص محمل التحديثات الفورية OTA Hot-Patch (0.5 ثانية)
python -m unittest tests/test_core_patch_updater.py

# فحص الالتزام بحدود الأسطر (<550 سطراً لكل ملف)
python -m unittest tests/test_stage4_srp_decomposition.py

# فحص تزامن خريطة المعمارية مع المستودع
python scripts/update_arch_map.py --check
```

---

## 📄 License
This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.  
جميع الحقوق محفوظة للمشروع بموجب ترخيص MIT الحر مفتوح المصدر.
