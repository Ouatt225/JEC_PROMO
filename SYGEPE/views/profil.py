"""Vues de profil employé SYGEPE (espace personnel + téléchargement PDF)."""

from datetime import date

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache

from ..forms import EmployeProfilForm
from ..models import Employe
from ..services.pdf import generer_pdf_profil
from .decorators import get_employe_or_none, is_rh, rh_requis


@never_cache
@login_required
def profil(request):
    """Affiche le profil de l'utilisateur connecté avec son solde de congés.

    Accès : tout utilisateur connecté.
    Vérifie la cohérence session/user (protection contre le détournement de session).
    - RH / Admin / DAF → template profil.html (espace RH).
    - Employé → template espace_employe/profil.html.
    """
    session_uid = request.session.get('_auth_user_id')
    if not session_uid or str(request.user.pk) != str(session_uid):
        logout(request)
        return redirect('sygepe:login')

    employe = get_employe_or_none(request.user)
    ctx = {'employe': employe}
    if employe:
        annee              = date.today().year
        jours_pris         = employe.jours_conge_pris(annee)
        ctx['solde_conge'] = max(0, settings.QUOTA_CONGES_ANNUELS - jours_pris)
        ctx['jours_pris']  = jours_pris
        ctx['quota_total'] = settings.QUOTA_CONGES_ANNUELS
        ctx['annee']       = annee

    if not is_rh(request.user):
        return render(request, 'SYGEPE/espace_employe/profil.html', ctx)
    return render(request, 'SYGEPE/profil.html', ctx)


@login_required
def modifier_profil_employe(request):
    """Permet à un employé de modifier ses informations personnelles."""
    try:
        employe = request.user.employe
    except Employe.DoesNotExist:
        messages.error(request, "Aucun profil employé associé à votre compte.")
        return redirect('sygepe:profil')

    if request.method == 'POST':
        form = EmployeProfilForm(request.POST, request.FILES, instance=employe)
        if form.is_valid():
            form.save()
            messages.success(request, "Votre profil a été mis à jour avec succès.")
            return redirect('sygepe:profil')
    else:
        form = EmployeProfilForm(instance=employe)

    return render(request, 'SYGEPE/espace_employe/modifier_profil.html',
                  {'form': form, 'employe': employe})


@login_required
def changer_mot_de_passe(request):
    """Formulaire de changement de mot de passe (utilisateur connecté uniquement).

    Accès : tout utilisateur connecté.
    update_session_auth_hash maintient la session courante active et invalide
    automatiquement toutes les autres sessions (autres appareils) via le mécanisme
    de hash de session Django (AuthenticationMiddleware détecte le mismatch).
    - RH / Admin / DAF → template changer_mot_de_passe.html.
    - Employé → template espace_employe/changer_mot_de_passe.html.
    """
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Votre mot de passe a été modifié avec succès.")
            return redirect('sygepe:profil')
    else:
        form = PasswordChangeForm(request.user)

    if not is_rh(request.user):
        return render(request, 'SYGEPE/espace_employe/changer_mot_de_passe.html', {'form': form})
    return render(request, 'SYGEPE/changer_mot_de_passe.html', {'form': form})


@never_cache
@login_required
def telecharger_profil(request):
    """Téléchargement du profil PDF par l'employé lui-même."""
    try:
        employe = request.user.employe
    except Employe.DoesNotExist:
        messages.error(request, "Aucun profil employé associé à votre compte.")
        return redirect('sygepe:profil')
    return generer_pdf_profil(employe)


@never_cache
@rh_requis
def telecharger_profil_employe(request, pk):
    """Téléchargement du profil PDF d'un employé par la RH ou la DAF."""
    employe = get_object_or_404(Employe, pk=pk)
    return generer_pdf_profil(employe)
