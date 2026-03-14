"""Vue historique des actions RH SYGEPE."""

from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from ..models import ActionLog
from .decorators import get_departement_responsable, rh_ou_responsable_requis


@rh_ou_responsable_requis
def historique_actions(request):
    """Liste paginée du journal des actions RH (ActionLog).

    Accès : RH / Admin / DAF / responsable de département.
    Les responsables voient uniquement les actions concernant leur département.
    GET params : q (recherche dans description, username, nom/prénom employé), page.
    Pagination : 30 entrées par page (via Paginator Django standard).
    """
    logs = ActionLog.objects.select_related('utilisateur', 'employe').order_by('-date')

    dept = get_departement_responsable(request.user)
    if dept:
        logs = logs.filter(employe__departement=dept)

    q = request.GET.get('q', '')
    if q:
        logs = logs.filter(
            Q(description__icontains=q) |
            Q(utilisateur__username__icontains=q) |
            Q(employe__nom__icontains=q) |
            Q(employe__prenom__icontains=q)
        )
    paginator = Paginator(logs, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'SYGEPE/historique_actions.html', {'page_obj': page, 'q': q})
