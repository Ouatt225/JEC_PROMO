# ══════════════════════════════════════════════════════════════════════════════
# SYGEPE — Dockerfile de production
# Build multi-stage · Python 3.13-slim · Gunicorn WSGI
#
# Construction : docker build -t sygepe .
# Lancement    : docker run --env-file .env -p 8000:8000 sygepe
# ══════════════════════════════════════════════════════════════════════════════


# ── Étape 1 : compilation des dépendances ─────────────────────────────────────
# Utilise les outils de compilation dans une image séparée pour ne pas
# les embarquer dans l'image finale (réduit la taille et la surface d'attaque).
FROM python:3.13-slim AS builder

WORKDIR /build

# Outils système nécessaires pour compiler certaines roues Python
# (nécessaires seulement si une roue binaire pré-compilée n'est pas disponible)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libjpeg-dev \
        libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip --quiet \
 && pip wheel --no-cache-dir --wheel-dir=/dist -r requirements.txt


# ── Étape 2 : image de production minimale ────────────────────────────────────
FROM python:3.13-slim

LABEL maintainer="JEC PROMO <contact@jecpromo.ci>"
LABEL org.opencontainers.image.title="SYGEPE"
LABEL org.opencontainers.image.description="Système de Gestion des Employés — JEC PROMO"

# Variables d'environnement Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=projetjecpromo.settings \
    PORT=8000

WORKDIR /app

# Installer uniquement les roues construites à l'étape précédente
# (aucun outil de compilation requis ici)
COPY --from=builder /dist /dist
COPY requirements.txt .
RUN pip install --no-cache-dir --find-links=/dist -r requirements.txt \
 && rm -rf /dist

# Utilisateur non-root pour réduire la surface d'attaque
RUN useradd --no-create-home --shell /bin/false sygepe

# Copier le code source avec les droits de l'utilisateur applicatif
COPY --chown=sygepe:sygepe . .

USER sygepe

EXPOSE 8000

# Vérification de santé : requête HTTP sur la page de login
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c \
        "import urllib.request, sys; \
         urllib.request.urlopen('http://localhost:8000/login/'); \
         sys.exit(0)" \
        || exit 1

# Démarrage : collectstatic → migrations → Gunicorn
# Les variables SECRET_KEY, DB_PASSWORD, REDIS_URL… doivent être passées
# via --env-file .env ou les variables d'environnement du serveur.
CMD ["sh", "-c", \
     "python manage.py collectstatic --noinput && \
      python manage.py migrate --noinput && \
      exec gunicorn projetjecpromo.wsgi:application \
           --config gunicorn.conf.py"]
