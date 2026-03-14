"""
Vues API JSON — SYGEPE
======================
Ce module expose deux endpoints JSON consommés par le frontend (Fetch API / FullCalendar).
Aucune authentification par token n'est requise : les appels sont faits dans le même contexte
de session Django (cookie de session).

Endpoints disponibles
---------------------
GET /api/notifications/conges/     → api_notifications_conges   (tout utilisateur connecté)
GET /api/calendrier/events/        → api_calendrier_events       (RH / Admin / DAF uniquement)

Voir les schémas de réponse dans les docstrings de chaque vue.
"""

from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from ..models import Conge, Employe, Permission
from .decorators import is_rh, rh_requis


# ── Helpers privés ────────────────────────────────────────────────────────────

def _notif_conge(urgence: str, titre: str, conge, pour_rh: bool = True) -> dict:
    """Construit un dict de notification pour un congé."""
    debut = conge.date_debut.strftime('%d/%m/%Y')
    fin   = conge.date_fin.strftime('%d/%m/%Y')
    if pour_rh:
        message = f"{conge.employe.get_full_name()} — {conge.get_type_conge_display()} du {debut} au {fin}"
    else:
        message = f"{conge.get_type_conge_display()} du {debut} au {fin}"
    return {'urgence': urgence, 'titre': titre, 'message': message}


def _event_dict(prefix: str, obj, titre: str, bg_color: str) -> dict:
    """Construit un dict d'événement FullCalendar pour un congé ou une permission."""
    return {
        'id'             : f'{prefix}-{obj.pk}',
        'title'          : titre,
        'start'          : obj.date_debut.isoformat(),
        'end'            : (obj.date_fin + timedelta(days=1)).isoformat(),
        'backgroundColor': bg_color,
        'borderColor'    : bg_color,
        'extendedProps'  : {
            'type'   : prefix,
            'statut' : obj.get_statut_display(),
            'employe': obj.employe.get_full_name(),
        },
    }


# ── Vues ──────────────────────────────────────────────────────────────────────

@login_required
def api_notifications_conges(request):
    """Retourne les congés approuvés débutant dans 7 jours ou demain.

    Endpoint
    --------
    GET /api/notifications/conges/

    Accès
    -----
    Tout utilisateur connecté (session Django requise).
    - RH / Admin / DAF → toutes les notifications de tous les employés
    - Employé           → uniquement ses propres congés

    Paramètres
    ----------
    Aucun paramètre de requête.

    Réponse (200 OK)
    ----------------
    {
        "notifications": [
            {
                "urgence" : "warning" | "danger",
                "titre"   : str,   // ex. "Congé dans 7 jours"
                "message" : str    // ex. "Jean Dupont — Congé payé du 10/03/2026 au 14/03/2026"
            },
            ...
        ]
    }

    Réponse (302)
    -------------
    Redirige vers /login/ si l'utilisateur n'est pas authentifié.

    Exemples de valeurs "urgence"
    -----------------------------
    - "warning" : congé dans exactement 7 jours (J+7)
    - "danger"  : congé commence demain        (J+1)
    """
    today  = date.today()
    j7     = today + timedelta(days=7)
    veille = today + timedelta(days=1)

    notifications = []

    if is_rh(request.user):
        for c in Conge.objects.filter(statut='approuve', date_debut=j7).select_related('employe'):
            notifications.append(_notif_conge('warning', 'Congé dans 7 jours', c))
        for c in Conge.objects.filter(statut='approuve', date_debut=veille).select_related('employe'):
            notifications.append(_notif_conge('danger', 'Congé commence demain !', c))
    else:
        try:
            employe = request.user.employe
            for c in employe.conges.filter(statut='approuve', date_debut=j7):
                notifications.append(_notif_conge('warning', 'Votre congé dans 7 jours', c, pour_rh=False))
            for c in employe.conges.filter(statut='approuve', date_debut=veille):
                notifications.append(_notif_conge('danger', 'Votre congé commence demain !', c, pour_rh=False))
        except Employe.DoesNotExist:
            pass

    return JsonResponse({'notifications': notifications})


@rh_requis
def calendrier_conges(request):
    """Affiche la page du calendrier mensuel (HTML).

    Endpoint
    --------
    GET /calendrier/

    Accès
    -----
    RH / Admin / DAF uniquement (403 sinon).
    La page charge FullCalendar et appelle /api/calendrier/events/ en XHR.
    """
    return render(request, 'SYGEPE/calendrier.html')


@rh_requis
def api_calendrier_events(request):
    """Endpoint JSON pour FullCalendar : congés + permissions (hors annulés, fenêtre ±3 mois).

    Endpoint
    --------
    GET /api/calendrier/events/

    Accès
    -----
    RH / Admin / DAF uniquement (403 sinon).

    Paramètres
    ----------
    Aucun paramètre de requête.

    Fenêtre temporelle
    ------------------
    Retourne les événements dont date_debut ≤ today+92j ET date_fin ≥ today−92j.
    Les congés/permissions avec statut='annule' sont exclus.

    Réponse (200 OK) — tableau JSON (format FullCalendar EventObject)
    -----------------------------------------------------------------
    [
        {
            "id"             : str,          // ex. "conge-42" ou "perm-7"
            "title"          : str,          // ex. "🏖 Jean Dupont (Congé payé)"
            "start"          : str,          // date ISO 8601, ex. "2026-03-10"
            "end"            : str,          // date ISO 8601 exclusive, ex. "2026-03-15"
            "backgroundColor": str,          // couleur hex selon statut
            "borderColor"    : str,          // identique à backgroundColor
            "extendedProps"  : {
                "type"   : "conge" | "perm",
                "statut" : str,              // libellé affiché, ex. "Approuvé"
                "employe": str               // nom complet, ex. "Jean Dupont"
            }
        },
        ...
    ]

    Couleurs par statut (congés)
    ----------------------------
    - approuve   : #16a34a  (vert)
    - en_attente : #d97706  (orange)
    - refuse     : #dc2626  (rouge)
    - (défaut)   : #6b7280  (gris)

    Couleur permissions
    -------------------
    - toujours   : #1d4ed8  (bleu)

    Réponse (403)
    -------------
    HttpResponseForbidden si l'utilisateur n'est pas RH/Admin/DAF.
    """
    COULEURS = {
        'approuve'  : '#16a34a',
        'en_attente': '#d97706',
        'refuse'    : '#dc2626',
        'annule'    : '#9ca3af',
    }

    today  = date.today()
    debut  = today - timedelta(days=92)   # ~3 mois en arrière
    fin    = today + timedelta(days=92)   # ~3 mois en avant

    events = []

    conges = (
        Conge.objects
        .select_related('employe')
        .exclude(statut='annule')
        .filter(date_debut__lte=fin, date_fin__gte=debut)
    )
    for conge in conges:
        couleur = COULEURS.get(conge.statut, '#6b7280')
        events.append(_event_dict(
            'conge', conge,
            f"🏖 {conge.employe.get_full_name()} ({conge.get_type_conge_display()})",
            couleur,
        ))

    perms = (
        Permission.objects
        .select_related('employe')
        .exclude(statut='annule')
        .filter(date_debut__lte=fin, date_fin__gte=debut)
    )
    for perm in perms:
        events.append(_event_dict(
            'perm', perm,
            f"🔖 {perm.employe.get_full_name()} (Permission)",
            '#1d4ed8',
        ))

    return JsonResponse(events, safe=False)
