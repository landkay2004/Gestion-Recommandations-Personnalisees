"""
Migration : DemandeAbonnement + PaiementPlatforme
"""
from django.db import migrations, models
import django.db.models.deletion
import tenants.models


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0005_alter_annuaireutilisateur_type_compte_and_more'),
    ]

    operations = [
        # ── DemandeAbonnement ────────────────────────────────────────────────
        migrations.CreateModel(
            name='DemandeAbonnement',
            fields=[
                ('id',            models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message',       models.TextField(blank=True, verbose_name="Message de l'école")),
                ('contact_email', models.EmailField(blank=True, verbose_name='Email contact')),
                ('contact_nom',   models.CharField(blank=True, max_length=200, verbose_name='Nom contact')),
                ('statut',        models.CharField(
                    choices=[
                        ('en_attente', 'En attente'),
                        ('approuvee',  'Approuvée'),
                        ('rejetee',    'Rejetée'),
                        ('annulee',    'Annulée'),
                    ],
                    db_index=True, default='en_attente', max_length=20, verbose_name='Statut',
                )),
                ('reponse_admin', models.TextField(blank=True, verbose_name='Réponse super-admin')),
                ('traite_par',    models.CharField(blank=True, max_length=200, verbose_name='Traité par')),
                ('traite_le',     models.DateTimeField(blank=True, null=True, verbose_name='Traité le')),
                ('created_at',    models.DateTimeField(auto_now_add=True)),
                ('ecole', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='demandes_abonnement',
                    to='tenants.ecole',
                    verbose_name='École',
                )),
                ('plan_actuel', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+',
                    to='tenants.planabonnement',
                    verbose_name='Plan actuel',
                )),
                ('plan_souhaite', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+',
                    to='tenants.planabonnement',
                    verbose_name='Plan souhaité',
                )),
            ],
            options={
                'verbose_name': "Demande d'abonnement",
                'verbose_name_plural': "Demandes d'abonnement",
                'ordering': ['-created_at'],
                'app_label': 'tenants',
            },
        ),
        # ── PaiementPlatforme ────────────────────────────────────────────────
        migrations.CreateModel(
            name='PaiementPlatforme',
            fields=[
                ('id',                 models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('montant',            models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Montant (USD)')),
                ('mode',               models.CharField(
                    choices=[
                        ('mobile_money', 'Mobile Money'),
                        ('virement',     'Virement bancaire'),
                        ('especes',      'Espèces'),
                    ],
                    max_length=20, verbose_name='Mode',
                )),
                ('numero_transaction', models.CharField(blank=True, max_length=100, verbose_name='N° transaction')),
                ('preuve',             models.FileField(blank=True, null=True,
                                                        upload_to=tenants.models._preuve_upload_path,
                                                        verbose_name='Preuve')),
                ('notes',              models.TextField(blank=True, verbose_name='Notes école')),
                ('statut',             models.CharField(
                    choices=[
                        ('en_attente', 'En attente de validation'),
                        ('valide',     'Validé'),
                        ('rejete',     'Rejeté'),
                    ],
                    db_index=True, default='en_attente', max_length=20, verbose_name='Statut',
                )),
                ('valide_par',         models.CharField(blank=True, max_length=200, verbose_name='Validé par')),
                ('valide_le',          models.DateTimeField(blank=True, null=True, verbose_name='Validé le')),
                ('notes_admin',        models.TextField(blank=True, verbose_name='Notes admin')),
                ('jours_accordes',     models.IntegerField(default=0, verbose_name='Jours accordés')),
                ('ip_soumission',      models.GenericIPAddressField(blank=True, null=True, verbose_name='IP soumission')),
                ('created_at',         models.DateTimeField(auto_now_add=True)),
                ('updated_at',         models.DateTimeField(auto_now=True)),
                ('ecole', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='paiements_plateforme',
                    to='tenants.ecole',
                    verbose_name='École',
                )),
            ],
            options={
                'verbose_name': 'Paiement plateforme',
                'verbose_name_plural': 'Paiements plateforme',
                'ordering': ['-created_at'],
                'app_label': 'tenants',
            },
        ),
    ]
