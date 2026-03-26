# financiary_local

Programma Python standalone che accede a Dropbox, legge i file presenti e produce statistiche sui dati.

## Struttura

```
financiary_local/
├── main.py          # entry point
├── auth.py          # autenticazione Dropbox OAuth2
├── explorer.py      # lista file/cartelle Dropbox
├── reader.py        # lettura file CSV/XLSX in DataFrame
├── .env.example     # template credenziali
├── requirements.txt # dipendenze
└── .venv/           # ambiente virtuale (non in git)
```

## Setup

```bash
# 1. Copia e compila le credenziali
cp .env.example .env
# → vai su https://www.dropbox.com/developers/apps e crea una app
# → inserisci APP_KEY, APP_SECRET e REFRESH_TOKEN nel file .env

# 2. Attiva il venv
source .venv/bin/activate

# 3. Installa dipendenze
pip install -r requirements.txt

# 4. Avvia
python main.py
```

## Dipendenze principali

- `dropbox` — SDK ufficiale Dropbox
- `pandas` — lettura e manipolazione dati
- `python-dotenv` — gestione variabili d'ambiente
- `pyinstaller` — compilazione standalone

## Versione Android (APK)

E stata aggiunta una base mobile separata in `mobile/`.

- Entry point mobile: `mobile/own_finance_mobile/main.py`
- Build Android: `mobile/buildozer.spec`
- Guida rapida: `mobile/README.md`

La versione desktop resta invariata (entry point `main.py`).
