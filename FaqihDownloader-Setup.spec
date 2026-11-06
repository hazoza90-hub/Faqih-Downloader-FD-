# -*- mode: python ; coding: utf-8 -*-
import os
import sys

_src_path = os.path.abspath('src')
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

from PyInstaller.utils.hooks import collect_submodules

payload_dir = os.path.abspath('installer_payload')
sd_hidden = (
    collect_submodules('faqih_downloader.installer')
    + collect_submodules('faqih_downloader.services.browser')
    + collect_submodules('faqih_downloader.locales')
)

# Do NOT bundle ffmpeg into extra_binaries because it is already bundled in payload/ffmpeg.exe
extra_binaries = []

a = Analysis(
    ['installer.py'],
    pathex=[_src_path],
    binaries=extra_binaries,
    datas=[
        (payload_dir, 'payload'),
        ('assets/app_icon.ico', 'assets'),
        ('assets/app_icon.png', 'assets'),
        ('assets/app_icon.ico', '.'),
        ('assets/app_icon.png', '.'),
    ],
    hiddenimports=[
        'faqih_downloader',
        'faqih_downloader.config',
        'faqih_downloader.i18n',
        'faqih_downloader.utils.file_ops',
        'faqih_downloader.utils.window_effects',
        'smart_download',
        'win32com',
        'win32com.client',
        'register_browser',
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
    ] + sd_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['yt_dlp', 'PIL', 'pystray', 'cryptography', 'webview', 'scipy', 'numpy', 'matplotlib'],
    noarchive=False,
    optimize=0,
)

# Strip redundant Tcl/Tk tzdata, msgs, and demos
a.datas = [d for d in a.datas if not any(k in d[0].replace('\\', '/').lower().split('/') for k in ('tzdata', 'msgs', 'demos'))]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='FaqihDownloader-Setup',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/app_icon.ico',
    manifest='assets/app.manifest',
)
