"""Vues de gestion des congés SYGEPE."""

from datetime import date

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..forms import CongeForm, ModifierCongeForm, ValidationCongeForm
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
    conges_qs = Conge.objects.select_related('employe').all()

    if not is_rh(request.user):
        try:
            employe = request.user.employe
            conges_qs = conges_qs.filter(employe=employe)
        except Employe.DoesNotExist:
            conges_qs = Conge.objects.none()

    # Compteurs calculés AVANT le filtre par statut
    total_conges    = conges_qs.count()
    nb_en_attente   = conges_qs.filter(statut='en_attente').count()
    nb_approuves    = conges_qs.filter(statut='approuve').count()

    if statut:
        conges_qs = conges_qs.filter(statut=statut)

    conges, page_range = paginer(conges_qs, request)

    # IDs des congés que l'utilisateur connecté peut valider (règle croisée RH/DAF incluse)
    ids_validables = set()
    if is_rh(request.user):
        for c in conges:
            if c.statut == 'en_attente' and peut_valider_pour(request.user, c.employe):
                ids_validables.add(c.pk)

    context = {
        'conges':             conges,
        'page_range':         page_range,
        'params':             get_params(request),
        'statut_selectionne': statut,
        'ids_validables':     ids_validables,
        'today':              date.today(),
        'total_conges':       total_conges,
        'nb_en_attente':      nb_en_attente,
        'nb_approuves':       nb_approuves,
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
def modifier_conge(request, pk):
    """Fractionnement d'un congé approuvé en 1 ou 2 nouvelles périodes.

    Accès : propriétaire du congé uniquement (ou RH pour n'importe quel congé).
    - Le congé original doit être à statut 'approuve' et ne pas avoir commencé.
    - À la soumission : congé original → 'annule', 1 ou 2 nouveaux congés → 'en_attente'.
    """
    conge = get_object_or_404(Conge, pk=pk)
    employe = get_employe_or_none(request.user)

    # Contrôle d'accès : propriétaire ou RH
    if not is_rh(request.user):
        if employe is None or conge.employe != employe:
            raise PermissionDenied

    # Garde-fous métier
    if conge.statut != 'approuve':
        messages.error(request, "Seul un congé approuvé peut être modifié.")
        return redirect('sygepe:liste_conges')
    if conge.date_debut <= date.today():
        messages.error(request, "Impossible de modifier un congé déjà commencé ou passé.")
        return redirect('sygepe:liste_conges')

    employe_conge = conge.employe

    if request.method == 'POST':
        form = ModifierCongeForm(request.POST, conge_original=conge, employe=employe_conge)
        if form.is_valid():
            cd = form.cleaned_data
            with transaction.atomic():
                # Annuler le congé original
                conge.statut = 'annule'
                conge.commentaire_valideur = f"Fractionné par l'agent le {date.today().strftime('%d/%m/%Y')}."
                conge.save()

                # Créer la période 1
                c1 = Conge.objects.create(
                    employe=employe_conge,
                    type_conge=conge.type_conge,
                    date_debut=cd['date_debut_1'],
                    date_fin=cd['date_fin_1'],
                    motif=cd['motif'],
                    statut='en_attente',
                    conge_parent=conge,
                )

                # Créer la période 2 si renseignée
                c2 = None
                if cd.get('date_debut_2') and cd.get('date_fin_2'):
                    c2 = Conge.objects.create(
                        employe=employe_conge,
                        type_conge=conge.type_conge,
                        date_debut=cd['date_debut_2'],
                        date_fin=cd['date_fin_2'],
                        motif=cd['motif'],
                        statut='en_attente',
                        conge_parent=conge,
                    )

                periodes = f"Période 1 : {c1.date_debut} → {c1.date_fin}"
                if c2:
                    periodes += f" | Période 2 : {c2.date_debut} → {c2.date_fin}"
                log_action(
                    request, 'conge_modifie',
                    f"Congé {conge.get_type_conge_display()} du {conge.date_debut} au {conge.date_fin} "
                    f"fractionné en {2 if c2 else 1} période(s). {periodes}",
                    employe=employe_conge,
                )

            nb = 2 if c2 else 1
            messages.success(
                request,
                f"Congé fractionné en {nb} nouvelle(s) demande(s) soumise(s) à validation."
            )
            return redirect('sygepe:liste_conges')
    else:
        form = ModifierCongeForm(conge_original=conge, employe=employe_conge)

    ctx = {'form': form, 'conge': conge}
    if not is_rh(request.user):
        return render(request, 'SYGEPE/espace_employe/modifier_conge.html', ctx)
    return render(request, 'SYGEPE/conges/modifier.html', ctx)


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
    conges_qs = Conge.objects.filter(employe=employe).select_related('employe')

    total_conges  = conges_qs.count()
    nb_en_attente = conges_qs.filter(statut='en_attente').count()
    nb_approuves  = conges_qs.filter(statut='approuve').count()

    if statut:
        conges_qs = conges_qs.filter(statut=statut)

    conges, page_range = paginer(conges_qs, request)
    annee      = date.today().year
    jours_pris = employe.jours_conge_pris(annee)
    return render(request, 'SYGEPE/espace_employe/mes_conges.html', {
        'conges':             conges,
        'page_range':         page_range,
        'params':             get_params(request),
        'statut_selectionne': statut,
        'solde_conge':        max(0, settings.QUOTA_CONGES_ANNUELS - jours_pris),
        'jours_pris':         jours_pris,
        'today':              date.today(),
        'total_conges':       total_conges,
        'nb_en_attente':      nb_en_attente,
        'nb_approuves':       nb_approuves,
    })
