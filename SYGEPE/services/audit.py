"""Service d'audit : enregistrement des actions RH dans ActionLog."""

from ..models import ActionLog


def log_action(request, action, description, employe=None):
    """Enregistre une action dans l'historique RH."""
    ActionLog.objects.create(
        utilisateur=request.user,
        action=action,
        description=description,
        employe=employe,
    )
