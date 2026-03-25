"""Vues de gestion des congés SYGEPE."""

from datetime import date

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..forms import CongeForm, ValidationCongeForm
from ..models import Conge, Employe
from ..services.audit import log_action
from ..services.email import notifier_statut_conge
from .decorators import get_employe_or_none, get_params, is_rh, paginer, peut_valider_pour, rh_requis


@login_required
def liste_conges(request):
    """Liste paginée des demandes de congé (double audience).

    Accès : tout utilisateur connecté.
    - RH / Admin / DAF → tous les congés, template conges/liste.html.
    - Employé           → ses propres congés uniquement, template espace_employe/mes_conges.html.
    GET params : statut (en_attente / approuve / refuse).
    Pagination : 20 par page (filtres préservés dans les liens).
    """
    statut = request.GET.get('statut', '')
    conges = Conge.objects.select_related('employe').all()

    if not is_rh(request.user):
        try:
            employe = request.user.employe
            conges  = conges.filter(employe=employe)
        except Employe.DoesNotExist:
            conges = Conge.objects.none()

    if statut:
        conges = conges.filter(statut=statut)

    conges, page_range = paginer(conges, request)

    # IDs des congés que l'utilisateur connecté peut valider (règle croisée RH/DAF incluse)
    ids_validables = set()
    if is_rh(request.user):
        for c in conges:
            if c.statut == 'en_attente' and peut_valider_pour(request.user, c.employe):
                ids_validables.add(c.pk)

    context = {
        'conges':            conges,
        'page_range':        page_range,
        'params':            get_params(request),
        'statut_selectionne': statut,
        'ids_validables':    ids_validables,
    }
    if not is_rh(request.user):
        return render(request, 'SYGEPE/espace_employe/mes_conges.html', context)
    return render(request, 'SYGEPE/conges/liste.html', context)


@login_required
def demander_conge(request):
    """Formulaire de demande de congé (employé ou RH pour lui-même).

    Accès : tout utilisateur connecté ayant un profil employé.
    CongeForm valide le quota annuel, les chevauchements et les règles métier
    (maternité réservée aux femmes, types sans quota, etc.).
    Redirige vers liste_conges après soumission réussie.
    """
    employe = get_employe_or_none(request.user)

    annee       = date.today().year
    jours_pris  = employe.jours_conge_pris(annee) if employe else 0
    solde_conge = max(0, settings.QUOTA_CONGES_ANNUELS - jours_pris)

    if request.method == 'POST':
        form = CongeForm(request.POST, request.FILES, employe=employe)
        if form.is_valid():
            conge = form.save(commit=False)
            if not employe:
                messages.error(request, "Votre profil employé n'existe pas. Contactez l'administrateur.")
                return redirect('sygepe:liste_conges')
            conge.employe = employe
            with transaction.atomic():
                conge.save()
                log_action(
                    request, 'conge_demande',
                    f"Demande de congé {conge.get_type_conge_display()} "
                    f"du {conge.date_debut} au {conge.date_fin}",
                    employe=employe,
                )
            messages.success(request, "Demande de congé soumise avec succès.")
            return redirect('sygepe:liste_conges')
    else:
        form = CongeForm(employe=employe)

    ctx = {'form': form, 'solde_conge': solde_conge, 'jours_pris': jours_pris, 'annee': annee}
    if not is_rh(request.user):
        return render(request, 'SYGEPE/espace_employe/form_conge.html', ctx)
    return render(request, 'SYGEPE/conges/form.html', ctx)


@rh_requis
def valider_conge(request, pk):
    """Approuve ou refuse une demande de congé.

    Accès : RH / Admin / DAF uniquement (@rh_requis).
    Enregistre le valideur et la date de validation.
    Redirige vers liste_conges après traitement.
    """
    conge = get_object_or_404(Conge, pk=pk)
    # Règle croisée : RH ne peut pas valider pour un RH, DAF ne peut pas valider pour un DAF
    if not peut_valider_pour(request.user, conge.employe):
        raise PermissionDenied
    if request.method == 'POST':
        form = ValidationCongeForm(request.POST, instance=conge)
        if form.is_valid():
            c = form.save(commit=False)
            c.valideur        = request.user
            c.date_validation = timezone.now()
            with transaction.atomic():
                c.save()
                action_key = 'conge_approuve' if c.statut == 'approuve' else 'conge_refuse'
                log_action(
                    request, action_key,
                    f"Congé de {c.employe.get_full_name()} du {c.date_debut} au {c.date_fin} : "
                    f"{c.get_statut_display()}",
                    employe=c.employe,
                )
            notifier_statut_conge(c)  # e-mail hors transaction (fail silencieux)
            messages.success(request, f"Congé {c.get_statut_display().lower()}.")
            return redirect('sygepe:liste_conges')
    else:
        form = ValidationCongeForm(instance=conge)
    return render(request, 'SYGEPE/conges/valider.html', {'form': form, 'conge': conge})


@login_required
def mes_conges_perso(request):
    """Congés personnels de l'utilisateur connecté — mode employé forcé.

    Utilisé par RH/DAF/Admin qui ont une fiche Employe et veulent voir
    uniquement leurs propres congés (espace employé), indépendamment de leur rôle.
    """
    employe = get_employe_or_none(request.user)
    if not employe:
        return redirect('sygepe:profil')

    statut = request.GET.get('statut', '')
    conges = Conge.objects.filter(employe=employe).select_related('employe')
    if statut:
        conges = conges.filter(statut=statut)

    conges, page_range = paginer(conges, request)
    annee      = date.today().year
    jours_pris = employe.jours_conge_pris(annee)
    return render(request, 'SYGEPE/espace_employe/mes_conges.html', {
        'conges':            conges,
        'page_range':        page_range,
        'params':            get_params(request),
        'statut_selectionne': statut,
        'solde_conge':       max(0, settings.QUOTA_CONGES_ANNUELS - jours_pris),
        'jours_pris':        jours_pris,
    })
