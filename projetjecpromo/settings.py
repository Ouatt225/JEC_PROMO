"""
Django settings for projetjecpromo project.
"""

from pathlib import Path
from decouple import config, Csv


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# ── Clés & mode ──────────────────────────────────────────────────────────────

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)

# En développement : localhost,127.0.0.1
# En production : mettez vos domaines réels dans .env
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())


# ── Applications ─────────────────────────────────────────────────────────────

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'SYGEPE',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'SYGEPE.middleware.ContentSecurityPolicyMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'projetjecpromo.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'SYGEPE.context_processors.roles_utilisateur',
            ],
        },
    },
]

WSGI_APPLICATION = 'projetjecpromo.wsgi.application'


# ── Cache ─────────────────────────────────────────────────────────────────────
# Développement (DEBUG=True)  → LocMemCache  (pas besoin de Redis)
# Production   (DEBUG=False)  → RedisCache   (nécessite pip install redis)

REDIS_URL = config('REDIS_URL', default='redis://127.0.0.1:6379/1')

if DEBUG:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
   }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'socket_connect_timeout': 5,
               'socket_timeout': 5,
           },
            'KEY_PREFIX': 'sygepe',
        }
    }

# Durées de cache du dashboard (en secondes)
CACHE_TTL_DASHBOARD_STATS  = 300    # 5 min  — compteurs temps réel
CACHE_TTL_DASHBOARD_CHARTS = 3600   # 1 h    — graphiques historiques
CACHE_TTL_DASHBOARD_ALERTS = 3600   # 1 h    — alertes anniversaires

# ── Base de données ───────────────────────────────────────────────────────────

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='sygepe_db'),
        'USER': config('DB_USER', default='postgres'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'OPTIONS': {
            'client_encoding': 'UTF8',
        },
        # Base de test isolée — configurable via TEST_DB_NAME dans .env ou CI
        'TEST': {
            'NAME': config('TEST_DB_NAME', default='test_sygepe_db'),
        },
    }
}
# ── Validation des mots de passe ─────────────────────────────────────────────

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ── Internationalisation ─────────────────────────────────────────────────────

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Abidjan'
USE_I18N = True
USE_TZ = True


# ── Fichiers statiques & médias ──────────────────────────────────────────────

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'   # pour collectstatic en production

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ── Authentification ─────────────────────────────────────────────────────────

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/login/'


# ── CSRF ─────────────────────────────────────────────────────────────────────

CSRF_USE_SESSIONS = True
CSRF_FAILURE_VIEW = 'SYGEPE.views.csrf_failure'


# ── Session ──────────────────────────────────────────────────────────────────

SESSION_COOKIE_NAME = 'sygepe_sessionid'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 3600
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = False  # Ne sauvegarde la session que si elle a été modifiée


# ── En-têtes de sécurité (actifs en développement ET production) ─────────────

# Empêche le navigateur de deviner le type MIME (protection contre MIME sniffing)
SECURE_CONTENT_TYPE_NOSNIFF = True

# Active le filtre XSS intégré des navigateurs anciens
SECURE_BROWSER_XSS_FILTER = True

# Interdit à d'autres sites d'intégrer SYGEPE dans un <iframe> (anti-clickjacking)
X_FRAME_OPTIONS = 'DENY'


# ── En-têtes supplémentaires actifs uniquement en PRODUCTION (DEBUG=False) ───

if not DEBUG:
    # Force HTTPS — à n'activer que si votre serveur est en HTTPS
    SECURE_SSL_REDIRECT = True

    # HSTS : dit aux navigateurs de n'utiliser que HTTPS pendant 1 an
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Cookie de session uniquement en HTTPS
    SESSION_COOKIE_SECURE = True

    # Cookie CSRF uniquement en HTTPS
    CSRF_COOKIE_SECURE = True

    # ── Optimisation des fichiers statiques en production ─────────────────────
    # ManifestStaticFilesStorage ajoute un hash dans le nom de chaque fichier
    # (cache-busting) et compresse avec gzip. Nécessite `python manage.py collectstatic`.
    # Pour la minification réelle (CSS/JS), deux options :
    #   Option A — django-compressor : pip install django-compressor
    #              Ajouter 'compressor' à INSTALLED_APPS et {% load compress %}
    #              + {% compress css %}...{% endcompress %} dans les templates.
    #   Option B — Build tool (Vite/esbuild) : minifier en amont, puis collectstatic.
    STATICFILES_STORAGE = 'projetjecpromo.storage.MinifiedManifestStaticFilesStorage'


# ── E-mail ────────────────────────────────────────────────────────────────────
# Développement (DEBUG=True)  → console (affiche l'e-mail dans le terminal)
# Production   (DEBUG=False)  → SMTP (configurer EMAIL_HOST_USER/PASSWORD dans .env)

EMAIL_BACKEND = (
    'django.core.mail.backends.console.EmailBackend'
    if DEBUG else
    'django.core.mail.backends.smtp.EmailBackend'
)
EMAIL_HOST          = config('EMAIL_HOST',          default='smtp.gmail.com')
EMAIL_PORT          = config('EMAIL_PORT',          default=587, cast=int)
EMAIL_USE_TLS       = config('EMAIL_USE_TLS',       default=True, cast=bool)
EMAIL_HOST_USER     = config('EMAIL_HOST_USER',     default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL  = config('DEFAULT_FROM_EMAIL',  default='SYGEPE <noreply@sygepe.ci>')


# ── Règles métier RH ─────────────────────────────────────────────────────────

# Nombre maximum de tentatives de connexion par IP par minute
LOGIN_RATE_LIMIT = '5/m'

# Cache utilisé par django-ratelimit (doit pointer sur le même backend Redis)
RATELIMIT_USE_CACHE = 'default'

# Nombre maximum de lignes exportées en un seul fichier Excel/PDF
# Au-delà, la vue renvoie HTTP 400 plutôt que de laisser le worker Gunicorn timeout.
EXPORT_MAX_ROWS = 5_000

# Nombre de jours de congé payé annuel autorisé par employé
QUOTA_CONGES_ANNUELS = 30

# Âge légal de départ à la retraite (en années)
AGE_RETRAITE = 60


# ── Divers ───────────────────────────────────────────────────────────────────

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
