"""Vues d'authentification SYGEPE."""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django_ratelimit.decorators import ratelimit
from django_ratelimit.exceptions import Ratelimited

from .decorators import is_responsable, is_rh


# Helper dédié uniquement à la vérification du rate limit (block=True).
# Appelé explicitement dans login_view avec try/except Ratelimited,
# ce qui permet de :
#   1. bloquer au niveau du décorateur (avant tout code de la vue)
#   2. tout en affichant un message d'erreur personnalisé sur le formulaire.
@ratelimit(key='ip', rate=settings.LOGIN_RATE_LIMIT, method='POST', block=True)
def _check_login_rate(request):
    pass


def csrf_failure(request, reason=""):
    """Intercepte les erreurs 403 CSRF et redirige vers login avec message."""
    request.session.pop('_csrftoken', None)
    request.session.modified = True
    messages.warning(request, "Votre session a expiré. Reconnectez-vous pour continuer.")
    return redirect('sygepe:login')


@never_cache
def root_view(request):
    """URL racine : déconnecte toujours avant d'afficher le login."""
    if request.user.is_authenticated:
        logout(request)
    return redirect('sygepe:login')


@never_cache
def login_view(request):
    """Affiche et traite le formulaire de connexion.

    Accès : public (non authentifié).
    Rate-limit : LOGIN_RATE_LIMIT tentatives par minute et par IP (django-ratelimit,
    block=True). Le blocage est imposé au niveau du décorateur de _check_login_rate,
    avant tout traitement des identifiants. L'exception Ratelimited est catchée ici
    pour afficher un message d'erreur lisible sur le formulaire.
    Redirige vers `next` si fourni, sinon vers le dashboard (RH/responsable)
    ou le profil employé selon le rôle.
    """
    next_url = request.GET.get('next') or request.POST.get('next', '')

    if request.user.is_authenticated:
        if next_url:
            return redirect(next_url)
        logout(request)

    if request.method == 'POST':
        # Blocage brute-force : lève Ratelimited si l'IP dépasse la limite.
        # Avec block=True, aucun code ci-dessous n'est atteint en cas de dépassement.
        try:
            _check_login_rate(request)
        except Ratelimited:
            messages.error(
                request,
                "Trop de tentatives de connexion. Veuillez patienter 1 minute avant de réessayer.",
            )
            return render(request, 'SYGEPE/login.html', {'next': next_url})

        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        if not username or not password:
            messages.error(request, "Veuillez remplir tous les champs.")
        else:
            user = authenticate(request, username=username, password=password)
            if user:
                request.session.flush()
                login(request, user)
                default = 'sygepe:dashboard' if (is_rh(user) or is_responsable(user)) else 'sygepe:profil'
                return redirect(next_url or default)
            else:
                messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")
    return render(request, 'SYGEPE/login.html', {'next': next_url})


@login_required
def logout_view(request):
    """Déconnecte l'utilisateur (POST uniquement) et redirige vers login.

    Accès : tout utilisateur authentifié.
    Seul le POST est traité — un GET laisse la session intacte.
    Les templates utilisent un <form method="post"> + {% csrf_token %}.
    """
    if request.method == 'POST':
        logout(request)
    return redirect('sygepe:login')
