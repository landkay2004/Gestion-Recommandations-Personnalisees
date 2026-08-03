#!/usr/bin/env bash
# Script de build Vercel — exécuté depuis la racine du dépôt
set -e

# Se placer dans le dossier de l'application Django
cd "$(dirname "$0")"

pip install -r requirements.txt

# ── Migrations ────────────────────────────────────────────────────────────────
# Applique les migrations sur le schéma public (shared apps : super_admin,
# tenants, onboarding, auth, sessions, etc.).  Les schémas des écoles (tenants)
# sont migrés automatiquement lors du premier accès ou via la tâche de fond.
python manage.py migrate_schemas --shared --noinput
# S'assure que les migrations de l'app super_admin sont appliquées explicitement.
python manage.py migrate super_admin --noinput

# Collecter les fichiers statiques (whitenoise les sert directement)
python manage.py collectstatic --noinput
