"""
Migration 0004 — school_settings
Ajout du modèle MatriculeConfig (configuration de la matriculation automatique).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('school_settings', '0003_schoolinfo_logo_tenant'),
    ]

    operations = [
        migrations.CreateModel(
            name='MatriculeConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('format_matricule', models.CharField(
                    default='{PREFIXE}{ANNEE2}{SEQ4}',
                    help_text='Variables : {PREFIXE}, {ANNEE}, {ANNEE2}, {MOIS}, {SEQ}, {SEQ3}, {SEQ4}, {SEQ5}. Exemple : {PREFIXE}-{ANNEE2}-{SEQ4} → EL-25-0001',
                    max_length=100,
                    verbose_name='Format du matricule',
                )),
                ('prefixe', models.CharField(
                    default='EL',
                    help_text='Remplace {PREFIXE} dans le format. Ex : EL, IB, ETD',
                    max_length=10,
                    verbose_name='Préfixe',
                )),
                ('compteur', models.PositiveIntegerField(
                    default=0,
                    help_text='Incrémenté automatiquement à chaque inscription.',
                    verbose_name='Compteur actuel',
                )),
                ('reset_annuel', models.BooleanField(
                    default=False,
                    help_text='Si activé, le compteur repart à 0 au début de chaque nouvelle année scolaire.',
                    verbose_name='Réinitialiser le compteur chaque année scolaire',
                )),
                ('annee_reference', models.CharField(
                    blank=True,
                    default='',
                    help_text="Année scolaire en cours lors du dernier incrément.",
                    max_length=4,
                    verbose_name='Année de référence du compteur',
                )),
            ],
            options={
                'verbose_name': 'Configuration de la matriculation',
            },
        ),
    ]
