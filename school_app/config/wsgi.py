import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# ── Auto-migration au démarrage du worker serverless ─────────────────────────
# Fallback si DATABASE_URL n'était pas disponible pendant le build Vercel.
# `migrate_schemas --shared` est idempotent : < 200 ms si déjà à jour.
try:
    import django
    django.setup()
    from django.core.management import call_command
    import sys as _sys
    print("[wsgi] Vérification des migrations (schéma public)...", file=_sys.stderr)
    call_command("migrate_schemas", "--shared", "--noinput", verbosity=1)
    print("[wsgi] Migrations OK", file=_sys.stderr)
except Exception as _mig_err:
    import sys as _sys
    print(f"[wsgi] Avertissement migration : {_mig_err}", file=_sys.stderr)

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
