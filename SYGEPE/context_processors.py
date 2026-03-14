"""Context processors SYGEPE — injectés dans tous les templates."""

from .views.decorators import is_responsable, is_rh


def roles_utilisateur(request):
    """Expose is_rh_user et is_responsable_user dans tous les templates."""
    if not request.user.is_authenticated:
        return {'is_rh_user': False, 'is_responsable_user': False}
    return {
        'is_rh_user': is_rh(request.user),
        'is_responsable_user': is_responsable(request.user),
    }
