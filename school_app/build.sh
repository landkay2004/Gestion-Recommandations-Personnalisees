#!/usr/bin/env bash
# Script de build Vercel — exécuté depuis la racine du dépôt
set -e

# Se placer dans le dossier de l'application Django
cd "$(dirname "$0")"

pip install -r requirements.txt

# Collecter les fichiers statiques (whitenoise les sert directement)
python manage.py collectstatic --noinput
