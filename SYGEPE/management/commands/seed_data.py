"""
Commande pour peupler la base de données avec des données de démonstration.
Usage : python manage.py seed_data
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from django.utils import timezone
from datetime import date, timedelta, time
import random
import unicodedata


def normalize_username(s):
    """Supprime les accents pour créer un identifiant simple."""
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii').lower()

from SYGEPE.models import Departement, Employe, Presence, Conge, Permission


class Command(BaseCommand):
    help = "Crée des données de démonstration pour SYGEPE"

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Creation des donnees de demonstration SYGEPE ==="))

        # Groupes
        self._creer_groupes()

        # Superuser admin
        self._creer_admin()

        # Départements
        depts = self._creer_departements()

        # Employés
        employes = self._creer_employes(depts)

        # Présences (30 derniers jours)
        self._creer_presences(employes)

        # Congés
        self._creer_conges(employes)

        # Permissions
        self._creer_permissions(employes)

        self.stdout.write(self.style.SUCCESS("\n[OK] Donnees de demonstration creees avec succes !"))
        self.stdout.write("   Admin : admin / admin123")
        self.stdout.write("   URL   : http://127.0.0.1:8000/")

    def _creer_groupes(self):
        for nom in ['Admin', 'RH', 'Employé']:
            g, created = Group.objects.get_or_create(name=nom)
            if created:
                self.stdout.write(f"  [OK] Groupe '{nom}' cree")

    def _creer_admin(self):
        if not User.objects.filter(username='admin').exists():
            admin = User.objects.create_superuser('admin', 'admin@sygepe.ci', 'admin123')
            admin.first_name = 'Super'
            admin.last_name = 'Admin'
            admin.save()
            self.stdout.write("  [OK] Superuser 'admin' cree (mdp: admin123)")

    def _creer_departements(self):
        data = [
            ("Direction Générale", "Direction et stratégie de l'entreprise"),
            ("Ressources Humaines", "Gestion du personnel et recrutement"),
            ("Informatique", "Systèmes d'information et développement"),
            ("Finance & Comptabilité", "Gestion financière et comptable"),
            ("Commercial", "Ventes et développement commercial"),
            ("Logistique", "Supply chain et logistique"),
        ]
        depts = []
        for nom, desc in data:
            d, created = Departement.objects.get_or_create(nom=nom, defaults={'description': desc})
            depts.append(d)
            if created:
                self.stdout.write(f"  [OK] Departement '{nom}' cree")
        return depts

    def _creer_employes(self, depts):
        employes_data = [
            ("Koné", "Amadou", "DG-001", "Directeur Général", depts[0]),
            ("Diallo", "Fatoumata", "RH-001", "Responsable RH", depts[1]),
            ("Traoré", "Ibrahim", "IT-001", "Développeur Senior", depts[2]),
            ("Coulibaly", "Mariam", "IT-002", "Analyste Système", depts[2]),
            ("Bamba", "Seydou", "FIN-001", "Comptable Principal", depts[3]),
            ("Touré", "Aissatou", "COM-001", "Chef Commercial", depts[4]),
            ("Sanogo", "Moussa", "LOG-001", "Responsable Logistique", depts[5]),
            ("Konaté", "Rokia", "RH-002", "Assistante RH", depts[1]),
            ("Diabaté", "Adama", "IT-003", "Développeur Junior", depts[2]),
            ("Ouédraogo", "Salimata", "FIN-002", "Contrôleur Financier", depts[3]),
            ("Sawadogo", "Boureima", "COM-002", "Commercial Terrain", depts[4]),
            ("Zongo", "Aminata", "LOG-002", "Agent Logistique", depts[5]),
        ]

        employes = []
        rh_group = Group.objects.get(name='RH')
        emp_group = Group.objects.get(name='Employé')

        for i, (nom, prenom, matricule, poste, dept) in enumerate(employes_data):
            email = f"{normalize_username(prenom)}.{normalize_username(nom)}@sygepe.ci"
            if not Employe.objects.filter(matricule=matricule).exists():
                # Créer un user Django pour chaque employé (sans accents dans le username)
                username = f"{normalize_username(prenom)}.{normalize_username(nom)}"
                user, _ = User.objects.get_or_create(
                    username=username,
                    defaults={
                        'email': email,
                        'first_name': prenom,
                        'last_name': nom,
                    }
                )
                user.set_password('employe123')
                if i == 1:  # Responsable RH
                    user.groups.set([rh_group])
                else:
                    user.groups.set([emp_group])
                user.save()

                emp = Employe.objects.create(
                    user=user,
                    matricule=matricule,
                    nom=nom,
                    prenom=prenom,
                    email=email,
                    poste=poste,
                    departement=dept,
                    date_embauche=date.today() - timedelta(days=random.randint(180, 1800)),
                    telephone=f"+225 0{random.randint(1,9)} {random.randint(10,99)} {random.randint(10,99)} {random.randint(10,99)}",
                    statut='actif',
                )
                employes.append(emp)
                self.stdout.write(f"  [OK] Employe '{emp.get_full_name()}' cree")
            else:
                employes.append(Employe.objects.get(matricule=matricule))

        return employes

    def _creer_presences(self, employes):
        today = date.today()
        statuts = ['present', 'present', 'present', 'present', 'absent', 'retard']
        count = 0
        for emp in employes:
            for days_ago in range(0, 30):
                jour = today - timedelta(days=days_ago)
                if jour.weekday() < 5:  # Lun-Ven
                    statut = random.choice(statuts)
                    if not Presence.objects.filter(employe=emp, date=jour).exists():
                        Presence.objects.create(
                            employe=emp,
                            date=jour,
                            heure_arrivee=time(8, random.randint(0, 30)) if statut != 'absent' else None,
                            heure_depart=time(17, random.randint(0, 30)) if statut != 'absent' else None,
                            statut=statut,
                        )
                        count += 1
        self.stdout.write(f"  [OK] {count} enregistrements de presence crees")

    def _creer_conges(self, employes):
        types = ['paye', 'maladie', 'exceptionnel']
        statuts = ['en_attente', 'approuve', 'approuve', 'refuse']
        count = 0
        admin = User.objects.get(username='admin')
        for emp in random.sample(employes, min(6, len(employes))):
            type_c = random.choice(types)
            debut = date.today() + timedelta(days=random.randint(-10, 30))
            fin = debut + timedelta(days=random.randint(1, 7))
            statut = random.choice(statuts)
            Conge.objects.create(
                employe=emp,
                type_conge=type_c,
                date_debut=debut,
                date_fin=fin,
                motif="Demande de congé pour raison personnelle.",
                statut=statut,
                valideur=admin if statut != 'en_attente' else None,
                date_validation=timezone.now() if statut != 'en_attente' else None,
            )
            count += 1
        self.stdout.write(f"  [OK] {count} demandes de conge creees")

    def _creer_permissions(self, employes):
        statuts = ['en_attente', 'approuve', 'approuve', 'refuse']
        count = 0
        admin = User.objects.get(username='admin')
        for emp in random.sample(employes, min(8, len(employes))):
            jour = date.today() + timedelta(days=random.randint(-5, 15))
            debut = time(10, 0)
            fin = time(12, 0)
            statut = random.choice(statuts)
            Permission.objects.create(
                employe=emp,
                date=jour,
                heure_debut=debut,
                heure_fin=fin,
                motif="Rendez-vous médical / démarche administrative.",
                statut=statut,
                valideur=admin if statut != 'en_attente' else None,
                date_validation=timezone.now() if statut != 'en_attente' else None,
            )
            count += 1
        self.stdout.write(f"  [OK] {count} demandes de permission creees")
