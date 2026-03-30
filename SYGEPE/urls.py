from django.urls import path
from . import views

app_name = 'sygepe'

urlpatterns = [
    # Authentification
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Racine → déconnecte + login
    path('', views.root_view),

    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),

    # Employés
    path('employes/', views.liste_employes, name='liste_employes'),
    path('employes/ajouter/', views.ajouter_employe, name='ajouter_employe'),
    path('employes/<int:pk>/', views.detail_employe, name='detail_employe'),
    path('employes/<int:pk>/modifier/', views.modifier_employe, name='modifier_employe'),
    path('employes/<int:pk>/supprimer/', views.supprimer_employe, name='supprimer_employe'),
    path('employes/<int:pk>/telecharger/', views.telecharger_profil_employe, name='telecharger_profil_employe'),

    # Présences
    path('presences/', views.liste_presences, name='liste_presences'),
    path('presences/marquer/', views.marquer_presence, name='marquer_presence'),

    # Congés
    path('conges/', views.liste_conges, name='liste_conges'),
    path('conges/demander/', views.demander_conge, name='demander_conge'),
    path('conges/<int:pk>/valider/', views.valider_conge, name='valider_conge'),
    path('conges/<int:pk>/modifier/', views.modifier_conge, name='modifier_conge'),
    path('mes-conges/', views.mes_conges_perso, name='mes_conges_perso'),

    # Absences
    path('absences/', views.liste_absences, name='liste_absences'),
    path('absences/demander/', views.demander_absence, name='demander_absence'),
    path('absences/<int:pk>/valider/', views.valider_absence, name='valider_absence'),
    path('mes-absences/', views.mes_absences_perso, name='mes_absences_perso'),

    # Permissions
    path('permissions/', views.liste_permissions, name='liste_permissions'),
    path('permissions/demander/', views.demander_permission, name='demander_permission'),
    path('permissions/<int:pk>/valider/', views.valider_permission, name='valider_permission'),
    path('mes-permissions/', views.mes_permissions_perso, name='mes_permissions_perso'),

    # Profil
    path('profil/', views.profil, name='profil'),
    path('profil/modifier/', views.modifier_profil_employe, name='modifier_profil_employe'),
    path('profil/modifier-compte/', views.modifier_compte_staff, name='modifier_compte_staff'),
    path('profil/mot-de-passe/', views.changer_mot_de_passe, name='changer_mot_de_passe'),
    path('profil/telecharger/', views.telecharger_profil, name='telecharger_profil'),

    # Rapports
    path('rapports/', views.rapports, name='rapports'),
    path('rapports/presences/', views.rapport_presences, name='rapport_presences'),
    path('rapports/conges/', views.rapport_conges, name='rapport_conges'),
    path('rapports/permissions/', views.rapport_permissions, name='rapport_permissions'),
    path('rapports/rh-complet/', views.rapport_rh_complet, name='rapport_rh_complet'),

    # API
    path('api/notifications/conges/', views.api_notifications_conges, name='api_notifications_conges'),
    path('api/calendrier/events/',    views.api_calendrier_events,    name='api_calendrier_events'),

    # Calendrier
    path('calendrier/', views.calendrier_conges, name='calendrier_conges'),

    # Exports Excel
    path('exports/presences/', views.export_excel_presences,  name='export_excel_presences'),
    path('exports/conges/',    views.export_excel_conges,     name='export_excel_conges'),
    path('exports/permissions/',views.export_excel_permissions,name='export_excel_permissions'),

    # Historique RH
    path('historique/', views.historique_actions, name='historique_actions'),

]
