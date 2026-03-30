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
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Percorso base del progetto
project_dir = Path(os.path.dirname(os.path.abspath(SPEC)))

# Include .env solo se presente
datas = []
# Include dati runtime di matplotlib (font, styles, backend config)
datas += collect_data_files('matplotlib')
# Include plugin necessari per l'integrazione Tk/Pillow
datas += collect_data_files('PIL')
env_path = project_dir / '.env'
if env_path.exists():
    datas.append((str(env_path), '.'))

# Include assets (icona e risorse UI)
assets_path = project_dir / 'assets'
if assets_path.exists():
    datas.append((str(assets_path), 'assets'))

# Icone per piattaforma
icon_ico = project_dir / 'assets' / 'dollar.ico'
icon_icns = project_dir / 'assets' / 'dollar.icns'

# Hidden imports robusti per matplotlib/tk e runtime grafici
extra_hiddenimports = []
extra_hiddenimports += collect_submodules('matplotlib.backends')
extra_hiddenimports += collect_submodules('matplotlib')
extra_hiddenimports += collect_submodules('PIL')

a = Analysis(
    ['main.py'],
    pathex=[str(project_dir)],
    binaries=[],
    datas=datas,
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
        'matplotlib.pyplot',
        'matplotlib.backends.backend_tkagg',
        'matplotlib.backends.backend_agg',
        'matplotlib.backends._backend_tk',
        'matplotlib.figure',
        # Pillow helper per tkinter
        'PIL._tkinter_finder',
        # Numpy
        'numpy',
        'numpy.core._multiarray_umath',
        # dotenv
        'dotenv',
        # Tkinter (di solito incluso, ma lo esplicitiamo)
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        # Certificati SSL (necessari per HTTPS verso Dropbox)
        'certifi',
        'ssl',
        # Richiesto da pkg_resources a runtime (hook pyi_rth_pkgres)
        'platformdirs',
        # Moduli standard usati
        'threading',
        'io',
        'datetime',
        'numbers',
    ] + extra_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='OwnFinance',
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
    # Icona eseguibile (Windows)
    icon=str(icon_ico) if icon_ico.exists() else None,
)

# Su macOS crea anche il bundle .app
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='OwnFinance.app',
        icon=str(icon_icns) if icon_icns.exists() else None,
        bundle_identifier='com.ownfinance.app',
        info_plist={
            'NSHighResolutionCapable': True,
            'CFBundleShortVersionString': '1.0.0',
        },
    )
