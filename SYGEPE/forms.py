import os
from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from .models import Employe, Departement, Presence, Conge, Permission

PHOTO_MAX_SIZE    = 10 * 1024 * 1024  # 10 Mo — Pillow compresse à l'enregistrement (→ ~30 Ko)
PHOTO_EXTENSIONS  = {'.jpg', '.jpeg', '.png', '.webp'}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _valider_chevauchement(model_cls, employe, date_debut, date_fin, exclude_pk, label):
    """Vérifie qu'il n'y a pas de chevauchement avec un(e) congé/permission existant(e)."""
    qs = model_cls.objects.filter(
        employe=employe,
        statut__in=['en_attente', 'approuve'],
        date_debut__lte=date_fin,
        date_fin__gte=date_debut,
    )
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    if qs.exists():
        existing = qs.first()
        raise forms.ValidationError(
            f"Cette période chevauche {label} "
            f"({existing.date_debut.strftime('%d/%m/%Y')} → "
            f"{existing.date_fin.strftime('%d/%m/%Y')}, {existing.get_statut_display()})."
        )


def _valider_photo(photo):
    """Validation commune : taille ≤ 5 Mo et extension JPEG/PNG/WebP."""
    if photo and hasattr(photo, 'size'):
        if photo.size > PHOTO_MAX_SIZE:
            raise forms.ValidationError("La photo ne doit pas dépasser 10 Mo.")
        ext = os.path.splitext(photo.name)[1].lower()
        if ext not in PHOTO_EXTENSIONS:
            raise forms.ValidationError(
                "Format non supporté. Utilisez JPEG, PNG ou WebP."
            )
    return photo


# ── Mixin ──────────────────────────────────────────────────────────────────────

class FormClassMixin:
    """Applique automatiquement widget_css_class à tous les widgets du formulaire.

    Utilise setdefault pour ne pas écraser une classe déjà présente.
    Les HiddenInput sont ignorés (pas de rendu visuel).
    Surcharger widget_css_class = 'ec-form-control' pour l'espace employé.
    """
    widget_css_class = 'form-control'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_widget_classes()

    def _apply_widget_classes(self):
        for field in self.fields.values():
            if not isinstance(field.widget, forms.HiddenInput):
                field.widget.attrs.setdefault('class', self.widget_css_class)


# ── Formulaires ────────────────────────────────────────────────────────────────

class EmployeForm(FormClassMixin, forms.ModelForm):
    class Meta:
        model = Employe
        fields = [
            'matricule', 'nom', 'prenom', 'sexe', 'email', 'telephone',
            'poste', 'departement', 'date_embauche', 'date_naissance',
            'lieu_naissance', 'situation_familiale', 'nombre_enfants',
            'commune', 'ville', 'num_cnps',
            'photo', 'statut', 'adresse',
        ]
        widgets = {
            'matricule':           forms.TextInput(attrs={'placeholder': 'Ex: EMP001'}),
            'nom':                 forms.TextInput(attrs={'placeholder': 'Nom de famille'}),
            'prenom':              forms.TextInput(attrs={'placeholder': 'Prénom'}),
            'sexe':                forms.Select(),
            'email':               forms.EmailInput(attrs={'placeholder': 'email@exemple.com'}),
            'telephone':           forms.TextInput(attrs={'placeholder': '+225 XX XX XX XX'}),
            'poste':               forms.TextInput(attrs={'placeholder': 'Intitulé du poste'}),
            'departement':         forms.Select(),
            'date_embauche':       forms.DateInput(attrs={'type': 'date'}),
            'date_naissance':      forms.DateInput(attrs={'type': 'date'}),
            'lieu_naissance':      forms.TextInput(attrs={'placeholder': 'Ville de naissance'}),
            'situation_familiale': forms.Select(),
            'nombre_enfants':      forms.NumberInput(attrs={'min': '0'}),
            'commune':             forms.TextInput(attrs={'placeholder': 'Commune de résidence'}),
            'ville':               forms.TextInput(attrs={'placeholder': 'Ville de résidence'}),
            'num_cnps':            forms.TextInput(attrs={'placeholder': 'Numéro CNPS'}),
            'photo':               forms.FileInput(),
            'statut':              forms.Select(),
            'adresse':             forms.Textarea(attrs={'rows': 3, 'placeholder': 'Adresse complète'}),
        }

    def clean_photo(self):
        return _valider_photo(self.cleaned_data.get('photo'))


class DepartementForm(FormClassMixin, forms.ModelForm):
    class Meta:
        model = Departement
        fields = ['nom', 'description']
        widgets = {
            'nom':         forms.TextInput(attrs={'placeholder': 'Nom du département'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class PresenceForm(FormClassMixin, forms.ModelForm):
    class Meta:
        model = Presence
        fields = ['employe', 'date', 'heure_arrivee', 'heure_depart', 'statut', 'observation']
        widgets = {
            'employe':      forms.Select(),
            'date':         forms.DateInput(attrs={'type': 'date'}),
            'heure_arrivee': forms.TimeInput(attrs={'type': 'time'}),
            'heure_depart': forms.TimeInput(attrs={'type': 'time'}),
            'statut':       forms.Select(),
            'observation':  forms.Textarea(attrs={'rows': 2}),
        }


class CongeForm(FormClassMixin, forms.ModelForm):

    def __init__(self, *args, employe=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.employe = employe

    def clean(self):
        cleaned_data = super().clean()
        type_conge = cleaned_data.get('type_conge')
        date_debut = cleaned_data.get('date_debut')
        date_fin   = cleaned_data.get('date_fin')

        if date_debut and date_fin:
            # Règle 1 : date_fin >= date_debut
            if date_fin < date_debut:
                raise forms.ValidationError(
                    "La date de fin ne peut pas être antérieure à la date de début."
                )

            if self.employe:
                # Règle 2 : vérifier le chevauchement avec d'autres congés
                _valider_chevauchement(
                    Conge, self.employe, date_debut, date_fin,
                    self.instance.pk or None, "un congé existant",
                )

                # Règle 3 : quota congés annuels
                if type_conge == 'paye':
                    nb_jours = (date_fin - date_debut).days + 1
                    jours_deja_pris = self.employe.jours_conge_pris(
                        date_debut.year, exclude_pk=self.instance.pk or None
                    )
                    total = jours_deja_pris + nb_jours
                    if total > settings.QUOTA_CONGES_ANNUELS:
                        restants = max(0, settings.QUOTA_CONGES_ANNUELS - jours_deja_pris)
                        raise forms.ValidationError(
                            f"Quota dépassé : vous avez déjà utilisé {jours_deja_pris} jour(s) "
                            f"de congé annuel en {date_debut.year} et vous en demandez {nb_jours} "
                            f"de plus ({total} jours au total). "
                            f"Il vous reste {restants} jour(s) disponible(s)."
                        )

                # Règle 4 : congé maternité — exactement 98 jours, employée féminine
                if type_conge == 'maternite':
                    nb_jours = (date_fin - date_debut).days + 1
                    if nb_jours != 98:
                        raise forms.ValidationError(
                            f"Le congé maternité est fixé à 98 jours "
                            f"(durée calculée : {nb_jours} jour(s)). "
                            f"Sélectionnez une date de début pour que la date de retour soit calculée automatiquement."
                        )
                    if self.employe.sexe != 'F':
                        raise forms.ValidationError(
                            "Le congé maternité est réservé aux employées de sexe féminin."
                        )

        # Règle 5 : congé maladie — pièce justificative obligatoire (indépendante des dates)
        if type_conge == 'maladie':
            piece = cleaned_data.get('piece_justificative')
            if not piece and not (self.instance.pk and self.instance.piece_justificative):
                raise forms.ValidationError(
                    "Une pièce justificative (certificat médical) est obligatoire pour un congé maladie."
                )

        return cleaned_data

    class Meta:
        model = Conge
        fields = ['type_conge', 'date_debut', 'date_fin', 'motif', 'piece_justificative']
        widgets = {
            'type_conge':          forms.Select(),
            'date_debut':          forms.DateInput(attrs={'type': 'date'}),
            'date_fin':            forms.DateInput(attrs={'type': 'date'}),
            'motif':               forms.Textarea(attrs={'rows': 4, 'placeholder': 'Décrivez la raison de votre demande...'}),
            'piece_justificative': forms.ClearableFileInput(),
        }


class ValidationCongeForm(FormClassMixin, forms.ModelForm):
    class Meta:
        model = Conge
        fields = ['statut', 'commentaire_valideur']
        widgets = {
            'statut':               forms.HiddenInput(),  # ignoré par le mixin
            'commentaire_valideur': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Motif du rejet (obligatoire en cas de refus)'}),
        }

    def clean_statut(self):
        statut = self.cleaned_data.get('statut')
        if statut not in ('approuve', 'refuse'):
            raise forms.ValidationError("Décision invalide.")
        return statut

    def clean(self):
        cleaned_data = super().clean()
        statut = cleaned_data.get('statut')
        commentaire = cleaned_data.get('commentaire_valideur', '').strip()
        if statut == 'refuse' and not commentaire:
            self.add_error('commentaire_valideur', "Un motif de rejet est obligatoire.")
        return cleaned_data


class PermissionForm(FormClassMixin, forms.ModelForm):

    def __init__(self, *args, employe=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.employe = employe

    def clean(self):
        cleaned_data = super().clean()
        date_debut = cleaned_data.get('date_debut')
        date_fin   = cleaned_data.get('date_fin')

        if date_debut and date_fin:
            # Règle 1 : date_fin >= date_debut
            if date_fin < date_debut:
                raise forms.ValidationError(
                    "La date de fin ne peut pas être antérieure à la date de début."
                )

            # Règle 2 : durée maximale 3 jours
            nb_jours = (date_fin - date_debut).days + 1
            if nb_jours > 3:
                raise forms.ValidationError(
                    f"Une permission ne peut pas dépasser 3 jours "
                    f"(durée demandée : {nb_jours} jours)."
                )

            # Règle 3 : chevauchement avec d'autres permissions
            if self.employe:
                _valider_chevauchement(
                    Permission, self.employe, date_debut, date_fin,
                    self.instance.pk or None, "une permission existante",
                )

        return cleaned_data

    class Meta:
        model = Permission
        fields = ['date_debut', 'date_fin', 'motif']
        widgets = {
            'date_debut': forms.DateInput(attrs={'type': 'date'}),
            'date_fin':   forms.DateInput(attrs={'type': 'date'}),
            'motif':      forms.Textarea(attrs={'rows': 4, 'placeholder': 'Décrivez la raison de votre demande...'}),
        }


class ValidationPermissionForm(FormClassMixin, forms.ModelForm):
    """
    step=1 → responsable/DAF : valide_responsable ou refuse
    step=2 → DRH : approuve ou refuse
    """

    def __init__(self, *args, step=2, **kwargs):
        super().__init__(*args, **kwargs)
        if step == 1:
            self.fields['statut'].widget = forms.Select(choices=[
                ('valide_responsable', 'Transmettre à la DRH'),
                ('refuse', 'Refuser'),
            ])
        else:
            self.fields['statut'].widget = forms.Select(choices=[
                ('approuve', 'Approuver'),
                ('refuse', 'Refuser'),
            ])
        # Re-appliquer après remplacement du widget statut
        self._apply_widget_classes()

    def clean(self):
        cleaned_data = super().clean()
        statut = cleaned_data.get('statut')
        commentaire = cleaned_data.get('commentaire_valideur', '').strip()
        if statut == 'refuse' and not commentaire:
            self.add_error('commentaire_valideur', "Un motif de rejet est obligatoire.")
        return cleaned_data

    class Meta:
        model = Permission
        fields = ['statut', 'commentaire_valideur']
        widgets = {
            'statut':               forms.Select(),
            'commentaire_valideur': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Motif du rejet (obligatoire en cas de refus)',
            }),
        }


class EmployeProfilForm(FormClassMixin, forms.ModelForm):
    """Formulaire de modification du profil employé (auto-service).
    Seuls les champs que l'employé peut modifier lui-même sont inclus.
    Les champs administratifs (matricule, poste, département, rôle, statut) sont exclus.
    """
    widget_css_class = 'ec-form-control'

    class Meta:
        model = Employe
        fields = [
            'photo',
            'telephone', 'email',
            'sexe', 'date_naissance', 'lieu_naissance',
            'situation_familiale', 'nombre_enfants',
            'commune', 'ville', 'adresse',
            'num_cnps',
            'num_cni',
        ]
        widgets = {
            'photo':               forms.FileInput(attrs={'accept': 'image/*'}),
            'telephone':           forms.TextInput(attrs={'placeholder': '+225 XX XX XX XX'}),
            'email':               forms.EmailInput(attrs={'placeholder': 'votre@email.com'}),
            'sexe':                forms.Select(),
            'date_naissance':      forms.DateInput(attrs={'type': 'date'}),
            'lieu_naissance':      forms.TextInput(attrs={'placeholder': 'Ville de naissance'}),
            'situation_familiale': forms.Select(),
            'nombre_enfants':      forms.NumberInput(attrs={'min': '0'}),
            'commune':             forms.TextInput(attrs={'placeholder': 'Commune de résidence'}),
            'ville':               forms.TextInput(attrs={'placeholder': 'Ville de résidence'}),
            'adresse':             forms.Textarea(attrs={'rows': 3, 'placeholder': 'Adresse complète'}),
            'num_cnps':            forms.TextInput(attrs={'placeholder': 'Numéro CNPS'}),
            'num_cni':             forms.TextInput(attrs={'placeholder': 'Numéro CNI'}),
        }

    def clean_photo(self):
        return _valider_photo(self.cleaned_data.get('photo'))


class UserCompteForm(FormClassMixin, forms.ModelForm):
    """Modification du compte staff (RH/DAF/Admin sans fiche Employe liée).
    Permet de modifier nom, prénom et e-mail du compte Django.
    """

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'placeholder': 'Prénom'}),
            'last_name':  forms.TextInput(attrs={'placeholder': 'Nom de famille'}),
            'email':      forms.EmailInput(attrs={'placeholder': 'email@exemple.com'}),
        }
        labels = {
            'first_name': 'Prénom',
            'last_name':  'Nom de famille',
            'email':      'Adresse e-mail',
        }


