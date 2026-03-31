"""Vues de gestion des absences SYGEPE.

Types : Mission professionnelle, Formation interne, Atelier.
Circuit à 2 étapes : responsable de département → DRH (identique aux permissions).
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
from .decorators import (
    dept_a_premier_valideur,
    get_employe_or_none,
    get_params,
    is_rh,
    is_responsable,
    paginer,
    peut_faire_premiere_validation,
    peut_valider_pour,
    rh_requis,
)


@login_required
def liste_absences(request):
    """Liste paginée des absences (triple audience).

    - RH / Admin / DAF  → toutes les absences, template absences/liste.html.
    - Responsable       → absences de son département uniquement.
    - Employé           → ses propres absences, template espace_employe/mes_absences.html.
    """
    statut      = request.GET.get('statut', '')
    absences_qs = Absence.objects.select_related('employe__departement').all()

    user = request.user
    if is_rh(user):
        pass  # voit tout
    elif is_responsable(user):
        from .decorators import get_departement_responsable
        dept = get_departement_responsable(user)
        absences_qs = absences_qs.filter(employe__departement=dept) if dept else Absence.objects.none()
    else:
        try:
            employe     = user.employe
            absences_qs = absences_qs.filter(employe=employe)
        except Employe.DoesNotExist:
            absences_qs = Absence.objects.none()

    total_absences = absences_qs.count()
    nb_en_attente  = absences_qs.filter(statut='en_attente').count()
    nb_approuves   = absences_qs.filter(statut='approuve').count()

    if statut:
        absences_qs = absences_qs.filter(statut=statut)

    absences, page_range = paginer(absences_qs, request)

    # Calcule quelles absences l'utilisateur peut traiter (étape 1 ou 2)
    peut_premier_ids = set()
    peut_final_ids   = set()
    if is_rh(user) or is_responsable(user):
        for a in absences:
            if a.statut == 'en_attente' and peut_faire_premiere_validation(user, a.employe):
                # Étape 1 : responsable valide son département
                peut_premier_ids.add(a.pk)
            elif a.statut == 'en_attente' and is_rh(user) and not dept_a_premier_valideur(a.employe):
                # Pas de responsable désigné → DRH valide directement (règle croisée)
                if peut_valider_pour(user, a.employe):
                    peut_final_ids.add(a.pk)
            elif a.statut == 'valide_responsable' and is_rh(user):
                # Étape 2 : DRH valide après le responsable (règle croisée)
                if peut_valider_pour(user, a.employe):
                    peut_final_ids.add(a.pk)

    context = {
        'absences':           absences,
        'page_range':         page_range,
        'params':             get_params(request),
        'statut_selectionne': statut,
        'peut_premier_ids':   peut_premier_ids,
        'peut_final_ids':     peut_final_ids,
        'total_absences':     total_absences,
        'nb_en_attente':      nb_en_attente,
        'nb_approuves':       nb_approuves,
    }
    if not (is_rh(user) or is_responsable(user)):
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


@login_required
def valider_absence(request, pk):
    """Validation en deux étapes : responsable (étape 1) → DRH (étape 2)."""
    absence = get_object_or_404(Absence, pk=pk)
    user    = request.user

    employe_role = getattr(absence.employe, 'role', None)
    etape = None

    if employe_role in ('rh', 'daf'):
        # Personnel RH/DAF → validation directe par le rôle opposé (règle croisée)
        if not peut_valider_pour(user, absence.employe):
            raise PermissionDenied
        if absence.statut not in ('en_attente', 'valide_responsable'):
            raise PermissionDenied
        etape = 2
    else:
        # Circuit normal à 2 étapes
        if absence.statut == 'en_attente':
            if peut_faire_premiere_validation(user, absence.employe):
                etape = 1
            elif is_rh(user) and not dept_a_premier_valideur(absence.employe):
                etape = 2
        elif absence.statut == 'valide_responsable' and is_rh(user):
            etape = 2

    if etape is None:
        raise PermissionDenied

    if request.method == 'POST':
        form = ValidationAbsenceForm(request.POST, instance=absence, step=etape)
        if form.is_valid():
            a = form.save(commit=False)
            if etape == 1:
                a.valideur_responsable        = user
                a.date_validation_responsable = timezone.now()
                action_key = 'absence_validee_resp' if a.statut == 'valide_responsable' else 'absence_refusee'
                statut_msg = "transmise à la DRH" if a.statut == 'valide_responsable' else "refusée"
            else:
                a.valideur        = user
                a.date_validation = timezone.now()
                action_key = 'absence_approuvee' if a.statut == 'approuve' else 'absence_refusee'
                statut_msg = a.get_statut_display().lower()

            with transaction.atomic():
                a.save()
                log_action(
                    request, action_key,
                    f"Absence {a.get_type_absence_display()} de {a.employe.get_full_name()} "
                    f"du {a.date_debut} au {a.date_fin} (étape {etape}) : {statut_msg}",
                    employe=a.employe,
                )
            messages.success(request, f"Absence {statut_msg}.")
            return redirect('sygepe:liste_absences')
    else:
        form = ValidationAbsenceForm(instance=absence, step=etape)

    return render(request, 'SYGEPE/absences/valider.html', {
        'form':    form,
        'absence': absence,
        'etape':   etape,
    })


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
