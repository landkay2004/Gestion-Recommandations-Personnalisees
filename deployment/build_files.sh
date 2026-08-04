#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Script de build Vercel pour EducNet (Django)
# Exécuté par Vercel avant l'empaquetage de la fonction serverless.
# Les dépendances Python sont installées automatiquement par Vercel via
# requirements.txt — ce script s'occupe des étapes Django spécifiques.
# ─────────────────────────────────────────────────────────────────────────────
set -e

cd school_app

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║       EducNet — Build Vercel             ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── [1/2] Migrations du schéma public ────────────────────────────────────────
# Applique les migrations des apps partagées (SHARED_APPS) sur le schéma public.
# Idempotent : si tout est à jour, revient en < 200 ms.
# Nécessite DATABASE_URL ou DB_HOST dans les variables d'environnement Vercel.
if [ -n "${DATABASE_URL:-}" ] || [ -n "${DB_HOST:-}" ]; then
    echo "==> [1/2] Application des migrations (schéma public)"
    python manage.py migrate_schemas --shared --noinput
    echo "    ✓ Migrations appliquées"

    echo "==> [2/2] Chargement des données de test"
    python manage.py seed_test_school
    echo "    ✓ Données de test chargées"
else
    echo "==> [1/2] Migrations ignorées (DATABASE_URL / DB_HOST absent pendant le build)"
    echo "    ℹ Les migrations s'appliqueront au démarrage du worker (wsgi.py)"
fi

echo ""

# ── [3/3] Collecte des fichiers statiques ────────────────────────────────────
# On neutralise CLOUDINARY_URL pendant le build : les fichiers statiques sont
# servis par WhiteNoise (pas Cloudinary), et django-cloudinary-storage 0.3.0
# crashe sur collectstatic en Django 6.0 (utilise le vieux STATICFILES_STORAGE).
echo "==> [3/3] Collecte des fichiers statiques"
CLOUDINARY_URL="" python manage.py collectstatic --noinput --clear
echo "    ✓ Fichiers statiques collectés"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║       Build terminé avec succès ✓        ║"
echo "╚══════════════════════════════════════════╝"
echo ""

cd ..
