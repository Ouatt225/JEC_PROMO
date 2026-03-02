"""
Commande d'import du personnel réel JEC PROMO 2026.
Usage : python manage.py import_employes
"""
from django.core.management.base import BaseCommand
from datetime import datetime
import re


def parse_date(s):
    """Extrait la date (DD/MM/YYYY) depuis une chaîne comme '09/04/1977 ABOBO'."""
    m = re.search(r'(\d{1,2})\s*/\s*(\d{2})\s*/\s*(\d{4})', s)
    if m:
        try:
            return datetime.strptime(f"{m.group(1).zfill(2)}/{m.group(2)}/{m.group(3)}", "%d/%m/%Y").date()
        except ValueError:
            return None
    return None


def parse_lieu(s):
    """Extrait le lieu de naissance depuis '09/04/1977 ABOBO' → 'ABOBO'."""
    # Retire la date et les mots parasites (à, a, Ã )
    s = re.sub(r'\d{1,2}\s*/\s*\d{2}\s*/\s*\d{4}', '', s)
    s = re.sub(r'\b[àaÀÃ]\b', '', s)
    s = s.strip(' /\xa0')
    return s.strip() or ''


def parse_enfants(s):
    """Extrait le nombre d'enfants depuis '2 enfants', '(05) enfants', '0', etc."""
    s = str(s).strip()
    m = re.search(r'\d+', s)
    return int(m.group()) if m else 0


def parse_situation(s):
    s = s.strip().upper()
    if 'MARIE' in s:
        return 'marie'
    return 'celibataire'


# ─────────────────────────────────────────────────────────────────────────────
# Données réelles — LISTE DU PERSONNEL JEC PROMO 2026
# Format : (num, nom, prenom, date_nais_raw, matrimonial, enfants_raw,
#            telephone, contrat, poste, cnps, date_emb_raw)
# ─────────────────────────────────────────────────────────────────────────────
PERSONNEL = [
    (1,  'MEA',        'AKOUA MICHELLE',         '09/04/1977 ABOBO',              'MARIEE',      '2 enfants',  '07 47 22 83 93 / 05 65 29 39 25',  'CDI', 'CHARGEE DE MISSION',      '277 011 019 725', '19/12/2008'),
    (2,  'BOLI BI',    'TAH FERDINAND',           '29/12/1974 LOLOGUI/GOHITAFLA',  'CELIBATAIRE', '2 enfants',  '07 87 60 28 70 / 01 51 97 01 64',  'CDI', 'MAGASINIER',              '174 011 617 126', '01/01/2015'),
    (3,  'KONE',       'OUMAR',                   '20/05/1984 BECEDI',             'CELIBATAIRE', '3 enfants',  '07 08 95 95 97',                   'CDI', 'RESPONSABLE SECTEUR',    '184 011 643 716', '01/07/2016'),
    (4,  'OBOU',       'GOUEDJI EDITH STEPHANIE', '11/03/1989 KOUMASSI',           'CELIBATAIRE', '3 enfants',  '07 58 51 71 76 / 01 02 82 82 41',  'CDI', 'RESPONSABLE BOUTIQUE',   '289 011 643 665', '01/07/2016'),
    (5,  'KOUHE',      'GUI ADISSA REINE',        '13/12/1989 ATTECOUBO',          'MARIEE',      '2 enfants',  '07 48 41 44 36',                   'CDI', 'ANIMATRICE RESEAU',      '289 011 643 499', '01/07/2016'),
    (6,  'ANGAMAN',    'BENIE HENRI JOEL',        '20/02/1994 DAME/AGNIBILEKRO',   'CELIBATAIRE', '0',          '07 48 65 17 99',                   'CDI', 'CHEF COMPTABLE',         '194 011 755 154', '01/08/2017'),
    (7,  'GUEY',       'GNONMAHO FELICITE',       '07/03/1981 BOUAKE',             'MARIEE',      '2 enfants',  '79 14 11 83 / 04 48 93 13',        'CDI', 'RESPONSABLE BOUTIQUE',   '281 011 872 351', '01/08/2018'),
    (8,  'TADJO',      "N'DA ANOUMOU",            '23/08/1993 ABENGOUROU',         'CELIBATAIRE', '1 enfant',   '78 86 41 82 / 46 89 62 42',        'CDI', 'CONSEILLERE CLIENTELE',  '293 011 872 376', '01/08/2018'),
    (9,  'BROU',       'ALICE YEHICI',            '30/08/1984 BOUAKE',             'CELIBATAIRE', '0 enfant',   '07 78 48 88 58',                   'CDI', 'RESPONSABLE BOUTIQUE',   '284 011 872 226', '01/08/2018'),
    (10, 'FOUO',       'MOHAMED LAMINE',          '06/06/1988 ADJAME',             'CELIBATAIRE', '1 enfant',   '07 48 99 79 40 / 07 87 83 41 64',  'CDI', 'RESPONSABLE SECTEUR',    '188 011 872 485', '01/08/2018'),
    (11, 'FOUO',       'ABDOULAYE YOUSSEF',       '16/07/1991 ADJAME',             'CELIBATAIRE', '0',          '07 57 10 80 77',                   'CDI', 'RESPONSABLE VAD',        '191 011 872 159', '01/08/2018'),
    (12, 'SYLLA',      'KALILOU',                 '19/06/1977 DALOA',              'CELIBATAIRE', '3 enfants',  '05 05 22 39 86',                   'CDI', 'CHAUFFEUR',              '177 011 872 144', '01/08/2018'),
    (13, 'KISSY',      'JEAN NOEL ARMAND',        '22/12/1994 BONAHOUINO',         'CELIBATAIRE', '1 enfant',   '07 58 63 24 57',                   'CDI', 'ASSISTANT SERVICE+',     '194 011 872 169', '01/08/2018'),
    (14, 'DIABAGATE',  'RAISSA ADELAIDE',         '23/12/1988 ADJAME',             'CELIBATAIRE', '1 enfant',   '08 14 78 66 / 41 53 85 31',        'CDI', 'CONSEILLERE CLIENTELE',  '288 011 872 239', '01/08/2018'),
    (15, 'COULIBALY',  'SALIMATA KINIFO',         '24/06/1992 ABOBO',              'CELIBATAIRE', '2 enfants',  '77 54 89 80 / 06 87 10 89',        'CDI', 'CONSEILLERE CLIENTELE',  '292 011 872 429', '01/08/2018'),
    (16, 'YAO',        'AHOU CLAVERIE',           '24/12/1992 GADOUAN/DALOA',      'CELIBATAIRE', '2 enfants',  '59 17 12 16',                      'CDI', 'CHARGE RECOUVREMENT',    '292 011 872 453', '01/08/2018'),
    (17, 'YORO',       'AWA CHARLENE',            '18/11/1993 KOUMASSI',           'CELIBATAIRE', '0 enfant',   '07 48 61 71 19',                   'CDI', 'RESPONSABLE REABO',      '293 011 872 439', '01/08/2018'),
    (18, 'FOUO',       'RAMATOULAYE SAFANE',      '15/07/1991 ADJAME',             'MARIEE',      '2 enfants',  '07 87 90 53 86 / 07 47 76 39 96',  'CDI', 'DAF',                    '291 011 891 504', '01/11/2018'),
    (19, 'BLEH',       'TOUETY RITA JOCELYNE',    '29/04/1988 ADJAME',             'MARIEE',      '2 enfants',  '07 62 53 55 / 40 40 38 25',        'CDI', 'CONSEILLERE CLIENTELE',  '288 011 904 781', '01/01/2019'),
    (20, 'COULIBALY',  'MANGOUWA',                '02/10/1977 YAMOUSSOUKRO',       'CELIBATAIRE', '4 enfants',  '05 80 19 65 / 57 19 29 21',        'CDI', 'RVAD AGNEBI-TIASSA',     '177 011 781 323', '01/08/2019'),
    (21, 'GBESSO',     'AWOHO DOMINIQUE',         '30/03/1990 DABOU',              'CELIBATAIRE', '1 enfant',   '59 96 07 51 / 41 62 34 37',        'CDI', 'COMPTABLE',              '290 011 967 155', '01/09/2019'),
    (22, 'FOUO',       'ISMAEL SEYDOU',           '01/06/1988 COCODY',             'CELIBATAIRE', '1 enfant',   '40 87 49 66',                      'CDI', 'RESPONSABLE LOGISTIQUE', '188 012 041 009', '01/05/2020'),
    (23, 'SYLLA',      'MOUSSA',                  '01/01/1979 DALOA',              'CELIBATAIRE', '5 enfants',  '05 08 33 77 / 02 05 19 89',        'CDI', 'CHAUFFEUR',              '179 012 040 980', '01/05/2020'),
    (24, 'AMOIN',      'EDWIGE',                  '15/03/1992 DABOU',              'CELIBATAIRE', '0 enfant',   '49 50 50 51 / 04 36 02 28',        'CDI', 'RESPONSABLE BOUTIQUE',   '292 012 047 924', '01/05/2020'),
    (25, 'KIPRE',      'BRYNDA GRACE VICTOIRE',   '01/03/1996 TREICHVILLE',        'CELIBATAIRE', '0',          '07 09 12 56 62',                   'CDI', 'ASSISTANTE RH',          '296 012 040 102', '01/06/2020'),
    (26, 'GOLE',       'ESTHER ANGE ROSINE',      '31/03/1996 ABOBO',              'MARIEE',      '1 enfant',   '59 36 80 78',                      'CDI', 'TRESORIERE',             '296 012 040 974', '01/06/2020'),
    (27, 'KOUAME',     'HOUPHOUET STANISLAS',     '20/10/1985 ZAHAKRO/TOUMODI',    'CELIBATAIRE', '0',          '59 47 65 92',                      'CDI', 'INFORMATICIEN',          '202 100 008 826', '01/01/2021'),
    (28, 'BINI',       'DJACKE MOUSTAPHA',        '01/09/1989 ABIDJAN',            'CELIBATAIRE', '3 enfants',  '07 49 64 18 37 / 05 06 23 21 76',  'CDI', 'CHAUFFEUR',              '202 100 025 397', '01/01/2021'),
    (29, 'IBO',        'REBECCA',                 '25/03/1993 OUME',               'MARIEE',      '0',          '07 59 90 03 70 / 01 41 38 40 09',  'CDI', 'CAISSIERE',              '202 100 010 098', '01/01/2021'),
    (30, 'VAHOUA',     'MARIE LAURE',             '29/11/1986 MAHIDIDIO',          'CELIBATAIRE', '4 enfants',  '40 22 50 70 / 77 19 05 12',        'CDI', 'RESPONSABLE BOUTIQUE',   '202 100 025 407', '01/01/2021'),
    (31, 'OUPOH',      'OZOUA SOLANGE',           '11/08/1990 GUEYO',              'CELIBATAIRE', '2 enfants',  '07 08 55 97 42',                   'CDI', 'A. RECOUVREMENT',        '202 100 038 631', '01/04/2021'),
    (32, 'KOUASSI',    'GBAYORO MOISE',           '13/07/1990 ADJAME',             'CELIBATAIRE', '0',          '07 57 94 34 35 / 01 02 83 06 88',  'CDI', 'COMPTABLE',              '202 100 073 010', '01/08/2021'),
    (33, 'ELLOH',      'AKESSE YVON YANNICK',     '30/05/1983 GRAND-BASSAM',       'MARIE',       '5 enfants',  '05 86 14 52 01',                   'CDI', 'DIRECTEUR COMMERCIAL',   '183 010 902 512', '01/06/2022'),
    (34, 'KOFFI',      'JEAN EUDES',              '18/07/1993 KOUMASSI',           'MARIE',       '1 enfant',   '07 49 71 17 51 / 07 09 37 78 94',  'CDI', 'RESPONSABLE VAD',        '202 300 035 346', '01/11/2022'),
    (35, 'KONE',       'HABSATOU',                '22/12/1995 BOUAKE',             'CELIBATAIRE', '1 enfant',   '07 09 00 97 86 / 01 44 15 23 44',  'CDI', 'A. TRESORIERE',          '202 300 011 000', '01/01/2023'),
    (36, 'AMIE',       'DEDOHONON MIREILLE',      '07/05/1997 ZAGBALEBE',          'CELIBATAIRE', '0',          '48 37 69 41 / 71 13 37 71',        'CDI', 'RESPONSABLE BOUTIQUE',   '202 300 035 457', '01/01/2023'),
    (37, 'KONE',       'MASSANDJE',               '26/10/1991 SAN-PEDRO',          'CELIBATAIRE', '1 enfant',   '07 47 01 45 25',                   'CDD', 'CONSEILLERE CLIENTELE',  '202 100 038 450', '01/11/2023'),
    (38, 'KAKOU',      'GUY CHARLES',             '19/06/1988 TREICHVILLE',        'CELIBATAIRE', '2 enfants',  '07 07 06 83 63 / 01 01 06 69 77',  'CDD', 'RESPONSABLE BOUTIQUE',   '188 011 564 239', '01/11/2023'),
    (39, 'ESSE',       'DOROTHEE',                "10/08/1994 M'BATTO",            'CELIBATAIRE', '3 enfants',  '07 79 06 18 47',                   'CDD', 'CONSEILLERE CLIENTELE',  '202 400 103 328', '01/09/2024'),
    (40, 'GOLI',       'API RAISSA',              '22/12/1996 BOUAFOUKRO',         'CELIBATAIRE', '0',          '07 57 28 62 41 / 05 95 88 10 15',  'CDD', 'CONSEILLERE CLIENTELE',  '202 400 103 476', '02/10/2024'),
    (41, 'AMANI',      'CYRIAC',                  '10/11/2000 ZERGBEU',            'CELIBATAIRE', '0',          '07 08 77 36 90 / 01 03 90 32 77',  'CDD', 'RVAD GRAND-LAHOU',       '202 400 101 929', '01/09/2024'),
    (42, 'KOUASSI',    'AYA OLIVIA',              '11/01/2003 ABOUAKRO',           'CELIBATAIRE', '0',          '07 99 03 78 73 / 05 45 06 97 08',  'CDD', 'CONSEILLERE CLIENTELE',  '202 400 102 035', '01/09/2024'),
    (43, 'WAWA',       'DAH OSWALD',              '08/11/1994 PORT-BOUET',         'CELIBATAIRE', '0',          '07 79 73 43 86 / 01 02 17 93 24',  'CDD', 'RESPONSABLE BOUTIQUE',   '202 200 018 062', '01/09/2024'),
    (44, 'OUATTARA',   'ABDOUL LATIF',            '21/02/2000 KORHOGO',            'CELIBATAIRE', '0',          '07 98 37 37 00 / 05 85 26 88 39',  'CDD', 'RESPONSABLE SERVICE+',   '202 500 082 827', '01/07/2025'),
    (45, 'YAO BI',     'JOCELIN',                 '23/12/1987 DAHIOKE',            'CELIBATAIRE', '2 enfants',  '01 42 30 54 44',                   'CDD', 'RVAD DABOU',             '202 500 108 320', '01/10/2025'),
    (46, 'DIABAGATE',  'SOUHALIO',                '05/04/1994 TALAHINI-TOMORA',    'CELIBATAIRE', '3 enfants',  '07 02 92 35 96',                   'CDD', 'CHAUFFEUR',              '202 500 108 328', '01/10/2025'),
    (47, 'DIOMANDE',   'MAHIKAN',                 '20/12/1997 KANTA',              'CELIBATAIRE', '0',          '07 88 58 73 51',                   'CDD', 'CALL CENTER',            '202 500 126 575', '01/11/2025'),
    (48, 'BLEHEROU',   'DORCAS',                  '09/02/1998 FACOBLY',            'CELIBATAIRE', '0',          '07 48 62 26 68',                   'CDD', 'CALL CENTER',            '202 500 127 097', '01/11/2025'),
    (49, 'TEKO',       'FABIENNE',                '08/12/1999 AHOUYA/DABOU',       'CELIBATAIRE', '0',          '07 88 60 50 14 / 05 76 63 36 31',  'CDD', 'CALL CENTER',            '202 500 129 461', '01/11/2025'),
    (50, 'KONE',       'NADEGE',                  '16/07/1999 FERKESSEDOUGOU',     'CELIBATAIRE', '0',          '07 79 18 18 37',                   'CDD', 'CHARGEE CALL CENTER',    '202 400 096 642', '01/11/2025'),
    (51, 'SEMY',       'PANISSE',                 '30/12/1997 BONON',              'CELIBATAIRE', '0',          '07 78 70 87 66 / 05 74 35 84 02',  'CDD', 'ASSISTANT LOGISTIQUE',   '202 500 129 586', '01/11/2025'),
]


class Command(BaseCommand):
    help = 'Importe les 51 employés réels de JEC PROMO 2026'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Supprime tous les employés existants avant l\'import',
        )

    def handle(self, *args, **options):
        from SYGEPE.models import Employe

        if options['reset']:
            count_del = Employe.objects.all().delete()[0]
            self.stdout.write(self.style.WARNING(f'{count_del} employé(s) supprimé(s).'))

        created = 0
        updated = 0
        errors  = 0

        for row in PERSONNEL:
            num, nom, prenom, nais_raw, matr, enf_raw, tel, contrat, poste, cnps, emb_raw = row

            matricule = f"JEC{num:03d}"
            date_nais  = parse_date(nais_raw)
            lieu_nais  = parse_lieu(nais_raw)
            date_emb   = parse_date(emb_raw)
            situation  = parse_situation(matr)
            nb_enfants = parse_enfants(enf_raw)
            # Nettoyage numéro CNPS (retrait espaces)
            cnps_clean = re.sub(r'\s+', ' ', cnps).strip()

            try:
                # Email placeholder unique basé sur le matricule
                email_placeholder = f'{matricule.lower()}@jecpromo.ci'

                emp, created_flag = Employe.objects.update_or_create(
                    matricule=matricule,
                    defaults=dict(
                        nom=nom.strip(),
                        prenom=prenom.strip(),
                        email=email_placeholder,
                        date_naissance=date_nais,
                        lieu_naissance=lieu_nais,
                        situation_familiale=situation,
                        nombre_enfants=nb_enfants,
                        telephone=tel.strip(),
                        poste=poste.strip(),
                        num_cnps=cnps_clean,
                        date_embauche=date_emb,
                        statut='actif',
                        role='employe',
                        ville='Abidjan',
                    ),
                )
                if created_flag:
                    created += 1
                    self.stdout.write(f'  OK Cree  : {matricule} - {prenom} {nom}')
                else:
                    updated += 1
                    self.stdout.write(f'  MAJ      : {matricule} - {prenom} {nom}')
            except Exception as e:
                errors += 1
                self.stdout.write(self.style.ERROR(f'  ERREUR ({matricule} {nom}) : {e}'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Import termine : {created} cree(s), {updated} mis a jour, {errors} erreur(s).'
        ))
