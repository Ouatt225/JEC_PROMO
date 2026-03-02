from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.views.decorators.cache import never_cache
from django.http import HttpResponse, JsonResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import os
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.db.models import Count, Q
from datetime import date, timedelta
from functools import wraps
import json

from .models import Employe, Departement, Presence, Conge, Permission, Boutique
from .forms import (
    EmployeForm, EmployeProfilForm, DepartementForm, PresenceForm,
    CongeForm, ValidationCongeForm, PermissionForm, ValidationPermissionForm,
    BoutiqueForm
)


# ─────────────────────────────────────────────
# Helpers de rôles
# ─────────────────────────────────────────────
def is_admin(user):
    return user.is_superuser or user.groups.filter(name='Admin').exists()


def is_rh(user):
    return user.is_superuser or user.groups.filter(name__in=['Admin', 'RH', 'DAF']).exists()


def rh_requis(f):
    """Décorateur : accès réservé aux rôles RH et Admin. Lève 403 si refusé."""
    @wraps(f)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not is_rh(request.user):
            raise PermissionDenied
        return f(request, *args, **kwargs)
    return wrapper


def admin_requis(f):
    """Décorateur : accès réservé aux Admins uniquement. Lève 403 si refusé."""
    @wraps(f)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not is_admin(request.user):
            raise PermissionDenied
        return f(request, *args, **kwargs)
    return wrapper


# ─────────────────────────────────────────────
# Gestion d'échec CSRF — redirige proprement
# ─────────────────────────────────────────────
def csrf_failure(request, reason=""):
    """Intercepte les erreurs 403 CSRF et redirige vers login avec un message clair."""
    # Purge le token CSRF périmé pour forcer un nouveau token au prochain GET
    request.session.pop('_csrftoken', None)
    request.session.modified = True
    messages.warning(
        request,
        "Votre session a expiré. Reconnectez-vous pour continuer."
    )
    return redirect('login')


# ─────────────────────────────────────────────
# Authentification
# ─────────────────────────────────────────────
@never_cache
def root_view(request):
    """URL racine : déconnecte toujours avant d'afficher le login."""
    if request.user.is_authenticated:
        logout(request)
    return redirect('login')


def login_view(request):
    next_url = request.GET.get('next') or request.POST.get('next', '')

    if request.user.is_authenticated:
        if next_url:
            # Redirigé par @login_required → OK, on garde la session
            return redirect(next_url)
        # Accès direct à /login/ → on déconnecte l'ancien compte
        # pour permettre à quelqu'un d'autre de se connecter
        logout(request)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        if not username or not password:
            messages.error(request, "Veuillez remplir tous les champs.")
        else:
            user = authenticate(request, username=username, password=password)
            if user:
                # Vider l'ancienne session avant de créer la nouvelle
                request.session.flush()
                login(request, user)
                default = 'profil' if not is_rh(user) else 'dashboard'
                return redirect(next_url or default)
            else:
                messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")
    return render(request, 'SYGEPE/login.html', {'next': next_url})


@login_required
def logout_view(request):
    logout(request)
    return redirect('login')


# ─────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────
@never_cache
@login_required
def dashboard(request):
    if not is_rh(request.user):
        return redirect('profil')
    today = date.today()

    total_employes = Employe.objects.filter(statut='actif').count()
    presences_aujourd_hui = Presence.objects.filter(date=today, statut='present').count()
    conges_en_attente = Conge.objects.filter(statut='en_attente').count()
    permissions_en_attente = Permission.objects.filter(statut='en_attente').count()

    # Présences des 6 derniers mois
    labels_presences = []
    data_presences = []
    for i in range(5, -1, -1):
        mois = today.replace(day=1) - timedelta(days=i * 30)
        label = mois.strftime('%b %Y')
        count = Presence.objects.filter(
            date__year=mois.year,
            date__month=mois.month,
            statut='present'
        ).count()
        labels_presences.append(label)
        data_presences.append(count)

    # Employés par département
    depts = Departement.objects.annotate(nb=Count('employes')).filter(nb__gt=0)
    labels_dept = [d.nom for d in depts]
    data_dept = [d.nb for d in depts]

    # Dernières demandes (congés + permissions)
    derniers_conges = Conge.objects.select_related('employe').order_by('-date_demande')[:5]
    dernieres_permissions = Permission.objects.select_related('employe').order_by('-date_demande')[:5]

    context = {
        'total_employes': total_employes,
        'presences_aujourd_hui': presences_aujourd_hui,
        'conges_en_attente': conges_en_attente,
        'permissions_en_attente': permissions_en_attente,
        'labels_presences': json.dumps(labels_presences),
        'data_presences': json.dumps(data_presences),
        'labels_dept': json.dumps(labels_dept),
        'data_dept': json.dumps(data_dept),
        'derniers_conges': derniers_conges,
        'dernieres_permissions': dernieres_permissions,
        'today': today,
    }
    return render(request, 'SYGEPE/dashboard.html', context)


# ─────────────────────────────────────────────
# Employés
# ─────────────────────────────────────────────
@login_required
def liste_employes(request):
    if not is_rh(request.user):
        return redirect('profil')
    q = request.GET.get('q', '')
    dept = request.GET.get('departement', '')
    statut = request.GET.get('statut', '')

    employes = Employe.objects.select_related('departement').all()
    if q:
        employes = employes.filter(
            Q(nom__icontains=q) | Q(prenom__icontains=q) | Q(matricule__icontains=q)
        )
    if dept:
        employes = employes.filter(departement__id=dept)
    if statut:
        employes = employes.filter(statut=statut)

    departements = Departement.objects.all()
    context = {
        'employes': employes,
        'departements': departements,
        'q': q,
        'dept_selectionne': dept,
        'statut_selectionne': statut,
    }
    return render(request, 'SYGEPE/employes/liste.html', context)


@login_required
def detail_employe(request, pk):
    if not is_rh(request.user):
        return redirect('profil')
    employe = get_object_or_404(Employe, pk=pk)
    presences_recentes = employe.presences.order_by('-date')[:10]
    conges_recents = employe.conges.order_by('-date_demande')[:5]
    permissions_recentes = employe.permissions.order_by('-date_demande')[:5]
    context = {
        'employe': employe,
        'presences_recentes': presences_recentes,
        'conges_recents': conges_recents,
        'permissions_recentes': permissions_recentes,
    }
    return render(request, 'SYGEPE/employes/detail.html', context)


@rh_requis
def ajouter_employe(request):
    if request.method == 'POST':
        form = EmployeForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Employé ajouté avec succès.")
            return redirect('liste_employes')
    else:
        form = EmployeForm()
    return render(request, 'SYGEPE/employes/form.html', {'form': form, 'titre': 'Ajouter un employé'})


@rh_requis
def modifier_employe(request, pk):
    employe = get_object_or_404(Employe, pk=pk)
    if request.method == 'POST':
        form = EmployeForm(request.POST, request.FILES, instance=employe)
        if form.is_valid():
            form.save()
            messages.success(request, "Employé modifié avec succès.")
            return redirect('detail_employe', pk=pk)
    else:
        form = EmployeForm(instance=employe)
    return render(request, 'SYGEPE/employes/form.html', {'form': form, 'titre': 'Modifier l\'employé', 'employe': employe})


@admin_requis
def supprimer_employe(request, pk):
    employe = get_object_or_404(Employe, pk=pk)
    if request.method == 'POST':
        employe.delete()
        messages.success(request, "Employé supprimé.")
        return redirect('liste_employes')
    return render(request, 'SYGEPE/employes/confirmer_suppression.html', {'employe': employe})


# ─────────────────────────────────────────────
# Présences
# ─────────────────────────────────────────────
@login_required
def liste_presences(request):
    if not is_rh(request.user):
        return redirect('profil')
    date_filtre = request.GET.get('date', str(date.today()))
    employe_id = request.GET.get('employe', '')

    presences = Presence.objects.select_related('employe').all()
    if date_filtre:
        presences = presences.filter(date=date_filtre)
    if employe_id:
        presences = presences.filter(employe__id=employe_id)

    employes = Employe.objects.filter(statut='actif')
    context = {
        'presences': presences,
        'employes': employes,
        'date_filtre': date_filtre,
        'employe_selectionne': employe_id,
    }
    return render(request, 'SYGEPE/presences/liste.html', context)


@rh_requis
def marquer_presence(request):
    if request.method == 'POST':
        form = PresenceForm(request.POST)
        if form.is_valid():
            presence = form.save(commit=False)
            presence.enregistre_par = request.user
            presence.save()
            messages.success(request, "Présence enregistrée.")
            return redirect('liste_presences')
    else:
        form = PresenceForm(initial={'date': date.today()})
    return render(request, 'SYGEPE/presences/form.html', {'form': form})


# ─────────────────────────────────────────────
# Congés
# ─────────────────────────────────────────────
@login_required
def liste_conges(request):
    statut = request.GET.get('statut', '')
    conges = Conge.objects.select_related('employe').all()

    if not is_rh(request.user):
        try:
            employe = request.user.employe
            conges = conges.filter(employe=employe)
        except Employe.DoesNotExist:
            conges = Conge.objects.none()

    if statut:
        conges = conges.filter(statut=statut)

    context = {'conges': conges, 'statut_selectionne': statut}
    if not is_rh(request.user):
        return render(request, 'SYGEPE/espace_employe/mes_conges.html', context)
    return render(request, 'SYGEPE/conges/liste.html', context)


@login_required
def demander_conge(request):
    try:
        employe = request.user.employe
    except Employe.DoesNotExist:
        employe = None

    # Calcul du quota de congés payés pour l'année en cours
    annee = date.today().year
    solde_conge = 30
    jours_pris = 0
    if employe:
        jours_pris = sum(
            (c.date_fin - c.date_debut).days + 1
            for c in employe.conges.filter(
                type_conge='paye',
                date_debut__year=annee,
                statut__in=['en_attente', 'approuve'],
            )
        )
        solde_conge = max(0, 30 - jours_pris)

    if request.method == 'POST':
        form = CongeForm(request.POST, employe=employe)
        if form.is_valid():
            conge = form.save(commit=False)
            if not employe:
                messages.error(request, "Votre profil employé n'existe pas. Contactez l'administrateur.")
                return redirect('liste_conges')
            conge.employe = employe
            conge.save()
            messages.success(request, "Demande de congé soumise avec succès.")
            return redirect('liste_conges')
    else:
        form = CongeForm(employe=employe)

    ctx = {
        'form': form,
        'solde_conge': solde_conge,
        'jours_pris': jours_pris,
        'annee': annee,
    }
    if not is_rh(request.user):
        return render(request, 'SYGEPE/espace_employe/form_conge.html', ctx)
    return render(request, 'SYGEPE/conges/form.html', ctx)


@rh_requis
def valider_conge(request, pk):
    conge = get_object_or_404(Conge, pk=pk)
    if request.method == 'POST':
        form = ValidationCongeForm(request.POST, instance=conge)
        if form.is_valid():
            c = form.save(commit=False)
            c.valideur = request.user
            c.date_validation = timezone.now()
            c.save()
            messages.success(request, f"Congé {c.get_statut_display().lower()}.")
            return redirect('liste_conges')
    else:
        form = ValidationCongeForm(instance=conge)
    return render(request, 'SYGEPE/conges/valider.html', {'form': form, 'conge': conge})


# ─────────────────────────────────────────────
# Permissions
# ─────────────────────────────────────────────
@login_required
def liste_permissions(request):
    statut = request.GET.get('statut', '')
    permissions = Permission.objects.select_related('employe').all()

    if not is_rh(request.user):
        try:
            employe = request.user.employe
            permissions = permissions.filter(employe=employe)
        except Employe.DoesNotExist:
            permissions = Permission.objects.none()

    if statut:
        permissions = permissions.filter(statut=statut)

    context = {'permissions': permissions, 'statut_selectionne': statut}
    if not is_rh(request.user):
        return render(request, 'SYGEPE/espace_employe/mes_permissions.html', context)
    return render(request, 'SYGEPE/permissions/liste.html', context)


@login_required
def demander_permission(request):
    if request.method == 'POST':
        form = PermissionForm(request.POST)
        if form.is_valid():
            perm = form.save(commit=False)
            try:
                perm.employe = request.user.employe
            except Employe.DoesNotExist:
                messages.error(request, "Votre profil employé n'existe pas. Contactez l'administrateur.")
                return redirect('liste_permissions')
            perm.save()
            messages.success(request, "Demande de permission soumise avec succès.")
            return redirect('liste_permissions')
    else:
        form = PermissionForm()
    if not is_rh(request.user):
        return render(request, 'SYGEPE/espace_employe/form_permission.html', {'form': form})
    return render(request, 'SYGEPE/permissions/form.html', {'form': form})


@rh_requis
def valider_permission(request, pk):
    perm = get_object_or_404(Permission, pk=pk)
    if request.method == 'POST':
        form = ValidationPermissionForm(request.POST, instance=perm)
        if form.is_valid():
            p = form.save(commit=False)
            p.valideur = request.user
            p.date_validation = timezone.now()
            p.save()
            messages.success(request, f"Permission {p.get_statut_display().lower()}.")
            return redirect('liste_permissions')
    else:
        form = ValidationPermissionForm(instance=perm)
    return render(request, 'SYGEPE/permissions/valider.html', {'form': form, 'permission': perm})


# ─────────────────────────────────────────────
# Profil
# ─────────────────────────────────────────────
@never_cache
@login_required
def profil(request):
    # Vérification explicite : la session doit appartenir à l'utilisateur actuel
    session_uid = request.session.get('_auth_user_id')
    if not session_uid or str(request.user.pk) != str(session_uid):
        logout(request)
        return redirect('login')
    try:
        employe = request.user.employe
    except Employe.DoesNotExist:
        employe = None
    # Employé ordinaire → Espace Contractuel
    if not is_rh(request.user):
        return render(request, 'SYGEPE/espace_employe/profil.html', {'employe': employe})
    return render(request, 'SYGEPE/profil.html', {'employe': employe})


@login_required
def modifier_profil_employe(request):
    """Permet à un employé de modifier ses informations personnelles."""
    try:
        employe = request.user.employe
    except Employe.DoesNotExist:
        messages.error(request, "Aucun profil employé associé à votre compte.")
        return redirect('profil')

    if request.method == 'POST':
        form = EmployeProfilForm(request.POST, request.FILES, instance=employe)
        if form.is_valid():
            form.save()
            messages.success(request, "Votre profil a été mis à jour avec succès.")
            return redirect('profil')
    else:
        form = EmployeProfilForm(instance=employe)

    return render(request, 'SYGEPE/espace_employe/modifier_profil.html', {
        'form': form,
        'employe': employe,
    })


# ─────────────────────────────────────────────
# Boutiques
# ─────────────────────────────────────────────
@login_required
def liste_boutiques(request):
    if not is_rh(request.user):
        return redirect('profil')
    q = request.GET.get('q', '')
    boutiques = Boutique.objects.prefetch_related('employes').select_related('responsable').all()
    if q:
        boutiques = boutiques.filter(nom__icontains=q)
    context = {
        'boutiques': boutiques,
        'q': q,
        'total_boutiques': Boutique.objects.count(),
        'total_employes_boutiques': Employe.objects.filter(boutique__isnull=False, statut='actif').count(),
    }
    return render(request, 'SYGEPE/boutiques/liste.html', context)


@login_required
def detail_boutique(request, pk):
    boutique = get_object_or_404(Boutique, pk=pk)
    employes = boutique.employes.filter(statut='actif').select_related('departement')
    context = {'boutique': boutique, 'employes': employes}
    return render(request, 'SYGEPE/boutiques/detail.html', context)


@rh_requis
def ajouter_boutique(request):
    if request.method == 'POST':
        form = BoutiqueForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Boutique ajoutée avec succès.")
            return redirect('liste_boutiques')
    else:
        form = BoutiqueForm()
    return render(request, 'SYGEPE/boutiques/form.html', {'form': form, 'titre': 'Ajouter une boutique'})


@rh_requis
def modifier_boutique(request, pk):
    boutique = get_object_or_404(Boutique, pk=pk)
    if request.method == 'POST':
        form = BoutiqueForm(request.POST, instance=boutique)
        if form.is_valid():
            form.save()
            messages.success(request, "Boutique modifiée avec succès.")
            return redirect('detail_boutique', pk=pk)
    else:
        form = BoutiqueForm(instance=boutique)
    return render(request, 'SYGEPE/boutiques/form.html', {'form': form, 'titre': 'Modifier la boutique', 'boutique': boutique})


@admin_requis
def supprimer_boutique(request, pk):
    boutique = get_object_or_404(Boutique, pk=pk)
    if request.method == 'POST':
        boutique.delete()
        messages.success(request, "Boutique supprimée.")
        return redirect('liste_boutiques')
    return render(request, 'SYGEPE/boutiques/confirmer_suppression.html', {'boutique': boutique})


# ─────────────────────────────────────────────
# Téléchargement du profil en PDF
# ─────────────────────────────────────────────
def _generer_pdf_profil(employe):
    """Génère et retourne une HttpResponse PDF pour un employé donné."""
    from datetime import datetime

    response = HttpResponse(content_type='application/pdf')
    nom_fichier = f"profil_{employe.matricule}_{employe.nom}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{nom_fichier}"'

    doc = SimpleDocTemplate(
        response, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )

    PAGE_W = A4[0] - 3*cm   # 21cm - 1.5cm * 2
    GREEN  = colors.HexColor('#2E7D32')
    ORANGE = colors.HexColor('#E65100')
    LGRAY  = colors.HexColor('#F5F5F5')

    styles = getSampleStyleSheet()

    titre_style = ParagraphStyle('Titre', parent=styles['Normal'],
                                 fontSize=16, fontName='Helvetica-Bold',
                                 textColor=GREEN, alignment=TA_CENTER, spaceAfter=1)
    sous_titre_style = ParagraphStyle('SousTitre', parent=styles['Normal'],
                                      fontSize=9, textColor=colors.black,
                                      alignment=TA_CENTER, spaceAfter=8)
    section_style = ParagraphStyle('Section', parent=styles['Normal'],
                                   fontSize=10, fontName='Helvetica-Bold',
                                   textColor=colors.white)
    lbl_style = ParagraphStyle('Lbl', parent=styles['Normal'],
                                fontSize=8.5, fontName='Helvetica-Bold',
                                textColor=colors.black)
    val_style = ParagraphStyle('Val', parent=styles['Normal'],
                                fontSize=8.5, textColor=ORANGE)
    mat_style = ParagraphStyle('Mat', parent=styles['Normal'],
                                fontSize=8, fontName='Helvetica-Bold',
                                textColor=GREEN, alignment=TA_CENTER)
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'],
                                   fontSize=7, textColor=colors.grey,
                                   alignment=TA_CENTER)

    elements = []

    # ── Titre ─────────────────────────────────────────────────────────
    elements.append(Paragraph("JEC PROMO", titre_style))
    elements.append(Paragraph("FICHE EMPLOYÉ", sous_titre_style))

    # ── Helpers ───────────────────────────────────────────────────────
    def section_header(titre):
        t = Table([[Paragraph(f"  {titre}", section_style)]], colWidths=[PAGE_W])
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, -1), GREEN),
            ('TOPPADDING',    (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING',   (0, 0), (-1, -1), 8),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
        ]))
        return t

    def v(val):
        if val is None or str(val).strip() == '':
            return '—'
        return str(val)

    def make_grid(data, col_widths):
        t = Table(data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('TOPPADDING',    (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING',   (0, 0), (-1, -1), 6),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, LGRAY]),
            ('LINEBELOW', (0, 0), (-1, -1), 0.3, colors.HexColor('#CCCCCC')),
        ]))
        return t

    def row4(l1, v1, l2='', v2=None):
        return [
            Paragraph(l1, lbl_style),
            Paragraph(v(v1), val_style),
            Paragraph(l2, lbl_style),
            Paragraph(v(v2) if l2 else '', val_style),
        ]

    # ══════════════════════════════════════════════════════════════════
    # SECTION 1 : INFORMATIONS GÉNÉRALES
    # ══════════════════════════════════════════════════════════════════
    elements.append(section_header("INFORMATIONS GÉNÉRALES"))

    PHOTO_W = 3.5 * cm
    GAP_W   = 0.3 * cm
    INFO_W  = PAGE_W - PHOTO_W - GAP_W
    LBL_W   = 4.5 * cm
    VAL_W   = INFO_W - LBL_W

    # Rows alongside the photo
    side_rows = []
    side_rows.append([Paragraph("Matricule :", lbl_style),
                       Paragraph(v(employe.matricule), val_style)])
    side_rows.append([Paragraph("Nom et Prénoms :", lbl_style),
                       Paragraph(employe.get_full_name().upper(), val_style)])
    if employe.date_naissance:
        side_rows.append([Paragraph("Date de Naissance :", lbl_style),
                           Paragraph(employe.date_naissance.strftime('%d/%m/%Y'), val_style)])
    if employe.lieu_naissance:
        side_rows.append([Paragraph("Lieu de Naissance :", lbl_style),
                           Paragraph(v(employe.lieu_naissance).upper(), val_style)])
    if employe.age:
        side_rows.append([Paragraph("Âge actuel :", lbl_style),
                           Paragraph(f"{employe.age} ans", val_style)])
    if employe.annee_retraite:
        side_rows.append([Paragraph("Année de Retraite :", lbl_style),
                           Paragraph(v(employe.annee_retraite), val_style)])

    info_left = make_grid(side_rows, [LBL_W, VAL_W])

    # Photo block
    if employe.photo:
        try:
            photo_elem = RLImage(employe.photo.path, width=PHOTO_W, height=4.5*cm)
        except Exception:
            photo_elem = Paragraph('', val_style)
    else:
        photo_elem = Paragraph('', val_style)

    photo_block = Table(
        [[photo_elem], [Paragraph(v(employe.matricule), mat_style)]],
        colWidths=[PHOTO_W],
    )
    photo_block.setStyle(TableStyle([
        ('TOPPADDING',    (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
        ('ALIGN',         (0, 1), (0, 1),   'CENTER'),
    ]))

    top_layout = Table([[info_left, photo_block]], colWidths=[INFO_W, PHOTO_W])
    top_layout.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(top_layout)

    # 4-column rows (no photo alongside)
    LBL2 = 3.5 * cm
    VAL2 = (PAGE_W - 2 * LBL2) / 2
    extra = []
    if employe.sexe:
        extra.append(row4("Sexe :", employe.get_sexe_display().upper(),
                          "Email :", employe.email))
    elif employe.email:
        extra.append(row4("Email :", employe.email))
    if employe.num_cnps:
        extra.append(row4("Numéro CNPS :", employe.num_cnps,
                          "Commune :", employe.commune))
    if employe.telephone:
        extra.append(row4("Téléphone :", employe.telephone,
                          "Nombre d'enfants :", employe.nombre_enfants))
    if employe.ville:
        extra.append(row4("Ville :", v(employe.ville).upper()))
    if employe.situation_familiale:
        extra.append(row4("Situation Familiale :",
                          employe.get_situation_familiale_display().upper()))
    if extra:
        elements.append(make_grid(extra, [LBL2, VAL2, LBL2, VAL2]))

    elements.append(Spacer(1, 6))

    # ══════════════════════════════════════════════════════════════════
    # SECTION 2 : EMPLOI
    # ══════════════════════════════════════════════════════════════════
    elements.append(section_header("EMPLOI"))

    LBL3 = 3.8 * cm
    VAL3 = (PAGE_W - 2 * LBL3) / 2
    emploi = []
    emploi.append(row4("Entreprise :", "JEC PROMO",
                       "Date d'embauche :",
                       employe.date_embauche.strftime('%d/%m/%Y') if employe.date_embauche else None))
    if employe.departement:
        emploi.append([Paragraph("Direction :", lbl_style),
                        Paragraph(str(employe.departement).upper(), val_style),
                        Paragraph('', lbl_style), Paragraph('', val_style)])
    emploi.append(row4("Emploi :", v(employe.poste).upper(),
                       "Lieu de travail :",
                       employe.boutique if employe.boutique else employe.ville))
    if employe.adresse:
        emploi.append([Paragraph("Adresse :", lbl_style),
                        Paragraph(employe.adresse, val_style),
                        Paragraph('', lbl_style), Paragraph('', val_style)])
    elements.append(make_grid(emploi, [LBL3, VAL3, LBL3, VAL3]))
    elements.append(Spacer(1, 6))

    # ══════════════════════════════════════════════════════════════════
    # SECTION 3 : ETAT AGENT
    # ══════════════════════════════════════════════════════════════════
    elements.append(section_header("ETAT AGENT"))

    # Compute leave statistics
    conges_approuves = employe.conges.filter(statut='approuve')
    jours_pris = sum((c.date_fin - c.date_debut).days + 1 for c in conges_approuves)
    today = date.today()
    if employe.date_embauche:
        mois = (today.year - employe.date_embauche.year) * 12 + \
               (today.month - employe.date_embauche.month)
        jours_acquis = round(mois * 2.5)
        solde = max(0, jours_acquis - jours_pris)
    else:
        solde = 0

    # Date de départ à la retraite
    depart_retraite = '—'
    if employe.date_naissance:
        try:
            depart_retraite = employe.date_naissance.replace(
                year=employe.date_naissance.year + 60
            ).strftime('%d/%m/%Y')
        except ValueError:
            depart_retraite = str(employe.date_naissance.year + 60)

    LBL4 = 4.0 * cm
    VAL4 = (PAGE_W - 2 * LBL4) / 2
    etat = []
    etat.append(row4("Date prise de service :",
                     employe.date_embauche.strftime('%d/%m/%Y') if employe.date_embauche else None,
                     "Solde Congés :", f"{solde} jour(s)"))
    etat.append(row4("Date départ retraite :", depart_retraite,
                     "Congés Pris :", f"{jours_pris} jour(s)"))
    etat.append(row4("Etat :", employe.get_statut_display().upper()))
    elements.append(make_grid(etat, [LBL4, VAL4, LBL4, VAL4]))

    elements.append(Spacer(1, 12))

    # ── Pied de page ─────────────────────────────────────────────────
    elements.append(HRFlowable(width="100%", thickness=0.5,
                                color=GREEN, spaceBefore=6, spaceAfter=4))
    elements.append(Paragraph(
        f"Document généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')} — SYGEPE / JEC PROMO",
        footer_style,
    ))

    doc.build(elements)
    return response


@never_cache
@login_required
def telecharger_profil(request):
    """Téléchargement du profil par l'employé lui-même."""
    try:
        employe = request.user.employe
    except Employe.DoesNotExist:
        messages.error(request, "Aucun profil employé associé à votre compte.")
        return redirect('profil')
    return _generer_pdf_profil(employe)


@never_cache
@rh_requis
def telecharger_profil_employe(request, pk):
    """Téléchargement du profil d'un employé par la RH ou la DAF."""
    employe = get_object_or_404(Employe, pk=pk)
    return _generer_pdf_profil(employe)


# ─────────────────────────────────────────────
# Rapports PDF (RH / DAF)
# ─────────────────────────────────────────────

@rh_requis
def rapports(request):
    """Page d'accueil des rapports téléchargeables."""
    today = date.today()
    mois_courant  = int(request.GET.get('mois',  today.month))
    annee_courante = int(request.GET.get('annee', today.year))
    # Années disponibles : de l'année de la première présence à aujourd'hui
    premiere = Presence.objects.order_by('date').values_list('date__year', flat=True).first()
    debut = premiere if premiere else today.year
    annees = list(range(today.year, debut - 1, -1))
    MOIS = [
        (1,'Janvier'),(2,'Février'),(3,'Mars'),(4,'Avril'),
        (5,'Mai'),(6,'Juin'),(7,'Juillet'),(8,'Août'),
        (9,'Septembre'),(10,'Octobre'),(11,'Novembre'),(12,'Décembre'),
    ]
    return render(request, 'SYGEPE/rapports.html', {
        'mois_courant': mois_courant,
        'annee_courante': annee_courante,
        'annees': annees,
        'mois_liste': MOIS,
    })


def _pdf_styles():
    """Retourne les styles et couleurs communs aux rapports."""
    GREEN  = colors.HexColor('#2E7D32')
    ORANGE = colors.HexColor('#E65100')
    LGRAY  = colors.HexColor('#F5F5F5')
    styles = getSampleStyleSheet()
    titre_style = ParagraphStyle('Titre', parent=styles['Normal'],
                                 fontSize=15, fontName='Helvetica-Bold',
                                 textColor=GREEN, alignment=TA_CENTER, spaceAfter=2)
    sous_titre_style = ParagraphStyle('SousTitre', parent=styles['Normal'],
                                      fontSize=9, textColor=colors.black,
                                      alignment=TA_CENTER, spaceAfter=10)
    section_style = ParagraphStyle('Section', parent=styles['Normal'],
                                   fontSize=10, fontName='Helvetica-Bold',
                                   textColor=colors.white)
    th_style  = ParagraphStyle('TH', parent=styles['Normal'],
                                fontSize=8, fontName='Helvetica-Bold',
                                textColor=colors.white, alignment=TA_CENTER)
    td_style  = ParagraphStyle('TD', parent=styles['Normal'],
                                fontSize=8, textColor=colors.black)
    tdc_style = ParagraphStyle('TDC', parent=styles['Normal'],
                                fontSize=8, textColor=colors.black, alignment=TA_CENTER)
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'],
                                   fontSize=7, textColor=colors.grey,
                                   alignment=TA_CENTER)
    return {
        'GREEN': GREEN, 'ORANGE': ORANGE, 'LGRAY': LGRAY,
        'titre': titre_style, 'sous_titre': sous_titre_style,
        'section': section_style, 'th': th_style,
        'td': td_style, 'tdc': tdc_style, 'footer': footer_style,
    }


def _make_section_header(titre, page_w, styles):
    t = Table([[Paragraph(f"  {titre}", styles['section'])]], colWidths=[page_w])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), styles['GREEN']),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
    ]))
    return t


def _make_data_table(header_row, data_rows, col_widths, styles):
    """Crée un tableau avec en-tête vert et lignes alternées."""
    all_rows = [header_row] + data_rows
    t = Table(all_rows, colWidths=col_widths)
    ts = TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0),  styles['GREEN']),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, styles['LGRAY']]),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING',   (0, 0), (-1, -1), 5),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 5),
        ('LINEBELOW',     (0, 0), (-1, -1), 0.3, colors.HexColor('#CCCCCC')),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ])
    t.setStyle(ts)
    return t


@rh_requis
def rapport_presences(request):
    """PDF : Rapport mensuel de présence."""
    from datetime import datetime as dt
    today = date.today()
    mois  = int(request.GET.get('mois',  today.month))
    annee = int(request.GET.get('annee', today.year))

    presences = (Presence.objects
                 .filter(date__year=annee, date__month=mois)
                 .select_related('employe')
                 .order_by('employe__nom', 'employe__prenom'))

    # Agréger par employé
    from collections import defaultdict
    bilan = defaultdict(lambda: {'present': 0, 'absent': 0, 'retard': 0,
                                  'conge': 0, 'permission': 0, 'employe': None})
    for p in presences:
        key = p.employe.pk
        bilan[key]['employe'] = p.employe
        bilan[key][p.statut] = bilan[key].get(p.statut, 0) + 1

    response = HttpResponse(content_type='application/pdf')
    nom_mois = dt(annee, mois, 1).strftime('%B %Y')
    response['Content-Disposition'] = f'attachment; filename="rapport_presences_{annee}_{mois:02d}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4,
                             leftMargin=1.5*cm, rightMargin=1.5*cm,
                             topMargin=2*cm, bottomMargin=2*cm)
    PAGE_W = A4[0] - 3*cm
    s = _pdf_styles()
    elems = []

    elems.append(Paragraph("JEC PROMO", s['titre']))
    elems.append(Paragraph(f"RAPPORT DE PRÉSENCE — {nom_mois.upper()}", s['sous_titre']))
    elems.append(_make_section_header("RÉCAPITULATIF PAR EMPLOYÉ", PAGE_W, s))

    header = [Paragraph(h, s['th']) for h in
              ['Matricule', 'Nom & Prénoms', 'Présent', 'Absent', 'Retard', 'En congé', 'Permission', 'Total']]
    cw = [2.5*cm, 5.5*cm, 1.7*cm, 1.7*cm, 1.7*cm, 1.9*cm, 2.0*cm, 1.6*cm]
    rows = []
    for data in bilan.values():
        emp = data['employe']
        total = data['present'] + data['absent'] + data['retard'] + data['conge'] + data['permission']
        rows.append([
            Paragraph(emp.matricule, s['tdc']),
            Paragraph(emp.get_full_name(), s['td']),
            Paragraph(str(data['present']),    s['tdc']),
            Paragraph(str(data['absent']),     s['tdc']),
            Paragraph(str(data['retard']),     s['tdc']),
            Paragraph(str(data['conge']),      s['tdc']),
            Paragraph(str(data['permission']), s['tdc']),
            Paragraph(str(total),              s['tdc']),
        ])
    if rows:
        elems.append(_make_data_table(header, rows, cw, s))
    else:
        elems.append(Paragraph("Aucune donnée de présence pour cette période.", s['td']))

    elems.append(Spacer(1, 10))
    elems.append(HRFlowable(width="100%", thickness=0.5, color=s['GREEN'], spaceBefore=4, spaceAfter=4))
    elems.append(Paragraph(
        f"Document généré le {dt.now().strftime('%d/%m/%Y à %H:%M')} — SYGEPE / JEC PROMO",
        s['footer']))
    doc.build(elems)
    return response


@rh_requis
def rapport_conges(request):
    """PDF : Rapport des congés."""
    from datetime import datetime as dt
    today = date.today()
    mois  = int(request.GET.get('mois',  today.month))
    annee = int(request.GET.get('annee', today.year))

    conges = (Conge.objects
              .filter(date_demande__year=annee, date_demande__month=mois)
              .select_related('employe')
              .order_by('employe__nom', 'date_debut'))

    response = HttpResponse(content_type='application/pdf')
    from datetime import datetime as dt
    nom_mois = dt(annee, mois, 1).strftime('%B %Y')
    response['Content-Disposition'] = f'attachment; filename="rapport_conges_{annee}_{mois:02d}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4,
                             leftMargin=1.5*cm, rightMargin=1.5*cm,
                             topMargin=2*cm, bottomMargin=2*cm)
    PAGE_W = A4[0] - 3*cm
    s = _pdf_styles()
    elems = []

    elems.append(Paragraph("JEC PROMO", s['titre']))
    elems.append(Paragraph(f"RAPPORT DES CONGÉS — {nom_mois.upper()}", s['sous_titre']))
    elems.append(_make_section_header("LISTE DES DEMANDES DE CONGÉS", PAGE_W, s))

    header = [Paragraph(h, s['th']) for h in
              ['Matricule', 'Nom & Prénoms', 'Type', 'Date début', 'Date fin', 'Durée', 'Statut']]
    cw = [2.3*cm, 4.8*cm, 2.8*cm, 2.3*cm, 2.3*cm, 1.6*cm, 2.5*cm]
    rows = []
    for c in conges:
        nb = (c.date_fin - c.date_debut).days + 1
        rows.append([
            Paragraph(c.employe.matricule, s['tdc']),
            Paragraph(c.employe.get_full_name(), s['td']),
            Paragraph(c.get_type_conge_display(), s['td']),
            Paragraph(c.date_debut.strftime('%d/%m/%Y'), s['tdc']),
            Paragraph(c.date_fin.strftime('%d/%m/%Y'),   s['tdc']),
            Paragraph(f"{nb} j", s['tdc']),
            Paragraph(c.get_statut_display(), s['tdc']),
        ])
    if rows:
        elems.append(_make_data_table(header, rows, cw, s))
    else:
        elems.append(Paragraph("Aucun congé pour cette période.", s['td']))

    elems.append(Spacer(1, 10))
    elems.append(HRFlowable(width="100%", thickness=0.5, color=s['GREEN'], spaceBefore=4, spaceAfter=4))
    elems.append(Paragraph(
        f"Document généré le {dt.now().strftime('%d/%m/%Y à %H:%M')} — SYGEPE / JEC PROMO",
        s['footer']))
    doc.build(elems)
    return response


@rh_requis
def rapport_permissions(request):
    """PDF : Rapport des permissions du mois."""
    from datetime import datetime as dt
    today = date.today()
    mois  = int(request.GET.get('mois',  today.month))
    annee = int(request.GET.get('annee', today.year))
    nom_mois = dt(annee, mois, 1).strftime('%B %Y')

    perms = (Permission.objects
             .filter(date_demande__year=annee, date_demande__month=mois)
             .select_related('employe')
             .order_by('employe__nom', 'date_debut'))

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="rapport_permissions_{annee}_{mois:02d}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4,
                             leftMargin=1.5*cm, rightMargin=1.5*cm,
                             topMargin=2*cm, bottomMargin=2*cm)
    PAGE_W = A4[0] - 3*cm
    s = _pdf_styles()
    elems = []

    elems.append(Paragraph("JEC PROMO", s['titre']))
    elems.append(Paragraph(f"RAPPORT DES PERMISSIONS — {nom_mois.upper()}", s['sous_titre']))
    elems.append(_make_section_header("LISTE DES DEMANDES DE PERMISSION", PAGE_W, s))

    header = [Paragraph(h, s['th']) for h in
              ['Matricule', 'Nom & Prénoms', 'Date début', 'Date fin', 'Durée', 'Motif', 'Statut']]
    cw = [2.3*cm, 4.5*cm, 2.3*cm, 2.3*cm, 1.6*cm, 4.2*cm, 2.4*cm]
    rows = []
    for p in perms:
        rows.append([
            Paragraph(p.employe.matricule, s['tdc']),
            Paragraph(p.employe.get_full_name(), s['td']),
            Paragraph(p.date_debut.strftime('%d/%m/%Y'), s['tdc']),
            Paragraph(p.date_fin.strftime('%d/%m/%Y'),   s['tdc']),
            Paragraph(f"{p.nb_jours} j", s['tdc']),
            Paragraph(p.motif[:35] + ('…' if len(p.motif) > 35 else ''), s['td']),
            Paragraph(p.get_statut_display(), s['tdc']),
        ])
    if rows:
        elems.append(_make_data_table(header, rows, cw, s))
    else:
        elems.append(Paragraph("Aucune demande de permission pour cette période.", s['td']))

    elems.append(Spacer(1, 10))
    elems.append(HRFlowable(width="100%", thickness=0.5, color=s['GREEN'], spaceBefore=4, spaceAfter=4))
    elems.append(Paragraph(
        f"Document généré le {dt.now().strftime('%d/%m/%Y à %H:%M')} — SYGEPE / JEC PROMO",
        s['footer']))
    doc.build(elems)
    return response


@rh_requis
def rapport_rh_complet(request):
    """PDF : Rapport RH complet (synthèse mensuelle)."""
    from datetime import datetime as dt
    today = date.today()
    mois  = int(request.GET.get('mois',  today.month))
    annee = int(request.GET.get('annee', today.year))
    nom_mois = dt(annee, mois, 1).strftime('%B %Y')

    employes_actifs = Employe.objects.filter(statut='actif')
    total_employes  = employes_actifs.count()

    presences_mois = Presence.objects.filter(date__year=annee, date__month=mois)
    nb_present   = presences_mois.filter(statut='present').count()
    nb_absent    = presences_mois.filter(statut='absent').count()
    nb_retard    = presences_mois.filter(statut='retard').count()
    nb_conge_p   = presences_mois.filter(statut='conge').count()
    nb_perm_p    = presences_mois.filter(statut='permission').count()

    conges_mois  = Conge.objects.filter(date_debut__year=annee, date_debut__month=mois).select_related('employe')
    perms_mois   = Permission.objects.filter(date_debut__year=annee, date_debut__month=mois).select_related('employe')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="rapport_rh_complet_{annee}_{mois:02d}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4,
                             leftMargin=1.5*cm, rightMargin=1.5*cm,
                             topMargin=2*cm, bottomMargin=2*cm)
    PAGE_W = A4[0] - 3*cm
    s = _pdf_styles()
    ORANGE = s['ORANGE']
    lbl_s = ParagraphStyle('Lbl', parent=getSampleStyleSheet()['Normal'],
                            fontSize=8.5, fontName='Helvetica-Bold')
    val_s = ParagraphStyle('Val', parent=getSampleStyleSheet()['Normal'],
                            fontSize=8.5, textColor=ORANGE)
    elems = []

    elems.append(Paragraph("JEC PROMO", s['titre']))
    elems.append(Paragraph(f"RAPPORT RH COMPLET — {nom_mois.upper()}", s['sous_titre']))

    # ── Synthèse générale ──────────────────────────────────────────────
    elems.append(_make_section_header("SYNTHÈSE GÉNÉRALE", PAGE_W, s))
    LBL = 4*cm; VAL = (PAGE_W - 2*LBL) / 2
    kpi_data = [
        [Paragraph("Total employés actifs :", lbl_s), Paragraph(str(total_employes), val_s),
         Paragraph("Jours présents :", lbl_s),        Paragraph(str(nb_present), val_s)],
        [Paragraph("Jours absents :", lbl_s),  Paragraph(str(nb_absent), val_s),
         Paragraph("Jours en retard :", lbl_s), Paragraph(str(nb_retard), val_s)],
        [Paragraph("Jours en congé :", lbl_s),  Paragraph(str(nb_conge_p), val_s),
         Paragraph("Jours en permission :", lbl_s), Paragraph(str(nb_perm_p), val_s)],
    ]
    kt = Table(kpi_data, colWidths=[LBL, VAL, LBL, VAL])
    kt.setStyle(TableStyle([
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, s['LGRAY']]),
        ('LINEBELOW', (0, 0), (-1, -1), 0.3, colors.HexColor('#CCCCCC')),
    ]))
    elems.append(kt)
    elems.append(Spacer(1, 8))

    # ── Congés du mois ────────────────────────────────────────────────
    elems.append(_make_section_header("CONGÉS DU MOIS", PAGE_W, s))
    if conges_mois.exists():
        header = [Paragraph(h, s['th']) for h in
                  ['Employé', 'Type', 'Du', 'Au', 'Durée', 'Statut']]
        cw = [5.0*cm, 3.2*cm, 2.5*cm, 2.5*cm, 1.8*cm, 3.6*cm]
        rows = [[
            Paragraph(c.employe.get_full_name(), s['td']),
            Paragraph(c.get_type_conge_display(), s['td']),
            Paragraph(c.date_debut.strftime('%d/%m/%Y'), s['tdc']),
            Paragraph(c.date_fin.strftime('%d/%m/%Y'),   s['tdc']),
            Paragraph(f"{(c.date_fin - c.date_debut).days + 1} j", s['tdc']),
            Paragraph(c.get_statut_display(), s['tdc']),
        ] for c in conges_mois]
        elems.append(_make_data_table(header, rows, cw, s))
    else:
        elems.append(Paragraph("  Aucun congé ce mois.", s['td']))
    elems.append(Spacer(1, 8))

    # ── Permissions du mois ───────────────────────────────────────────
    elems.append(_make_section_header("PERMISSIONS DU MOIS", PAGE_W, s))
    if perms_mois.exists():
        header = [Paragraph(h, s['th']) for h in
                  ['Employé', 'Date début', 'Date fin', 'Durée', 'Motif', 'Statut']]
        cw = [4.5*cm, 2.5*cm, 2.5*cm, 1.8*cm, 4.5*cm, 2.8*cm]
        rows = [[
            Paragraph(p.employe.get_full_name(), s['td']),
            Paragraph(p.date_debut.strftime('%d/%m/%Y'), s['tdc']),
            Paragraph(p.date_fin.strftime('%d/%m/%Y'),   s['tdc']),
            Paragraph(f"{p.nb_jours} j", s['tdc']),
            Paragraph(p.motif[:40] + ('…' if len(p.motif) > 40 else ''), s['td']),
            Paragraph(p.get_statut_display(), s['tdc']),
        ] for p in perms_mois]
        elems.append(_make_data_table(header, rows, cw, s))
    else:
        elems.append(Paragraph("  Aucune permission ce mois.", s['td']))

    elems.append(Spacer(1, 10))
    elems.append(HRFlowable(width="100%", thickness=0.5, color=s['GREEN'], spaceBefore=4, spaceAfter=4))
    elems.append(Paragraph(
        f"Document généré le {dt.now().strftime('%d/%m/%Y à %H:%M')} — SYGEPE / JEC PROMO",
        s['footer']))
    doc.build(elems)
    return response


# ─────────────────────────────────────────────
# Changement de mot de passe
# ─────────────────────────────────────────────
@login_required
def changer_mot_de_passe(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Votre mot de passe a été modifié avec succès.")
            return redirect('profil')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'SYGEPE/changer_mot_de_passe.html', {'form': form})


# ─────────────────────────────────────────────
# API Notifications congés
# ─────────────────────────────────────────────
@login_required
def api_notifications_conges(request):
    """Retourne les congés approuvés débutant dans 7 jours ou demain."""
    today  = date.today()
    j7     = today + timedelta(days=7)
    veille = today + timedelta(days=1)

    notifications = []

    if is_rh(request.user):
        # RH/DAF : tous les employés
        for c in Conge.objects.filter(statut='approuve', date_debut=j7).select_related('employe'):
            notifications.append({
                'urgence': 'warning',
                'titre'  : 'Congé dans 7 jours',
                'message': f"{c.employe.get_full_name()} — {c.get_type_conge_display()} du {c.date_debut.strftime('%d/%m/%Y')} au {c.date_fin.strftime('%d/%m/%Y')}",
            })
        for c in Conge.objects.filter(statut='approuve', date_debut=veille).select_related('employe'):
            notifications.append({
                'urgence': 'danger',
                'titre'  : 'Congé commence demain !',
                'message': f"{c.employe.get_full_name()} — {c.get_type_conge_display()} du {c.date_debut.strftime('%d/%m/%Y')} au {c.date_fin.strftime('%d/%m/%Y')}",
            })
    else:
        # Employé : seulement ses propres congés
        try:
            employe = request.user.employe
            for c in employe.conges.filter(statut='approuve', date_debut=j7):
                notifications.append({
                    'urgence': 'warning',
                    'titre'  : 'Votre congé dans 7 jours',
                    'message': f"{c.get_type_conge_display()} du {c.date_debut.strftime('%d/%m/%Y')} au {c.date_fin.strftime('%d/%m/%Y')}",
                })
            for c in employe.conges.filter(statut='approuve', date_debut=veille):
                notifications.append({
                    'urgence': 'danger',
                    'titre'  : 'Votre congé commence demain !',
                    'message': f"{c.get_type_conge_display()} du {c.date_debut.strftime('%d/%m/%Y')} au {c.date_fin.strftime('%d/%m/%Y')}",
                })
        except Exception:
            pass

    return JsonResponse({'notifications': notifications})
