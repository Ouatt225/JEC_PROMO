"""Vues d'export Excel SYGEPE (openpyxl).

Optimisations anti-timeout :
- values_list()      → tuples bruts au lieu d'instances ORM complètes (~5x moins de mémoire)
- iterator(500)      → streaming PostgreSQL par chunks, pas de chargement tout-en-RAM
- garde EXPORT_MAX_ROWS → HTTP 400 explicite si le volume dépasse le seuil configurable
  (settings.EXPORT_MAX_ROWS, défaut 5 000 lignes) plutôt que de laisser Gunicorn timeout.
"""

from datetime import date, datetime as dt

from django.conf import settings
from django.http import HttpResponse

from ..models import Absence, Conge, Permission, Presence
from ..services.excel import construire_classeur, wb_vers_response
from .decorators import rh_requis

EXPORT_MAX_ROWS = getattr(settings, 'EXPORT_MAX_ROWS', 5_000)

STATUT_ABSENCES = {
    'present': 'Présent', 'absent': 'Absent', 'retard': 'En retard',
    'conge': 'En congé', 'permission': 'En permission',
}
STATUT_RH = {
    'en_attente': 'En attente', 'approuve': 'Approuvé',
    'refuse': 'Refusé', 'annule': 'Annulé',
}
TYPE_CONGE = {
    'paye': 'Annuel', 'maternite': 'Maternité',
}


def _param_int(request, key, default):
    """Retourne request.GET[key] converti en int, ou default si absent/invalide."""
    try:
        return int(request.GET.get(key, default))
    except (ValueError, TypeError):
        return default


def _trop_de_lignes(count, label):
    """Retourne une HttpResponse 400 si count > EXPORT_MAX_ROWS, None sinon."""
    if count > EXPORT_MAX_ROWS:
        return HttpResponse(
            f"Export limité à {EXPORT_MAX_ROWS:,} lignes. "
            f"Ce filtre retourne {count:,} enregistrements ({label}). "
            f"Affinez la période ou contactez l'administrateur.",
            status=400,
            content_type='text/plain; charset=utf-8',
        )
    return None


@rh_requis
def export_excel_presences(request):
    """Exporte les présences filtrées au format Excel (.xlsx)."""
    mois  = _param_int(request, 'mois',  date.today().month)
    annee = _param_int(request, 'annee', date.today().year)

    qs = (
        Presence.objects
        .filter(date__year=annee, date__month=mois)
        .values_list(
            'employe__matricule', 'employe__nom', 'employe__prenom',
            'date', 'heure_arrivee', 'heure_depart', 'statut', 'observation',
        )
        .order_by('date', 'employe__nom')
    )

    guard = _trop_de_lignes(qs.count(), f'présences {mois:02d}/{annee}')
    if guard:
        return guard

    headers = ['Matricule', 'Nom', 'Prénoms', 'Date',
               'Heure arrivée', 'Heure départ', 'Statut', 'Observation']
    rows = [
        [
            mat,
            nom.upper(),
            prenom,
            d.strftime('%d/%m/%Y'),
            ha.strftime('%H:%M') if ha else '—',
            hd.strftime('%H:%M') if hd else '—',
            STATUT_ABSENCES.get(statut, statut),
            obs or '',
        ]
        for mat, nom, prenom, d, ha, hd, statut, obs in qs.iterator(chunk_size=500)
    ]

    wb = construire_classeur('Présences', headers, rows)
    return wb_vers_response(wb, f'presences_{dt(annee, mois, 1).strftime("%B_%Y")}.xlsx')


@rh_requis
def export_excel_conges(request):
    """Exporte les congés au format Excel (.xlsx)."""
    annee = _param_int(request, 'annee', date.today().year)

    qs = (
        Conge.objects
        .filter(date_debut__year=annee)
        .values_list(
            'employe__matricule', 'employe__nom', 'employe__prenom',
            'type_conge', 'date_debut', 'date_fin', 'statut', 'motif',
        )
        .order_by('-date_demande')
    )

    guard = _trop_de_lignes(qs.count(), f'congés {annee}')
    if guard:
        return guard

    headers = ['Matricule', 'Nom', 'Prénoms', 'Type congé',
               'Date début', 'Date fin', 'Nb jours', 'Statut', 'Motif']
    rows = [
        [
            mat,
            nom.upper(),
            prenom,
            TYPE_CONGE.get(type_c, type_c),
            dd.strftime('%d/%m/%Y'),
            df.strftime('%d/%m/%Y'),
            (df - dd).days + 1,
            STATUT_RH.get(statut, statut),
            (motif or '')[:100],
        ]
        for mat, nom, prenom, type_c, dd, df, statut, motif in qs.iterator(chunk_size=500)
    ]

    wb = construire_classeur('Congés', headers, rows)
    return wb_vers_response(wb, f'conges_{annee}.xlsx')


@rh_requis
def export_excel_permissions(request):
    """Exporte les permissions au format Excel (.xlsx)."""
    annee = _param_int(request, 'annee', date.today().year)

    qs = (
        Permission.objects
        .filter(date_debut__year=annee)
        .values_list(
            'employe__matricule', 'employe__nom', 'employe__prenom',
            'date_debut', 'date_fin', 'statut', 'motif',
        )
        .order_by('-date_demande')
    )

    guard = _trop_de_lignes(qs.count(), f'permissions {annee}')
    if guard:
        return guard

    headers = ['Matricule', 'Nom', 'Prénoms', 'Date début',
               'Date fin', 'Nb jours', 'Statut', 'Motif']
    rows = [
        [
            mat,
            nom.upper(),
            prenom,
            dd.strftime('%d/%m/%Y'),
            df.strftime('%d/%m/%Y'),
            (df - dd).days + 1,
            STATUT_RH.get(statut, statut),
            (motif or '')[:100],
        ]
        for mat, nom, prenom, dd, df, statut, motif in qs.iterator(chunk_size=500)
    ]

    wb = construire_classeur('Permissions', headers, rows)
    return wb_vers_response(wb, f'permissions_{annee}.xlsx')


@rh_requis
def export_excel_absences(request):
    """Exporte les absences spéciales au format Excel (.xlsx)."""
    annee = _param_int(request, 'annee', date.today().year)

    qs = (
        Absence.objects
        .filter(date_debut__year=annee)
        .values_list(
            'employe__matricule', 'employe__nom', 'employe__prenom',
            'type_absence', 'date_debut', 'date_fin', 'statut', 'motif',
        )
        .order_by('-date_demande')
    )

    guard = _trop_de_lignes(qs.count(), f'absences {annee}')
    if guard:
        return guard

    TYPE_ABSENCE = {
        'mission_pro':       'Mission professionnelle',
        'formation_interne': 'Formation interne',
        'atelier':           'Atelier',
    }

    headers = ['Matricule', 'Nom', 'Prénoms', 'Type absence',
               'Date début', 'Date fin', 'Nb jours', 'Statut', 'Motif']
    rows = [
        [
            mat,
            nom.upper(),
            prenom,
            TYPE_ABSENCE.get(type_a, type_a),
            dd.strftime('%d/%m/%Y'),
            df.strftime('%d/%m/%Y'),
            (df - dd).days + 1,
            STATUT_RH.get(statut, statut),
            (motif or '')[:100],
        ]
        for mat, nom, prenom, type_a, dd, df, statut, motif in qs.iterator(chunk_size=500)
    ]

    wb = construire_classeur('Absences', headers, rows)
    return wb_vers_response(wb, f'absences_{annee}.xlsx')
