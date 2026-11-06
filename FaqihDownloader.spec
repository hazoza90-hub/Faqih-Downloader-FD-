# -*- mode: python ; coding: utf-8 -*-
import os
import sys

_root_path = os.path.abspath('.')
_src_path = os.path.abspath('src')

# Clean root paths from sys.path so 'faqih_downloader' is collected strictly from src/
sys.path = [p for p in sys.path if p not in ('', '.', _root_path)]
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)
os.environ['PYTHONPATH'] = _src_path

if 'faqih_downloader' in sys.modules:
    del sys.modules['faqih_downloader']

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

yt_hidden = collect_submodules('yt_dlp')
yt_datas = collect_data_files('yt_dlp')
pystray_hidden = collect_submodules('pystray')
sd_hidden = collect_submodules('faqih_downloader')

extra_binaries = []

entry_script = os.path.abspath(os.path.join('scripts', 'pyinstaller_entry.py'))

a = Analysis(
    [entry_script],
    pathex=[_src_path],
    binaries=extra_binaries,
    datas=[
        ('extension', 'extension'),
        ('assets/app_icon.ico', 'assets'),
        ('assets/app_icon.png', 'assets'),
        ('assets/app_icon.ico', '.'),
        ('assets/app_icon.png', '.'),
        ('src/faqih_downloader/locales', 'faqih_downloader/locales'),
        ('src/faqih_downloader/locales', 'smart_download/locales'),
    ] + yt_datas,
    hiddenimports=[
        'faqih_downloader',
        'faqih_downloader.services.media_extractor',
        'faqih_downloader.services.preview_stream_bridge',
        'faqih_downloader.ui.modals.preview_html_builder',
        'smart_download',
        'updater',
        'youtube_resolver',
        'turbo_downloader',
        'faqih_downloader',
        'browser_bridge',
        'native_messaging_host',
        'register_browser',
        'yt_dlp',
        'PIL',
        'PIL.ImageTk',
        'pystray',
        'pystray._win32',
    ] + yt_hidden + pystray_hidden + sd_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# Strip redundant Tcl/Tk tzdata, msgs, and demos to prevent extracting 700+ unnecessary files on startup
a.datas = [d for d in a.datas if not any(k in d[0].replace('\\', '/').lower().split('/') for k in ('tzdata', 'msgs', 'demos'))]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='FaqihDownloader',
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
