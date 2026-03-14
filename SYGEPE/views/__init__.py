"""Package views SYGEPE.

Re-exporte toutes les fonctions-vues afin que urls.py puisse continuer
d'utiliser « from . import views » + « views.ma_vue » sans modification.
"""

from .auth import csrf_failure, login_view, logout_view, root_view
from .dashboard import dashboard
from .employes import (
    ajouter_employe, detail_employe, liste_employes,
    modifier_employe, supprimer_employe,
)
from .presences import liste_presences, marquer_presence
from .conges import demander_conge, liste_conges, valider_conge
from .permissions import (
    demander_permission, liste_permissions, valider_permission,
)
from .profil import (
    changer_mot_de_passe, modifier_profil_employe, profil,
    telecharger_profil, telecharger_profil_employe,
)
from .rapports import (
    rapport_conges, rapport_permissions, rapport_presences,
    rapport_rh_complet, rapports,
)
from .exports import (
    export_excel_conges, export_excel_permissions, export_excel_presences,
)
from .api import api_calendrier_events, api_notifications_conges, calendrier_conges
from .historique import historique_actions

__all__ = [
    # auth
    'csrf_failure', 'root_view', 'login_view', 'logout_view',
    # dashboard
    'dashboard',
    # employes
    'liste_employes', 'detail_employe', 'ajouter_employe',
    'modifier_employe', 'supprimer_employe',
    # presences
    'liste_presences', 'marquer_presence',
    # conges
    'liste_conges', 'demander_conge', 'valider_conge',
    # permissions
    'liste_permissions', 'demander_permission', 'valider_permission',
    # profil
    'profil', 'modifier_profil_employe', 'changer_mot_de_passe',
    'telecharger_profil', 'telecharger_profil_employe',
    # rapports
    'rapports', 'rapport_presences', 'rapport_conges',
    'rapport_permissions', 'rapport_rh_complet',
    # exports
    'export_excel_presences', 'export_excel_conges', 'export_excel_permissions',
    # api
    'api_notifications_conges', 'api_calendrier_events', 'calendrier_conges',
    # historique
    'historique_actions',
]
