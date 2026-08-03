"""
Migration 0004 — accounts
Passage de photo_profil à un chemin tenant-aware (callable upload_to).
Aucun changement de schéma SQL — uniquement la métadonnée Django.
"""
from django.db import migrations, models
import accounts.models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_alter_customuser_role'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customuser',
            name='photo_profil',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to=accounts.models.user_photo_profil_path,
                verbose_name='Photo de profil',
            ),
        ),
    ]
