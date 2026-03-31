"""Context processors SYGEPE — injectés dans tous les templates."""

from .views.decorators import get_departement_responsable, is_responsable, is_rh


def roles_utilisateur(request):
    """Expose is_rh_user, is_responsable_user et les badges de la sidebar dans tous les templates."""
    if not request.user.is_authenticated:
        return {
            'is_rh_user': False,
            'is_responsable_user': False,
            'conges_en_attente_count': 0,
            'permissions_en_attente_count': 0,
            'absences_en_attente_count': 0,
        }

    rh   = is_rh(request.user)
    resp = is_responsable(request.user)

    conge_count = perm_count = abs_count = 0
    if rh or resp:
        from .models import Absence, Conge, Permission
        dept = get_departement_responsable(request.user) if (resp and not rh) else None

        conge_qs = Conge.objects.filter(statut='en_attente')
        perm_qs  = Permission.objects.filter(statut='en_attente')
        if dept:
            # Responsable : absences en attente de sa première validation
            abs_qs = Absence.objects.filter(statut='en_attente', employe__departement=dept)
        else:
            # RH/Admin : absences transmises par les responsables (étape 2) + sans responsable
            abs_qs = Absence.objects.filter(statut__in=['en_attente', 'valide_responsable'])

        if dept:
            conge_qs = conge_qs.filter(employe__departement=dept)
            perm_qs  = perm_qs.filter(employe__departement=dept)

        conge_count = conge_qs.count()
        perm_count  = perm_qs.count()
        abs_count   = abs_qs.count()

    return {
        'is_rh_user': rh,
        'is_responsable_user': resp,
        'conges_en_attente_count': conge_count,
        'permissions_en_attente_count': perm_count,
        'absences_en_attente_count': abs_count,
    }
