#!/usr/bin/env bash
set -Eeuo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT_DIR/school_app"
PORT="${PORT:-8000}"

# --- Couleurs (désactivées automatiquement si le terminal ne les supporte pas) ---
if [[ -t 1 ]] && command -v tput >/dev/null 2>&1 && [[ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]]; then
    C_RESET="$(tput sgr0)"; C_BOLD="$(tput bold)"
    C_INDIGO="$(tput setaf 5)"; C_CYAN="$(tput setaf 6)"
    C_GREEN="$(tput setaf 2)"; C_YELLOW="$(tput setaf 3)"; C_RED="$(tput setaf 1)"
else
    C_RESET=""; C_BOLD=""; C_INDIGO=""; C_CYAN=""; C_GREEN=""; C_YELLOW=""; C_RED=""
fi

step()  { printf '%s[%s]%s %s\n' "$C_CYAN" "$1" "$C_RESET" "$2"; }
ok()    { printf '%s✔%s %s\n' "$C_GREEN" "$C_RESET" "$1"; }
warn()  { printf '%s⚠%s %s\n' "$C_YELLOW" "$C_RESET" "$1"; }
err()   { printf '%s✘ %s%s\n' "$C_RED" "$1" "$C_RESET" >&2; }

# --- Banner EducNet ---
printf '%s%s\n' "$C_INDIGO" "$C_BOLD"
cat <<'BANNER'
 ______    _            _   _      _
|  ____|  | |          | \ | |    | |
| |__   __| |_   _  ___|  \| | ___| |_
|  __| / _` | | | |/ __| . ` |/ _ \ __|
| |___| (_| | |_| | (__| |\  |  __/ |_
|______\__,_|\__,_|\___|_| \_|\___|\__|
BANNER
printf '%s\n' "$C_RESET"
printf '%s%s        Plateforme de gestion scolaire%s\n\n' "$C_BOLD" "$C_INDIGO" "$C_RESET"

# Détection automatique d'un exécutable Python valide si PYTHON_BIN n'est
# pas explicitement fourni. Sous Windows, la commande "python" est souvent
# interceptée par l'alias Microsoft Store et ne fonctionne pas ; "py" est
# alors le lanceur à utiliser.
find_python() {
    local candidate
    for candidate in "${PYTHON_BIN:-}" python3 python py; do
        [[ -z "$candidate" ]] && continue
        if command -v "$candidate" >/dev/null 2>&1; then
            # Sur Windows, "python" peut exister mais être un simple stub
            # Microsoft Store qui ne renvoie rien d'utile : on vérifie qu'il
            # répond réellement à --version.
            if "$candidate" --version >/dev/null 2>&1; then
                echo "$candidate"
                return 0
            fi
        fi
    done
    return 1
}

if ! PYTHON_BIN="$(find_python)"; then
    err "Aucun exécutable Python valide trouvé (python, python3, py)."
    err "Installe Python (https://www.python.org/downloads/) en cochant 'Add python.exe to PATH',"
    err "ou définis PYTHON_BIN manuellement, ex : PYTHON_BIN=py ./start.sh"
    exit 1
fi
step "0/5" "Exécutable Python détecté : $C_BOLD$PYTHON_BIN$C_RESET"

cd "$ROOT_DIR"
if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    echo "[1/5] Environnement virtuel actif : $VIRTUAL_ENV"
    if [[ -x "$VIRTUAL_ENV/bin/python" ]]; then
        PYTHON_BIN="$VIRTUAL_ENV/bin/python"
    elif [[ -x "$VIRTUAL_ENV/Scripts/python.exe" ]]; then
        PYTHON_BIN="$VIRTUAL_ENV/Scripts/python.exe"
    else
        echo "Erreur : impossible de trouver l'exécutable Python dans $VIRTUAL_ENV" >&2
        exit 1
    fi
elif [[ -n "${REPL_ID:-}" ]]; then
    # Replit gère les dépendances Python dans .pythonlibs. Ne pas créer un
    # second environnement à chaque démarrage du workflow.
    echo "[1/5] Environnement Python Replit actif"
else
    VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
    VENV_CREATED=0
    if [[ -x "$VENV_DIR/bin/python" ]]; then
        PYTHON_BIN="$VENV_DIR/bin/python"
        echo "[1/5] Activation de l'environnement virtuel : $VENV_DIR"
    elif [[ -x "$VENV_DIR/Scripts/python.exe" ]]; then
        PYTHON_BIN="$VENV_DIR/Scripts/python.exe"
        echo "[1/5] Activation de l'environnement virtuel : $VENV_DIR"
    else
        echo "[1/5] Création de l'environnement virtuel : $VENV_DIR"
        "$PYTHON_BIN" -m venv "$VENV_DIR"
        if [[ -x "$VENV_DIR/bin/python" ]]; then
            PYTHON_BIN="$VENV_DIR/bin/python"
        else
            PYTHON_BIN="$VENV_DIR/Scripts/python.exe"
        fi
        VENV_CREATED=1
    fi

    # Ne réinstalle les dépendances que si requirements.txt a changé depuis
    # la dernière installation (évite un pip install inutile à chaque
    # démarrage). Basé sur un hash stocké dans le venv.
    REQ_FILE="$APP_DIR/requirements.txt"
    HASH_FILE="$VENV_DIR/.requirements.sha256"
    NEW_HASH="$(sha256sum "$REQ_FILE" 2>/dev/null | awk '{print $1}')"
    OLD_HASH="$( [[ -f "$HASH_FILE" ]] && cat "$HASH_FILE" || echo "" )"
    if [[ "$VENV_CREATED" == "1" || "$NEW_HASH" != "$OLD_HASH" ]]; then
        echo "[1/5] Installation des dépendances (requirements.txt modifié ou venv neuf)"
        [[ "$VENV_CREATED" == "1" ]] && "$PYTHON_BIN" -m pip install --upgrade pip --quiet
        "$PYTHON_BIN" -m pip install -r "$REQ_FILE" --quiet
        echo "$NEW_HASH" > "$HASH_FILE"
    else
        echo "[1/5] Dépendances déjà à jour, installation sautée"
    fi
fi
cd "$APP_DIR"

if [[ "${SKIP_DB_CHECK:-0}" != "1" ]]; then
    echo "[2/5] Vérification de la connexion à la base de données"
    "$PYTHON_BIN" manage.py shell -c \
        "from django.db import connection; connection.ensure_connection(); print('Connexion DB OK : ' + connection.vendor)"
else
    echo "[2/5] Vérification DB sautée (SKIP_DB_CHECK=1)"
fi

echo "[3/5] Application des migrations"
if [[ -n "${DATABASE_URL:-}" || -n "${DB_HOST:-}" ]]; then
    "$PYTHON_BIN" manage.py migrate_schemas --noinput
    echo "[3b/5] Initialisation du tenant public (PostgreSQL)"
    "$PYTHON_BIN" manage.py init_public_tenant
    echo "[3c/5] Données de test (école + utilisateurs)"
    "$PYTHON_BIN" manage.py seed_test_school
else
    "$PYTHON_BIN" manage.py migrate --noinput
fi

if [[ "${SKIP_COLLECTSTATIC:-0}" != "1" ]]; then
    echo "[4/5] Collecte des fichiers statiques"
    "$PYTHON_BIN" manage.py collectstatic --noinput
else
    echo "[4/5] Collectstatic sauté (SKIP_COLLECTSTATIC=1)"
fi

echo "[5/5] Démarrage du serveur sur le port $PORT"
exec "$PYTHON_BIN" manage.py runserver "0.0.0.0:$PORT" --noreload