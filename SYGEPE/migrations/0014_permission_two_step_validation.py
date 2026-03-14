"""Migration : validation en deux étapes pour les permissions."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('SYGEPE', '0013_add_new_roles'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='permission',
            name='valideur_responsable',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='permissions_validees_resp',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='permission',
            name='date_validation_responsable',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='permission',
            name='statut',
            field=models.CharField(
                choices=[
                    ('en_attente', 'En attente'),
                    ('valide_responsable', 'Validé par responsable'),
                    ('approuve', 'Approuvé'),
                    ('refuse', 'Refusé'),
                    ('annule', 'Annulé'),
                ],
                default='en_attente',
                max_length=20,
            ),
        ),
    ]
