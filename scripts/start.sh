#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT_DIR/school_app"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PORT="${PORT:-8000}"

cd "$ROOT_DIR"

if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    echo "[1/5] Environnement virtuel actif : $VIRTUAL_ENV"
elif [[ -n "${REPL_ID:-}" ]]; then
    # Replit gère les dépendances Python dans .pythonlibs. Ne pas créer un
    # second environnement à chaque démarrage du workflow.
    echo "[1/5] Environnement Python Replit actif"
else
    VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
    if [[ ! -x "$VENV_DIR/bin/python" ]]; then
        echo "[1/5] Création de l'environnement virtuel : $VENV_DIR"
        "$PYTHON_BIN" -m venv "$VENV_DIR"
        "$VENV_DIR/bin/python" -m pip install --upgrade pip
        "$VENV_DIR/bin/python" -m pip install -r "$APP_DIR/requirements.txt"
    else
        echo "[1/5] Activation de l'environnement virtuel : $VENV_DIR"
    fi
    PYTHON_BIN="$VENV_DIR/bin/python"
fi

cd "$APP_DIR"

echo "[2/5] Vérification de la connexion à la base de données"
"$PYTHON_BIN" manage.py shell -c \
    "from django.db import connection; connection.ensure_connection(); print('Connexion DB OK : ' + connection.vendor)"

echo "[3/5] Application des migrations"
if [[ -n "${DATABASE_URL:-}" || -n "${DB_HOST:-}" ]]; then
    "$PYTHON_BIN" manage.py migrate_schemas --noinput
else
    "$PYTHON_BIN" manage.py migrate --noinput
fi

echo "[4/5] Collecte des fichiers statiques"
"$PYTHON_BIN" manage.py collectstatic --noinput

echo "[5/5] Démarrage du serveur sur le port $PORT"
exec "$PYTHON_BIN" manage.py runserver "0.0.0.0:$PORT" --noreload