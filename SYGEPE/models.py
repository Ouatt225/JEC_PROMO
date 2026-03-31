from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from datetime import date as _date


class PeriodeMixin:
    """Mixin pour les modèles ayant date_debut et date_fin.
    Fournit nb_jours sans dupliquer le calcul.
    Pas un models.Model → aucune migration requise.
    """
    @property
    def nb_jours(self):
        return (self.date_fin - self.date_debut).days + 1


class Departement(models.Model):
    nom = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    date_creation = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.nom

    class Meta:
        verbose_name = "Département"
        verbose_name_plural = "Départements"
        ordering = ['nom']



class Employe(models.Model):
    STATUT_CHOICES = [
        ('actif', 'Actif'),
        ('inactif', 'Inactif'),
        ('suspendu', 'Suspendu'),
    ]

    SEXE_CHOICES = [
        ('M', 'Masculin'),
        ('F', 'Féminin'),
    ]

    SITUATION_CHOICES = [
        ('celibataire', 'Célibataire'),
        ('marie', 'Marié(e)'),
        ('divorce', 'Divorcé(e)'),
        ('veuf', 'Veuf/Veuve'),
    ]

    ROLE_CHOICES = [
        ('employe', 'Employé'),
        ('rh', 'Ressources Humaines (RH)'),
        ('daf', 'DAF'),
        ('admin', 'Administrateur'),
        ('dir_commercial', 'Directeur Commercial'),
        ('resp_logistique', 'Responsable Logistique'),
        ('resp_reabo', 'Responsable Réabo'),
        ('chef_comptable', 'Chef Comptable'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employe', null=True, blank=True)
    role = models.CharField(
        max_length=16, choices=ROLE_CHOICES, default='employe',
        verbose_name="Rôle",
        help_text="Détermine les droits d'accès de la personne dans le système."
    )
    matricule = models.CharField(max_length=20, unique=True)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    email = models.EmailField(unique=True, blank=True, default='')
    telephone = models.CharField(max_length=50, blank=True)
    poste = models.CharField(max_length=100)
    departement = models.ForeignKey(Departement, on_delete=models.SET_NULL, null=True, blank=True, related_name='employes')
    date_embauche = models.DateField(null=True, blank=True)
    date_naissance = models.DateField(null=True, blank=True)
    photo = models.ImageField(upload_to='employes/photos/', null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='actif')
    adresse = models.TextField(blank=True)

    # Champs contractuels supplémentaires
    sexe = models.CharField(max_length=1, choices=SEXE_CHOICES, blank=True)
    lieu_naissance = models.CharField(max_length=100, blank=True)
    num_cnps = models.CharField(max_length=30, blank=True, verbose_name="Numéro CNPS")
    num_cni = models.CharField(max_length=30, blank=True, verbose_name="Numéro CNI")
    commune = models.CharField(max_length=100, blank=True)
    ville = models.CharField(max_length=100, blank=True)
    nombre_enfants = models.PositiveIntegerField(default=0)
    situation_familiale = models.CharField(max_length=20, choices=SITUATION_CHOICES, blank=True)

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.matricule})"

    def get_full_name(self):
        return f"{self.prenom} {self.nom}"

    def _compresser_photo(self):
        """Redimensionne et compresse la photo en JPEG 400×400 max, qualité 80.
        Appelé uniquement après un nouvel upload (photo._committed était False).
        Écrase le fichier sur disque en place — le chemin en base reste inchangé.
        """
        from PIL import Image
        import io
        try:
            with Image.open(self.photo.path) as img:
                img.thumbnail((400, 400), Image.LANCZOS)
                if img.mode in ('RGBA', 'P', 'LA'):
                    img = img.convert('RGB')
                img.save(self.photo.path, format='JPEG', quality=80, optimize=True)
        except Exception:
            pass  # Ne jamais bloquer le save pour une photo non critique

    # ── Cache des groupes de rôles ────────────────────────────────────────────
    # Chargé en une seule requête au premier save() qui en a besoin.
    # Partagé entre toutes les instances → 1 SELECT pour 500 saves en import.
    # Clés : 'Admin', 'RH', 'DAF', 'Employé'. Valeurs : Group instances.
    _role_groups_cache: 'dict | None' = None

    @classmethod
    def _get_role_groups(cls) -> dict:
        """Retourne le dict {nom: Group} des 4 groupes de rôles (cache LRU simplifié)."""
        if cls._role_groups_cache is None:
            from django.contrib.auth.models import Group
            cls._role_groups_cache = {
                g.name: g
                for g in Group.objects.filter(name__in=['Admin', 'RH', 'DAF', 'Employé'])
            }
        return cls._role_groups_cache

    _ROLE_TO_GROUP = {'admin': 'Admin', 'rh': 'RH', 'daf': 'DAF'}
    _STAFF_ROLES   = frozenset({'admin', 'rh', 'daf'})

    def _sync_groupes(self):
        """Synchronise les groupes Django selon self.role — 3 requêtes exactement.

        Utilise la table through (auth_user_groups) directement pour éviter
        le lazy-load de self.user et supprimer les 4 get_or_create() séparés.
        """
        groups = self._get_role_groups()
        if not groups:
            return  # DB vierge, pas encore de groupes
        target_name = self._ROLE_TO_GROUP.get(self.role, 'Employé')
        target_group = groups.get(target_name)
        if not target_group:
            return
        group_ids = [g.id for g in groups.values()]
        UserGroups = User.groups.through                     # table auth_user_groups
        UserGroups.objects.filter(
            user_id=self.user_id, group_id__in=group_ids
        ).delete()                                           # requête 1 : DELETE ciblé
        UserGroups.objects.create(
            user_id=self.user_id, group_id=target_group.id
        )                                                    # requête 2 : INSERT
        User.objects.filter(pk=self.user_id).update(
            is_staff=self.role in self._STAFF_ROLES
        )                                                    # requête 3 : UPDATE

    def save(self, *args, **kwargs):
        photo_is_new = bool(self.photo) and not self.photo._committed
        super().save(*args, **kwargs)
        if photo_is_new:
            self._compresser_photo()
        # Synchroniser le rôle avec les groupes Django
        # update_fields guard : skip si on sait que 'role' n'a pas changé
        if self.user_id:
            update_fields = kwargs.get('update_fields')
            if update_fields is None or 'role' in update_fields:
                self._sync_groupes()

    def jours_conge_pris(self, annee, exclude_pk=None):
        """Retourne le total de jours de congé payé pris ou en attente pour l'année donnée."""
        qs = self.conges.filter(
            type_conge='paye',
            date_debut__year=annee,
            statut__in=['en_attente', 'approuve'],
        )
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        return sum((c.date_fin - c.date_debut).days + 1 for c in qs)

    @property
    def age(self):
        if not self.date_naissance:
            return None
        today = _date.today()
        years = today.year - self.date_naissance.year
        if (today.month, today.day) < (self.date_naissance.month, self.date_naissance.day):
            years -= 1
        return years

    @property
    def annee_retraite(self):
        if not self.date_naissance:
            return None
        return self.date_naissance.year + settings.AGE_RETRAITE

    class Meta:
        verbose_name = "Employé"
        verbose_name_plural = "Employés"
        ordering = ['nom', 'prenom']


class Presence(models.Model):
    STATUT_CHOICES = [
        ('present', 'Présent'),
        ('absent', 'Absent'),
        ('retard', 'En retard'),
        ('conge', 'En congé'),
        ('permission', 'En permission'),
    ]

    employe = models.ForeignKey(Employe, on_delete=models.CASCADE, related_name='presences')
    date = models.DateField()
    heure_arrivee = models.TimeField(null=True, blank=True)
    heure_depart = models.TimeField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='present')
    observation = models.TextField(blank=True)
    enregistre_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='presences_enregistrees')

    def __str__(self):
        return f"{self.employe} - {self.date} ({self.get_statut_display()})"

    class Meta:
        verbose_name = "Présence"
        verbose_name_plural = "Présences"
        ordering = ['-date']
        unique_together = ['employe', 'date']
        indexes = [
            models.Index(fields=['date', 'employe'], name='presence_date_employe_idx'),
        ]


class Conge(PeriodeMixin, models.Model):
    TYPE_CHOICES = [
        ('paye', 'Congé annuel'),
        ('maternite', 'Congé maternité'),
        ('maladie', 'Congé maladie'),
    ]

    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('approuve', 'Approuvé'),
        ('refuse', 'Refusé'),
        ('annule', 'Annulé'),
    ]

    employe = models.ForeignKey(Employe, on_delete=models.CASCADE, related_name='conges')
    type_conge = models.CharField(max_length=20, choices=TYPE_CHOICES)
    date_debut = models.DateField()
    date_fin = models.DateField()
    motif = models.TextField()
    piece_justificative = models.FileField(
        upload_to='conges/justificatifs/',
        null=True, blank=True,
        verbose_name="Pièce justificative"
    )
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')
    conge_parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fractions', verbose_name='Congé d\'origine (fractionnement)'
    )
    valideur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='conges_valides')
    date_validation = models.DateTimeField(null=True, blank=True)
    commentaire_valideur = models.TextField(blank=True)
    date_demande = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.employe} - {self.get_type_conge_display()} ({self.date_debut} → {self.date_fin})"

    class Meta:
        verbose_name = "Congé"
        verbose_name_plural = "Congés"
        ordering = ['-date_demande']
        indexes = [
            models.Index(fields=['date_debut', 'employe', 'statut'], name='conge_date_employe_statut_idx'),
        ]


class ActionLog(models.Model):
    """Historique des actions RH — audit trail."""
    ACTION_CHOICES = [
        ('employe_ajoute',     'Employé ajouté'),
        ('employe_modifie',    'Employé modifié'),
        ('employe_supprime',   'Employé supprimé'),
        ('conge_demande',      'Congé demandé'),
        ('conge_approuve',     'Congé approuvé'),
        ('conge_refuse',       'Congé refusé'),
        ('conge_modifie',      'Congé modifié / fractionné'),
        ('absence_demandee',    'Absence demandée'),
        ('absence_validee_resp','Absence validée par responsable'),
        ('absence_approuvee',   'Absence approuvée'),
        ('absence_refusee',     'Absence refusée'),
        ('permission_demande', 'Permission demandée'),
        ('permission_approuve','Permission approuvée'),
        ('permission_refuse',  'Permission refusée'),
        ('presence_marquee',   'Présence marquée'),
        ('autre',              'Autre'),
    ]

    utilisateur = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='actions_log',
        verbose_name='Utilisateur'
    )
    action      = models.CharField(max_length=30, choices=ACTION_CHOICES)
    description = models.TextField()
    employe     = models.ForeignKey(
        'Employe', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='actions_log',
        verbose_name='Employé concerné'
    )
    date        = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.date:%d/%m/%Y %H:%M} — {self.get_action_display()} par {self.utilisateur}"

    class Meta:
        verbose_name        = "Action RH"
        verbose_name_plural = "Historique des actions RH"
        ordering            = ['-date']


class Absence(PeriodeMixin, models.Model):
    """Demande d'absence spéciale : mission professionnelle, formation interne, atelier.
    Circuit à 2 étapes : responsable de département → DRH (identique aux permissions).
    """
    TYPE_CHOICES = [
        ('mission_pro',       'Mission professionnelle'),
        ('formation_interne', 'Formation interne'),
        ('atelier',           'Atelier'),
    ]
    STATUT_CHOICES = [
        ('en_attente',          'En attente'),
        ('valide_responsable',  'Validé par responsable'),
        ('approuve',            'Approuvé'),
        ('refuse',              'Refusé'),
        ('annule',              'Annulé'),
    ]

    employe           = models.ForeignKey(Employe, on_delete=models.CASCADE, related_name='absences')
    type_absence      = models.CharField(max_length=30, choices=TYPE_CHOICES, verbose_name="Type d'absence")
    date_debut        = models.DateField()
    date_fin          = models.DateField()
    motif             = models.TextField()
    statut            = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')
    # Étape 1 : validation par le responsable de département
    valideur_responsable          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                                       related_name='absences_validees_resp')
    date_validation_responsable   = models.DateTimeField(null=True, blank=True)
    # Étape 2 : validation finale par la DRH
    valideur          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name='absences_validees')
    date_validation   = models.DateTimeField(null=True, blank=True)
    commentaire_valideur = models.TextField(blank=True)
    date_demande      = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.employe} - {self.get_type_absence_display()} du {self.date_debut} au {self.date_fin}"

    class Meta:
        verbose_name        = "Absence"
        verbose_name_plural = "Absences"
        ordering            = ['-date_demande']


class Permission(PeriodeMixin, models.Model):
    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('valide_responsable', 'Validé par responsable'),
        ('approuve', 'Approuvé'),
        ('refuse', 'Refusé'),
        ('annule', 'Annulé'),
    ]

    employe = models.ForeignKey(Employe, on_delete=models.CASCADE, related_name='permissions')
    date_debut = models.DateField()
    date_fin = models.DateField()
    motif = models.TextField()
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')
    # Étape 1 : validation par le responsable de département
    valideur_responsable = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='permissions_validees_resp'
    )
    date_validation_responsable = models.DateTimeField(null=True, blank=True)
    # Étape 2 : validation finale par la DRH
    valideur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='permissions_validees')
    date_validation = models.DateTimeField(null=True, blank=True)
    commentaire_valideur = models.TextField(blank=True)
    date_demande = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.employe} - Permission du {self.date_debut} au {self.date_fin}"

    class Meta:
        verbose_name = "Permission"
        verbose_name_plural = "Permissions"
        ordering = ['-date_demande']
