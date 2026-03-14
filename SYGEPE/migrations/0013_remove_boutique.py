from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('SYGEPE', '0012_add_conge_maladie_piece_justificative'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='employe',
            name='boutique',
        ),
        migrations.DeleteModel(
            name='Boutique',
        ),
    ]
