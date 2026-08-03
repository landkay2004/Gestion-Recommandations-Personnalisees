"""
Migration 0002 — portail
Passage de PortailConfig.logo à un chemin tenant-aware.
Aucun changement de schéma SQL.
"""
from django.db import migrations, models
import portail.models


class Migration(migrations.Migration):

    dependencies = [
        ('portail', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='portailconfig',
            name='logo',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to=portail.models.portail_logo_path,
            ),
        ),
    ]
