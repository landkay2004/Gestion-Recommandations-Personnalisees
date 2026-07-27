from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('super_admin', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlatformSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('site_name', models.CharField(default='SGN RDC', max_length=200, verbose_name='Nom du site')),
                ('site_slogan', models.CharField(blank=True, default='School Governance Network', max_length=300, verbose_name='Slogan')),
                ('site_devise', models.CharField(blank=True, max_length=300, verbose_name='Devise')),
                ('site_logo', models.ImageField(blank=True, null=True, upload_to='platform/', verbose_name='Logo plateforme')),
                ('adresse', models.TextField(blank=True, verbose_name='Adresse')),
                ('email_contact', models.EmailField(blank=True, max_length=254, verbose_name='E-mail contact')),
                ('telephone', models.CharField(blank=True, max_length=50, verbose_name='Téléphone')),
                ('site_web', models.URLField(blank=True, verbose_name='Site web')),
                ('couleur_principale', models.CharField(default='#4D44B5', max_length=7, verbose_name='Couleur principale')),
            ],
            options={
                'verbose_name': 'Paramètres de la plateforme',
                'app_label': 'super_admin',
            },
        ),
    ]
