# SYGEPE — Système de Gestion du Personnel

Application web Django de gestion RH pour JEC PROMO : employés, congés, permissions,
présences, boutiques, rapports PDF/Excel et tableau de bord analytique.

---

## Table des matières

1. [Prérequis](#prérequis)
2. [Installation locale (développement)](#installation-locale)
3. [Déploiement Docker (production)](#déploiement-docker)
4. [Configuration — variables d'environnement](#configuration)
5. [Données de démonstration](#données-de-démonstration)
6. [Rôles utilisateurs](#rôles-utilisateurs)
7. [Flux de validation](#flux-de-validation)
8. [Tests](#tests)
9. [Architecture](#architecture)
10. [Endpoints JSON (API interne)](#endpoints-json)
11. [Règles métier](#règles-métier)
12. [Dépendances principales](#dépendances-principales)
13. [Dépannage](#dépannage)

---

## Prérequis

| Outil      | Version minimale | Notes                                        |
|------------|-----------------|----------------------------------------------|
| Python     | 3.11            | Testé avec 3.13                              |
| PostgreSQL | 14              | Base de données principale                   |
| Redis      | 6               | Cache dashboard (3 niveaux) + rate-limit login |

> **Développement sans Redis** : `DEBUG=True` bascule automatiquement sur
> `LocMemCache` — aucune configuration Redis requise.

---

## Installation locale

```bash
# 1. Cloner le dépôt
git clone <url-du-depot>
cd projetjecpromo

# 2. Créer et activer l'environnement virtuel
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows

# 3. Installer les dépendances
pip install -r requirements.txt
pip install -r requirements-dev.txt   # outils de test (coverage, factory_boy)

# 4. Configurer l'environnement
cp .env.example .env
# → Éditer .env : renseigner SECRET_KEY et DB_PASSWORD au minimum

# 5. Créer la base de données PostgreSQL
psql -U postgres -c "CREATE DATABASE sygepe_db;"

# 6. Appliquer les migrations
python manage.py migrate

# 7. Créer les groupes de rôles (obligatoire)
python manage.py shell -c "
from django.contrib.auth.models import Group
for g in ['Admin', 'RH', 'DAF', 'Employé']:
    Group.objects.get_or_create(name=g)
print('Groupes créés.')
"

# 8. Créer un super-utilisateur
python manage.py createsuperuser

# 9. Lancer le serveur
python manage.py runserver
```

L'application est accessible sur **http://127.0.0.1:8000/**.

---

## Déploiement Docker

Le `Dockerfile` utilise un **build multi-stage** (builder + image finale minimale)
avec un utilisateur non-root et un health-check intégré.

### Lancement simple

```bash
# Construire l'image
docker build -t sygepe .

# Lancer avec les variables d'environnement depuis .env
docker run --env-file .env -p 8000:8000 sygepe
```

Au démarrage, le conteneur exécute automatiquement :
1. `collectstatic --noinput`
2. `migrate --noinput`
3. Gunicorn sur `0.0.0.0:8000` (4 workers, timeout 120 s)

### Variables obligatoires en production

```dotenv
SECRET_KEY=<valeur-longue-aléatoire>
DB_PASSWORD=<mot-de-passe-postgres>
ALLOWED_HOSTS=votre-domaine.com
DEBUG=False
REDIS_URL=redis://redis:6379/1
```

### Exemple docker-compose (PostgreSQL + Redis + SYGEPE)

```yaml
version: "3.9"
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: sygepe_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine

  web:
    build: .
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis
    volumes:
      - media_files:/app/media
      - static_files:/app/staticfiles

volumes:
  postgres_data:
  media_files:
  static_files:
```

> **Nginx** : pointer `location /static/` vers le volume `static_files`
> et `location /media/` vers le volume `media_files`.

---

## Configuration

Copier `.env.example` vers `.env` et renseigner les valeurs :

```dotenv
# ── Obligatoire ──────────────────────────────────────────────────────────────

# Générer avec :
# python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
SECRET_KEY=changez-moi

DB_PASSWORD=changez-moi

# ── Optionnel (valeurs par défaut indiquées) ─────────────────────────────────

DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=sygepe_db
DB_USER=postgres
DB_HOST=localhost
DB_PORT=5432

REDIS_URL=redis://127.0.0.1:6379/1
```

> **Sécurité** : le fichier `.env` est exclu par `.gitignore` — ne jamais le committer.

---

## Données de démonstration

Pour peupler rapidement la base avec des données réalistes :

```bash
python manage.py seed_data
```

Crée automatiquement :
- Les 4 groupes de rôles (`Admin`, `RH`, `DAF`, `Employé`)
- Un super-utilisateur `admin` / `admin123`
- 5 départements (Commercial, Logistique, Réabo, Comptabilité, Finance)
- ~20 employés avec postes et contrats variés
- 30 jours de présences historiques
- Des demandes de congé et permission en différents statuts

> **Usage** : développement et démonstration uniquement.
> Ne jamais exécuter en production sur une base contenant des données réelles.

---

## Rôles utilisateurs

| Groupe Django | Droits d'accès                                                       |
|---------------|----------------------------------------------------------------------|
| **Admin**     | Accès complet — CRUD employés, suppression, toutes les vues RH       |
| **RH**        | Gestion congés/permissions/présences, rapports, calendrier, exports  |
| **DAF**       | Mêmes droits que RH (accès aux données financières RH)               |
| **Employé**   | Espace personnel : profil, ses congés, ses permissions uniquement    |

Les groupes sont créés lors de l'installation ou via `seed_data`.
L'attribution des rôles se fait depuis `/admin/` → Utilisateurs → Groupes.

### Responsables de département

Certains employés ont un **rôle métier** (`role` sur le modèle `Employe`) qui leur
donne un accès limité à leur département :

| Rôle              | Département géré |
|-------------------|-----------------|
| `dir_commercial`  | Commercial       |
| `resp_logistique` | Logistique       |
| `resp_reabo`      | Réabo            |
| `chef_comptable`  | Comptabilité     |

---

## Flux de validation

### Congés (1 étape)

```
Employé soumet → En attente → RH approuve / refuse
```

### Permissions (2 étapes selon le département)

```
Employé soumet → En attente
    ├── Département avec responsable désigné :
    │       Responsable valide (étape 1) → Validé par responsable
    │                                            └── RH approuve / refuse (étape 2)
    └── Département sans responsable :
            RH approuve / refuse directement (1 seule étape)
```

Les droits de validation sont calculés dynamiquement à chaque affichage de liste,
en itérant uniquement sur la page courante (optimisation pagination).

---

## Tests

```bash
# Suite complète
python manage.py test SYGEPE --keepdb

# Une classe
python manage.py test SYGEPE.tests.CongeFormTest --keepdb

# Un test précis
python manage.py test SYGEPE.tests.CongeFormTest.test_type_maternite_pas_de_quota --keepdb

# Avec couverture (cible >= 84 %)
python -m coverage run --source=SYGEPE manage.py test SYGEPE --keepdb
python -m coverage report -m
python -m coverage html        # rapport HTML dans htmlcov/
```

**État actuel** : 152 tests, 0 échec, couverture ~84 %.

`--keepdb` réutilise la base de test PostgreSQL existante et divise par ~3
le temps d'exécution sur les lancements suivants.

---

## Architecture

```
projetjecpromo/
├── SYGEPE/
│   ├── views/                  # Un module par domaine fonctionnel
│   │   ├── __init__.py         # Ré-exporte tout pour urls.py
│   │   ├── decorators.py       # @rh_requis, @admin_requis, paginer(), is_rh()
│   │   ├── auth.py             # Login / logout (POST uniquement pour logout)
│   │   ├── dashboard.py        # Cache Redis 3 niveaux (5 min / 1 h)
│   │   ├── employes.py         # CRUD employés
│   │   ├── conges.py           # Gestion des congés
│   │   ├── permissions.py      # Permissions (validation 2 étapes)
│   │   ├── presences.py        # Suivi des présences
│   │   ├── boutiques.py        # Gestion des boutiques
│   │   ├── profil.py           # Espace employé (profil, mot de passe)
│   │   ├── historique.py       # Journal des actions RH
│   │   ├── rapports.py         # Génération PDF (ReportLab)
│   │   ├── exports.py          # Export Excel (openpyxl)
│   │   └── api.py              # Endpoints JSON (FullCalendar, notifications)
│   ├── services/
│   │   ├── audit.py            # log_action() — trace toutes les actions RH
│   │   ├── excel.py            # Helpers openpyxl (styles, construire_classeur)
│   │   └── pdf.py              # Helpers ReportLab (styles, tableaux, profils)
│   ├── models.py               # Employe, Conge, Permission, Presence, Boutique, ActionLog
│   ├── forms.py                # FormClassMixin + validation métier (quota, chevauchement)
│   ├── urls.py                 # Routes (namespace : sygepe)
│   ├── admin.py                # Interface d'administration Django
│   └── tests.py                # 152 tests — factory_boy — couverture 84 %
├── templates/
│   └── SYGEPE/
│       ├── base_root.html      # Squelette HTML commun (ancêtre)
│       ├── base.html           # Base espace RH (thème Soleil d'Harmattan)
│       ├── base_employe.html   # Base espace employé (design navy/vert)
│       └── includes/           # Partials réutilisables
│           ├── pagination.html         # Navigation multi-pages avec ellipsis
│           ├── filter_bar_statut.html  # Barre de filtre par statut
│           ├── empty_state.html        # État vide générique
│           ├── modal_rejet.html        # Modale de rejet avec commentaire
│           └── notifications.html      # Cloche de notifications
├── static/SYGEPE/
│   ├── css/style.css           # Thème Soleil d'Harmattan (espace RH)
│   └── js/main.js
├── projetjecpromo/
│   ├── settings.py             # Configuration (python-decouple)
│   └── urls.py                 # URLs racine + handler403/500
├── Dockerfile                  # Build multi-stage production
├── .env.example
├── requirements.txt            # Dépendances production (versions épinglées)
├── requirements-dev.txt        # Dépendances développement
└── manage.py
```

### Patterns essentiels

**Contrôle d'accès**
```python
@rh_requis        # Admin + RH + DAF → lève PermissionDenied (403)
@admin_requis     # Admin uniquement
@login_required   # Authentification seule

is_rh(request.user)   # Booléen utilisable en milieu de vue
```

**Audit trail — toujours dans une transaction**
```python
with transaction.atomic():
    obj.save()
    log_action(request, 'clé_action', "Description lisible", employe=employe)
```

**Pagination**
```python
from .decorators import paginer, get_params

qs, page_range = paginer(qs, request, par_page=20)
context = {
    'objets':     qs,           # Page object — itérable directement
    'page_range': page_range,   # Inclut les ellipsis
    'params':     get_params(request),  # Filtres GET préservés
}
```

---

## Endpoints JSON

| URL                              | Accès                     | Description                                    |
|----------------------------------|---------------------------|------------------------------------------------|
| `GET /api/notifications/conges/` | Tout utilisateur connecté | Congés approuvés débutant dans 1 ou 7 jours   |
| `GET /api/calendrier/events/`    | RH / Admin / DAF          | Événements FullCalendar (±3 mois)              |

Authentification par session Django (cookie) — aucun token requis.

---

## Règles métier

| Paramètre              | Valeur par défaut | Réglage dans `settings.py`     |
|------------------------|-------------------|--------------------------------|
| Quota congés annuels   | 30 jours          | `QUOTA_CONGES_ANNUELS`         |
| Âge de départ retraite | 60 ans            | `AGE_RETRAITE`                 |
| Rate-limit login       | 5 tentatives/min  | `LOGIN_RATE_LIMIT`             |
| Durée de session       | 1 heure           | `SESSION_COOKIE_AGE`           |

Règles de validation des congés (appliquées dans `CongeForm.clean()`) :
- Fin ≥ Début
- Pas de chevauchement avec un congé approuvé ou en attente
- Quota annuel non dépassé (sauf congés maladie, maternité, décès)
- Congé maternité réservé aux employées de sexe féminin

---

## Dépendances principales

| Package          | Version | Usage                              |
|------------------|---------|------------------------------------|
| Django           | 5.0     | Framework web                      |
| psycopg          | 3.3     | Pilote PostgreSQL                  |
| python-decouple  | 3.8     | Configuration via `.env`           |
| openpyxl         | 3.1     | Export Excel (.xlsx)               |
| reportlab        | 4.4     | Génération PDF                     |
| Pillow           | 12.1    | Photos employés (ImageField + PDF) |
| django-ratelimit | 4.1     | Rate-limiting sur `/login/`        |
| gunicorn         | 22.0    | Serveur WSGI production            |
| factory_boy      | 3.3     | Fixtures de tests                  |
| coverage         | 7.x     | Mesure de couverture               |

---

## Dépannage

**`python manage.py check --deploy` signale des avertissements**
Vérifier que `.env` contient `DEBUG=False`, `ALLOWED_HOSTS` avec le domaine réel,
et que PostgreSQL + Redis sont accessibles.

**`OperationalError: could not connect to server`**
PostgreSQL n'est pas démarré ou les paramètres `DB_HOST` / `DB_PORT` / `DB_PASSWORD`
dans `.env` sont incorrects.

**`ConnectionError: Error 111 connecting to localhost:6379`**
Redis n'est pas démarré. En développement, passer `DEBUG=True` dans `.env` pour
utiliser le cache mémoire local (LocMemCache — pas de Redis requis).

**La page 403 affiche le design Django par défaut**
Vérifier que `templates/403.html` existe et que `DIRS` dans `settings.py` pointe
vers le dossier `templates/` racine du projet.

**Les photos d'employés ne s'affichent pas en production**
Le dossier `media/` doit être servi par Nginx (ou un stockage S3).
En développement, `DEBUG=True` sert automatiquement les médias.

**`UnorderedObjectListWarning` à la pagination**
Ajouter `.order_by(...)` au queryset avant de le passer à `paginer()`.

**Les tests échouent avec `KeyError: 'default'` sur Redis**
Utiliser le décorateur `@override_settings(CACHES=_LOCMEM_CACHE)` sur la classe
de test concernée (voir en-tête de `tests.py` pour la définition de `_LOCMEM_CACHE`).
