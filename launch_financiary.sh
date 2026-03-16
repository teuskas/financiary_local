#!/usr/bin/env bash
set -euo pipefail

# Directory reale in cui si trova questo script (anche se invocato via symlink)
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# Launcher portabile: prova nome nuovo e fallback legacy
CANDIDATES=(
  "$SCRIPT_DIR/OwnFinance"
  "$SCRIPT_DIR/dist/OwnFinance"
  "$SCRIPT_DIR/Financiary"
  "$SCRIPT_DIR/dist/Financiary"
)

EXECUTABLE=""
for candidate in "${CANDIDATES[@]}"; do
  if [[ -x "$candidate" ]]; then
    EXECUTABLE="$candidate"
    break
  fi
done

if [[ -z "$EXECUTABLE" ]]; then
  echo "Errore: eseguibile OwnFinance/Financiary non trovato o non eseguibile." >&2
  echo "Percorsi provati:" >&2
  for candidate in "${CANDIDATES[@]}"; do
    echo " - $candidate" >&2
  done
  exit 1
fi

cd "$(dirname "$EXECUTABLE")"
exec "$EXECUTABLE"
