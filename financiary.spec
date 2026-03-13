# -*- mode: python ; coding: utf-8 -*-
"""
financiary.spec
File di configurazione PyInstaller per generare l'eseguibile di Financiary.

Uso:
  Linux/Mac:  pyinstaller financiary.spec
  Windows:    pyinstaller financiary.spec

L'eseguibile viene creato nella cartella dist/ nella directory del progetto.
"""

import sys
import os
from pathlib import Path

block_cipher = None

# Percorso base del progetto
project_dir = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    ['main.py'],
    pathex=[project_dir],
    binaries=[],
    datas=[
        # Include il file .env se presente (credenziali Dropbox)
        ('.env', '.'),
    ],
    hiddenimports=[
        # Dropbox SDK
        'dropbox',
        'dropbox.files',
        'dropbox.users',
        'dropbox.auth',
        'dropbox.oauth',
        # Pandas + openpyxl per lettura xlsx
        'pandas',
        'openpyxl',
        'openpyxl.styles',
        'openpyxl.utils',
        'openpyxl.workbook',
        # Matplotlib backend Tkinter
        'matplotlib',
        'matplotlib.backends.backend_tkagg',
        'matplotlib.backends._backend_tk',
        'matplotlib.figure',
        # Numpy
        'numpy',
        'numpy.core._multiarray_umath',
        # dotenv
        'dotenv',
        'python_dotenv',
        # Tkinter (di solito incluso, ma lo esplicitiamo)
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        # Certificati SSL (necessari per HTTPS verso Dropbox)
        'certifi',
        'ssl',
        # Moduli standard usati
        'threading',
        'io',
        'datetime',
        'numbers',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest',
        'unittest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Financiary',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    # Nasconde la finestra console su Windows
    console=False,
    # Su Windows aggiunge .exe automaticamente
    disable_windowed_traceback=False,
    argv_emulation=False,
    # Per Mac: crea un .app bundle
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# Su macOS crea anche il bundle .app
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='Financiary.app',
        icon=None,
        bundle_identifier='com.financiary.app',
        info_plist={
            'NSHighResolutionCapable': True,
            'CFBundleShortVersionString': '1.0.0',
        },
    )

