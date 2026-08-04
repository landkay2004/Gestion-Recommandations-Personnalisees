import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

# ── Auto-migration au démarrage du worker serverless ─────────────────────────
# Fallback si DATABASE_URL n'était pas disponible pendant le build Vercel.
# `migrate_schemas --shared` est idempotent : < 200 ms si déjà à jour.
try:
    from django.core.management import call_command
    print("[wsgi] Vérification des migrations (schéma public)...", file=sys.stderr)
    call_command("migrate_schemas", "--shared", "--noinput", verbosity=1)
    print("[wsgi] Migrations OK", file=sys.stderr)
except Exception as _mig_err:
    print(f"[wsgi] Avertissement migration : {_mig_err}", file=sys.stderr)
