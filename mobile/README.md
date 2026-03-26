# Own Finance Mobile (APK)

Questa cartella contiene la versione Android dell'app, separata dalla desktop.

## Cosa fa ora

- Connessione a Dropbox automatica usando le credenziali lette dal file `.env` del progetto al momento della build APK
- Download del file `/me/new total inv.xlsx`
- Rilevamento automatico del foglio annuale piu recente (`2026`, `2027`, ...)
- Visualizzazione rapida delle 3 tabelle:
  - `investimenti`
  - `guadagni`
  - `inv_guad`

Non e necessario inserire credenziali dentro l'app: la build genera automaticamente `mobile/own_finance_mobile/embedded_creds.py` a partire da `.env`.

La versione desktop resta invariata e continua a vivere nel root del progetto.

## Prerequisiti Linux per build APK

Serve un ambiente Linux con Java/SDK/NDK configurati da Buildozer.

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv git zip unzip openjdk-17-jdk
```

## Build locale APK (debug)

```bash
cd /home/matteo/workspace/financiary_local
python3 -m venv .venv-mobile
source .venv-mobile/bin/activate
pip install -r mobile/requirements-mobile.txt

cd mobile
chmod +x build_apk.sh
./build_apk.sh
```

Output atteso:
- APK in `mobile/bin/`
- L'app mobile apre direttamente le funzionalita senza schermata di inserimento credenziali

## Test veloce parser mobile

```bash
cd /home/matteo/workspace/financiary_local
python3 mobile/smoke_test.py
```

## Note sicurezza

- Le credenziali vengono embeddate automaticamente nell'APK leggendo `.env` durante la build.
- Il file generato `mobile/own_finance_mobile/embedded_creds.py` e ignorato da Git.
- Se un token e stato esposto in repo, va rigenerato da Dropbox.

