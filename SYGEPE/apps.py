from django.apps import AppConfig


class SygepeConfig(AppConfig):
    name = 'SYGEPE'

    def ready(self):
        from django.db.models.signals import post_migrate
        from django.dispatch import receiver

        @receiver(post_migrate, sender=self)
        def create_roles(sender, **kwargs):
            """Crée automatiquement les 3 groupes de rôles au démarrage."""
            from django.contrib.auth.models import Group
            for name in ['Admin', 'RH', 'DAF', 'Employé']:
                Group.objects.get_or_create(name=name)
