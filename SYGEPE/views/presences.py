"""Vues de gestion des présences SYGEPE."""

from datetime import date

from django.contrib import messages
from django.shortcuts import redirect, render

from ..forms import PresenceForm
from ..models import Employe, Presence
from .decorators import get_departement_responsable, get_params, paginer, rh_ou_responsable_requis, rh_requis


@rh_ou_responsable_requis
def liste_presences(request):
    """Liste paginée des présences avec filtres date et employé.

    Accès : RH / Admin / DAF / responsable de département.
    Les responsables voient uniquement les présences de leur département.
    GET params : date (ISO YYYY-MM-DD, défaut aujourd'hui), employe (pk).
    Pagination : 50 par page.
    """
    date_filtre = request.GET.get('date', str(date.today()))
    employe_id  = request.GET.get('employe', '')

    presences = Presence.objects.select_related('employe').all()
    employes  = Employe.objects.filter(statut='actif')

    dept = get_departement_responsable(request.user)
    if dept:
        presences = presences.filter(employe__departement=dept)
        employes  = employes.filter(departement=dept)

    if date_filtre:
        presences = presences.filter(date=date_filtre)
    if employe_id:
        presences = presences.filter(employe__id=employe_id)

    presences, page_range = paginer(presences, request, par_page=50)
    context = {
        'presences': presences,
        'page_range': page_range,
        'params': get_params(request),
        'employes': employes,
        'date_filtre': date_filtre,
        'employe_selectionne': employe_id,
    }
    return render(request, 'SYGEPE/presences/liste.html', context)


@rh_ou_responsable_requis
def marquer_presence(request):
    """Formulaire de saisie d'une présence.

    Accès : RH / Admin / DAF / responsable de département.
    Les responsables ne peuvent saisir que pour les employés actifs de leur département.
    Redirige vers liste_presences après enregistrement.
    """
    dept = get_departement_responsable(request.user)

    if request.method == 'POST':
        form = PresenceForm(request.POST)
        if dept:
            form.fields['employe'].queryset = Employe.objects.filter(statut='actif', departement=dept)
        if form.is_valid():
            presence = form.save(commit=False)
            presence.enregistre_par = request.user
            presence.save()
            messages.success(request, "Présence enregistrée.")
            return redirect('sygepe:liste_presences')
    else:
        form = PresenceForm(initial={'date': date.today()})
        if dept:
            form.fields['employe'].queryset = Employe.objects.filter(statut='actif', departement=dept)

    return render(request, 'SYGEPE/presences/form.html', {'form': form})
