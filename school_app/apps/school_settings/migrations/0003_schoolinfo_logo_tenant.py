"""
Migration 0003 — school_settings
Passage de SchoolInfo.logo à un chemin tenant-aware (callable upload_to).
Aucun changement de schéma SQL.
"""
from django.db import migrations, models
import school_settings.models


class Migration(migrations.Migration):

    dependencies = [
        ('school_settings', '0002_v2_planning_repos_school_fields_smtp'),
    ]

    operations = [
        migrations.AlterField(
            model_name='schoolinfo',
            name='logo',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to=school_settings.models.school_info_logo_path,
            ),
        ),
    ]
