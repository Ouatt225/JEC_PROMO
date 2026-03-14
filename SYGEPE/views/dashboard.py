"""Vue Dashboard RH SYGEPE."""

import json
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache

from ..models import Conge, Departement, Employe, Permission, Presence
from .decorators import get_departement_responsable, is_rh, is_responsable


@never_cache
@login_required
def dashboard(request):
    """Tableau de bord principal RH et responsables de département.

    Accès : RH / Admin / DAF / responsable de département.
    Redirige vers le profil employé si l'utilisateur n'a pas ces droits.

    Cache Redis (3 niveaux, clé préfixée par date + département) :
    - Bloc 1 — stats du jour (taux de présence, demandes en attente) : TTL 5 min
    - Bloc 2 — alertes anniversaires (7 prochains jours)              : TTL 1 h
    - Bloc 3 — données graphiques (Chart.js, 6 derniers mois)         : TTL 1 h
    Les 5 derniers congés/permissions sont toujours récupérés en temps réel.

    Les responsables voient uniquement les données de leur département ;
    les clés de cache incluent le suffixe `_dept<pk>` pour les isoler.
    """
    if not (is_rh(request.user) or is_responsable(request.user)):
        return redirect('sygepe:profil')

    today = date.today()
    today_str = today.isoformat()

    # Département filtré pour les responsables (None = accès global RH)
    dept = get_departement_responsable(request.user)
    dept_suffix = f'_dept{dept.pk}' if dept else ''

    # ── Bloc 1 : stats du jour (TTL 5 min) ────────────────────────────────────
    key_stats = f'dashboard_stats_{today_str}{dept_suffix}'
    stats = cache.get(key_stats)
    if stats is None:
        emp_qs  = Employe.objects.filter(statut='actif')
        pres_qs = Presence.objects.filter(date=today)
        cong_qs = Conge.objects.filter(statut='en_attente')
        perm_qs = Permission.objects.filter(statut='en_attente')

        if dept:
            emp_qs  = emp_qs.filter(departement=dept)
            pres_qs = pres_qs.filter(employe__departement=dept)
            cong_qs = cong_qs.filter(employe__departement=dept)
            perm_qs = perm_qs.filter(employe__departement=dept)

        total_employes            = emp_qs.count()
        presences_aujourd_hui     = pres_qs.filter(statut='present').count()
        conges_en_attente         = cong_qs.count()
        permissions_en_attente    = perm_qs.count()
        taux_presence             = round(presences_aujourd_hui / total_employes * 100) if total_employes else 0
        absents_aujourd_hui       = pres_qs.filter(statut='absent').count()
        en_conge_aujourd_hui      = pres_qs.filter(statut='conge').count()
        en_permission_aujourd_hui = pres_qs.filter(statut='permission').count()
        stats = {
            'total_employes': total_employes,
            'presences_aujourd_hui': presences_aujourd_hui,
            'conges_en_attente': conges_en_attente,
            'permissions_en_attente': permissions_en_attente,
            'taux_presence': taux_presence,
            'absents_aujourd_hui': absents_aujourd_hui,
            'en_conge_aujourd_hui': en_conge_aujourd_hui,
            'en_permission_aujourd_hui': en_permission_aujourd_hui,
        }
        cache.set(key_stats, stats, settings.CACHE_TTL_DASHBOARD_STATS)

    # ── Bloc 2 : alertes anniversaires — 7 prochains jours (TTL 1 h) ──────────
    key_anniv = f'dashboard_anniversaires_{today_str}{dept_suffix}'
    alertes_anniversaires = cache.get(key_anniv)
    if alertes_anniversaires is None:
        alertes_anniversaires = []
        for i in range(0, 8):
            jour = today + timedelta(days=i)
            emp_anniv = Employe.objects.filter(
                statut='actif',
                date_naissance__month=jour.month,
                date_naissance__day=jour.day,
            )
            if dept:
                emp_anniv = emp_anniv.filter(departement=dept)
            for emp in emp_anniv:
                alertes_anniversaires.append({'employe': emp, 'date': jour, 'dans': i})
        cache.set(key_anniv, alertes_anniversaires, settings.CACHE_TTL_DASHBOARD_ALERTS)

    # ── Bloc 3 : graphiques (TTL 1 h) ─────────────────────────────────────────
    key_charts = f'dashboard_charts_{today_str}{dept_suffix}'
    charts = cache.get(key_charts)
    if charts is None:
        mois_liste = []
        for i in range(5, -1, -1):
            mois_num  = today.month - i
            annee_num = today.year
            while mois_num <= 0:
                mois_num  += 12
                annee_num -= 1
            mois_liste.append(date(annee_num, mois_num, 1))

        debut_periode = mois_liste[0]
        pres_db = Presence.objects.filter(statut='present', date__gte=debut_periode)
        if dept:
            pres_db = pres_db.filter(employe__departement=dept)
        pres_db = (
            pres_db
            .annotate(mois=TruncMonth('date'))
            .values('mois')
            .annotate(nb=Count('id'))
            .order_by('mois')
        )
        pres_dict = {
            (p['mois'].date() if hasattr(p['mois'], 'hour') else p['mois']): p['nb']
            for p in pres_db
        }

        if dept:
            depts = Departement.objects.filter(pk=dept.pk).annotate(nb=Count('employes'))
        else:
            depts = Departement.objects.annotate(nb=Count('employes')).filter(nb__gt=0)

        charts = {
            'labels_presences': json.dumps([m.strftime('%b %Y') for m in mois_liste]),
            'data_presences':   json.dumps([pres_dict.get(m, 0) for m in mois_liste]),
            'labels_dept':      json.dumps([d.nom for d in depts]),
            'data_dept':        json.dumps([d.nb for d in depts]),
        }
        cache.set(key_charts, charts, settings.CACHE_TTL_DASHBOARD_CHARTS)

    # ── Dernières demandes : toujours fraîches (pas de cache) ─────────────────
    derniers_conges       = Conge.objects.select_related('employe').order_by('-date_demande')
    dernieres_permissions = Permission.objects.select_related('employe').order_by('-date_demande')
    if dept:
        derniers_conges       = derniers_conges.filter(employe__departement=dept)
        dernieres_permissions = dernieres_permissions.filter(employe__departement=dept)
    derniers_conges       = derniers_conges[:5]
    dernieres_permissions = dernieres_permissions[:5]

    context = {
        **stats,
        'alertes_anniversaires': alertes_anniversaires,
        **charts,
        'derniers_conges': derniers_conges,
        'dernieres_permissions': dernieres_permissions,
        'today': today,
        'departement_filtre': dept,
    }
    return render(request, 'SYGEPE/dashboard.html', context)
