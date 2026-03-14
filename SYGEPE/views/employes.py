"""Vues de gestion des employés SYGEPE."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import EmployeForm
from ..models import Departement, Employe
from ..services.audit import log_action
from .decorators import admin_requis, get_departement_responsable, get_params, is_rh, paginer, rh_ou_responsable_requis, rh_requis


@rh_ou_responsable_requis
def liste_employes(request):
    """Liste paginée des employés avec recherche et filtres.

    Accès : RH / Admin / DAF (tous les employés) ou responsable de département
    (limité à son propre département — filtre automatique).
    GET params : q (recherche nom/prénom/matricule), departement (id), statut.
    Pagination : 20 par page.
    """
    q      = request.GET.get('q', '')
    dept   = request.GET.get('departement', '')
    statut = request.GET.get('statut', '')

    employes = Employe.objects.select_related('departement').all()

    # Responsable de département : limité à son propre département
    dept_responsable = get_departement_responsable(request.user)
    if dept_responsable:
        employes = employes.filter(departement=dept_responsable)
        departements = [dept_responsable]
    else:
        departements = Departement.objects.all()
        if dept:
            employes = employes.filter(departement__id=dept)

    if q:
        employes = employes.filter(
            Q(nom__icontains=q) | Q(prenom__icontains=q) | Q(matricule__icontains=q)
        )
    if statut:
        employes = employes.filter(statut=statut)

    employes, page_range = paginer(employes, request)
    context = {
        'employes': employes,
        'page_range': page_range,
        'params': get_params(request),
        'departements': departements,
        'q': q,
        'dept_selectionne': dept,
        'statut_selectionne': statut,
        'vue_filtree': dept_responsable is not None,
    }
    return render(request, 'SYGEPE/employes/liste.html', context)


@rh_ou_responsable_requis
def detail_employe(request, pk):
    """Fiche détaillée d'un employé (présences récentes, congés, permissions).

    Accès : RH / Admin / DAF ou responsable de département.
    Un responsable ne peut consulter qu'un employé de son département (403 sinon).
    """
    employe = get_object_or_404(Employe, pk=pk)

    # Responsable : ne peut voir qu'un employé de son département
    dept_responsable = get_departement_responsable(request.user)
    if dept_responsable and employe.departement != dept_responsable:
        raise PermissionDenied

    context = {
        'employe': employe,
        'presences_recentes': employe.presences.order_by('-date')[:10],
        'conges_recents': employe.conges.order_by('-date_demande')[:5],
        'permissions_recentes': employe.permissions.order_by('-date_demande')[:5],
    }
    return render(request, 'SYGEPE/employes/detail.html', context)


@rh_requis
def ajouter_employe(request):
    """Formulaire de création d'un employé (RH uniquement).

    Accès : RH / Admin / DAF (403 sinon).
    Enregistre une action dans l'audit trail via log_action().
    Redirige vers la liste des employés après succès.
    """
    if request.method == 'POST':
        form = EmployeForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                employe = form.save()
                log_action(request, 'employe_ajoute',
                           f"Ajout de l'employé {employe.get_full_name()} ({employe.matricule})",
                           employe=employe)
            messages.success(request, "Employé ajouté avec succès.")
            return redirect('sygepe:liste_employes')
    else:
        form = EmployeForm()
    return render(request, 'SYGEPE/employes/form.html',
                  {'form': form, 'titre': 'Ajouter un employé'})


@rh_requis
def modifier_employe(request, pk):
    """Formulaire de modification d'un employé existant (RH uniquement).

    Accès : RH / Admin / DAF (403 sinon).
    Enregistre une action dans l'audit trail.
    Redirige vers la fiche détaillée après succès.
    """
    employe = get_object_or_404(Employe, pk=pk)
    if request.method == 'POST':
        form = EmployeForm(request.POST, request.FILES, instance=employe)
        if form.is_valid():
            with transaction.atomic():
                form.save()
                log_action(request, 'employe_modifie',
                           f"Modification de l'employé {employe.get_full_name()} ({employe.matricule})",
                           employe=employe)
            messages.success(request, "Employé modifié avec succès.")
            return redirect('sygepe:detail_employe', pk=pk)
    else:
        form = EmployeForm(instance=employe)
    return render(request, 'SYGEPE/employes/form.html',
                  {'form': form, 'titre': "Modifier l'employé", 'employe': employe})


@admin_requis
def supprimer_employe(request, pk):
    """Page de confirmation puis suppression d'un employé (Admin uniquement).

    Accès : Admin uniquement (403 pour RH/DAF).
    GET → page de confirmation. POST → suppression effective avec log_action().
    """
    employe = get_object_or_404(Employe, pk=pk)
    if request.method == 'POST':
        with transaction.atomic():
            log_action(request, 'employe_supprime',
                       f"Suppression de l'employé {employe.get_full_name()} ({employe.matricule})")
            employe.delete()
        messages.success(request, "Employé supprimé.")
        return redirect('sygepe:liste_employes')
    return render(request, 'SYGEPE/employes/confirmer_suppression.html', {'employe': employe})
