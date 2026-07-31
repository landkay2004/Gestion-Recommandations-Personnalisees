#!/usr/bin/env bash
set -Eeuo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT_DIR/school_app"
PORT="${PORT:-8000}"

# ── Chargement du fichier .env si présent ───────────────────────────────────
if [[ -f "$APP_DIR/.env" ]]; then
    # shellcheck source=/dev/null
    source "$APP_DIR/.env"
fi

# ── Couleurs (désactivées si le terminal ne les supporte pas) ─────────────────
if [[ -t 1 ]] && command -v tput >/dev/null 2>&1 && [[ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]]; then
    C_RESET="$(tput sgr0)";  C_BOLD="$(tput bold)"
    C_BLUE="$(tput setaf 4)"; C_CYAN="$(tput setaf 6)"; C_WHITE="$(tput setaf 7)"
    C_GREEN="$(tput setaf 2)"; C_YELLOW="$(tput setaf 3)"; C_RED="$(tput setaf 1)"
    C_BG_BLUE="$(tput setab 4)" 2>/dev/null || C_BG_BLUE=""
else
    C_RESET=""; C_BOLD=""; C_BLUE=""; C_CYAN=""; C_WHITE=""
    C_GREEN=""; C_YELLOW=""; C_RED=""; C_BG_BLUE=""
fi

# ── Fonctions d'affichage ─────────────────────────────────────────────────────
hr()   { printf '%s%s%s\n' "$C_BLUE" "$(printf '%0.s─' {1..62})" "$C_RESET"; }
ok()   { printf '  %s[OK]%s  %s\n'  "$C_GREEN"  "$C_RESET" "$1"; }
warn() { printf '  %s[!!]%s  %s\n'  "$C_YELLOW" "$C_RESET" "$1"; }
err()  { printf '  %s[ERR]%s %s\n'  "$C_RED"    "$C_RESET" "$1" >&2; }
step() { printf '\n%s[%s]%s %s%s%s\n' "$C_CYAN" "$1" "$C_RESET" "$C_BOLD" "$2" "$C_RESET"; }

# ── Bannière ──────────────────────────────────────────────────────────────────
printf '\n'
hr
printf '%s%s\n' "$C_BLUE$C_BOLD" \
'                                                              '
printf '%s%s\n' "$C_BLUE$C_BOLD" \
'     ______    _            _   _      _                     '
printf '%s%s\n' "$C_BLUE$C_BOLD" \
'    |  ____|  | |          | \ | |    | |                    '
printf '%s%s\n' "$C_BLUE$C_BOLD" \
'    | |__   __| |_   _  ___|  \| | ___| |_                  '
printf '%s%s\n' "$C_BLUE$C_BOLD" \
'    |  __| / _` | | | |/ __| . ` |/ _ \ __|                 '
printf '%s%s\n' "$C_BLUE$C_BOLD" \
'    | |___| (_| | |_| | (__| |\  |  __/ |_                  '
printf '%s%s\n' "$C_BLUE$C_BOLD" \
'    |______\__,_|\__,_|\___|_| \_|\___|\__|                  '
printf '%s%s\n' "$C_BLUE$C_BOLD" \
'                                                              '
printf '%s%s%s\n' "$C_CYAN$C_BOLD" \
'         Plateforme de Gestion Scolaire  —  EducNet          ' "$C_RESET"
hr
printf '\n'

# ── Détection Python ──────────────────────────────────────────────────────────
find_python() {
    local candidate
    for candidate in "${PYTHON_BIN:-}" python3 python py; do
        [[ -z "$candidate" ]] && continue
        if command -v "$candidate" >/dev/null 2>&1; then
            if "$candidate" --version >/dev/null 2>&1; then
                echo "$candidate"
                return 0
            fi
        fi
    done
    return 1
}

if ! PYTHON_BIN="$(find_python)"; then
    err "Aucun exécutable Python valide trouvé (python3, python, py)."
    err "Installe Python >= 3.10 et ajoute-le au PATH."
    exit 1
fi

PYTHON_VER="$("$PYTHON_BIN" --version 2>&1)"

# ── Étape 1 — Environnement et dépendances ───────────────────────────────────
cd "$ROOT_DIR"
step "1/6" "Environnement et dépendances"
ok "Exécutable : $PYTHON_BIN  ($PYTHON_VER)"

if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    if [[ -x "$VIRTUAL_ENV/bin/python" ]]; then
        PYTHON_BIN="$VIRTUAL_ENV/bin/python"
    elif [[ -x "$VIRTUAL_ENV/Scripts/python.exe" ]]; then
        PYTHON_BIN="$VIRTUAL_ENV/Scripts/python.exe"
    else
        err "Impossible de trouver Python dans le venv : $VIRTUAL_ENV"
        exit 1
    fi
    ok "Environnement virtuel actif : $VIRTUAL_ENV"

elif [[ -n "${REPL_ID:-}" ]]; then
    ok "Environnement Replit détecté"
    # Sur Replit, les packages sont dans .pythonlibs (déjà dans sys.path)
    # On vérifie si Django est importable ; si non, on tente pip --break-system-packages
    if "$PYTHON_BIN" -c "import django, dotenv, tenants" 2>/dev/null; then
        DJANGO_VER="$("$PYTHON_BIN" -c "import django; print(django.__version__)" 2>/dev/null)"
        ok "Dépendances disponibles (Django $DJANGO_VER)"
    else
        warn "Dépendances manquantes — tentative d'installation..."
        "$PYTHON_BIN" -m pip install -r "$APP_DIR/requirements.txt" \
            --quiet --disable-pip-version-check --break-system-packages 2>/dev/null \
            || "$PYTHON_BIN" -m pip install -r "$APP_DIR/requirements.txt" \
               --quiet --disable-pip-version-check 2>/dev/null \
            || warn "Installation pip impossible — vérifiez les dépendances."
        ok "Tentative d'installation terminée"
    fi

else
    VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
    VENV_CREATED=0

    if [[ -x "$VENV_DIR/bin/python" ]] || [[ -x "$VENV_DIR/Scripts/python.exe" ]]; then
        [[ -x "$VENV_DIR/bin/python"         ]] && PYTHON_BIN="$VENV_DIR/bin/python"
        [[ -x "$VENV_DIR/Scripts/python.exe" ]] && PYTHON_BIN="$VENV_DIR/Scripts/python.exe"
        ok "Environnement virtuel chargé : $VENV_DIR"
    else
        ok "Création de l'environnement virtuel : $VENV_DIR"
        "$PYTHON_BIN" -m venv "$VENV_DIR"
        [[ -x "$VENV_DIR/bin/python"         ]] && PYTHON_BIN="$VENV_DIR/bin/python"
        [[ -x "$VENV_DIR/Scripts/python.exe" ]] && PYTHON_BIN="$VENV_DIR/Scripts/python.exe"
        VENV_CREATED=1
    fi

    REQ_FILE="$APP_DIR/requirements.txt"
    HASH_FILE="$VENV_DIR/.requirements.sha256"
    NEW_HASH="$(sha256sum "$REQ_FILE" 2>/dev/null | awk '{print $1}')"
    OLD_HASH="$( [[ -f "$HASH_FILE" ]] && cat "$HASH_FILE" || echo '' )"

    if [[ "$VENV_CREATED" == "1" || "$NEW_HASH" != "$OLD_HASH" ]]; then
        ok "Installation des dépendances (requirements.txt modifié ou venv neuf)"
        [[ "$VENV_CREATED" == "1" ]] && "$PYTHON_BIN" -m pip install --upgrade pip --quiet
        "$PYTHON_BIN" -m pip install -r "$REQ_FILE" --quiet
        echo "$NEW_HASH" > "$HASH_FILE"
        ok "Dépendances installées"
    else
        ok "Dépendances déjà à jour — installation sautée"
    fi
fi

cd "$APP_DIR"

# ── Étape 2 — Connexion base de données ──────────────────────────────────────
step "2/6" "Connexion à la base de données"

if [[ "${SKIP_DB_CHECK:-0}" == "1" ]]; then
    warn "Vérification DB sautée (SKIP_DB_CHECK=1)"
else
    DB_VENDOR="$("$PYTHON_BIN" manage.py shell -c \
        "from django.db import connection; connection.ensure_connection(); print(connection.vendor)" \
        2>&1)"
    ok "Connexion établie : $DB_VENDOR"
fi

# ── Étape 3 — Migrations ──────────────────────────────────────────────────────
step "3/6" "Migrations"

if [[ -n "${DATABASE_URL:-}" || -n "${DB_HOST:-}" ]]; then
    "$PYTHON_BIN" manage.py migrate_schemas --noinput
    ok "Schémas migrés (mode PostgreSQL multi-tenant)"

    "$PYTHON_BIN" manage.py init_public_tenant
    ok "Tenant public initialisé"
else
    err "PostgreSQL requis : définissez DATABASE_URL ou DB_HOST dans votre fichier .env."
    exit 1
fi

# ── Étape 4 — Données & comptes de test ───────────────────────────────────────
step "4/6" "Données de test (seed)"

if [[ -n "${DATABASE_URL:-}" || -n "${DB_HOST:-}" ]]; then
    if "$PYTHON_BIN" manage.py help seed_test_school >/dev/null 2>&1; then
        "$PYTHON_BIN" manage.py seed_test_school && ok "École de test créée/mise à jour (seed_test_school)"
    fi
    if "$PYTHON_BIN" manage.py help seed_super_admin >/dev/null 2>&1; then
        "$PYTHON_BIN" manage.py seed_super_admin >/dev/null 2>&1 && ok "Super-admin créé/mis à jour"
    fi
else
    err "PostgreSQL requis pour le démarrage : définissez DATABASE_URL ou DB_HOST dans votre fichier .env."
    exit 1
fi

# ── Étape 5 — Fichiers statiques ──────────────────────────────────────────────
step "5/6" "Fichiers statiques"

if [[ "${SKIP_COLLECTSTATIC:-0}" == "1" ]]; then
    warn "Collectstatic sauté (SKIP_COLLECTSTATIC=1)"
else
    STATIC_OUT="$("$PYTHON_BIN" manage.py collectstatic --noinput 2>&1 | tail -1)"
    ok "$STATIC_OUT"
fi

# ── Étape 6 — Démarrage du serveur ───────────────────────────────────────────
step "6/6" "Démarrage du serveur"

printf '\n'
hr
printf '  %sServeur actif sur le port %s%s%s\n' \
    "$C_GREEN$C_BOLD" "$C_WHITE$C_BOLD" "$PORT" "$C_RESET"
hr
printf '\n'

exec "$PYTHON_BIN" manage.py runserver "0.0.0.0:$PORT"
