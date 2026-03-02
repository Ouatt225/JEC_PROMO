from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('SYGEPE', '0008_role_daf'),
    ]

    operations = [
        # Ajout des nouveaux champs avec valeur par défaut temporaire
        migrations.AddField(
            model_name='permission',
            name='date_debut',
            field=models.DateField(default=datetime.date.today),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='permission',
            name='date_fin',
            field=models.DateField(default=datetime.date.today),
            preserve_default=False,
        ),
        # Suppression des anciens champs
        migrations.RemoveField(
            model_name='permission',
            name='date',
        ),
        migrations.RemoveField(
            model_name='permission',
            name='heure_debut',
        ),
        migrations.RemoveField(
            model_name='permission',
            name='heure_fin',
        ),
    ]
