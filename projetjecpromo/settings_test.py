"""
Settings de test pour CI/CD — aucune infrastructure externe requise.

Usage :
    DJANGO_SETTINGS_MODULE=projetjecpromo.settings_test python manage.py test SYGEPE
    DJANGO_SETTINGS_MODULE=projetjecpromo.settings_test python -m coverage run manage.py test SYGEPE

Différences avec settings.py :
    - SQLite :memory:  → pas de PostgreSQL, pas de credentials
    - LocMemCache      → pas de Redis
    - CSP middleware   → retiré (inutile en test, allège les assertions)
"""

import os

# Fournir les variables d'env obligatoires (config() lève ImproperlyConfigured sans elles)
os.environ.setdefault('SECRET_KEY', 'ci-test-secret-key-not-for-production')
os.environ.setdefault('DB_PASSWORD', 'unused-sqlite-has-no-password')

from projetjecpromo.settings import *  # noqa: E402, F401, F403

# ── Base de données ───────────────────────────────────────────────────────────
# SQLite en mémoire : rapide, isolé, détruit à la fin du processus.
# Pas de --keepdb possible (ni nécessaire) avec :memory:.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# ── Cache ─────────────────────────────────────────────────────────────────────
# LocMemCache : évite la dépendance Redis.
# Équivalent à l'@override_settings(_LOCMEM_CACHE) déjà appliqué sur LoginViewTest.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# ── Middleware ────────────────────────────────────────────────────────────────
# Retirer le middleware CSP : pas utile en test, évite d'avoir à asserter l'en-tête
# dans chaque test qui vérifie les réponses HTTP.
MIDDLEWARE = [m for m in MIDDLEWARE if 'ContentSecurityPolicy' not in m]

# ── Mots de passe ─────────────────────────────────────────────────────────────
# Hasher minimal → tests ~10× plus rapides (pas de bcrypt en test)
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# ── Médias ────────────────────────────────────────────────────────────────────
# Évite d'écrire des fichiers sur disque pendant les tests
DEFAULT_FILE_STORAGE = 'django.core.files.storage.InMemoryStorage'
