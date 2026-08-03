from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0006_demande_abonnement_paiement_plateforme'),
    ]

    operations = [
        migrations.CreateModel(
            name='DemandeInscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom_ecole', models.CharField(max_length=200, verbose_name="Nom de l'établissement")),
                ('type_ecole', models.CharField(blank=True, choices=[('primaire', 'École primaire'), ('secondaire', 'École secondaire'), ('institut', 'Institut'), ('lycee', 'Lycée'), ('college', 'Collège'), ('autre', 'Autre')], max_length=30, verbose_name="Type d'établissement")),
                ('nom_responsable', models.CharField(max_length=150, verbose_name='Nom du responsable')),
                ('telephone', models.CharField(max_length=30, verbose_name='Téléphone')),
                ('email', models.EmailField(verbose_name='E-mail')),
                ('province', models.CharField(blank=True, max_length=100, verbose_name='Province')),
                ('ville', models.CharField(blank=True, max_length=100, verbose_name='Ville')),
                ('message', models.TextField(blank=True, verbose_name='Message / Informations complémentaires')),
                ('statut', models.CharField(choices=[('en_attente', 'En attente'), ('approuvee', 'Approuvée'), ('rejetee', 'Rejetée')], db_index=True, default='en_attente', max_length=20, verbose_name='Statut')),
                ('notes_admin', models.TextField(blank=True, verbose_name='Notes super-admin')),
                ('traite_par', models.CharField(blank=True, max_length=150, verbose_name='Traité par')),
                ('traite_le', models.DateTimeField(blank=True, null=True, verbose_name='Traité le')),
                ('ip_soumission', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP soumission')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': "Demande d'inscription",
                'verbose_name_plural': "Demandes d'inscription",
                'ordering': ['-created_at'],
            },
        ),
    ]
