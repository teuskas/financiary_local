#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_DIR/.env"
CREDS_FILE="$SCRIPT_DIR/own_finance_mobile/embedded_creds.py"
cd "$SCRIPT_DIR"

if [[ -z "${JAVA_HOME:-}" && -d "/usr/lib/jvm/java-17-openjdk-amd64" ]]; then
  export JAVA_HOME="/usr/lib/jvm/java-17-openjdk-amd64"
  export PATH="$JAVA_HOME/bin:$PATH"
fi

if ! command -v buildozer >/dev/null 2>&1; then
  echo "buildozer non trovato. Installa dipendenze prima (vedi mobile/README.md)."
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "File .env non trovato in $PROJECT_DIR"
  exit 1
fi

export OWN_FINANCE_PROJECT_DIR="$PROJECT_DIR"

python3 - <<'PY'
import os
from pathlib import Path

project_dir = Path(os.environ["OWN_FINANCE_PROJECT_DIR"])
env_file = project_dir / ".env"
creds_file = project_dir / "mobile" / "own_finance_mobile" / "embedded_creds.py"

data: dict[str, str] = {}
for raw_line in env_file.read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    data[key.strip()] = value.strip()

required = ["DROPBOX_APP_KEY", "DROPBOX_APP_SECRET", "DROPBOX_REFRESH_TOKEN"]
missing = [key for key in required if not data.get(key)]
if missing:
    raise SystemExit(f"Variabili mancanti nel file .env: {', '.join(missing)}")

creds_file.write_text(
    '"""Credenziali embeddate generate automaticamente da mobile/build_apk.sh."""\n\n'
    f"DROPBOX_APP_KEY = {data['DROPBOX_APP_KEY']!r}\n"
    f"DROPBOX_APP_SECRET = {data['DROPBOX_APP_SECRET']!r}\n"
    f"DROPBOX_REFRESH_TOKEN = {data['DROPBOX_REFRESH_TOKEN']!r}\n",
    encoding="utf-8",
)
PY

buildozer -v android debug

echo
echo "APK generato in: $SCRIPT_DIR/bin"

