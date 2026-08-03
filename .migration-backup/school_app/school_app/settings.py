from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# En production : définir la variable d'environnement DJANGO_SECRET_KEY
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-rdcschool-2024-secret-key-change-in-production'
)

DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

ALLOWED_HOSTS = ['*']

# CSRF : domaines autorisés
_site_url = os.environ.get('DJANGO_SITE_URL', '').strip()

CSRF_TRUSTED_ORIGINS = [
    'https://*.replit.dev',
    'https://*.spock.replit.dev',
    'https://*.replit.app',
    'https://*.pythonanywhere.com',
    'http://localhost:8000',
    'http://localhost:8008',
]

if _site_url:
    if not _site_url.startswith(('http://', 'https://')):
        _site_url = 'https://' + _site_url
    CSRF_TRUSTED_ORIGINS.append(_site_url)

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'dashboard',
    'students',
    'teachers',
    'subjects',
    'classes',
    'bulletin',
    'grades',
    'reports',
    'school_settings',
    'portail',
    'carte_eleve',
    'notifications',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'accounts.middleware.ForcePasswordChangeMiddleware',   # doit être APRÈS AuthenticationMiddleware
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'school_app.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'school_settings.context_processors.school_info',
                'super_admin.context_processors.platform_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'school_app.wsgi.application'

# ── Configuration de la base de données ──
DB_ENGINE = os.environ.get('DB_ENGINE', 'django.db.backends.sqlite3')

if DB_ENGINE == 'django.db.backends.postgresql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'school_db'),
            'USER': os.environ.get('DB_USER', 'postgres'),
            'PASSWORD': os.environ.get('DB_PASSWORD', 'password'),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
            'CONN_MAX_AGE': 600,
            'OPTIONS': {
                'sslmode': os.environ.get('DB_SSLMODE', 'prefer'),
            },
        }
    }
else:
    # SQLite (par défaut)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            'CONN_MAX_AGE': 60,
            'OPTIONS': {
                'timeout': 20,
            },
        }
    }

AUTH_USER_MODEL = 'accounts.CustomUser'

AUTHENTICATION_BACKENDS = [
    'accounts.backends.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
]

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Kinshasa'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/login/'

MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

# ── Cache (mémoire locale — suffisant pour 1 processus, remplacer par Redis en multi-worker) ──
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'sgn-cache',
        'TIMEOUT': 300,          # 5 minutes par défaut
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
        },
    }
}

# ── Sécurité des sessions ─────────────────────────────────────────────────────
SESSION_COOKIE_HTTPONLY  = True          # JS ne peut pas lire le cookie de session
SESSION_COOKIE_SAMESITE  = 'Lax'        # Protection CSRF renforcée
SESSION_COOKIE_AGE       = 28800        # Expiration après 8 h d'inactivité (en secondes)
SESSION_EXPIRE_AT_BROWSER_CLOSE = False  # Persiste si "Se souvenir de moi" (à implémenter)

# ── En-têtes de sécurité HTTP ─────────────────────────────────────────────────
SECURE_BROWSER_XSS_FILTER    = True   # X-XSS-Protection (vieux navigateurs)
SECURE_CONTENT_TYPE_NOSNIFF  = True   # X-Content-Type-Options: nosniff
X_FRAME_OPTIONS              = 'SAMEORIGIN'  # Autorise les iframes du même domaine (PWA)

# En production (HTTPS), activer ces paramètres :
# SECURE_SSL_REDIRECT         = True
# SECURE_HSTS_SECONDS         = 31536000
# SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# SESSION_COOKIE_SECURE       = True
# CSRF_COOKIE_SECURE          = True

# ── Logging ───────────────────────────────────────────────────────────────────
import os as _os
_os.makedirs(BASE_DIR / 'logs', exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} [{levelname}] {name}: {message}',
            'style': '{',
        },
        'simple': {
            'format': '[{levelname}] {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'level': 'WARNING',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(BASE_DIR / 'logs' / 'sgn.log'),
            'maxBytes': 5 * 1024 * 1024,   # 5 MB par fichier
            'backupCount': 3,
            'formatter': 'verbose',
            'level': 'INFO',
            'encoding': 'utf-8',
        },
        'security_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(BASE_DIR / 'logs' / 'sgn_security.log'),
            'maxBytes': 2 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
            'level': 'INFO',
            'encoding': 'utf-8',
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['file', 'security_file'],
            'level': 'WARNING',
            'propagate': False,
        },
        # Logger applicatif SGN — utilisé avec logging.getLogger('sgn')
        'sgn': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        # Logger sécurité SGN — connexions, déconnexions, actions critiques
        'sgn.security': {
            'handlers': ['console', 'security_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
