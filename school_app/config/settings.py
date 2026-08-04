"""
Configuration Django — Plateforme EducNet (Multi-Tenant)
"""
import sys
from pathlib import Path
import os
from urllib.parse import urlparse
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Python path : toutes les apps dans apps/ ─────────────────────────────────
sys.path.insert(0, str(BASE_DIR / 'apps'))

# ─────────────────────────────────────────────────────────────────────────────
# SÉCURITÉ
# ─────────────────────────────────────────────────────────────────────────────
_raw_secret = os.environ.get('DJANGO_SECRET_KEY', '')
if not _raw_secret:
    import secrets as _secrets
    _raw_secret = _secrets.token_urlsafe(64)
SECRET_KEY = _raw_secret

DEBUG = os.environ.get('DJANGO_DEBUG', 'True').strip().lower() in ('true', '1', 'yes')

# En production, restreindre les hôtes autorisés
_site_url = os.environ.get('DJANGO_SITE_URL', os.environ.get('VERCEL_URL', '')).strip()
if DEBUG:
    ALLOWED_HOSTS = ['*']
else:
    ALLOWED_HOSTS = [
        'localhost', '127.0.0.1',
        '.replit.dev', '.replit.app', '.pythonanywhere.com', '.vercel.app',
        '.koyeb.app', '.koyeb.com',
    ]
    if _site_url:
        from urllib.parse import urlparse as _up
        _h = _up(_site_url).hostname
        if _h:
            ALLOWED_HOSTS.append(_h)

CSRF_TRUSTED_ORIGINS = [
    'https://*.replit.dev',
    'https://*.spock.replit.dev',
    'https://*.replit.app',
    'https://*.pythonanywhere.com',
    'https://*.vercel.app',
    'https://*.koyeb.app',
    'https://*.koyeb.com',
    'http://localhost:8000',
    'http://localhost:8008',
]
if _site_url:
    if not _site_url.startswith(('http://', 'https://')):
        _site_url = 'https://' + _site_url
    CSRF_TRUSTED_ORIGINS.append(_site_url)

# ─────────────────────────────────────────────────────────────────────────────
# APPLICATIONS
# ─────────────────────────────────────────────────────────────────────────────
_USE_TENANTS = os.environ.get('DB_HOST', '') or os.environ.get('DATABASE_URL', '')

# Ces paramètres sont nécessaires dès l'import de TenantMixin/DomainMixin.
TENANT_MODEL       = 'tenants.Ecole'
TENANT_DOMAIN_MODEL = 'tenants.EcoleDomain'
PUBLIC_SCHEMA_NAME = 'public'

if _USE_TENANTS:
    SHARED_APPS = [
        'django_tenants',
        'tenants',
        'super_admin',
        'onboarding',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
    ]
    TENANT_APPS = [
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
        'planning',
        'abonnement',
        'comptable',
    ]
    # Cloudinary est nécessaire pour l'envoi des médias distants
    SHARED_APPS.insert(-1, 'cloudinary')
    SHARED_APPS.insert(-1, 'cloudinary_storage')

    INSTALLED_APPS = list(SHARED_APPS) + TENANT_APPS
    DATABASE_ROUTERS    = ['django_tenants.routers.TenantSyncRouter']
else:
    raise ImproperlyConfigured(
        'PostgreSQL requis : définissez DB_HOST ou DATABASE_URL dans votre fichier .env.'
    )

# ─────────────────────────────────────────────────────────────────────────────
# MIDDLEWARE
# ─────────────────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'config.middleware.SessionTenantMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'config.middleware.SuperAdminAuthMiddleware',
    'accounts.middleware.ForcePasswordChangeMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'config.middleware.OnboardingMiddleware',
    'config.middleware.AbonnementMiddleware',
    'config.middleware.MaintenanceMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

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
                'config.context_processors.school_info_safe',
                'config.context_processors.tenant_context',
                'config.context_processors.platform_settings_ctx',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ─────────────────────────────────────────────────────────────────────────────
# BASE DE DONNÉES
# ─────────────────────────────────────────────────────────────────────────────
_pg_host = os.environ.get('DB_HOST', '')
_db_url  = os.environ.get('DATABASE_URL', '')

if _db_url:
    # DATABASE_URL format: postgres://user:password@host[:port]/dbname
    # The managed Replit database may omit the port and may include query
    # options (for example ?sslmode=disable), so do not parse it with a
    # restrictive regular expression.
    _parsed_db_url = urlparse(_db_url)
    if _parsed_db_url.scheme in ('postgres', 'postgresql') and _parsed_db_url.hostname:
        _engine = 'django_tenants.postgresql_backend' if _USE_TENANTS else 'django.db.backends.postgresql'
        _db_options = {}
        if _parsed_db_url.query:
            from urllib.parse import parse_qs
            _db_options.update({
                key: values[-1]
                for key, values in parse_qs(_parsed_db_url.query).items()
                if values
            })
        _db_options.setdefault('sslmode', os.environ.get('DB_SSLMODE', 'prefer'))
        DATABASES = {
            'default': {
                'ENGINE':   _engine,
                'NAME':     (_parsed_db_url.path or '').lstrip('/'),
                'USER':     _parsed_db_url.username or '',
                'PASSWORD': _parsed_db_url.password or '',
                'HOST':     _parsed_db_url.hostname,
                'PORT':     str(_parsed_db_url.port or os.environ.get('DB_PORT', '5432')),
                'CONN_MAX_AGE': 600,
                'OPTIONS':  _db_options,
            }
        }
    else:
        raise ValueError('DATABASE_URL doit être une URL PostgreSQL valide.')

if _pg_host and not _db_url:
    _engine = 'django_tenants.postgresql_backend' if _USE_TENANTS else 'django.db.backends.postgresql'
    DATABASES = {
        'default': {
            'ENGINE':   _engine,
            'NAME':     os.environ.get('DB_NAME',     'sgn_db'),
            'USER':     os.environ.get('DB_USER',     'postgres'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST':     _pg_host,
            'PORT':     os.environ.get('DB_PORT',     '5432'),
            'CONN_MAX_AGE': 600,
            'OPTIONS':  {'sslmode': os.environ.get('DB_SSLMODE', 'prefer')},
        }
    }

if not _pg_host and not _db_url:
    raise ImproperlyConfigured(
        'Aucune configuration PostgreSQL détectée. ' \
        'Définissez DB_HOST ou DATABASE_URL dans votre fichier .env.'
    )

# ─────────────────────────────────────────────────────────────────────────────
# AUTHENTIFICATION
# ─────────────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = 'accounts.CustomUser'

AUTHENTICATION_BACKENDS = [
    'config.backends.MultiTenantAuthBackend',
    'accounts.backends.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL               = '/login/'
LOGIN_REDIRECT_URL      = '/dashboard/'
LOGOUT_REDIRECT_URL     = '/login/'

# ─────────────────────────────────────────────────────────────────────────────
# I18N
# ─────────────────────────────────────────────────────────────────────────────
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE     = 'Africa/Kinshasa'
USE_I18N      = True
USE_TZ        = True

# ─────────────────────────────────────────────────────────────────────────────
# FICHIERS STATIQUES & MEDIA
# ─────────────────────────────────────────────────────────────────────────────
STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
# ── Stockage des médias ───────────────────────────────────────────────────────
# Priorité : Cloudinary  →  Cloudflare R2 (optionnel)  →  filesystem local (dev)
#
# Cloudinary (production recommandée) — 1 seule variable :
#   CLOUDINARY_URL  →  cloudinary://api_key:api_secret@cloud_name
#   Obtenir depuis : cloudinary.com → Dashboard → "API Environment variable"
#
# Cloudflare R2 (alternative S3-compatible) :
#   R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME,
#   R2_ENDPOINT_URL, R2_PUBLIC_URL
#
# NB : Django 6.0 utilise le dictionnaire STORAGES (plus DEFAULT_FILE_STORAGE).

_CLOUDINARY_URL = os.environ.get('CLOUDINARY_URL', '').strip()
_R2_KEY_ID      = os.environ.get('R2_ACCESS_KEY_ID', '').strip()
_R2_SECRET      = os.environ.get('R2_SECRET_ACCESS_KEY', '').strip()
_R2_BUCKET      = os.environ.get('R2_BUCKET_NAME', '').strip()
_R2_ENDPOINT    = os.environ.get('R2_ENDPOINT_URL', '').strip()
_R2_PUBLIC_URL  = os.environ.get('R2_PUBLIC_URL', '').strip().rstrip('/')

_STATICFILES_STORAGE = {
    'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
}

if _CLOUDINARY_URL:
    # ── Cloudinary via django-cloudinary-storage (production recommandée) ────
    # cloudinary_storage.storage.MediaCloudinaryStorage lit CLOUDINARY_URL
    # automatiquement via le SDK cloudinary.
    import cloudinary
    cloudinary.config(cloudinary_url=_CLOUDINARY_URL)
    STORAGES = {
        'default': {
            'BACKEND': 'cloudinary_storage.storage.MediaCloudinaryStorage',
        },
        'staticfiles': _STATICFILES_STORAGE,
    }
    MEDIA_URL = '/media/'  # Cloudinary retourne des URLs absolues directement

elif _R2_KEY_ID and _R2_BUCKET:
    # ── Cloudflare R2 (S3-compatible) — alternative ───────────────────────────
    STORAGES = {
        'default': {
            'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage',
            'OPTIONS': {
                'access_key': _R2_KEY_ID,
                'secret_key': _R2_SECRET,
                'bucket_name': _R2_BUCKET,
                'endpoint_url': _R2_ENDPOINT,
                'custom_domain': _R2_PUBLIC_URL.replace('https://', '').replace('http://', '') if _R2_PUBLIC_URL else None,
                'default_acl': None,
                'querystring_auth': False,
                'signature_version': 's3v4',
                'file_overwrite': False,
            },
        },
        'staticfiles': _STATICFILES_STORAGE,
    }
    MEDIA_URL = (_R2_PUBLIC_URL + '/') if _R2_PUBLIC_URL else (f'{_R2_ENDPOINT}/{_R2_BUCKET}/')

else:
    # ── Développement local ───────────────────────────────────────────────────
    STORAGES = {
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': _STATICFILES_STORAGE,
    }
    MEDIA_URL = '/media/'

MEDIA_ROOT = BASE_DIR / 'media'


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─────────────────────────────────────────────────────────────────────────────
# SESSIONS
# ─────────────────────────────────────────────────────────────────────────────
SESSION_COOKIE_HTTPONLY         = True
SESSION_COOKIE_SAMESITE         = 'Lax'
SESSION_COOKIE_AGE              = 28800
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_ENGINE                  = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_NAME             = 'sgn_session'
# Cookies sécurisés uniquement en production HTTPS
SESSION_COOKIE_SECURE           = not DEBUG
CSRF_COOKIE_SECURE              = not DEBUG
CSRF_COOKIE_HTTPONLY            = True

# ─────────────────────────────────────────────────────────────────────────────
# EMAIL
# ─────────────────────────────────────────────────────────────────────────────
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'config.email_backend.DynamicEmailBackend'
)
EMAIL_HOST          = os.environ.get('EMAIL_HOST', 'localhost')
EMAIL_PORT          = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS       = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER     = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL  = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@educnet.local')

# ─────────────────────────────────────────────────────────────────────────────
# SÉCURITÉ HTTP
# ─────────────────────────────────────────────────────────────────────────────
SECURE_BROWSER_XSS_FILTER   = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS             = 'SAMEORIGIN'
SECURE_REFERRER_POLICY      = 'strict-origin-when-cross-origin'

# En production : activer HSTS + redirection HTTPS
if not DEBUG:
    SECURE_HSTS_SECONDS        = 31536000   # 1 an
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD        = True
    SECURE_SSL_REDIRECT        = False      # géré par le reverse proxy (Replit/nginx)

# ─────────────────────────────────────────────────────────────────────────────
# CACHE
# ─────────────────────────────────────────────────────────────────────────────
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'sgn-cache',
        'TIMEOUT': 300,
        'OPTIONS': {'MAX_ENTRIES': 1000},
    }
}
MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────────────
IS_SERVERLESS = bool(os.environ.get('VERCEL'))

if not IS_SERVERLESS:
    os.makedirs(BASE_DIR / 'logs', exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '{asctime} [{levelname}] {name}: {message}', 'style': '{'},
        'simple':  {'format': '[{levelname}] {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'simple', 'level': 'WARNING'},
    },
    'loggers': {
        'django.request':  {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        'django.security': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        'sgn':             {'handlers': ['console'], 'level': 'INFO',    'propagate': False},
        'sgn.security':    {'handlers': ['console'], 'level': 'INFO',    'propagate': False},
    },
}

if not IS_SERVERLESS:
    LOGGING['handlers']['file'] = {
        'class': 'logging.handlers.RotatingFileHandler',
        'filename': str(BASE_DIR / 'logs' / 'sgn.log'),
        'maxBytes': 5 * 1024 * 1024,
        'backupCount': 3,
        'formatter': 'verbose',
        'level': 'INFO',
        'encoding': 'utf-8',
    }
    LOGGING['handlers']['security_file'] = {
        'class': 'logging.handlers.RotatingFileHandler',
        'filename': str(BASE_DIR / 'logs' / 'sgn_security.log'),
        'maxBytes': 2 * 1024 * 1024,
        'backupCount': 5,
        'formatter': 'verbose',
        'level': 'INFO',
        'encoding': 'utf-8',
    }
    LOGGING['loggers']['django.request']['handlers'].append('file')
    LOGGING['loggers']['django.security']['handlers'].append('security_file')
    LOGGING['loggers']['sgn']['handlers'].append('file')
    LOGGING['loggers']['sgn.security']['handlers'].append('security_file')