import os
import sys
import json
import time
import urllib.request
import urllib.error
import subprocess

_src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if os.path.isdir(_src_dir) and _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

try:
    from smart_download.config import APP_VERSION
    from smart_download.services.core_patch_updater import build_core_patch_zip
except Exception:
    APP_VERSION = "2.0.2"
    build_core_patch_zip = None

REPO_OWNER = "hazoza90-hub"
REPO_NAME = "Faqih-Downloader-FD-"
TAG = f"v{APP_VERSION}"
RELEASE_NAME = f"Faqih Downloader (FD) / فقيه التنزيلات (FD) {TAG}"

RELEASE_BODY = rf"""# Faqih Downloader (FD) / فقيه التنزيلات (FD) {TAG}
## الإصدار الجديد {TAG} — مُنزّل وسائط وفيديوهات متكامل وعالي السرعة

---

### 🌟 English Highlights
Faqih Downloader (FD) {TAG} introduces a major update and architectural upgrade. It brings full-featured video downloading from leading social media platforms, a modern high-DPI frameless UI with Acrylic glass transparency, bilingual localization, and a streamlined Windows installer.

- **Multi-Platform Social Media Downloader**: Effortlessly download high-definition videos and audio from **YouTube, TikTok, Instagram, Facebook, X (formerly Twitter), and Reddit**.
- **Bilingual Localization & Language Switcher (`🌐 العربية / English`)**: One-click dynamic language toggle between Arabic and English directly on the title bar, with complete bilingual translations, right-to-left layout adaptation, and persistent language preference.
- **Multiple Download Links Detection Modal**: Intelligent extraction and presentation of multiple download candidates from web pages with interactive multi-selection, master select-all controls, file-type filtering badges, and batch download queuing.
- **Transparent High-DPI Modern Icon**: Brand new pixel-perfect transparent application icon with full multi-resolution Windows support (16x16 up to 256x256).
- **Optimized Ultra-Compact Installer**: Optimized payload bundling with bundled FFmpeg, Desktop & Start Menu shortcuts, auto-startup, and clean uninstaller.
- **High-Performance Multi-Segment Engine**: Lightning-fast parallel chunk downloads with dynamic midpoint splitting, rate limiting, and auto-reassembly.
- **Chrome & Edge Browser Integration**: Seamless native messaging extension integration with automatic one-click media capture.
- **Instant Zero-Elevation Background Startup**: Multi-tiered instant startup on Windows boot (Run key, Scheduled Task, and Startup shortcut) with zero elevation, starting silently in the tray.
- **Automatic `yt-dlp` Dynamic Self-Update Engine**: Automatically updates and loads the latest `yt-dlp` extractors in `%APPDATA%\SmartDownload\yt_dlp_plugin` without needing to rebuild or reinstall the `.exe`.
- **Built-in Application Auto-Updater**: Checks GitHub Releases for new versions in the background and provides a one-click **[⬇ Update Now]** upgrade experience.
- **Distribution Packages**:
  - `FaqihDownloader-Setup.exe`: Full Windows installer with zero-elevation installation, bundled FFmpeg, Desktop & Start Menu shortcuts, auto-startup, and clean uninstaller.
  - `FaqihDownloader-CorePatch.zip`: Lightweight OTA core hot-patch update archive.

---

### 🌟 أبرز مميزات الإصدار باللغة العربية
يمثل الإصدار **فقيه التنزيلات (FD) {TAG}** نقلة نوعية وتطويراً شاملاً للهوية والأداء:

- **تحميل الفيديوهات من كافة منصات التواصل الاجتماعي**: دعم التحميل بأعلى جودة وصيغ متعددة من **تيك توك (TikTok)، إنستغرام (Instagram)، فيسبوك (Facebook)، إكس / تويتر (X/Twitter)، ريديت (Reddit)، ويوتيوب (YouTube)**.
- **تعريب ثنائي اللغة متكامل ومفتاح تبديل فوري (`🌐 العربية / English`)**: زر تبديل ديناميكي فوري بين اللغتين العربية والإنجليزية في شريط العنوان مع تعريب شامل لكافة عناصر الواجهة ودعم اتجاه النصوص وحفظ اللغة المفضلة تلقائياً.
- **نافذة ذكية لاكتشاف روابط التحميل المتعددة (Multiple Candidates Modal)**: استخراج ذكي لكافة روابط الملفات والوسائط القابلة للتحميل من صفحات الويب، مع إمكانية التحديد المتعدد، واختيار الكل، وفلترة الأنواع، وبدء التحميل الدفعي فوراً.
- **تحديث ذاتي تلقائي لمحرك `yt-dlp` والبرنامج**: تحديث استخراج الفيديوهات تلقائياً في الخلفية مع نظام فحص وتحديث البرنامج بضغطة زر واحدة.
- **أيقونة شفافة فائقة الدقة (High-DPI)**: تصميم احترافي حديث بخلفية شفافة يدعم كافة شاشات العرض بدقة كاملة من 16×16 وحتى 256×256 بكسل.
- **مُثبّت فائق الرشاقة وصغير الحجم**: تقليل حجم ملف التثبيت عبر إزالة التكرار وربط التوافق ديناميكياً.
- **تشغيل تلقائي فوري في الخلفية بدون صلاحيات مسؤول**: بدء تلقائي صامت في شريط المهام عند إقلاع ويندوز عبر منظومة ثلاثية موثوقة (Run Key و Scheduled Task واختصار Startup) دون الحاجة لأي صلاحيات إدارية (UAC-free).
- **محرك تحميل خارق متعدد المسارات**: تجزئة ذكية ديناميكية للملفات أثناء التحميل لزيادة السرعة إلى أقصى حد ممكن مع إمكانية تحديد السرعة والإيقاف والاستئناف.
- **تكامل متكامل مع متصفحات Chrome و Edge**: التقاط الروابط تلقائياً عبر إضافة المتصفح الرسمية.
- **حزم التوزيع**:
  - `FaqihDownloader-Setup.exe`: برنامج تثبيت سريع وسلس لا يتطلب صلاحيات مسؤول ويندوز مع دعم برمجية FFmpeg المدمجة، والاختصارات، وبدء التشغيل التلقائي، وإلغاء التثبيت النظيف.
  - `FaqihDownloader-CorePatch.zip`: حزمة التحديث الفوري الخفيفة لتحديث البرنامج مباشرة وبسرعة فائقة.
"""


def log(msg):
    print(msg, flush=True)


def get_git_credentials():
    p = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True,
        text=True,
        check=True
    )
    token = None
    username = None
    for line in p.stdout.splitlines():
        if line.startswith("username="):
            username = line.split("=", 1)[1].strip()
        elif line.startswith("password="):
            token = line.split("=", 1)[1].strip()
    if not token:
        raise RuntimeError("Could not retrieve GitHub PAT/token from git credential fill")
    return username, token


def api_request(url, token, data=None, method="GET", headers=None):
    req_headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "SmartDownload-ReleaseTool"
    }
    if headers:
        req_headers.update(headers)

    body = None
    if data is not None:
        if isinstance(data, (dict, list)):
            body = json.dumps(data).encode("utf-8")
            req_headers["Content-Type"] = "application/json"
        elif isinstance(data, bytes):
            body = data

    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            content = resp.read()
            if resp.headers.get_content_type() == "application/json":
                return resp.status, json.loads(content.decode("utf-8"))
            return resp.status, content
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        try:
            err_json = json.loads(err_body)
            return e.code, err_json
        except Exception:
            return e.code, err_body


def upload_asset_with_curl(upload_url, token, file_path, max_retries=3):
    """Uses curl.exe for high-reliability binary streaming upload."""
    cmd = [
        "curl.exe",
        "--http1.1",
        "-L",
        "-X", "POST",
        "-H", f"Authorization: Bearer {token}",
        "-H", "Accept: application/vnd.github+json",
        "-H", "Content-Type: application/octet-stream",
        "--data-binary", f"@{file_path}",
        "--retry", "3",
        "--retry-delay", "5",
        upload_url
    ]
    for attempt in range(1, max_retries + 1):
        log(f"[*] Running curl.exe to stream '{os.path.basename(file_path)}' (attempt {attempt}/{max_retries})...")
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            try:
                data = json.loads(res.stdout)
                if isinstance(data, dict):
                    if "errors" in data or ("message" in data and "id" not in data):
                        if attempt < max_retries:
                            log(f"[-] GitHub API error on attempt {attempt}: {data}. Retrying in 5s...")
                            time.sleep(5)
                            continue
                        raise RuntimeError(f"GitHub API error during upload of '{os.path.basename(file_path)}': {data}")
                return data
            except json.JSONDecodeError:
                return {"raw_output": res.stdout}
        else:
            log(f"[-] curl.exe exited with code {res.returncode}: {res.stderr.strip() or res.stdout.strip()}")
            if attempt < max_retries:
                log("[*] Waiting 5s before retrying upload...")
                time.sleep(5)
            else:
                raise RuntimeError(f"curl.exe failed with code {res.returncode} after {max_retries} attempts: {res.stderr}")


def main():
    global TAG, RELEASE_NAME
    for idx, arg in enumerate(sys.argv):
        if arg == "--tag" and idx + 1 < len(sys.argv):
            TAG = sys.argv[idx + 1]
            RELEASE_NAME = f"Faqih Downloader (FD) / فقيه التنزيلات (FD) {TAG}"

    username, token = get_git_credentials()
    log(f"[+] Retrieved git credentials for user: {username}")

    base_api = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"

    # 1. Inspect release
    log(f"[*] Checking release {TAG}...")
    status, res = api_request(f"{base_api}/releases/tags/{TAG}", token)
    release_data = None
    if status == 200:
        log(f"[+] Release {TAG} exists (id: {res['id']}). Updating metadata...")
        release_data = res
        # Update name and body to ensure latest formatting
        update_payload = {
            "name": RELEASE_NAME,
            "body": RELEASE_BODY
        }
        api_request(f"{base_api}/releases/{res['id']}", token, data=update_payload, method="PATCH")
    elif status == 404:
        log(f"[*] Release {TAG} not found. Creating new release...")
        payload = {
            "tag_name": TAG,
            "target_commitish": "main",
            "name": RELEASE_NAME,
            "body": RELEASE_BODY,
            "draft": False,
            "prerelease": False
        }
        create_status, create_res = api_request(f"{base_api}/releases", token, data=payload, method="POST")
        if create_status in (200, 201):
            log(f"[+] Successfully created release {TAG} (id: {create_res['id']})!")
            release_data = create_res
        else:
            raise RuntimeError(f"Failed to create release: HTTP {create_status}: {create_res}")
    else:
        raise RuntimeError(f"Failed to inspect release: HTTP {status}: {res}")

    release_id = release_data["id"]
    upload_url_template = release_data["upload_url"]
    upload_base = upload_url_template.split("{")[0]
    log(f"[+] Upload URL base: {upload_base}")

    # Re-fetch latest release data to get current assets
    _, fresh_release = api_request(f"{base_api}/releases/{release_id}", token)
    existing_assets = {a["name"]: a for a in fresh_release.get("assets", [])}
    log(f"[*] Existing assets on release: {list(existing_assets.keys())}")

    # Aggressively delete legacy/stale assets (SmartDownload*, TurboDownloader*)
    for asset in list(fresh_release.get("assets", [])):
        a_name = asset.get("name", "")
        should_delete = False
        if a_name.startswith("SmartDownload") or a_name.startswith("TurboDownloader"):
            should_delete = True
        elif a_name == "FaqihDownloader.exe" and "--include-standalone" not in sys.argv:
            should_delete = True

        if should_delete:
            log(f"[*] Deleting legacy/stale '{a_name}' asset (id: {asset['id']}) from release...")
            del_status, _ = api_request(f"{base_api}/releases/assets/{asset['id']}", token, method="DELETE")
            if del_status in (200, 204):
                log(f"[+] Successfully removed '{a_name}' from GitHub release.")
                existing_assets.pop(a_name, None)
            else:
                log(f"[!] Warning: Failed to delete '{a_name}' asset (id: {asset['id']}): HTTP {del_status}")

    global build_core_patch_zip
    if build_core_patch_zip is None:
        _src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
        if os.path.isdir(_src_dir) and _src_dir not in sys.path:
            sys.path.insert(0, _src_dir)
        from smart_download.services.core_patch_updater import build_core_patch_zip

    is_full_build = "--full-build" in sys.argv

    # Generate lightweight OTA core patch zip (<150 KB, <0.5s, zero PyInstaller required)
    os.makedirs("dist", exist_ok=True)
    fd_core_patch = os.path.abspath(r"dist\FaqihDownloader-CorePatch.zip")
    log(f"[*] Building lightweight Core Patch archive: {fd_core_patch}...")
    build_core_patch_zip(fd_core_patch, version=TAG)
    if os.path.isfile(fd_core_patch):
        log(f"[+] Core Patch built successfully ({os.path.getsize(fd_core_patch):,} bytes).")

    fd_setup = os.path.abspath(r"dist\FaqihDownloader-Setup.exe")
    fd_standalone = os.path.abspath(r"dist\FaqihDownloader.exe")

    if is_full_build:
        if not os.path.isfile(fd_setup):
            raise FileNotFoundError(f"Setup executable requested via --full-build not found: {fd_setup}")
        assets_to_upload = [
            fd_setup,
            fd_core_patch,
        ]
        required_asset_names = {
            "FaqihDownloader-Setup.exe",
            "FaqihDownloader-CorePatch.zip"
        }
        if "--include-standalone" in sys.argv:
            if not os.path.isfile(fd_standalone):
                raise FileNotFoundError(f"Standalone executable requested via --include-standalone not found: {fd_standalone}")
            assets_to_upload.insert(0, fd_standalone)
            required_asset_names.add("FaqihDownloader.exe")
    else:
        log("[*] Standard publish mode: Focusing on FaqihDownloader-Setup.exe and FaqihDownloader-CorePatch.zip.")
        assets_to_upload = [fd_core_patch]
        required_asset_names = {"FaqihDownloader-CorePatch.zip"}
        if os.path.isfile(fd_setup):
            assets_to_upload.insert(0, fd_setup)
            required_asset_names.add("FaqihDownloader-Setup.exe")
        if "--include-standalone" in sys.argv:
            if not os.path.isfile(fd_standalone):
                raise FileNotFoundError(f"Standalone executable requested via --include-standalone not found: {fd_standalone}")
            assets_to_upload.insert(0, fd_standalone)
            required_asset_names.add("FaqihDownloader.exe")

    for asset_path in assets_to_upload:
        asset_name = os.path.basename(asset_path)
        if not os.path.isfile(asset_path):
            raise FileNotFoundError(f"Asset file not found: {asset_path}")

        file_size = os.path.getsize(asset_path)
        log(f"\n[*] Evaluating '{asset_name}' ({file_size:,} bytes)...")

        force_replace = any(flag in sys.argv for flag in ("--overwrite", "--force", "--replace-assets"))
        # Check if already uploaded and valid size
        if asset_name in existing_assets:
            existing_info = existing_assets[asset_name]
            existing_size = existing_info.get("size", 0)
            existing_state = existing_info.get("state", "")
            if existing_size == file_size and existing_state == "uploaded" and not force_replace:
                log(f"[+] Asset '{asset_name}' is already completely uploaded ({existing_size:,} bytes). Skipping.")
                continue
            else:
                asset_id = existing_info.get("id")
                log(f"[*] Deleting existing/mismatched asset '{asset_name}' (id: {asset_id}, size: {existing_size:,}) to replace with fresh build...")
                if asset_id:
                    del_status, _ = api_request(f"{base_api}/releases/assets/{asset_id}", token, method="DELETE")
                    if del_status in (200, 204):
                        log(f"[+] Deleted existing '{asset_name}' successfully from GitHub release.")

        target_upload_url = f"{upload_base}?name={asset_name}"
        log(f"[*] Uploading '{asset_name}' via curl stream...")
        up_res = upload_asset_with_curl(target_upload_url, token, asset_path)
        if "browser_download_url" in up_res:
            log(f"[+] Successfully uploaded '{asset_name}'!")
            log(f"    Download URL: {up_res.get('browser_download_url')}")
            log(f"    Size: {up_res.get('size', 0):,} bytes")
        elif "id" in up_res:
            log(f"[+] Uploaded '{asset_name}' with asset ID: {up_res.get('id')}")
        else:
            log(f"[?] Upload output: {up_res}")

    # Final verification
    log("\n[*] Verifying release assets on GitHub...")
    v_status, v_res = api_request(f"{base_api}/releases/{release_id}", token)
    if v_status == 200:
        final_assets = v_res.get("assets", [])
        log(f"[+] Verification succeeded! Total assets uploaded: {len(final_assets)}")
        for a in final_assets:
            dl_url = a.get("browser_download_url", "")
            sz = a.get("size", 0)
            log(f" - {a.get('name', 'unknown')} ({sz:,} bytes, state={a.get('state')}) -> {dl_url}")

        uploaded_names = {a["name"]: a for a in final_assets if a.get("state") == "uploaded"}
        if "--include-standalone" not in sys.argv and any(x in uploaded_names for x in ("SmartDownload.exe", "FaqihDownloader.exe")):
            raise RuntimeError("Release verification failed: standalone executable is still present on GitHub Release!")
        stale_present = [x for x in uploaded_names if x.startswith("SmartDownload") or x.startswith("TurboDownloader")]
        if stale_present:
            raise RuntimeError(f"Release verification failed: stale legacy assets still present: {stale_present}")
        missing = set(required_asset_names) - set(uploaded_names.keys())
        if missing:
            raise RuntimeError(f"Release verification failed: missing assets {missing}")
        extra = set(uploaded_names.keys()) - set(required_asset_names)
        if extra:
            raise RuntimeError(f"Release verification failed: unexpected extra assets on release: {extra}")
    else:
        raise RuntimeError(f"Could not verify release: HTTP {v_status}")

    log(f"\n[+] RELEASE {TAG} COMPLETE & PUBLISHED (Exactly {len(required_asset_names)} assets: {sorted(list(required_asset_names))})!")


if __name__ == "__main__":
    main()
