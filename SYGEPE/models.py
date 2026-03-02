from django.db import models
from django.contrib.auth.models import User
from datetime import date as _date


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


class Boutique(models.Model):
    nom = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    adresse = models.TextField(blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    responsable = models.ForeignKey(
        'Employe', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='boutiques_gerees'
    )
    date_creation = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.nom

    @property
    def nb_employes(self):
        return self.employes.filter(statut='actif').count()

    class Meta:
        verbose_name = "Boutique"
        verbose_name_plural = "Boutiques"
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
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employe', null=True, blank=True)
    role = models.CharField(
        max_length=10, choices=ROLE_CHOICES, default='employe',
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
    boutique = models.ForeignKey('Boutique', on_delete=models.SET_NULL, null=True, blank=True, related_name='employes')
    date_embauche = models.DateField(null=True, blank=True)
    date_naissance = models.DateField(null=True, blank=True)
    photo = models.ImageField(upload_to='employes/photos/', null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='actif')
    adresse = models.TextField(blank=True)

    # Champs contractuels supplémentaires
    sexe = models.CharField(max_length=1, choices=SEXE_CHOICES, blank=True)
    lieu_naissance = models.CharField(max_length=100, blank=True)
    num_cnps = models.CharField(max_length=30, blank=True, verbose_name="Numéro CNPS")
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

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Synchroniser le rôle avec les groupes Django
        if self.user_id:
            from django.contrib.auth.models import Group
            role_groups = Group.objects.filter(name__in=['Admin', 'RH', 'DAF', 'Employé'])
            self.user.groups.remove(*role_groups)
            if self.role == 'admin':
                grp, _ = Group.objects.get_or_create(name='Admin')
                self.user.groups.add(grp)
                User.objects.filter(pk=self.user_id).update(is_staff=True)
            elif self.role == 'rh':
                grp, _ = Group.objects.get_or_create(name='RH')
                self.user.groups.add(grp)
                User.objects.filter(pk=self.user_id).update(is_staff=True)
            elif self.role == 'daf':
                grp, _ = Group.objects.get_or_create(name='DAF')
                self.user.groups.add(grp)
                User.objects.filter(pk=self.user_id).update(is_staff=True)
            else:
                grp, _ = Group.objects.get_or_create(name='Employé')
                self.user.groups.add(grp)
                User.objects.filter(pk=self.user_id).update(is_staff=False)

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
        return self.date_naissance.year + 60

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


class Conge(models.Model):
    TYPE_CHOICES = [
        ('paye', 'Congé payé'),
        ('maladie', 'Congé maladie'),
        ('maternite', 'Congé maternité'),
        ('paternite', 'Congé paternité'),
        ('exceptionnel', 'Congé exceptionnel'),
        ('sans_solde', 'Congé sans solde'),
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
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')
    valideur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='conges_valides')
    date_validation = models.DateTimeField(null=True, blank=True)
    commentaire_valideur = models.TextField(blank=True)
    date_demande = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.employe} - {self.get_type_conge_display()} ({self.date_debut} → {self.date_fin})"

    @property
    def nb_jours(self):
        delta = self.date_fin - self.date_debut
        return delta.days + 1

    class Meta:
        verbose_name = "Congé"
        verbose_name_plural = "Congés"
        ordering = ['-date_demande']


class ActionLog(models.Model):
    """Historique des actions RH — audit trail."""
    ACTION_CHOICES = [
        ('employe_ajoute',     'Employé ajouté'),
        ('employe_modifie',    'Employé modifié'),
        ('employe_supprime',   'Employé supprimé'),
        ('conge_demande',      'Congé demandé'),
        ('conge_approuve',     'Congé approuvé'),
        ('conge_refuse',       'Congé refusé'),
        ('permission_demande', 'Permission demandée'),
        ('permission_approuve','Permission approuvée'),
        ('permission_refuse',  'Permission refusée'),
        ('presence_marquee',   'Présence marquée'),
        ('boutique_ajoutee',   'Boutique ajoutée'),
        ('boutique_modifiee',  'Boutique modifiée'),
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


class Permission(models.Model):
    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('approuve', 'Approuvé'),
        ('refuse', 'Refusé'),
        ('annule', 'Annulé'),
    ]

    employe = models.ForeignKey(Employe, on_delete=models.CASCADE, related_name='permissions')
    date_debut = models.DateField()
    date_fin = models.DateField()
    motif = models.TextField()
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')
    valideur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='permissions_validees')
    date_validation = models.DateTimeField(null=True, blank=True)
    commentaire_valideur = models.TextField(blank=True)
    date_demande = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.employe} - Permission du {self.date_debut} au {self.date_fin}"

    @property
    def nb_jours(self):
        delta = self.date_fin - self.date_debut
        return delta.days + 1

    class Meta:
        verbose_name = "Permission"
        verbose_name_plural = "Permissions"
        ordering = ['-date_demande']
