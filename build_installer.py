"""
========================================================================================
🔨 AUTOMATED BUILDER — Faqih Downloader (FD) & Faqih Downloader Setup
========================================================================================
Automates the build process for:
1. Standalone Application: dist/FaqihDownloader.exe (via FaqihDownloader.spec)
2. Standalone Windows Installer: dist/FaqihDownloader-Setup.exe (via FaqihDownloader-Setup.spec)
========================================================================================
"""

import os
import sys
import shutil
import subprocess
import tempfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
DIST_DIR = os.path.join(BASE_DIR, "dist")
PAYLOAD_DIR = os.path.join(BASE_DIR, "installer_payload")


ROOT_DIR = BASE_DIR

STALE_DIST_ARTIFACTS = [
    "SmartDownload.exe",
    "smart_download.exe",
    "SmartDownload-Setup.exe",
    "smart_download_setup.exe",
    "SmartDownload-CorePatch.zip",
    "com.smartdownload.host.json",
    "sd_host.bat",
    "TurboDownloader.exe",
    "turbo_downloader.exe",
    "TurboDownloader-Setup.exe",
    "turbo_downloader_setup.exe",
    "TurboDownloader-CorePatch.zip",
    "com.turbodownloader.host.json",
    "turbo_host.bat",
]


def clean_stale_shadow_modules():
    """Removes any stale smart_download.py or smart_download.pyc files from build/, dist/, core_plugin, and root."""
    search_dirs = [
        os.path.join(BASE_DIR, "build"),
        DIST_DIR,
        os.path.join(BASE_DIR, "__pycache__"),
    ]
    try:
        appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
        plugin_dir = os.path.join(appdata, "SmartDownload", "core_plugin")
        if os.path.isdir(plugin_dir):
            search_dirs.append(plugin_dir)
    except Exception:
        pass

    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        for root, dirs, files in os.walk(d):
            for fname in files:
                fn_lower = fname.lower()
                if fn_lower in ("smart_download.py", "smart_download.pyc") or (
                    fn_lower.startswith("smart_download.") and fn_lower.endswith(".pyc")
                ):
                    fpath = os.path.join(root, fname)
                    try:
                        os.chmod(fpath, 0o777)
                        os.remove(fpath)
                        print(f"[*] Removed stale shadow file: {fpath}")
                    except Exception as e:
                        print(f"[-] Warning: Failed to remove {fpath}: {e}")

    for root_shadow in ("smart_download.py", "smart_download.pyc"):
        fpath = os.path.join(BASE_DIR, root_shadow)
        if os.path.isfile(fpath):
            try:
                os.chmod(fpath, 0o777)
                os.remove(fpath)
                print(f"[*] Removed stale root shadow file: {fpath}")
            except Exception as e:
                print(f"[-] Warning: Failed to remove root shadow file {fpath}: {e}")


def verify_exe_startup(exe_path: str, timeout: int = 30):
    """Executes --test-startup verification in an isolated temporary directory."""
    if not os.path.isfile(exe_path):
        raise FileNotFoundError(f"Executable not found: {exe_path}")
    with open(exe_path, "rb") as f:
        header = f.read(2)
    if header != b"MZ":
        print(f"[*] Skipping --test-startup for non-PE binary: {exe_path}")
        return

    print(f"[*] Verifying built FaqihDownloader.exe (--test-startup): {exe_path}...")
    temp_cwd = tempfile.mkdtemp(prefix="sd_smoke_")
    try:
        verify_res = subprocess.run(
            [exe_path, "--test-startup"],
            cwd=temp_cwd,
            timeout=timeout,
            capture_output=True,
            text=True,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"Built FaqihDownloader.exe timed out during --test-startup verification: {e}")
    finally:
        try:
            shutil.rmtree(temp_cwd, ignore_errors=True)
        except Exception:
            pass

    if verify_res.returncode != 0:
        err_msg = verify_res.stderr.strip() if verify_res.stderr else ""
        raise RuntimeError(f"Built FaqihDownloader.exe failed --test-startup verification (exit code {verify_res.returncode}) {err_msg}".strip())

    print("[+] FaqihDownloader.exe passed --test-startup verification successfully.")


def clean_stale_dist_artifacts():
    """Removes legacy TurboDownloader/SmartDownload artifacts from dist/ and syncs the Faqih Downloader extension folder."""
    clean_stale_shadow_modules()
    for stale_spec in ("turbo_downloader.spec", "TurboDownloader.spec"):
        sp = os.path.join(ROOT_DIR, stale_spec)
        if os.path.exists(sp):
            try:
                os.chmod(sp, 0o777)
                os.remove(sp)
                print(f"[*] Removed stale spec file: {sp}")
            except Exception as e:
                print(f"[-] Warning: Failed to remove {sp}: {e}")

    if not os.path.isdir(DIST_DIR):
        return
    for name in STALE_DIST_ARTIFACTS:
        p = os.path.join(DIST_DIR, name)
        if os.path.exists(p):
            try:
                os.chmod(p, 0o777)
                os.remove(p)
            except Exception:
                pass
    src_ext = os.path.join(BASE_DIR, "extension")
    dist_ext = os.path.join(DIST_DIR, "extension")
    if os.path.isdir(src_ext):
        try:
            shutil.copytree(src_ext, dist_ext, dirs_exist_ok=True)
        except Exception:
            pass


def purge_stale_core_plugin():
    """Removes any stale %APPDATA%\\SmartDownload\\core_plugin directory."""
    try:
        try:
            from smart_download.services.core_patch_updater import get_core_plugin_dir
            plugin_dir = get_core_plugin_dir()
        except Exception:
            appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
            plugin_dir = os.path.join(appdata, "SmartDownload", "core_plugin")
        if plugin_dir and os.path.isdir(plugin_dir):
            shutil.rmtree(plugin_dir, ignore_errors=True)
            print(f"[*] Removed stale core_plugin directory: {plugin_dir}")
    except Exception as e:
        print(f"[-] Warning: Failed to remove core_plugin directory: {e}")


def build_app(rebuild: bool = False):
    """Compiles dist/FaqihDownloader.exe using PyInstaller."""
    clean_stale_shadow_modules()
    purge_stale_core_plugin()
    exe_path = os.path.join(DIST_DIR, "FaqihDownloader.exe")

    print("[*] Building FaqihDownloader.exe via PyInstaller...")
    spec_path = os.path.join(BASE_DIR, "FaqihDownloader.spec")
    if not os.path.isfile(spec_path):
        spec_path = os.path.join(BASE_DIR, "SmartDownload.spec")
    cmd = [sys.executable, "-m", "PyInstaller", spec_path, "--noconfirm"]
    if rebuild:
        cmd.append("--clean")
    res = subprocess.run(cmd, cwd=BASE_DIR)
    if res.returncode != 0:
        raise RuntimeError(f"PyInstaller failed to build FaqihDownloader.exe with returncode {res.returncode}")

    if not os.path.isfile(exe_path):
        raise FileNotFoundError(f"Expected binary not found after build: {exe_path}")

    # Mandatory Post-Build Binary Smoke Verification
    verify_exe_startup(exe_path)

    clean_stale_dist_artifacts()
    try:
        from smart_download.services.youtube_models import find_ffmpeg_bin
        ffmpeg_bin = find_ffmpeg_bin()
        if ffmpeg_bin and os.path.isfile(ffmpeg_bin):
            dist_ffmpeg = os.path.join(DIST_DIR, "ffmpeg.exe")
            if os.path.abspath(ffmpeg_bin) != os.path.abspath(dist_ffmpeg):
                shutil.copy2(ffmpeg_bin, dist_ffmpeg)
                print(f"[+] Copied FFmpeg next to standalone binary: {dist_ffmpeg}")
    except Exception as e:
        print(f"[-] Note: Could not copy FFmpeg to dist ({e})")

    print(f"[+] FaqihDownloader.exe successfully built: {os.path.getsize(exe_path):,} bytes")
    return exe_path


def prepare_payload():
    """Assembles all files needed in the installer payload directory (single copy of executable)."""
    print("[*] Preparing installer payload directory...")
    # Clean payload directory completely to prevent bundling stale or duplicate binaries
    if os.path.isdir(PAYLOAD_DIR):
        shutil.rmtree(PAYLOAD_DIR, ignore_errors=True)
    os.makedirs(PAYLOAD_DIR, exist_ok=True)

    # 1. Main executable: Bundle ONLY FaqihDownloader.exe
    src_exe = os.path.join(DIST_DIR, "FaqihDownloader.exe")
    if not os.path.isfile(src_exe):
        legacy_src = os.path.join(DIST_DIR, "SmartDownload.exe")
        if os.path.isfile(legacy_src):
            src_exe = legacy_src
        else:
            raise FileNotFoundError(f"Missing {src_exe}. Build it first.")
    payload_exe = os.path.join(PAYLOAD_DIR, "FaqihDownloader.exe")
    shutil.copy2(src_exe, payload_exe)
    verify_exe_startup(payload_exe)

    # 2. Icons
    src_ico = os.path.join(BASE_DIR, "assets", "app_icon.ico")
    if not os.path.isfile(src_ico):
        src_ico = os.path.join(BASE_DIR, "app_icon.ico")
    if os.path.isfile(src_ico):
        shutil.copy2(src_ico, os.path.join(PAYLOAD_DIR, "app_icon.ico"))

    # 3. Extension directory
    src_ext = os.path.join(BASE_DIR, "extension")
    dest_ext = os.path.join(PAYLOAD_DIR, "extension")
    if os.path.isdir(dest_ext):
        shutil.rmtree(dest_ext, ignore_errors=True)
    if os.path.isdir(src_ext):
        shutil.copytree(src_ext, dest_ext)

    # 4. Host launcher batch and registration script
    try:
        from smart_download.services.browser import registry as rb
        from smart_download.services.browser.host_manifest import generate_host_manifest, get_default_extension_origins
    except ImportError:
        import register_browser as rb
        from host_manifest import generate_host_manifest, get_default_extension_origins

    bat_dest = os.path.join(PAYLOAD_DIR, "fd_host.bat")
    json_dest = os.path.join(PAYLOAD_DIR, "com.faqihdownloader.host.json")
    rb.generate_launcher_batch(bat_dest)
    generate_host_manifest(bat_dest, json_dest, get_default_extension_origins(target_dir=PAYLOAD_DIR))

    try:
        generate_host_manifest(os.path.join(BASE_DIR, "fd_host.bat"), os.path.join(BASE_DIR, "com.faqihdownloader.host.json"))
    except Exception:
        pass

    reg_script = os.path.join(BASE_DIR, "src", "smart_download", "services", "browser", "registry.py")
    if not os.path.isfile(reg_script):
        reg_script = os.path.join(BASE_DIR, "register_browser.py")
    if os.path.isfile(reg_script):
        shutil.copy2(reg_script, os.path.join(PAYLOAD_DIR, "register_browser.py"))
    hm_script = os.path.join(BASE_DIR, "src", "smart_download", "services", "browser", "host_manifest.py")
    if os.path.isfile(hm_script):
        shutil.copy2(hm_script, os.path.join(PAYLOAD_DIR, "host_manifest.py"))

    # 5. FFmpeg binary bundling if available
    try:
        from smart_download.services.youtube_models import find_ffmpeg_bin
        ffmpeg_bin = find_ffmpeg_bin()
        if ffmpeg_bin and os.path.isfile(ffmpeg_bin):
            shutil.copy2(ffmpeg_bin, os.path.join(PAYLOAD_DIR, "ffmpeg.exe"))
            print(f"[+] Bundled FFmpeg into payload: {ffmpeg_bin}")
            dist_ffmpeg = os.path.join(DIST_DIR, "ffmpeg.exe")
            if os.path.abspath(ffmpeg_bin) != os.path.abspath(dist_ffmpeg):
                shutil.copy2(ffmpeg_bin, dist_ffmpeg)
                print(f"[+] Copied FFmpeg next to standalone binary: {dist_ffmpeg}")
    except Exception as e:
        print(f"[-] Note: FFmpeg bundling skipped ({e})")

    # 6. Compress heavy binaries into high-efficiency payload.lzma.zip
    try:
        import zipfile
        payload_archive = os.path.join(PAYLOAD_DIR, "payload.lzma.zip")
        binaries_to_pack = []
        if os.path.isfile(payload_exe):
            binaries_to_pack.append((payload_exe, "FaqihDownloader.exe"))
        payload_ffmpeg = os.path.join(PAYLOAD_DIR, "ffmpeg.exe")
        if os.path.isfile(payload_ffmpeg):
            binaries_to_pack.append((payload_ffmpeg, "ffmpeg.exe"))

        if binaries_to_pack:
            print("[*] Compressing heavy binaries into payload.lzma.zip (LZMA)...")
            with zipfile.ZipFile(payload_archive, "w", compression=zipfile.ZIP_LZMA) as zf:
                for fpath, arcname in binaries_to_pack:
                    zf.write(fpath, arcname=arcname)
                    print(f"  -> Added {arcname} ({os.path.getsize(fpath):,} bytes) to payload.lzma.zip")
            for fpath, _ in binaries_to_pack:
                try:
                    os.remove(fpath)
                except Exception:
                    pass
            print(f"[+] Created payload.lzma.zip: {os.path.getsize(payload_archive):,} bytes")
    except Exception as e:
        print(f"[-] Warning: Failed to compress payload into LZMA archive ({e})")

    print(f"[+] Installer payload prepared at: {PAYLOAD_DIR}")


def build_installer(rebuild: bool = False):
    """Compiles dist/FaqihDownloader-Setup.exe using PyInstaller."""
    print("[*] Building FaqihDownloader-Setup.exe via PyInstaller...")
    spec_path = os.path.join(BASE_DIR, "FaqihDownloader-Setup.spec")
    if not os.path.isfile(spec_path):
        spec_path = os.path.join(BASE_DIR, "SmartDownload-Setup.spec")
    cmd = [sys.executable, "-m", "PyInstaller", spec_path, "--noconfirm"]
    if rebuild:
        cmd.append("--clean")
    res = subprocess.run(cmd, cwd=BASE_DIR)
    if res.returncode != 0:
        raise RuntimeError(f"PyInstaller failed to build FaqihDownloader-Setup.exe with returncode {res.returncode}")

    setup_path = os.path.join(DIST_DIR, "FaqihDownloader-Setup.exe")
    if not os.path.isfile(setup_path):
        raise FileNotFoundError(f"Installer binary not found: {setup_path}")

    clean_stale_dist_artifacts()
    print(f"[+] FaqihDownloader-Setup.exe successfully built: {os.path.getsize(setup_path):,} bytes")
    return setup_path


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    import argparse
    parser = argparse.ArgumentParser(description="SmartDownload Build Automation")
    parser.add_argument("--rebuild-all", action="store_true", help="Force rebuild of SmartDownload.exe")
    parser.add_argument("--installer-only", action="store_true", help="Only build SmartDownload-Setup.exe")
    args = parser.parse_args()

    print("=" * 70)
    print("[*] SMART DOWNLOAD (SD) - BUILD PIPELINE")
    print("=" * 70)

    try:
        from smart_download.installer import terminate_running_app
        terminate_running_app()
    except Exception as e:
        print(f"[*] Warning terminating running app: {e}")

    if not args.installer_only:
        purge_stale_core_plugin()
        build_app(rebuild=args.rebuild_all)

    prepare_payload()
    setup_exe = build_installer(rebuild=args.rebuild_all)

    if not args.installer_only:
        try:
            from smart_download.installer import get_default_install_dir, install_application, terminate_running_app
            default_dir = get_default_install_dir()
            if os.path.exists(default_dir):
                print(f"[*] Updating installed application in default directory: {default_dir}")
                terminate_running_app()
                try:
                    install_application(
                        target_dir=default_dir,
                        register_browser=True,
                        create_desktop=True,
                        create_start_menu=True,
                        register_startup=True
                    )
                except Exception as first_err:
                    print(f"[*] Retrying installation after explicit process termination: {first_err}")
                    terminate_running_app()
                    time.sleep(0.5)
                    install_application(
                        target_dir=default_dir,
                        register_browser=True,
                        create_desktop=True,
                        create_start_menu=True,
                        register_startup=True
                    )
                print(f"[+] Updated installed application in {default_dir}")
        except Exception as e:
            print(f"[!] CRITICAL FAILURE: Error updating installed application in default directory: {e}")
            raise

    if not args.installer_only:
        print("[*] Packaging and applying core patch...")
        try:
            from smart_download.services.core_patch_updater import build_core_patch_zip, CoreHotPatchUpdater

            patch_zip = os.path.join(DIST_DIR, "FaqihDownloader-CorePatch.zip")
            build_core_patch_zip(patch_zip)
            CoreHotPatchUpdater().apply_core_patch(patch_zip)
            print(f"[+] Applied core patch from {patch_zip}")
        except Exception as e:
            print(f"[-] Error applying core patch: {e}")

    print("\n" + "=" * 70)
    print("[+] BUILD COMPLETE")
    print(f"App Binary:      {os.path.join(DIST_DIR, 'FaqihDownloader.exe')}")
    print(f"Setup Installer: {setup_exe}")
    print("=" * 70)


if __name__ == "__main__":
    main()
