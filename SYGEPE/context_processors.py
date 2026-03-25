"""Context processors SYGEPE — injectés dans tous les templates."""

from .views.decorators import get_departement_responsable, is_responsable, is_rh


def roles_utilisateur(request):
    """Expose is_rh_user, is_responsable_user et permissions_en_attente_count dans tous les templates."""
    if not request.user.is_authenticated:
        return {'is_rh_user': False, 'is_responsable_user': False, 'permissions_en_attente_count': 0}

    rh = is_rh(request.user)
    resp = is_responsable(request.user)

    # Badge "Permissions en attente" : nombre de permissions à valider par cet utilisateur
    perm_count = 0
    if rh or resp:
        from .models import Permission
        qs = Permission.objects.filter(statut='en_attente')
        if resp and not rh:
            # Responsable de département : filtre sur son département uniquement
            dept = get_departement_responsable(request.user)
            qs = qs.filter(employe__departement=dept) if dept else Permission.objects.none()
        perm_count = qs.count()

    return {
        'is_rh_user': rh,
        'is_responsable_user': resp,
        'permissions_en_attente_count': perm_count,
    }
