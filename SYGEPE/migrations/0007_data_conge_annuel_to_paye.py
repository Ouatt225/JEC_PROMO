"""
Data migration : renomme la valeur 'annuel' → 'paye' dans la table Conge.
"""
from django.db import migrations


def annuel_vers_paye(apps, schema_editor):
    Conge = apps.get_model('SYGEPE', 'Conge')
    Conge.objects.filter(type_conge='annuel').update(type_conge='paye')


def paye_vers_annuel(apps, schema_editor):
    Conge = apps.get_model('SYGEPE', 'Conge')
    Conge.objects.filter(type_conge='paye').update(type_conge='annuel')


class Migration(migrations.Migration):

    dependencies = [
        ('SYGEPE', '0006_conge_paye'),
    ]

    operations = [
        migrations.RunPython(annuel_vers_paye, reverse_code=paye_vers_annuel),
    ]
