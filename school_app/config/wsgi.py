import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# ── Auto-migration au démarrage (Vercel serverless) ──────────────────────────
# Vercel ignore `buildCommand` quand `builds` est présent dans vercel.json.
# On applique donc les migrations du schéma public ici, au démarrage du worker.
# `migrate_schemas --shared` est idempotent : si tout est déjà à jour,
# il revient en < 100 ms sans rien modifier.
try:
    import django
    django.setup()
    from django.core.management import call_command
    call_command("migrate_schemas", "--shared", "--noinput", verbosity=0)
except Exception as _mig_err:
    import sys as _sys
    print(f"[wsgi] migration warning: {_mig_err}", file=_sys.stderr)

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
