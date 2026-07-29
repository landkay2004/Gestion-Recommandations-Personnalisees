from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('super_admin', '0003_v2_planning_repos_school_fields_smtp'),
    ]

    operations = [
        migrations.AddField(
            model_name='platformsettings',
            name='alerte_quota_seuil',
            field=models.PositiveIntegerField(
                default=80,
                help_text="Pourcentage d'utilisation à partir duquel une alerte est envoyée (0–100).",
                verbose_name="Seuil d'alerte quota (%)",
            ),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='alerte_quota_email_actif',
            field=models.BooleanField(
                default=True,
                help_text="Envoyer un e-mail à l'admin de l'école quand un quota atteint le seuil.",
                verbose_name='Alertes quota par e-mail',
            ),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='alerte_quota_app_actif',
            field=models.BooleanField(
                default=True,
                help_text="Afficher une notification in-app à l'administrateur de l'école.",
                verbose_name="Alertes quota dans l'app",
            ),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='alerte_quota_message_email',
            field=models.TextField(
                blank=True,
                default='',
                help_text=(
                    'Variables disponibles : {ecole}, {ressource}, {usage}, {maximum}, '
                    '{pourcentage}, {site}. Laissez vide pour utiliser le message par défaut.'
                ),
                verbose_name='Modèle de message e-mail (alerte quota)',
            ),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='alerte_quota_message_app',
            field=models.TextField(
                blank=True,
                default='',
                help_text=(
                    'Message court affiché dans la notification in-app. '
                    'Variables : {ecole}, {ressource}, {usage}, {maximum}, {pourcentage}. '
                    'Laissez vide pour le message par défaut.'
                ),
                verbose_name='Modèle de message in-app (alerte quota)',
            ),
        ),
    ]
