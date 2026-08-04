"""
Point d'entrée WSGI pour Vercel (serverless).
Vercel détecte automatiquement la variable `app` comme handler WSGI.
"""
import sys
import os
from pathlib import Path

# Ajouter school_app/ au chemin Python pour que `config.settings` soit trouvable
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / 'school_app'))

# Variables d'environnement par défaut (surchargeables dans Vercel Dashboard)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ.setdefault('DJANGO_DEBUG', 'False')

from config.wsgi import application  # noqa: E402

# Vercel cherche `app` comme point d'entrée WSGI
app = application
