from io import BytesIO
from datetime import date, timedelta

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from django.core.files.uploadedfile import SimpleUploadedFile

from .models import Employe, Departement, Conge, Permission
from .forms import CongeForm, PermissionForm, EmployeForm, EmployeProfilForm
from .views import is_admin, is_rh, _groupes_utilisateur


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def _creer_employe(matricule='E001', nom='Koné', prenom='Seydou', dept=None, **kwargs):
    if dept is None:
        dept, _ = Departement.objects.get_or_create(nom='Ventes')
    return Employe.objects.create(
        matricule=matricule, nom=nom, prenom=prenom,
        poste='Vendeur', departement=dept, **kwargs
    )


def _creer_user_avec_groupe(username, groupe_nom):
    user = User.objects.create_user(username, password='testpass123')
    grp, _ = Group.objects.get_or_create(name=groupe_nom)
    user.groups.add(grp)
    return user


def _image_jpeg(nom='photo.jpg', taille_ko=50):
    """Crée un vrai fichier JPEG en mémoire via PIL."""
    try:
        from PIL import Image
        img = Image.new('RGB', (100, 100), color=(200, 150, 100))
        buf = BytesIO()
        img.save(buf, format='JPEG')
        buf.seek(0)
        return SimpleUploadedFile(nom, buf.read(), content_type='image/jpeg')
    except ImportError:
        # Pillow non disponible : retourne un contenu binaire minimal
        return SimpleUploadedFile(nom, b'\xff\xd8\xff\xe0' + b'\x00' * 20, content_type='image/jpeg')


# ─────────────────────────────────────────────────────────────
# 1. Tests Modèle Employe
# ─────────────────────────────────────────────────────────────
class EmployeModeleTest(TestCase):

    def setUp(self):
        self.employe = _creer_employe(date_naissance=None)

    def test_get_full_name(self):
        self.assertEqual(self.employe.get_full_name(), 'Seydou Koné')

    def test_str(self):
        self.assertIn('E001', str(self.employe))

    def test_age_sans_date_naissance(self):
        self.assertIsNone(self.employe.age)

    def test_age_avec_date_naissance(self):
        self.employe.date_naissance = date(1990, 1, 1)
        attendu = date.today().year - 1990
        if (date.today().month, date.today().day) < (1, 1):
            attendu -= 1
        self.assertEqual(self.employe.age, attendu)

    def test_jours_conge_pris_zero_par_defaut(self):
        self.assertEqual(self.employe.jours_conge_pris(date.today().year), 0)

    def test_jours_conge_pris_approuve(self):
        today = date.today()
        Conge.objects.create(
            employe=self.employe, type_conge='paye',
            date_debut=today + timedelta(days=1),
            date_fin=today + timedelta(days=5),
            motif='Test', statut='approuve',
        )
        self.assertEqual(self.employe.jours_conge_pris(today.year), 5)

    def test_jours_conge_pris_en_attente_compte(self):
        today = date.today()
        Conge.objects.create(
            employe=self.employe, type_conge='paye',
            date_debut=today + timedelta(days=1),
            date_fin=today + timedelta(days=3),
            motif='Test', statut='en_attente',
        )
        self.assertEqual(self.employe.jours_conge_pris(today.year), 3)

    def test_jours_conge_pris_refuse_ne_compte_pas(self):
        today = date.today()
        Conge.objects.create(
            employe=self.employe, type_conge='paye',
            date_debut=today + timedelta(days=1),
            date_fin=today + timedelta(days=5),
            motif='Test', statut='refuse',
        )
        self.assertEqual(self.employe.jours_conge_pris(today.year), 0)

    def test_jours_conge_pris_exclude_pk(self):
        """Lors d'une modification, le congé en cours doit être exclu du calcul."""
        today = date.today()
        c = Conge.objects.create(
            employe=self.employe, type_conge='paye',
            date_debut=today + timedelta(days=1),
            date_fin=today + timedelta(days=5),
            motif='Test', statut='approuve',
        )
        self.assertEqual(self.employe.jours_conge_pris(today.year, exclude_pk=c.pk), 0)


# ─────────────────────────────────────────────────────────────
# 2. Tests CongeForm
# ─────────────────────────────────────────────────────────────
class CongeFormTest(TestCase):

    def setUp(self):
        self.employe = _creer_employe('E002', 'Bamba', 'Aïcha')
        self.today = date.today()

    def _form(self, debut, fin, type_conge='paye', motif='Test'):
        return CongeForm(data={
            'type_conge': type_conge,
            'date_debut': debut,
            'date_fin':   fin,
            'motif':      motif,
        }, employe=self.employe)

    def test_dates_valides(self):
        f = self._form(self.today + timedelta(days=1), self.today + timedelta(days=5))
        self.assertTrue(f.is_valid(), f.errors)

    def test_date_fin_avant_debut(self):
        f = self._form(self.today + timedelta(days=5), self.today + timedelta(days=1))
        self.assertFalse(f.is_valid())
        self.assertIn('__all__', f.errors)

    def test_quota_30_jours_ok(self):
        annee = self.today.year
        f = self._form(date(annee, 2, 1), date(annee, 3, 2))  # 30 jours
        self.assertTrue(f.is_valid(), f.errors)

    def test_quota_31_jours_depasse(self):
        annee = self.today.year
        f = self._form(date(annee, 2, 1), date(annee, 3, 3))  # 31 jours
        self.assertFalse(f.is_valid())

    def test_quota_cumule_depasse(self):
        """Déjà 28 j pris + 5 j demandés → refusé."""
        today = self.today
        Conge.objects.create(
            employe=self.employe, type_conge='paye',
            date_debut=date(today.year, 1, 1), date_fin=date(today.year, 1, 28),
            motif='Existant', statut='approuve',
        )
        f = self._form(today + timedelta(days=60), today + timedelta(days=64))
        self.assertFalse(f.is_valid())

    def test_type_maladie_pas_de_quota(self):
        """Le quota ne s'applique qu'aux congés payés."""
        annee = self.today.year
        f = self._form(date(annee, 1, 1), date(annee, 3, 31), type_conge='maladie')
        self.assertTrue(f.is_valid(), f.errors)

    def test_chevauchement_refus(self):
        today = self.today
        Conge.objects.create(
            employe=self.employe, type_conge='maladie',
            date_debut=today + timedelta(days=5),
            date_fin=today + timedelta(days=10),
            motif='Existant', statut='approuve',
        )
        f = self._form(today + timedelta(days=8), today + timedelta(days=12), type_conge='maladie')
        self.assertFalse(f.is_valid())

    def test_chevauchement_conge_refuse_ignore(self):
        """Un congé refusé ne bloque pas une nouvelle demande sur la même période."""
        today = self.today
        Conge.objects.create(
            employe=self.employe, type_conge='maladie',
            date_debut=today + timedelta(days=5),
            date_fin=today + timedelta(days=10),
            motif='Refusé', statut='refuse',
        )
        f = self._form(today + timedelta(days=5), today + timedelta(days=10), type_conge='maladie')
        self.assertTrue(f.is_valid(), f.errors)

    def test_consecutive_valide(self):
        """Deux congés qui se suivent (sans chevauchement) sont tous deux valides."""
        today = self.today
        Conge.objects.create(
            employe=self.employe, type_conge='maladie',
            date_debut=today + timedelta(days=1),
            date_fin=today + timedelta(days=3),
            motif='Premier', statut='approuve',
        )
        f = self._form(today + timedelta(days=4), today + timedelta(days=6), type_conge='maladie')
        self.assertTrue(f.is_valid(), f.errors)


# ─────────────────────────────────────────────────────────────
# 3. Tests PermissionForm
# ─────────────────────────────────────────────────────────────
class PermissionFormTest(TestCase):

    def setUp(self):
        self.employe = _creer_employe('E003', 'Traoré', 'Moussa')
        self.today = date.today()

    def _form(self, debut, fin, motif='Test'):
        return PermissionForm(data={
            'date_debut': debut,
            'date_fin':   fin,
            'motif':      motif,
        }, employe=self.employe)

    def test_dates_valides(self):
        f = self._form(self.today + timedelta(days=1), self.today + timedelta(days=2))
        self.assertTrue(f.is_valid(), f.errors)

    def test_date_fin_avant_debut(self):
        f = self._form(self.today + timedelta(days=5), self.today)
        self.assertFalse(f.is_valid())

    def test_chevauchement_refus(self):
        today = self.today
        Permission.objects.create(
            employe=self.employe,
            date_debut=today + timedelta(days=2),
            date_fin=today + timedelta(days=5),
            motif='Existant', statut='approuve',
        )
        f = self._form(today + timedelta(days=4), today + timedelta(days=7))
        self.assertFalse(f.is_valid())

    def test_apres_existant_valide(self):
        today = self.today
        Permission.objects.create(
            employe=self.employe,
            date_debut=today + timedelta(days=1),
            date_fin=today + timedelta(days=3),
            motif='Premier', statut='approuve',
        )
        f = self._form(today + timedelta(days=4), today + timedelta(days=6))
        self.assertTrue(f.is_valid(), f.errors)

    def test_sans_employe_pas_de_chevauchement(self):
        """Sans employe passé au form, pas d'erreur de chevauchement."""
        f = PermissionForm(data={
            'date_debut': self.today + timedelta(days=1),
            'date_fin':   self.today + timedelta(days=3),
            'motif':      'Test',
        })
        self.assertTrue(f.is_valid(), f.errors)


# ─────────────────────────────────────────────────────────────
# 4. Tests validation photo
# ─────────────────────────────────────────────────────────────
class PhotoValidationTest(TestCase):

    def test_photo_jpeg_valide(self):
        photo = _image_jpeg()
        from .forms import _valider_photo
        result = _valider_photo(photo)
        self.assertEqual(result, photo)

    def test_photo_trop_grande(self):
        from .forms import _valider_photo
        from django.core.exceptions import ValidationError as DjangoVE
        from django import forms as dj_forms
        gros_fichier = SimpleUploadedFile(
            'big.jpg', b'\xff\xd8\xff\xe0' + b'x' * (6 * 1024 * 1024),
            content_type='image/jpeg'
        )
        with self.assertRaises(dj_forms.ValidationError):
            _valider_photo(gros_fichier)

    def test_photo_mauvaise_extension(self):
        from .forms import _valider_photo
        from django import forms as dj_forms
        fichier_bmp = SimpleUploadedFile('photo.bmp', b'BM' + b'\x00' * 50, content_type='image/bmp')
        with self.assertRaises(dj_forms.ValidationError):
            _valider_photo(fichier_bmp)

    def test_photo_none_ok(self):
        """Pas de photo → pas d'erreur (champ optionnel)."""
        from .forms import _valider_photo
        self.assertIsNone(_valider_photo(None))


# ─────────────────────────────────────────────────────────────
# 5. Tests helpers de rôles et cache
# ─────────────────────────────────────────────────────────────
class RolesEtCacheTest(TestCase):

    def setUp(self):
        self.user_rh    = _creer_user_avec_groupe('rh_user', 'RH')
        self.user_admin = _creer_user_avec_groupe('admin_user', 'Admin')
        self.user_daf   = _creer_user_avec_groupe('daf_user', 'DAF')
        self.user_emp   = User.objects.create_user('emp_user', password='testpass123')

    def test_is_rh_pour_rh(self):
        self.assertTrue(is_rh(self.user_rh))

    def test_is_rh_pour_admin(self):
        self.assertTrue(is_rh(self.user_admin))

    def test_is_rh_pour_daf(self):
        self.assertTrue(is_rh(self.user_daf))

    def test_is_rh_faux_pour_employe(self):
        self.assertFalse(is_rh(self.user_emp))

    def test_is_admin_vrai(self):
        self.assertTrue(is_admin(self.user_admin))

    def test_is_admin_faux_pour_rh(self):
        self.assertFalse(is_admin(self.user_rh))

    def test_is_admin_vrai_pour_superuser(self):
        su = User.objects.create_superuser('superadmin', password='testpass123')
        self.assertTrue(is_admin(su))

    def test_cache_groupes_meme_objet(self):
        """Deux appels consécutifs retournent le même objet set (pas de 2e requête DB)."""
        g1 = _groupes_utilisateur(self.user_rh)
        g2 = _groupes_utilisateur(self.user_rh)
        self.assertIs(g1, g2)

    def test_cache_contient_bons_groupes(self):
        groupes = _groupes_utilisateur(self.user_rh)
        self.assertIn('RH', groupes)
        self.assertNotIn('Admin', groupes)


# ─────────────────────────────────────────────────────────────
# 6. Tests vues principales
# ─────────────────────────────────────────────────────────────
class VuesDashboardTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user_rh  = _creer_user_avec_groupe('rh2', 'RH')
        self.user_emp = User.objects.create_user('emp2', password='testpass123')

    def test_dashboard_accessible_rh(self):
        self.client.login(username='rh2', password='testpass123')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_redirige_employe_vers_profil(self):
        self.client.login(username='emp2', password='testpass123')
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, reverse('profil'))

    def test_dashboard_non_connecte_redirige_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])


class VuesCongesTest(TestCase):

    def setUp(self):
        self.client  = Client()
        self.user    = User.objects.create_user('emp3', password='testpass123')
        self.employe = _creer_employe('E010', 'Diallo', 'Ibrahim')
        self.employe.user = self.user
        self.employe.save()

    def test_liste_conges_accessible(self):
        self.client.login(username='emp3', password='testpass123')
        response = self.client.get(reverse('liste_conges'))
        self.assertEqual(response.status_code, 200)

    def test_demande_conge_get(self):
        self.client.login(username='emp3', password='testpass123')
        response = self.client.get(reverse('demander_conge'))
        self.assertEqual(response.status_code, 200)

    def test_demande_conge_chevauchement_rejete(self):
        """Soumission d'un congé qui chevauche un existant → formulaire invalide."""
        today = date.today()
        Conge.objects.create(
            employe=self.employe, type_conge='maladie',
            date_debut=today + timedelta(days=5),
            date_fin=today + timedelta(days=10),
            motif='Existant', statut='approuve',
        )
        self.client.login(username='emp3', password='testpass123')
        response = self.client.post(reverse('demander_conge'), {
            'type_conge': 'paye',
            'date_debut': (today + timedelta(days=8)).isoformat(),
            'date_fin':   (today + timedelta(days=12)).isoformat(),
            'motif':      'Chevauchant',
        })
        # Le formulaire doit être ré-affiché avec des erreurs (pas de redirect)
        self.assertEqual(response.status_code, 200)


class VuesLoginTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user   = User.objects.create_user('login_user', password='testpass123')

    def test_login_get(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)

    def test_login_identifiants_corrects(self):
        response = self.client.post(reverse('login'), {
            'username': 'login_user',
            'password': 'testpass123',
        })
        self.assertEqual(response.status_code, 302)

    def test_login_mauvais_mot_de_passe(self):
        response = self.client.post(reverse('login'), {
            'username': 'login_user',
            'password': 'mauvais',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'incorrect')

    def test_logout_deconnecte(self):
        self.client.login(username='login_user', password='testpass123')
        response = self.client.get(reverse('logout'))
        self.assertRedirects(response, reverse('login'))
