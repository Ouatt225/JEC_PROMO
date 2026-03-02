from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.utils.html import format_html
from django import forms

from .models import Departement, Employe, Presence, Conge, Permission, Boutique

# ─── Personnalisation du site admin ───────────────────────────────────────────
admin.site.site_header  = "SYGEPE — Administration"
admin.site.site_title   = "SYGEPE"
admin.site.index_title  = "Panneau de gestion"


# ─── Helpers ──────────────────────────────────────────────────────────────────
ROLE_CHOICES = [
    ('employe', 'Employé — Espace Contractuel uniquement'),
    ('rh',      'Ressources Humaines (RH) — Tableau de bord + gestion congés/présences'),
    ('daf',     'DAF — Mêmes accès que RH (tableau de bord, congés, permissions)'),
    ('admin',   'Administrateur — Accès complet à toutes les fonctionnalités'),
]

ROLE_DESCRIPTION = (
    '<div style="background:#F8F9FA;border-left:4px solid #1565C0;padding:10px 14px;'
    'margin:8px 0;border-radius:0 6px 6px 0;font-size:0.88rem;line-height:1.7;">'
    '<strong>👤 Employé</strong> → voit uniquement son Espace Contractuel '
    '(profil, congés, permissions).<br>'
    '<strong>🏢 RH</strong> → accès au tableau de bord, peut valider les congés '
    'et permissions de tous les employés.<br>'
    '<strong>💼 DAF</strong> → mêmes accès que RH (tableau de bord, congés, permissions).<br>'
    '<strong>⚙ Administrateur</strong> → accès complet : gestion des employés, '
    'boutiques, présences + toutes les fonctions RH.'
    '</div>'
)


def _sync_role_to_groups(user, role):
    """Assigne le bon groupe Django et met à jour is_staff selon le rôle."""
    from django.contrib.auth.models import Group
    role_groups = Group.objects.filter(name__in=['Admin', 'RH', 'DAF', 'Employé'])
    user.groups.remove(*role_groups)
    if role == 'admin':
        grp, _ = Group.objects.get_or_create(name='Admin')
        user.groups.add(grp)
        User.objects.filter(pk=user.pk).update(is_staff=True)
    elif role == 'rh':
        grp, _ = Group.objects.get_or_create(name='RH')
        user.groups.add(grp)
        User.objects.filter(pk=user.pk).update(is_staff=True)
    elif role == 'daf':
        grp, _ = Group.objects.get_or_create(name='DAF')
        user.groups.add(grp)
        User.objects.filter(pk=user.pk).update(is_staff=True)
    else:
        grp, _ = Group.objects.get_or_create(name='Employé')
        user.groups.add(grp)
        User.objects.filter(pk=user.pk).update(is_staff=False)


# ─── Formulaire CRÉATION utilisateur ──────────────────────────────────────────
class SygepeUserCreationForm(UserCreationForm):
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        widget=forms.RadioSelect,
        initial='employe',
        label="Rôle dans le système",
        help_text=ROLE_DESCRIPTION,
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username',)


# ─── Formulaire MODIFICATION utilisateur ──────────────────────────────────────
class SygepeUserChangeForm(UserChangeForm):
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        widget=forms.RadioSelect,
        label="Rôle dans le système",
        help_text=ROLE_DESCRIPTION,
    )

    class Meta(UserChangeForm.Meta):
        model = User

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pré-remplir depuis le groupe actuel
        if self.instance and self.instance.pk:
            if self.instance.is_superuser or self.instance.groups.filter(name='Admin').exists():
                self.fields['role'].initial = 'admin'
            elif self.instance.groups.filter(name='RH').exists():
                self.fields['role'].initial = 'rh'
            elif self.instance.groups.filter(name='DAF').exists():
                self.fields['role'].initial = 'daf'
            else:
                self.fields['role'].initial = 'employe'


# ─── UserAdmin personnalisé ────────────────────────────────────────────────────
class SygepeUserAdmin(BaseUserAdmin):
    add_form = SygepeUserCreationForm
    form     = SygepeUserChangeForm

    # ── Liste
    list_display  = ('username', 'email', 'get_full_name', 'badge_role', 'is_active', 'last_login')
    list_filter   = ('is_active', 'groups')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering      = ('username',)

    # ── Formulaire CRÉATION ──
    add_fieldsets = (
        ('🔑 Informations de connexion', {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2'),
        }),
        ('🎭 Rôle dans le système', {
            'fields': ('role',),
        }),
    )

    # ── Formulaire MODIFICATION ──
    fieldsets = (
        ('🔑 Connexion', {
            'fields': ('username', 'password'),
        }),
        ('🎭 Rôle dans le système', {
            'fields': ('role',),
        }),
        ('👤 Informations personnelles', {
            'fields': ('first_name', 'last_name', 'email'),
            'classes': ('collapse',),
        }),
        ('📅 Statut & Dates', {
            'fields': ('is_active', 'last_login', 'date_joined'),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ('last_login', 'date_joined')

    # ── Badge rôle dans la liste ──
    def badge_role(self, obj):
        if obj.is_superuser or obj.groups.filter(name='Admin').exists():
            return format_html(
                '<span style="background:#FFEBEE;color:#C62828;padding:3px 12px;'
                'border-radius:50px;font-size:0.78rem;font-weight:700;">{}</span>',
                'Administrateur',
            )
        elif obj.groups.filter(name='RH').exists():
            return format_html(
                '<span style="background:#E3F2FD;color:#1565C0;padding:3px 12px;'
                'border-radius:50px;font-size:0.78rem;font-weight:700;">{}</span>',
                'RH',
            )
        elif obj.groups.filter(name='DAF').exists():
            return format_html(
                '<span style="background:#F3E5F5;color:#6A1B9A;padding:3px 12px;'
                'border-radius:50px;font-size:0.78rem;font-weight:700;">{}</span>',
                'DAF',
            )
        elif obj.groups.filter(name='Employé').exists():
            return format_html(
                '<span style="background:#E8F5E9;color:#1B5E20;padding:3px 12px;'
                'border-radius:50px;font-size:0.78rem;font-weight:700;">{}</span>',
                'Employé',
            )
        return format_html(
            '<span style="color:#9CA3AF;font-size:0.78rem;">{}</span>',
            '— Sans rôle',
        )
    badge_role.short_description = 'Rôle'

    # ── Synchroniser groupes à la sauvegarde ──
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        role = form.cleaned_data.get('role', 'employe')
        _sync_role_to_groups(obj, role)
        # Sync retour → champ role sur l'Employe lié
        try:
            employe = obj.employe
            role_map = {'employe': 'employe', 'rh': 'rh', 'daf': 'daf', 'admin': 'admin'}
            if employe.role != role_map.get(role, 'employe'):
                Employe.objects.filter(pk=employe.pk).update(role=role)
        except Exception:
            pass


# Remplacer le UserAdmin par défaut
admin.site.unregister(User)
admin.site.register(User, SygepeUserAdmin)


# ─── Formulaire enrichi pour EmployeAdmin ─────────────────────────────────────
class EmployeAdminForm(forms.ModelForm):
    """Ajoute la création de compte utilisateur directement depuis l'admin."""

    username = forms.CharField(
        label="Nom d'utilisateur (login)",
        max_length=150, required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Laisser vide si déjà lié à un compte'}),
        help_text="Remplir uniquement pour créer un NOUVEAU compte utilisateur.",
    )
    password1 = forms.CharField(
        label="Mot de passe",
        required=False,
        widget=forms.PasswordInput(attrs={'placeholder': 'Nouveau mot de passe'}),
    )
    password2 = forms.CharField(
        label="Confirmer le mot de passe",
        required=False,
        widget=forms.PasswordInput(attrs={'placeholder': 'Répéter le mot de passe'}),
    )

    class Meta:
        model = Employe
        fields = '__all__'
        widgets = {
            # Le rôle s'affiche en boutons radio bien visibles
            'role': forms.RadioSelect,
        }

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1', '')
        p2 = cleaned.get('password2', '')
        username = cleaned.get('username', '')
        if username and p1 != p2:
            self.add_error('password2', "Les deux mots de passe ne correspondent pas.")
        if username and not p1:
            self.add_error('password1', "Un mot de passe est requis pour créer le compte.")
        # Vérifier que le username n'est pas déjà pris
        if username and User.objects.filter(username=username).exists():
            self.add_error('username', f"Ce nom d'utilisateur « {username} » est déjà pris.")
        return cleaned


# ─── EmployeAdmin ─────────────────────────────────────────────────────────────
@admin.register(Employe)
class EmployeAdmin(admin.ModelAdmin):
    form = EmployeAdminForm

    # ── Liste ──
    list_display = (
        'matricule', 'nom_complet', 'poste',
        'departement', 'badge_role', 'badge_statut', 'badge_compte',
    )
    list_filter  = ('role', 'statut', 'departement', 'sexe', 'situation_familiale')
    search_fields = ('nom', 'prenom', 'matricule', 'email', 'num_cnps', 'user__username')
    list_per_page = 25
    ordering = ('nom', 'prenom')

    # ── Fieldsets ──
    fieldsets = (

        # 1. RÔLE — la section la plus importante, placée en premier
        ('🎭  Rôle & Droits d\'accès', {
            'fields': ('role',),
            'description': (
                '<strong>Employé</strong> → accès à son Espace Contractuel uniquement.<br>'
                '<strong>RH</strong> → gestion des congés, permissions et présences.<br>'
                '<strong>DAF</strong> → mêmes accès que RH.<br>'
                '<strong>Administrateur</strong> → accès complet à toutes les fonctionnalités.'
            ),
        }),

        # 2. COMPTE UTILISATEUR
        ('🔑  Compte utilisateur', {
            'fields': ('user', 'username', 'password1', 'password2'),
            'description': (
                'Si un compte existe déjà, sélectionnez-le dans <em>Compte lié</em>.<br>'
                'Pour créer un <strong>nouveau compte</strong>, remplissez les champs '
                '<em>Nom d\'utilisateur</em> et <em>Mot de passe</em> (laisser <em>Compte lié</em> vide).'
            ),
            'classes': ('collapse',),
        }),

        # 3. IDENTITÉ
        ('📋  Identité', {
            'fields': (
                ('matricule', 'statut'),
                ('nom', 'prenom'),
                ('sexe', 'date_naissance', 'lieu_naissance'),
                ('situation_familiale', 'nombre_enfants'),
            ),
        }),

        # 4. CONTACT
        ('📞  Contact', {
            'fields': (
                'email',
                'telephone',
                ('commune', 'ville'),
                'adresse',
            ),
        }),

        # 5. EMPLOI
        ('💼  Emploi', {
            'fields': (
                'poste',
                ('departement', 'boutique'),
                'date_embauche',
            ),
        }),

        # 6. CNPS / SOCIAL
        ('🏥  CNPS & Social', {
            'fields': ('num_cnps',),
            'classes': ('collapse',),
        }),

        # 7. PHOTO
        ('📷  Photo', {
            'fields': ('photo',),
            'classes': ('collapse',),
        }),
    )

    readonly_fields = ('date_creation', 'date_modification')

    # ── Méthodes d'affichage liste ──
    def nom_complet(self, obj):
        return obj.get_full_name()
    nom_complet.short_description = 'Nom complet'
    nom_complet.admin_order_field = 'nom'

    def badge_role(self, obj):
        cfg = {
            'admin':   ('#C62828', '#FFEBEE', '⚙ Administrateur'),
            'rh':      ('#1565C0', '#E3F2FD', '🏢 RH'),
            'daf':     ('#6A1B9A', '#F3E5F5', '💼 DAF'),
            'employe': ('#1B5E20', '#E8F5E9', '👤 Employé'),
        }
        color, bg, label = cfg.get(obj.role, ('#666', '#F5F5F5', obj.role))
        return format_html(
            '<span style="background:{bg};color:{c};padding:3px 10px;border-radius:50px;'
            'font-size:0.78rem;font-weight:700;">{l}</span>',
            bg=bg, c=color, l=label,
        )
    badge_role.short_description = 'Rôle'
    badge_role.admin_order_field = 'role'

    def badge_statut(self, obj):
        cfg = {
            'actif':    ('#1B5E20', '#E8F5E9', '● Actif'),
            'inactif':  ('#757575', '#F5F5F5', '● Inactif'),
            'suspendu': ('#E65100', '#FFF8E1', '● Suspendu'),
        }
        color, bg, label = cfg.get(obj.statut, ('#666', '#F5F5F5', obj.statut))
        return format_html(
            '<span style="background:{bg};color:{c};padding:3px 10px;border-radius:50px;'
            'font-size:0.78rem;font-weight:700;">{l}</span>',
            bg=bg, c=color, l=label,
        )
    badge_statut.short_description = 'Statut'

    def badge_compte(self, obj):
        if obj.user:
            return format_html(
                '<span style="color:#1B5E20;font-weight:600;">✓ {}</span>',
                obj.user.username,
            )
        return format_html('<span style="color:#E65100;">{}</span>', 'Aucun compte')
    badge_compte.short_description = 'Compte'

    # ── Création de compte à la sauvegarde ──
    def save_model(self, request, obj, form, change):
        username = form.cleaned_data.get('username', '').strip()
        password = form.cleaned_data.get('password1', '').strip()

        if username and password and not obj.user_id:
            user = User.objects.create_user(
                username=username,
                password=password,
                first_name=obj.prenom,
                last_name=obj.nom,
                email=obj.email,
            )
            obj.user = user

        super().save_model(request, obj, form, change)
        # Le save() du modèle synchronise automatiquement le groupe


# ─── Autres modèles ───────────────────────────────────────────────────────────
@admin.register(Departement)
class DepartementAdmin(admin.ModelAdmin):
    list_display  = ('nom', 'description', 'date_creation')
    search_fields = ('nom',)


@admin.register(Presence)
class PresenceAdmin(admin.ModelAdmin):
    list_display  = ('employe', 'date', 'heure_arrivee', 'heure_depart', 'statut')
    list_filter   = ('statut', 'date')
    search_fields = ('employe__nom', 'employe__prenom')
    date_hierarchy = 'date'


@admin.register(Conge)
class CongeAdmin(admin.ModelAdmin):
    list_display  = ('employe', 'type_conge', 'date_debut', 'date_fin', 'statut', 'date_demande')
    list_filter   = ('statut', 'type_conge')
    search_fields = ('employe__nom', 'employe__prenom')
    date_hierarchy = 'date_debut'


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display  = ('employe', 'date_debut', 'date_fin', 'statut', 'date_demande')
    list_filter   = ('statut',)
    search_fields = ('employe__nom', 'employe__prenom')
    date_hierarchy = 'date_debut'


@admin.register(Boutique)
class BoutiqueAdmin(admin.ModelAdmin):
    list_display  = ('nom', 'responsable', 'telephone', 'email', 'date_creation')
    search_fields = ('nom', 'responsable__nom', 'responsable__prenom')
