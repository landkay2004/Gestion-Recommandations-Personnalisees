"""
Migration 0004 : Enrichissement du PlanAbonnement + nouveaux modèles Abonnement et HistoriqueAbonnement.
"""
import django.db.models.deletion
from django.db import migrations, models


def _populate_slugs(apps, schema_editor):
    """Génère un slug unique pour chaque PlanAbonnement existant."""
    from django.utils.text import slugify as _slugify
    PlanAbonnement = apps.get_model('tenants', 'PlanAbonnement')
    for plan in PlanAbonnement.objects.all():
        if not plan.slug:
            base = _slugify(plan.nom)[:95] or 'plan'
            candidate = base
            i = 1
            while PlanAbonnement.objects.filter(slug=candidate).exclude(pk=plan.pk).exists():
                candidate = '%s-%d' % (base, i)
                i += 1
            plan.slug = candidate
            plan.save(update_fields=['slug'])


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0003_add_secretariat_to_annuaire_type_choices'),
    ]

    operations = [
        # ── Nouveaux champs sur PlanAbonnement ────────────────────────────────
        migrations.AddField(
            model_name='planabonnement',
            name='slug',
            field=models.SlugField(blank=True, max_length=100, null=True, unique=True, verbose_name='Slug'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='planabonnement',
            name='prix_annuel',
            field=models.DecimalField(decimal_places=2, default=0, help_text='Laisser à 0 pour calculer automatiquement (×12).', max_digits=10, verbose_name='Prix annuel (USD)'),
        ),
        migrations.AddField(
            model_name='planabonnement',
            name='essai_gratuit_jours',
            field=models.IntegerField(default=0, verbose_name="Jours d'essai gratuit"),
        ),
        migrations.AddField(
            model_name='planabonnement',
            name='max_stockage_go',
            field=models.IntegerField(default=1, verbose_name='Stockage max (Go)'),
        ),
        migrations.AddField(
            model_name='planabonnement',
            name='quota_sms_mensuel',
            field=models.IntegerField(default=0, verbose_name='Quota SMS / mois'),
        ),
        migrations.AddField(
            model_name='planabonnement',
            name='modules_inclus',
            field=models.JSONField(blank=True, default=list, help_text='Liste des clés de modules autorisés. Vide = tous les modules.', verbose_name='Modules inclus'),
        ),
        migrations.AddField(
            model_name='planabonnement',
            name='fonctionnalites_incluses',
            field=models.JSONField(blank=True, default=list, help_text='Liste des clés de fonctionnalités avancées.', verbose_name='Fonctionnalités incluses'),
        ),
        migrations.AddField(
            model_name='planabonnement',
            name='est_public',
            field=models.BooleanField(default=True, help_text='Visible dans la page de tarification publique.', verbose_name='Visible publiquement'),
        ),
        migrations.AddField(
            model_name='planabonnement',
            name='ordre_affichage',
            field=models.IntegerField(default=0, verbose_name="Ordre d'affichage"),
        ),

        # ── Mise à jour ordering de PlanAbonnement ────────────────────────────
        migrations.AlterModelOptions(
            name='planabonnement',
            options={'ordering': ['ordre_affichage', 'prix_mensuel'], 'verbose_name': "Plan d'abonnement", 'verbose_name_plural': "Plans d'abonnement"},
        ),

        # ── Peupler les slugs des plans existants (RunPython) ─────────────────
        migrations.RunPython(
            code=_populate_slugs,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name='planabonnement',
            name='slug',
            field=models.SlugField(blank=True, max_length=100, unique=True, verbose_name='Slug'),
        ),

        # ── Nouveau modèle Abonnement ─────────────────────────────────────────
        migrations.CreateModel(
            name='Abonnement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_debut', models.DateField(verbose_name='Date de début')),
                ('date_fin', models.DateField(blank=True, null=True, verbose_name='Date de fin')),
                ('statut', models.CharField(
                    choices=[('actif', 'Actif'), ('essai', 'Essai gratuit'), ('expire', 'Expiré'), ('suspendu', 'Suspendu')],
                    db_index=True, default='actif', max_length=20, verbose_name='Statut'
                )),
                ('renouvellement_auto', models.BooleanField(default=False, verbose_name='Renouvellement automatique')),
                ('notes_internes', models.TextField(blank=True, verbose_name='Notes internes (super-admin)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ecole', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='abonnement_detail',
                    to='tenants.ecole',
                    verbose_name='École'
                )),
                ('plan', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='abonnements',
                    to='tenants.planabonnement',
                    verbose_name='Plan'
                )),
            ],
            options={
                'verbose_name': 'Abonnement',
                'verbose_name_plural': 'Abonnements',
                'ordering': ['-created_at'],
                'app_label': 'tenants',
            },
        ),

        # ── Nouveau modèle HistoriqueAbonnement ───────────────────────────────
        migrations.CreateModel(
            name='HistoriqueAbonnement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ancien_statut', models.CharField(blank=True, max_length=20)),
                ('nouveau_statut', models.CharField(blank=True, max_length=20)),
                ('date_changement', models.DateTimeField(auto_now_add=True)),
                ('motif', models.TextField(blank=True)),
                ('modifie_par', models.CharField(blank=True, max_length=150)),
                ('abonnement', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='historique',
                    to='tenants.abonnement'
                )),
                ('ancien_plan', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+',
                    to='tenants.planabonnement'
                )),
                ('nouveau_plan', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+',
                    to='tenants.planabonnement'
                )),
            ],
            options={
                'verbose_name': 'Historique abonnement',
                'verbose_name_plural': 'Historiques abonnements',
                'ordering': ['-date_changement'],
                'app_label': 'tenants',
            },
        ),
    ]
