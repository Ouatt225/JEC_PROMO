"""Vues de gestion des permissions SYGEPE."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..forms import PermissionForm, ValidationPermissionForm
from ..models import Employe, Permission
from ..services.audit import log_action
from ..services.email import notifier_statut_permission
from .decorators import (
    dept_a_premier_valideur,
    get_departement_responsable,
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
def liste_permissions(request):
    """Liste paginée des demandes de permission (triple audience).

    Accès : tout utilisateur connecté.
    - RH / Admin / DAF → toutes les permissions, template permissions/liste.html.
    - Responsable de département → permissions de son département uniquement.
    - Employé → ses propres permissions, template espace_employe/mes_permissions.html.
    GET params : statut (en_attente / valide_responsable / approuve / refuse).
    Pagination : 20 par page. Calcul des droits de traitement sur la page courante uniquement.
    """
    statut      = request.GET.get('statut', '')
    permissions = Permission.objects.select_related('employe__departement').all()

    user = request.user
    if is_rh(user):
        pass  # voit tout
    elif is_responsable(user):
        dept = get_departement_responsable(user)
        permissions = permissions.filter(employe__departement=dept) if dept else Permission.objects.none()
    else:
        try:
            employe     = user.employe
            permissions = permissions.filter(employe=employe)
        except Employe.DoesNotExist:
            permissions = Permission.objects.none()

    if statut:
        permissions = permissions.filter(statut=statut)

    permissions, page_range = paginer(permissions, request)

    # Calcule quelles permissions l'utilisateur peut traiter (étape 1 ou 2)
    # Itère sur la page courante uniquement pour éviter un full-scan
    peut_premier_ids = set()
    peut_final_ids   = set()
    if is_rh(user) or is_responsable(user):
        for p in permissions:
            if p.statut == 'en_attente' and peut_faire_premiere_validation(user, p.employe):
                # Étape 1 : responsable valide son département — pas de règle croisée
                peut_premier_ids.add(p.pk)
            elif p.statut == 'en_attente' and is_rh(user) and not dept_a_premier_valideur(p.employe):
                # Pas de responsable désigné → RH/DAF valide directement (règle croisée)
                if peut_valider_pour(user, p.employe):
                    peut_final_ids.add(p.pk)
            elif p.statut == 'valide_responsable' and is_rh(user):
                # Étape 2 : DRH/DAF valide après le responsable (règle croisée)
                if peut_valider_pour(user, p.employe):
                    peut_final_ids.add(p.pk)

    context = {
        'permissions':        permissions,
        'page_range':         page_range,
        'params':             get_params(request),
        'statut_selectionne': statut,
        'peut_premier_ids':   peut_premier_ids,
        'peut_final_ids':     peut_final_ids,
    }
    if not (is_rh(user) or is_responsable(user)):
        return render(request, 'SYGEPE/espace_employe/mes_permissions.html', context)
    return render(request, 'SYGEPE/permissions/liste.html', context)


@login_required
def demander_permission(request):
    """Formulaire de demande de permission (employé ou RH pour lui-même).

    Accès : tout utilisateur connecté ayant un profil employé.
    Redirige vers liste_permissions après soumission réussie.
    """
    employe = get_employe_or_none(request.user)

    if request.method == 'POST':
        form = PermissionForm(request.POST, employe=employe)
        if form.is_valid():
            perm = form.save(commit=False)
            if not employe:
                messages.error(request, "Votre profil employé n'existe pas. Contactez l'administrateur.")
                return redirect('sygepe:liste_permissions')
            perm.employe = employe
            with transaction.atomic():
                perm.save()
                log_action(
                    request, 'permission_demande',
                    f"Demande de permission du {perm.date_debut} au {perm.date_fin}",
                    employe=employe,
                )
            messages.success(request, "Demande de permission soumise avec succès.")
            return redirect('sygepe:liste_permissions')
    else:
        form = PermissionForm(employe=employe)

    if not is_rh(request.user):
        return render(request, 'SYGEPE/espace_employe/form_permission.html', {'form': form})
    return render(request, 'SYGEPE/permissions/form.html', {'form': form})


@login_required
def valider_permission(request, pk):
    """Validation en deux étapes : responsable/DAF (étape 1) → DRH (étape 2)."""
    perm = get_object_or_404(Permission, pk=pk)
    user = request.user

    # Règle croisée RH/DAF : pour un employé RH ou DAF, validation directe
    # par le rôle opposé uniquement (bypass du circuit responsable)
    employe_role = getattr(perm.employe, 'role', None)
    etape = None

    if employe_role in ('rh', 'daf'):
        if not peut_valider_pour(user, perm.employe):
            raise PermissionDenied
        if perm.statut not in ('en_attente', 'valide_responsable'):
            raise PermissionDenied
        etape = 2  # Validation directe, pas de circuit responsable
    else:
        # Circuit normal 2 étapes
        if perm.statut == 'en_attente':
            if peut_faire_premiere_validation(user, perm.employe):
                etape = 1
            elif is_rh(user) and not dept_a_premier_valideur(perm.employe):
                etape = 2
        elif perm.statut == 'valide_responsable' and is_rh(user):
            etape = 2

    if etape is None:
        raise PermissionDenied

    if request.method == 'POST':
        form = ValidationPermissionForm(request.POST, instance=perm, step=etape)
        if form.is_valid():
            p = form.save(commit=False)
            if etape == 1:
                p.valideur_responsable        = user
                p.date_validation_responsable = timezone.now()
                action_key = 'permission_approuve' if p.statut == 'valide_responsable' else 'permission_refuse'
                statut_msg = "transmise à la DRH" if p.statut == 'valide_responsable' else "refusée"
            else:
                p.valideur        = user
                p.date_validation = timezone.now()
                action_key = 'permission_approuve' if p.statut == 'approuve' else 'permission_refuse'
                statut_msg = p.get_statut_display().lower()

            with transaction.atomic():
                p.save()
                log_action(
                    request, action_key,
                    f"Permission de {p.employe.get_full_name()} du {p.date_debut} au {p.date_fin} "
                    f"(étape {etape}) : {statut_msg}",
                    employe=p.employe,
                )
            notifier_statut_permission(p)  # e-mail hors transaction (fail silencieux)
            messages.success(request, f"Permission {statut_msg}.")
            return redirect('sygepe:liste_permissions')
    else:
        form = ValidationPermissionForm(instance=perm, step=etape)

    context = {
        'form':       form,
        'permission': perm,
        'etape':      etape,
    }
    return render(request, 'SYGEPE/permissions/valider.html', context)


@login_required
def mes_permissions_perso(request):
    """Permissions personnelles de l'utilisateur connecté — mode employé forcé.

    Utilisé par RH/DAF/Admin qui ont une fiche Employe et veulent voir
    uniquement leurs propres permissions (espace employé), indépendamment de leur rôle.
    """
    employe = get_employe_or_none(request.user)
    if not employe:
        return redirect('sygepe:profil')

    statut = request.GET.get('statut', '')
    permissions = Permission.objects.filter(employe=employe).select_related('employe__departement')
    if statut:
        permissions = permissions.filter(statut=statut)

    permissions, page_range = paginer(permissions, request)
    return render(request, 'SYGEPE/espace_employe/mes_permissions.html', {
        'permissions':       permissions,
        'page_range':        page_range,
        'params':            get_params(request),
        'statut_selectionne': statut,
    })
