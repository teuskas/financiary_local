import os
import dropbox
from dotenv import load_dotenv

load_dotenv()


def get_dropbox_client() -> dropbox.Dropbox:
    """
    Crea e restituisce un client Dropbox autenticato tramite OAuth2.
    Le credenziali vengono lette dal file .env
    """
    app_key = os.getenv("DROPBOX_APP_KEY")
    app_secret = os.getenv("DROPBOX_APP_SECRET")
    refresh_token = os.getenv("DROPBOX_REFRESH_TOKEN")

    if not all([app_key, app_secret, refresh_token]):
        raise ValueError(
            "Credenziali Dropbox mancanti. "
            "Copia .env.example in .env e compila i valori."
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

