#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Script de build Vercel pour EducNet (Django)
# Appelé automatiquement par Vercel à chaque déploiement.
# ─────────────────────────────────────────────────────────────────────────────
set -e

echo "==> [1/3] Installation des dépendances Python"
pip install -r school_app/requirements.txt --quiet

echo "==> [2/3] Application des migrations (schéma public)"
cd school_app
python manage.py migrate_schemas --shared --noinput
cd ..

echo "==> [3/3] Collecte des fichiers statiques"
cd school_app
python manage.py collectstatic --noinput --clear
cd ..

echo "==> Build terminé avec succès ✓"
