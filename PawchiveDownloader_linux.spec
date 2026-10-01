# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Specification File for Pawchive Downloader (Linux / CachyOS / Arch)
Builds a native Linux ELF binary with clean '_internal' layout and bundled QML/locale assets.
"""

import sys
import os

block_cipher = None

project_root = os.path.abspath(SPECPATH)

# Bundled data files (source_path, target_subfolder)
datas = [
    (os.path.join(project_root, 'qml'), 'qml'),
    (os.path.join(project_root, 'assets'), 'assets'),
    (os.path.join(project_root, 'locales'), 'locales'),
    (os.path.join(project_root, 'config', 'settings.example.json'), 'config'),
]

# Explicitly add Linux binaries from dependencies/ if present
deps_src = os.path.join(project_root, 'dependencies')
for bin_name in ['7za', 'yt-dlp', '7za.exe', 'yt-dlp.exe']:
    bin_path = os.path.join(deps_src, bin_name)
    if os.path.exists(bin_path):
        datas.append((bin_path, 'dependencies'))

# Hidden imports required for dynamic loading across PySide6 QML, PyCryptodome, and core services
hidden_imports = [
    # PySide6 Qt Quick / QML modules
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtQml',
    'PySide6.QtQuick',
    'PySide6.QtQuickControls2',
    'PySide6.QtNetwork',
    'PySide6.QtOpenGL',
    'PySide6.QtSvg',

    # Cryptography (pycryptodome) for Mega.nz AES-CTR decryption
    'Crypto',
    'Crypto.Cipher',
    'Crypto.Cipher.AES',
    'Crypto.Util',
    'Crypto.Util.Padding',
    'Crypto.Util.strxor',
    'Crypto.Random',

    # Network, imaging, and external cloud services
    'gdown',
    'requests',
    'urllib3',
    'PIL',
    'PIL.Image',
    'PIL.WebPImagePlugin',

    # Internal core, bridge, and service packages
    'core',
    'core.path_utils',
    'core.logger',
    'core.parser',
    'core.filter_engine',
    'core.api_client',
    'core.downloader',
    'core.session_manager',
    'core.recovery_manager',
    'core.memory_collector',
    'core.crypto_utils',
    'core.link_vault_manager',
    'core.storage_pool_manager',
    'core.task_scheduler',
    'core.known_manager',
    'core.archive_manager',
    'core.hardware_detector',
    'core.ai_semantic_matcher',
    'core.ai_reasoner',
    'core.text_utils',
    'services',
    'services.cookie_importer',
    'services.cloud_downloader',
    'services.link_extractor',
    'services.model_manager',
    'services.ytdlp_manager',
    'services.batch_loader',
    'services.multipart_downloader',
    'services.bunkr_client',
    'services.erome_client',
    'services.nhentai_client',
    'services.text_exporter',
    'services.bulk_decompressor',
    'services.report_generator',
    'services.telegram_service',
    'bridge',
    'bridge.app_bridge',
    'bridge.log_model',
    'bridge.queue_model',
    'bridge.known_model',
    'bridge.watchlist_model',
    'bridge.decompressor_bridge',
    'bridge.telegram_bridge',
    'core.audio_tagger',
    'mutagen',
    'telethon',
    'qrcode',
]

a = Analysis(
    ['main.py'],
    pathex=[project_root],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'pandas',
        'unittest',
        'pytest',
        'IPython',
        'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Safeguard: ensure no AI model weights or test cache are bundled into the binary
a.datas = [
    d for d in a.datas
    if not ('dependencies/models' in d[0] or 'dependencies\\models' in d[0] or
            '/models/' in d[0] or '\\models\\' in d[0] or
            d[0].lower().endswith('.onnx') or d[0].lower().endswith('.gguf'))
]

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='pawchive',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory='_internal',
)

# 2. Companion updater standalone binary (shares _internal directory)
a_updater = Analysis(
    ['updater.py'],
    pathex=[project_root],
    binaries=[],
    datas=[],
    hiddenimports=['tkinter'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'scipy', 'pandas', 'unittest', 'pytest', 'IPython', 'notebook'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz_updater = PYZ(
    a_updater.pure,
    a_updater.zipped_data,
    cipher=block_cipher
)

exe_updater = EXE(
    pyz_updater,
    a_updater.scripts,
    [],
    exclude_binaries=True,
    name='updater',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory='_internal',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    exe_updater,
    a_updater.binaries,
    a_updater.zipfiles,
    a_updater.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Pawchive Downloader',
)

