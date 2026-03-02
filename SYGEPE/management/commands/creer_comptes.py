"""
Crée les comptes utilisateurs Django pour tous les employés
et les lie à leur profil Employe.

Convention username : [initiale_prenom].[nom_normalisé].[4_derniers_chiffres_cnps]
Convention password : JEC[3_premiers_chars_nom]+[4_derniers_chiffres_cnps]@2026

Usage : python manage.py creer_comptes
        python manage.py creer_comptes --reset   # supprime et recrée tous les comptes
"""
import re
import unicodedata
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group


def normalize(s):
    """Supprime accents, espaces, apostrophes — retourne minuscule ASCII."""
    s = unicodedata.normalize('NFD', s)
    s = s.encode('ascii', 'ignore').decode('ascii')
    return re.sub(r"[^a-z0-9]", '', s.lower())


def cnps_digits(cnps):
    return re.sub(r'\D', '', cnps)


def make_username(nom, prenom, cnps):
    initiale = normalize(prenom.split()[0])[0] if prenom else 'x'
    nom_norm = normalize(nom)[:10]
    last4    = cnps_digits(cnps)[-4:]
    return f"{initiale}.{nom_norm}.{last4}"


def make_password(nom, cnps):
    nom_part = normalize(nom)[:3].upper()
    last4    = cnps_digits(cnps)[-4:]
    return f"JEC{nom_part}{last4}@2026"


class Command(BaseCommand):
    help = 'Crée les comptes utilisateurs Django pour les 51 employés JEC PROMO'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Supprime et recrée tous les comptes employés existants',
        )

    def handle(self, *args, **options):
        from SYGEPE.models import Employe

        # Groupe employé
        groupe_employe, _ = Group.objects.get_or_create(name='Employe')

        employes = Employe.objects.all().order_by('matricule')

        if not employes.exists():
            self.stdout.write(self.style.WARNING(
                'Aucun employe trouve. Lancez d abord : python manage.py import_employes'
            ))
            return

        created = updated = skipped = errors = 0

        for emp in employes:
            cnps    = emp.num_cnps or ''
            nom     = emp.nom or ''
            prenom  = emp.prenom or ''

            if not cnps or not nom or not prenom:
                self.stdout.write(f'  IGNORE : {emp.matricule} - donnees manquantes')
                skipped += 1
                continue

            username = make_username(nom, prenom, cnps)
            password = make_password(nom, cnps)
            email    = f'{emp.matricule.lower()}@jecpromo.ci'

            try:
                if options['reset'] and emp.user:
                    # Supprimer l'ancien compte lié
                    old_user = emp.user
                    emp.user = None
                    emp.save(update_fields=['user'])
                    old_user.delete()

                if emp.user:
                    # Compte déjà lié : mettre à jour le mot de passe et username
                    user = emp.user
                    user.username   = username
                    user.email      = email
                    user.first_name = prenom.title()
                    user.last_name  = nom.title()
                    user.set_password(password)
                    user.is_active  = True
                    user.is_staff   = False
                    user.save()
                    updated += 1
                    self.stdout.write(f'  MAJ     : {emp.matricule} -> {username}')
                else:
                    # Vérifier que le username n'existe pas déjà
                    if User.objects.filter(username=username).exists():
                        # Ajouter un suffixe numérique pour éviter le doublon
                        base = username
                        suffix = 2
                        while User.objects.filter(username=username).exists():
                            username = f'{base}{suffix}'
                            suffix += 1

                    user = User.objects.create_user(
                        username=username,
                        password=password,
                        email=email,
                        first_name=prenom.title(),
                        last_name=nom.title(),
                        is_active=True,
                        is_staff=False,
                    )
                    # Assigner le groupe Employe
                    user.groups.add(groupe_employe)

                    # Lier le compte à l'employé
                    emp.user = user
                    emp.role = 'employe'
                    emp.save(update_fields=['user', 'role'])

                    created += 1
                    self.stdout.write(f'  CREE    : {emp.matricule} -> {username}  |  mdp: {password}')

            except Exception as e:
                errors += 1
                self.stdout.write(self.style.ERROR(
                    f'  ERREUR  : {emp.matricule} {nom} -> {e}'
                ))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Termine : {created} cree(s), {updated} mis a jour, '
            f'{skipped} ignore(s), {errors} erreur(s).'
        ))
        self.stdout.write(
            f'Les agents peuvent se connecter sur /login/ avec leur username et mot de passe.'
        )
