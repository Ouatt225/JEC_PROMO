"""Vues de gestion des absences SYGEPE.

Types : Mission professionnelle, Formation interne, Atelier.
Validation directe par la DRH (pas de circuit responsable).
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..forms import AbsenceForm, ValidationAbsenceForm
from ..models import Absence, Employe
from ..services.audit import log_action
from .decorators import get_employe_or_none, get_params, is_rh, paginer, peut_valider_pour, rh_requis


@login_required
def liste_absences(request):
    """Liste paginée des absences (double audience).

    - RH / Admin / DAF → toutes les absences, template absences/liste.html.
    - Employé           → ses propres absences, template espace_employe/mes_absences.html.
    """
    statut    = request.GET.get('statut', '')
    absences_qs = Absence.objects.select_related('employe').all()

    if not is_rh(request.user):
        try:
            employe    = request.user.employe
            absences_qs = absences_qs.filter(employe=employe)
        except Employe.DoesNotExist:
            absences_qs = Absence.objects.none()

    total_absences = absences_qs.count()
    nb_en_attente  = absences_qs.filter(statut='en_attente').count()
    nb_approuves   = absences_qs.filter(statut='approuve').count()

    if statut:
        absences_qs = absences_qs.filter(statut=statut)

    absences, page_range = paginer(absences_qs, request)

    # IDs validables par l'utilisateur connecté (RH/Admin/DAF avec règle croisée)
    ids_validables = set()
    if is_rh(request.user):
        for a in absences:
            if a.statut == 'en_attente' and peut_valider_pour(request.user, a.employe):
                ids_validables.add(a.pk)

    context = {
        'absences':           absences,
        'page_range':         page_range,
        'params':             get_params(request),
        'statut_selectionne': statut,
        'ids_validables':     ids_validables,
        'total_absences':     total_absences,
        'nb_en_attente':      nb_en_attente,
        'nb_approuves':       nb_approuves,
    }
    if not is_rh(request.user):
        return render(request, 'SYGEPE/espace_employe/mes_absences.html', context)
    return render(request, 'SYGEPE/absences/liste.html', context)


@login_required
def demander_absence(request):
    """Formulaire de demande d'absence (employé ou RH pour lui-même)."""
    employe = get_employe_or_none(request.user)

    if request.method == 'POST':
        form = AbsenceForm(request.POST, employe=employe)
        if form.is_valid():
            absence = form.save(commit=False)
            if not employe:
                messages.error(request, "Votre profil employé n'existe pas. Contactez l'administrateur.")
                return redirect('sygepe:liste_absences')
            absence.employe = employe
            with transaction.atomic():
                absence.save()
                log_action(
                    request, 'absence_demandee',
                    f"Demande d'absence {absence.get_type_absence_display()} "
                    f"du {absence.date_debut} au {absence.date_fin}",
                    employe=employe,
                )
            messages.success(request, "Demande d'absence soumise avec succès.")
            return redirect('sygepe:liste_absences')
    else:
        form = AbsenceForm(employe=employe)

    ctx = {'form': form}
    if not is_rh(request.user):
        return render(request, 'SYGEPE/espace_employe/form_absence.html', ctx)
    return render(request, 'SYGEPE/absences/form.html', ctx)


@rh_requis
def valider_absence(request, pk):
    """Approuve ou refuse une demande d'absence.

    Accès : RH / Admin / DAF uniquement (@rh_requis).
    Règle croisée : RH ne valide pas pour RH, DAF ne valide pas pour DAF.
    """
    absence = get_object_or_404(Absence, pk=pk)
    if not peut_valider_pour(request.user, absence.employe):
        raise PermissionDenied
    if absence.statut != 'en_attente':
        messages.error(request, "Cette absence a déjà été traitée.")
        return redirect('sygepe:liste_absences')

    if request.method == 'POST':
        form = ValidationAbsenceForm(request.POST, instance=absence)
        if form.is_valid():
            a = form.save(commit=False)
            a.valideur        = request.user
            a.date_validation = timezone.now()
            with transaction.atomic():
                a.save()
                action_key = 'absence_approuvee' if a.statut == 'approuve' else 'absence_refusee'
                log_action(
                    request, action_key,
                    f"Absence {a.get_type_absence_display()} de {a.employe.get_full_name()} "
                    f"du {a.date_debut} au {a.date_fin} : {a.get_statut_display()}",
                    employe=a.employe,
                )
            messages.success(request, f"Absence {a.get_statut_display().lower()}.")
            return redirect('sygepe:liste_absences')
    else:
        form = ValidationAbsenceForm(instance=absence)

    return render(request, 'SYGEPE/absences/valider.html', {'form': form, 'absence': absence})


@login_required
def mes_absences_perso(request):
    """Absences personnelles — mode employé forcé (utilisé par RH/DAF/Admin)."""
    employe = get_employe_or_none(request.user)
    if not employe:
        return redirect('sygepe:profil')

    statut      = request.GET.get('statut', '')
    absences_qs = Absence.objects.filter(employe=employe).select_related('employe')

    total_absences = absences_qs.count()
    nb_en_attente  = absences_qs.filter(statut='en_attente').count()
    nb_approuves   = absences_qs.filter(statut='approuve').count()

    if statut:
        absences_qs = absences_qs.filter(statut=statut)

    absences, page_range = paginer(absences_qs, request)
    return render(request, 'SYGEPE/espace_employe/mes_absences.html', {
        'absences':           absences,
        'page_range':         page_range,
        'params':             get_params(request),
        'statut_selectionne': statut,
        'total_absences':     total_absences,
        'nb_en_attente':      nb_en_attente,
        'nb_approuves':       nb_approuves,
    })
