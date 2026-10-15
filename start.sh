#!/usr/bin/env bash
# SmarTel — one-command start (Linux / macOS / WSL)
#
#   ./start.sh
#
# Creates a virtual environment if needed, installs/updates the dependencies,
# then runs the bot. The owner claim code is printed in this terminal on the
# first run — send "/start <code>" to your bot in Telegram.
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Python 3.10+ is required but '$PY' was not found." >&2
  exit 1
fi

if [ ! -d .venv ]; then
  echo "==> Creating the virtual environment (.venv)"
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

if [ ! -f .venv/.deps-installed ] || [ requirements.txt -nt .venv/.deps-installed ]; then
  echo "==> Installing dependencies"
  python -m pip install --quiet --upgrade pip
  python -m pip install --quiet -r requirements.txt
  touch .venv/.deps-installed
fi

if [ ! -f .env ] && [ -f .env.example ]; then
  echo "==> No .env found: the first-run wizard will ask for your bot token."
fi

exec python main.py "$@"
