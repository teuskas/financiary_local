import os
import sys
from pathlib import Path

import dropbox
from dotenv import load_dotenv


# Cerca .env in modo robusto sia in sviluppo che in eseguibile PyInstaller.
def _load_env_file() -> Path | None:
    candidates: list[Path] = []

    if getattr(sys, "frozen", False):
        # Binario standalone: prima cartella del binario.
        candidates.append(Path(sys.executable).resolve().parent / ".env")
        # Build one-file: .env estratto in _MEIPASS se incluso nel bundle.
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / ".env")

    # Sviluppo / avvio da script: cartella corrente e cartella progetto.
    candidates.append(Path.cwd() / ".env")
    candidates.append(Path(__file__).resolve().parent / ".env")

    seen: set[Path] = set()
    for env_path in candidates:
        resolved = env_path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.exists():
            load_dotenv(dotenv_path=resolved, override=False)
            return resolved

    # Fallback standard di python-dotenv.
    load_dotenv(override=False)
    return None


_loaded_env_path = _load_env_file()


def get_dropbox_client() -> dropbox.Dropbox:
    """
    Crea e restituisce un client Dropbox autenticato tramite OAuth2.
    Le credenziali vengono lette dal file .env
    """
    app_key = os.getenv("DROPBOX_APP_KEY")
    app_secret = os.getenv("DROPBOX_APP_SECRET")
    refresh_token = os.getenv("DROPBOX_REFRESH_TOKEN")

    if not all([app_key, app_secret, refresh_token]):
        location_hint = (
            f".env caricato da: {_loaded_env_path}" if _loaded_env_path else ".env non trovato"
        )
        raise ValueError(
            "Credenziali Dropbox mancanti. "
            "Copia .env.example in .env e compila i valori. "
            f"({location_hint})"
        )

    dbx = dropbox.Dropbox(
        app_key=app_key,
        app_secret=app_secret,
        oauth2_refresh_token=refresh_token,
    )

    # Verifica connessione
    account = dbx.users_get_current_account()
    print(f"[OK] Connesso come: {account.name.display_name} ({account.email})")

    return dbx
