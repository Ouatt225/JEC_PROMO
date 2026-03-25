"""Service d'envoi d'e-mails de notification SYGEPE.

Déclenché lors des changements de statut des congés et permissions.
En développement (DEBUG=True) → console backend (pas d'envoi réel).
En production → SMTP configuré via les variables .env EMAIL_*.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

_STATUT_LABELS_CONGE = {
    'approuve':  'approuvée',
    'refuse':    'refusée',
}

_STATUT_LABELS_PERM = {
    'valide_responsable': 'transmise à la DRH pour approbation finale',
    'approuve':           'approuvée',
    'refuse':             'refusée',
}


def _email_employe(employe):
    """Retourne l'e-mail de l'employé (fiche > compte Django > None)."""
    if getattr(employe, 'email', ''):
        return employe.email
    try:
        return employe.user.email or None
    except Exception:
        return None


def _envoyer(to, sujet, corps):
    """Envoie un e-mail en absorbant toute erreur (log warning)."""
    try:
        send_mail(
            subject=sujet,
            message=corps,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to],
            fail_silently=False,
        )
    except Exception as exc:
        logger.warning("SYGEPE — e-mail non envoyé à %s : %s", to, exc)


def notifier_statut_conge(conge):
    """Notifie l'employé d'un changement de statut sur son congé.

    Appelé après valider_conge() pour les statuts finaux (approuve/refuse).
    """
    email = _email_employe(conge.employe)
    if not email:
        return

    statut_label = _STATUT_LABELS_CONGE.get(conge.statut)
    if not statut_label:
        return  # statut non notifiable (en_attente, etc.)

    sujet = f"[SYGEPE] Votre demande de congé a été {statut_label}"
    corps = (
        f"Bonjour {conge.employe.get_full_name()},\n\n"
        f"Votre demande de congé ({conge.get_type_conge_display()}) "
        f"du {conge.date_debut.strftime('%d/%m/%Y')} au {conge.date_fin.strftime('%d/%m/%Y')} "
        f"a été {statut_label}.\n\n"
        f"Connectez-vous sur SYGEPE pour consulter les détails.\n\n"
        f"Cordialement,\nL'équipe RH"
    )
    _envoyer(email, sujet, corps)


def notifier_statut_permission(perm):
    """Notifie l'employé d'un changement de statut sur sa permission.

    Appelé après valider_permission() pour tous les statuts (étape 1 et 2).
    """
    email = _email_employe(perm.employe)
    if not email:
        return

    statut_label = _STATUT_LABELS_PERM.get(perm.statut)
    if not statut_label:
        return

    sujet = f"[SYGEPE] Votre demande de permission a été {statut_label}"
    corps = (
        f"Bonjour {perm.employe.get_full_name()},\n\n"
        f"Votre demande de permission "
        f"du {perm.date_debut.strftime('%d/%m/%Y')} au {perm.date_fin.strftime('%d/%m/%Y')} "
        f"a été {statut_label}.\n\n"
        f"Connectez-vous sur SYGEPE pour consulter les détails.\n\n"
        f"Cordialement,\nL'équipe RH"
    )
    _envoyer(email, sujet, corps)
