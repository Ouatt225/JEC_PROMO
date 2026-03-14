# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Développement
python manage.py runserver
python manage.py check --deploy   # vérifie la config (0 erreur attendu)

# Tests
python manage.py test SYGEPE                         # tous les tests
python manage.py test SYGEPE.tests.EmployeViewTest   # une classe
python manage.py test SYGEPE.tests.EmployeViewTest.test_ajouter_employe  # un test seul

# Tests avec couverture (cible ≥ 84%)
python -m coverage run --source=SYGEPE manage.py test SYGEPE --keepdb
python -m coverage report -m

# Base de données
python manage.py migrate
python manage.py makemigrations SYGEPE   # après modification de models.py

# Production
python manage.py collectstatic --no-input
```

## Architecture

```
SYGEPE/
├── views/          # Un module par domaine fonctionnel
│   ├── __init__.py     ← ré-exporte tout pour urls.py
│   ├── decorators.py   ← @rh_requis, @admin_requis, is_rh()
│   ├── auth.py         ← login, logout (POST-only), csrf_failure
│   ├── dashboard.py    ← cache Redis 3 niveaux
│   ├── employes.py / conges.py / permissions.py / presences.py
│   ├── boutiques.py / profil.py / historique.py
│   ├── rapports.py     ← PDF via ReportLab
│   ├── exports.py      ← Excel via openpyxl
│   └── api.py          ← endpoints JSON (FullCalendar, notifications)
├── services/
│   ├── audit.py        ← log_action(request, action, description, employe)
│   ├── excel.py        ← construire_classeur(), wb_vers_response()
│   └── pdf.py          ← helpers ReportLab
├── models.py       ← Employe, Conge, Permission, Presence, Boutique, ActionLog
├── forms.py        ← validation métier (quota congés, chevauchements, photo)
└── tests.py        ← 152 tests, factory_boy, couverture 84%
```

## Patterns essentiels

### Contrôle d'accès
```python
@rh_requis        # accès Admin + RH + DAF → lève PermissionDenied (403)
@admin_requis     # accès Admin uniquement
@login_required   # authentification seule

is_rh(request.user)   # booléen, utilisable dans les vues sans décorateur
```
Les groupes Django s'appellent exactement `'Admin'`, `'RH'`, `'DAF'`, `'Employé'`.
`_groupes_utilisateur(user)` met en cache les groupes sur l'objet user pour la durée de la requête.

### Cache
`DEBUG=True` → `LocMemCache` (pas besoin de Redis local).
`DEBUG=False` → `RedisCache` sur `REDIS_URL`.
Le dashboard utilise 3 clés Redis préfixées `sygepe:` avec TTL distincts (stats 5 min, graphiques/alertes 1 h).

### Vues d'écriture avec audit trail
Toute opération `save()` + `log_action()` doit être dans `transaction.atomic()` :
```python
with transaction.atomic():
    obj.save()
    log_action(request, 'action_key', "description", employe=employe)
```

### Logout
`logout_view` n'accepte que POST. Les templates utilisent `<form method="post">` + `{% csrf_token %}` au lieu d'un `<a href>`.

### Accès dual (RH vs Employé)
`liste_conges` et `liste_permissions` servent deux audiences : RH voit tout, l'employé ne voit que ses propres données + un template différent. Vérifier `is_rh(request.user)` en début de vue.

### Tests
- Factories dans `tests.py` : `EmployeFactory`, `CongeFactory`, `PermissionFactory`, etc.
- Pour tout test qui POST vers `/login/`, appliquer `@override_settings(CACHES=_LOCMEM_CACHE)` sur la classe pour éviter la dépendance Redis (`_LOCMEM_CACHE` est défini en tête de `tests.py`).
- `--keepdb` pour réutiliser la base de test PostgreSQL et accélérer les relances.

## Configuration (.env)

Variables obligatoires : `SECRET_KEY`, `DB_PASSWORD`.
Variables optionnelles avec défaut : `DEBUG=False`, `DB_NAME=sygepe_db`, `DB_USER=postgres`, `DB_HOST=localhost`, `DB_PORT=5432`, `REDIS_URL=redis://127.0.0.1:6379/1`, `ALLOWED_HOSTS=localhost,127.0.0.1`.

Règles métier configurables dans `settings.py` : `QUOTA_CONGES_ANNUELS=30`, `AGE_RETRAITE=60`, `LOGIN_RATE_LIMIT='5/m'`.

## Modèles — points clés

- `Employe.save()` synchronise automatiquement les groupes Django à chaque sauvegarde.
- `Employe.jours_conge_pris(annee, exclude_pk=None)` calcule le solde congé payé (utilisé dans `CongeForm`).
- `Boutique.nb_employes` est une `@property` qui frappe la DB — ne pas appeler dans une boucle. Dans `liste_boutiques`, utiliser l'annotation `nb_employes_actifs` injectée par le queryset.
- `ActionLog` trace toutes les actions RH. Les clés d'action sont dans `ActionLog.ACTION_CHOICES`.
