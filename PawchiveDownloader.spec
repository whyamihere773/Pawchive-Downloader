# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Specification File for Pawchive Downloader
Windows Windowed Desktop Distribution (One Directory with Hidden Console)
"""

import sys
import os

block_cipher = None

project_root = os.path.abspath(SPECPATH)

# Bundled data files (source_path, target_subfolder)
datas = [
    (os.path.join(project_root, 'qml'), 'qml'),
    (os.path.join(project_root, 'assets'), 'assets'),
    (os.path.join(project_root, 'config', 'settings.example.json'), 'config'),
]

# Hidden imports required for dynamic loading across PySide6 QML and PyCryptodome
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
    'core.logger',
    'core.parser',
    'core.filter_engine',
    'core.api_client',
    'core.downloader',
    'core.session_manager',
    'core.known_manager',
    'services',
    'services.cloud_downloader',
    'services.link_extractor',
    'services.ytdlp_manager',
    'services.batch_loader',
    'services.multipart_downloader',
    'services.bunkr_client',
    'services.erome_client',
    'services.nhentai_client',
    'services.text_exporter',
    'bridge',
    'bridge.app_bridge',
    'bridge.log_model',
    'bridge.queue_model',
    'bridge.known_model',
]

# Optional application icon
icon_path = os.path.join(project_root, 'assets', 'icon.ico')
if not os.path.exists(icon_path):
    icon_path = None

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
    name='PawchiveDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Windows GUI (Console Hidden)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PawchiveDownloader',
)
