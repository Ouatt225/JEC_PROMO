"""Décorateurs de contrôle d'accès par rôle SYGEPE."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator

ITEMS_PAR_PAGE = 20


def paginer(qs, request, par_page=ITEMS_PAR_PAGE):
    """Pagine un queryset. Retourne (page_obj, page_range).

    page_obj est itérable et truthy si la page a des éléments.
    page_range inclut des ellipsis ('…') pour la navigation multi-pages.
    """
    paginator = Paginator(qs, par_page)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    page_range = paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1)
    return page_obj, page_range


def get_params(request):
    """Retourne les paramètres GET sans 'page', encodés pour les liens de pagination."""
    params = request.GET.copy()
    params.pop('page', None)
    return params.urlencode()


def get_employe_or_none(user):
    """Retourne l'Employe lié à user, ou None s'il n'en a pas.
    Évite de dupliquer le try/except Employe.DoesNotExist dans les vues.
    """
    try:
        return user.employe
    except AttributeError:
        return None

# Rôles responsables de département → nom exact du département en base
ROLE_VERS_DEPARTEMENT = {
    'dir_commercial':  'Commercial',
    'resp_logistique': 'Logistique',
    'resp_reabo':      'Réabo',
    'chef_comptable':  'Comptabilité',
}

# Département → qui fait la 1ère validation des permissions
# ('role', '<valeur>') = champ role de l'Employe
# ('group', '<nom>')   = groupe Django
DEPT_PREMIER_VALIDEUR = {
    'Commercial':   ('role',  'dir_commercial'),
    'Logistique':   ('role',  'resp_logistique'),
    'Réabo':        ('role',  'resp_reabo'),
    'Comptabilité': ('role',  'chef_comptable'),
    'Finance':      ('group', 'DAF'),
}


def _groupes_utilisateur(user):
    """Retourne les groupes de l'utilisateur (mis en cache sur l'objet pour la requête)."""
    if not hasattr(user, '_group_names_cache'):
        user._group_names_cache = set(user.groups.values_list('name', flat=True))
    return user._group_names_cache


def is_admin(user):
    return user.is_superuser or 'Admin' in _groupes_utilisateur(user)


def is_rh(user):
    return user.is_superuser or bool(_groupes_utilisateur(user) & {'Admin', 'RH', 'DAF'})


def is_responsable(user):
    """True si l'utilisateur est responsable d'un département (accès limité à son dept)."""
    try:
        return user.employe.role in ROLE_VERS_DEPARTEMENT
    except AttributeError:
        return False


def get_departement_responsable(user):
    """Retourne le Departement lié au rôle du responsable, ou None."""
    try:
        from ..models import Departement
        dept_nom = ROLE_VERS_DEPARTEMENT.get(user.employe.role)
        if dept_nom:
            return Departement.objects.filter(nom=dept_nom).first()
    except AttributeError:
        pass
    return None


def peut_faire_premiere_validation(user, employe):
    """True si user est le premier valideur désigné pour le département de l'employé."""
    if not employe or not employe.departement:
        return False
    mapping = DEPT_PREMIER_VALIDEUR.get(employe.departement.nom)
    if not mapping:
        return False
    typ, val = mapping
    if typ == 'role':
        try:
            return user.employe.role == val
        except AttributeError:
            return False
    elif typ == 'group':
        return val in _groupes_utilisateur(user)
    return False


def dept_a_premier_valideur(employe):
    """True si le département de l'employé a un 1er valideur désigné."""
    if not employe or not employe.departement:
        return False
    return employe.departement.nom in DEPT_PREMIER_VALIDEUR


def peut_valider_pour(user, employe):
    """Règle croisée RH ↔ DAF pour validation des congés/permissions du staff.

    - Demande d'un RH  → seuls DAF ou Admin peuvent valider (pas un autre RH)
    - Demande d'un DAF → seuls RH  ou Admin peuvent valider (pas un autre DAF)
    - Sinon            → tout staff (is_rh) peut valider
    """
    if not employe:
        return is_rh(user)
    groupes = _groupes_utilisateur(user)
    role = employe.role
    if role == 'rh':
        return 'DAF' in groupes or user.is_superuser or 'Admin' in groupes
    if role == 'daf':
        return 'RH' in groupes or user.is_superuser or 'Admin' in groupes
    return is_rh(user)


def rh_requis(f):
    """Décorateur : accès réservé aux rôles RH et Admin. Lève 403 si refusé."""
    @wraps(f)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not is_rh(request.user):
            raise PermissionDenied
        return f(request, *args, **kwargs)
    return wrapper


def admin_requis(f):
    """Décorateur : accès réservé aux Admins uniquement. Lève 403 si refusé."""
    @wraps(f)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not is_admin(request.user):
            raise PermissionDenied
        return f(request, *args, **kwargs)
    return wrapper


def rh_ou_responsable_requis(f):
    """Décorateur : accès RH/Admin (vue complète) OU responsable de département (vue filtrée)."""
    @wraps(f)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not (is_rh(request.user) or is_responsable(request.user)):
            raise PermissionDenied
        return f(request, *args, **kwargs)
    return wrapper
