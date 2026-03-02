import os
from django import forms
from django.contrib.auth.models import User
from .models import Employe, Departement, Presence, Conge, Permission, Boutique

PHOTO_MAX_SIZE    = 5 * 1024 * 1024  # 5 Mo
PHOTO_EXTENSIONS  = {'.jpg', '.jpeg', '.png', '.webp'}


def _valider_photo(photo):
    """Validation commune : taille ≤ 5 Mo et extension JPEG/PNG/WebP."""
    if photo and hasattr(photo, 'size'):
        if photo.size > PHOTO_MAX_SIZE:
            raise forms.ValidationError("La photo ne doit pas dépasser 5 Mo.")
        ext = os.path.splitext(photo.name)[1].lower()
        if ext not in PHOTO_EXTENSIONS:
            raise forms.ValidationError(
                "Format non supporté. Utilisez JPEG, PNG ou WebP."
            )
    return photo


class EmployeForm(forms.ModelForm):
    class Meta:
        model = Employe
        fields = [
            'matricule', 'nom', 'prenom', 'sexe', 'email', 'telephone',
            'poste', 'departement', 'boutique', 'date_embauche', 'date_naissance',
            'lieu_naissance', 'situation_familiale', 'nombre_enfants',
            'commune', 'ville', 'num_cnps',
            'photo', 'statut', 'adresse',
        ]
        widgets = {
            'matricule':          forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: EMP001'}),
            'nom':                forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom de famille'}),
            'prenom':             forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Prénom'}),
            'sexe':               forms.Select(attrs={'class': 'form-control'}),
            'email':              forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@exemple.com'}),
            'telephone':          forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+225 XX XX XX XX'}),
            'poste':              forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Intitulé du poste'}),
            'departement':        forms.Select(attrs={'class': 'form-control'}),
            'boutique':           forms.Select(attrs={'class': 'form-control'}),
            'date_embauche':      forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_naissance':     forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'lieu_naissance':     forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ville de naissance'}),
            'situation_familiale':forms.Select(attrs={'class': 'form-control'}),
            'nombre_enfants':     forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'commune':            forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Commune de résidence'}),
            'ville':              forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ville de résidence'}),
            'num_cnps':           forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Numéro CNPS'}),
            'photo':              forms.FileInput(attrs={'class': 'form-control'}),
            'statut':             forms.Select(attrs={'class': 'form-control'}),
            'adresse':            forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Adresse complète'}),
        }

    def clean_photo(self):
        return _valider_photo(self.cleaned_data.get('photo'))


class DepartementForm(forms.ModelForm):
    class Meta:
        model = Departement
        fields = ['nom', 'description']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom du département'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class PresenceForm(forms.ModelForm):
    class Meta:
        model = Presence
        fields = ['employe', 'date', 'heure_arrivee', 'heure_depart', 'statut', 'observation']
        widgets = {
            'employe': forms.Select(attrs={'class': 'form-control'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'heure_arrivee': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'heure_depart': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'statut': forms.Select(attrs={'class': 'form-control'}),
            'observation': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class CongeForm(forms.ModelForm):

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
                overlap = Conge.objects.filter(
                    employe=self.employe,
                    statut__in=['en_attente', 'approuve'],
                    date_debut__lte=date_fin,
                    date_fin__gte=date_debut,
                )
                if self.instance.pk:
                    overlap = overlap.exclude(pk=self.instance.pk)
                if overlap.exists():
                    c = overlap.first()
                    raise forms.ValidationError(
                        f"Cette période chevauche un congé existant "
                        f"({c.date_debut.strftime('%d/%m/%Y')} → "
                        f"{c.date_fin.strftime('%d/%m/%Y')}, {c.get_statut_display()})."
                    )

                # Règle 3 : quota congés payés
                if type_conge == 'paye':
                    nb_jours = (date_fin - date_debut).days + 1
                    jours_deja_pris = self.employe.jours_conge_pris(
                        date_debut.year, exclude_pk=self.instance.pk or None
                    )
                    total = jours_deja_pris + nb_jours
                    if total > 30:
                        restants = max(0, 30 - jours_deja_pris)
                        raise forms.ValidationError(
                            f"Quota dépassé : vous avez déjà utilisé {jours_deja_pris} jour(s) "
                            f"de congé payé en {date_debut.year} et vous en demandez {nb_jours} "
                            f"de plus ({total} jours au total). "
                            f"Il vous reste {restants} jour(s) disponible(s)."
                        )

        return cleaned_data

    class Meta:
        model = Conge
        fields = ['type_conge', 'date_debut', 'date_fin', 'motif']
        widgets = {
            'type_conge': forms.Select(attrs={'class': 'form-control'}),
            'date_debut': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'motif': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Décrivez la raison de votre demande...'}),
        }


class ValidationCongeForm(forms.ModelForm):
    class Meta:
        model = Conge
        fields = ['statut', 'commentaire_valideur']
        widgets = {
            'statut': forms.HiddenInput(),
            'commentaire_valideur': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Commentaire (optionnel)'}),
        }

    def clean_statut(self):
        statut = self.cleaned_data.get('statut')
        if statut not in ('approuve', 'refuse'):
            raise forms.ValidationError("Décision invalide.")
        return statut


class PermissionForm(forms.ModelForm):

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

            # Règle 2 : chevauchement avec d'autres permissions
            if self.employe:
                overlap = Permission.objects.filter(
                    employe=self.employe,
                    statut__in=['en_attente', 'approuve'],
                    date_debut__lte=date_fin,
                    date_fin__gte=date_debut,
                )
                if self.instance.pk:
                    overlap = overlap.exclude(pk=self.instance.pk)
                if overlap.exists():
                    p = overlap.first()
                    raise forms.ValidationError(
                        f"Cette période chevauche une permission existante "
                        f"({p.date_debut.strftime('%d/%m/%Y')} → "
                        f"{p.date_fin.strftime('%d/%m/%Y')}, {p.get_statut_display()})."
                    )

        return cleaned_data

    class Meta:
        model = Permission
        fields = ['date_debut', 'date_fin', 'motif']
        widgets = {
            'date_debut': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'motif': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Décrivez la raison de votre demande...'}),
        }


class ValidationPermissionForm(forms.ModelForm):
    class Meta:
        model = Permission
        fields = ['statut', 'commentaire_valideur']
        widgets = {
            'statut': forms.Select(attrs={'class': 'form-control'}, choices=[
                ('approuve', 'Approuvé'),
                ('refuse', 'Refusé'),
            ]),
            'commentaire_valideur': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Commentaire (optionnel)'}),
        }


class EmployeProfilForm(forms.ModelForm):
    """Formulaire de modification du profil employé (auto-service).
    Seuls les champs que l'employé peut modifier lui-même sont inclus.
    Les champs administratifs (matricule, poste, département, rôle, statut) sont exclus.
    """
    class Meta:
        model = Employe
        fields = [
            'photo',
            'telephone', 'email',
            'sexe', 'date_naissance', 'lieu_naissance',
            'situation_familiale', 'nombre_enfants',
            'commune', 'ville', 'adresse',
            'num_cnps',
        ]
        widgets = {
            'photo':              forms.FileInput(attrs={'class': 'ec-form-control', 'accept': 'image/*'}),
            'telephone':          forms.TextInput(attrs={'class': 'ec-form-control', 'placeholder': '+225 XX XX XX XX'}),
            'email':              forms.EmailInput(attrs={'class': 'ec-form-control', 'placeholder': 'votre@email.com'}),
            'sexe':               forms.Select(attrs={'class': 'ec-form-control'}),
            'date_naissance':     forms.DateInput(attrs={'class': 'ec-form-control', 'type': 'date'}),
            'lieu_naissance':     forms.TextInput(attrs={'class': 'ec-form-control', 'placeholder': 'Ville de naissance'}),
            'situation_familiale':forms.Select(attrs={'class': 'ec-form-control'}),
            'nombre_enfants':     forms.NumberInput(attrs={'class': 'ec-form-control', 'min': '0'}),
            'commune':            forms.TextInput(attrs={'class': 'ec-form-control', 'placeholder': 'Commune de résidence'}),
            'ville':              forms.TextInput(attrs={'class': 'ec-form-control', 'placeholder': 'Ville de résidence'}),
            'adresse':            forms.Textarea(attrs={'class': 'ec-form-control', 'rows': 3, 'placeholder': 'Adresse complète'}),
            'num_cnps':           forms.TextInput(attrs={'class': 'ec-form-control', 'placeholder': 'Numéro CNPS'}),
        }

    def clean_photo(self):
        return _valider_photo(self.cleaned_data.get('photo'))


class BoutiqueForm(forms.ModelForm):
    class Meta:
        model = Boutique
        fields = ['nom', 'description', 'adresse', 'telephone', 'email', 'responsable']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom de la boutique'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Description de la boutique'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Adresse de la boutique'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+225 XX XX XX XX'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@boutique.ci'}),
            'responsable': forms.Select(attrs={'class': 'form-control'}),
        }
