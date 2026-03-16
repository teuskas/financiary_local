"""
build.py
Script per generare l'eseguibile di Own Finance tramite PyInstaller.

Uso (dalla cartella del progetto, con il venv attivo):
  python build.py

Genera l'eseguibile nella cartella dist/:
  Linux  → dist/OwnFinance
  Windows→ dist/OwnFinance.exe
  macOS  → dist/OwnFinance.app  (bundle) + dist/OwnFinance (binario)

NOTA: PyInstaller genera eseguibili NATIVI per il SO corrente.
      Per avere l'eseguibile su Windows devi eseguire questo script su Windows,
      e così per macOS.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.resolve()
DIST_DIR = PROJECT_DIR / "dist"
BUILD_DIR = PROJECT_DIR / "build"


def check_env():
    """Avvisa se manca il file .env (le credenziali non saranno incluse)."""
    env_file = PROJECT_DIR / ".env"
    if not env_file.exists():
        print("[ATTENZIONE] File .env non trovato.")
        print("  L'eseguibile verrà comunque creato, ma dovrai affiancare")
        print("  un file .env con le tue credenziali Dropbox nella stessa")
        print("  cartella dell'eseguibile prima di avviarlo.")
    else:
        print("[OK] File .env trovato, verrà incluso nell'eseguibile.")


def clean_previous():
    """Rimuove le cartelle dist/ e build/ precedenti."""
    for folder in (DIST_DIR, BUILD_DIR):
        if folder.exists():
            print(f"[...] Pulizia {folder.name}/")
            shutil.rmtree(folder)


def build():
    """Lancia PyInstaller con il file .spec."""
    spec_file = PROJECT_DIR / "financiary.spec"
    if not spec_file.exists():
        print("[ERRORE] financiary.spec non trovato!")
        sys.exit(1)

    print(f"[...] Build in corso per {sys.platform}...")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", str(spec_file), "--distpath", str(PROJECT_DIR / "dist")],
        cwd=str(PROJECT_DIR),
    )

    if result.returncode != 0:
        print("[ERRORE] Build fallita.")
        sys.exit(1)


def report():
    """Mostra il percorso dell'eseguibile generato."""
    if sys.platform == "win32":
        exe = DIST_DIR / "OwnFinance.exe"
    elif sys.platform == "darwin":
        exe = DIST_DIR / "OwnFinance.app"
    else:
        exe = DIST_DIR / "OwnFinance"

    if exe.exists():
        print(f"\n[OK] Eseguibile generato con successo:")
        print(f"     {exe}")
        print(f"\nPuoi copiarlo dove preferisci e avviarlo direttamente.")
        if sys.platform != "win32" and sys.platform != "darwin":
            print(f"     (Su Linux potrebbe essere necessario: chmod +x '{exe}')")
    else:
        print(f"[ATTENZIONE] Eseguibile non trovato in {DIST_DIR}")


if __name__ == "__main__":
    print("=" * 55)
    print("  Own Finance – Build eseguibile standalone")
    print("=" * 55)
    check_env()
    clean_previous()
    build()
    report()

