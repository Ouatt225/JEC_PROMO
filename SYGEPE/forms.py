from django import forms
from django.contrib.auth.models import User
from .models import Employe, Departement, Presence, Conge, Permission, Boutique


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

        # Règle générale : date_fin doit être >= date_debut
        if date_debut and date_fin:
            if date_fin < date_debut:
                raise forms.ValidationError(
                    "La date de fin ne peut pas être antérieure à la date de début."
                )

        if type_conge == 'paye' and date_debut and date_fin:
            nb_jours = (date_fin - date_debut).days + 1
            annee = date_debut.year

            # Calcul des jours déjà utilisés cette année (approuvés ou en attente)
            if self.employe:
                qs = Conge.objects.filter(
                    employe=self.employe,
                    type_conge='paye',
                    date_debut__year=annee,
                    statut__in=['en_attente', 'approuve'],
                )
                if self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
                jours_deja_pris = sum(
                    (c.date_fin - c.date_debut).days + 1 for c in qs
                )
            else:
                jours_deja_pris = 0

            total = jours_deja_pris + nb_jours
            if total > 30:
                restants = max(0, 30 - jours_deja_pris)
                raise forms.ValidationError(
                    f"Quota dépassé : vous avez déjà utilisé {jours_deja_pris} jour(s) "
                    f"de congé payé en {annee} et vous en demandez {nb_jours} de plus "
                    f"({total} jours au total). Il vous reste {restants} jour(s) disponible(s)."
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
