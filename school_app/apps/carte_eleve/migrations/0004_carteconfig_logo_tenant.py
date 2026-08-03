"""
Migration 0004 — carte_eleve
Passage de CarteConfig.logo_override à un chemin tenant-aware.
Aucun changement de schéma SQL.
"""
from django.db import migrations, models
import carte_eleve.models


class Migration(migrations.Migration):

    dependencies = [
        ('carte_eleve', '0003_add_premium_models'),
    ]

    operations = [
        migrations.AlterField(
            model_name='carteconfig',
            name='logo_override',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to=carte_eleve.models.carte_logo_path,
                verbose_name='Logo spécifique aux cartes',
                help_text="Laissez vide pour utiliser le logo de l'établissement",
            ),
        ),
    ]
