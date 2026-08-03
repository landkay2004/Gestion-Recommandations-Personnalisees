from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('super_admin', '0004_platformsettings_alerte_quota'),
    ]

    operations = [
        # SuperAdmin: photo de profil + téléphone
        migrations.AddField(
            model_name='superadmin',
            name='telephone',
            field=models.CharField(blank=True, default='', max_length=50, verbose_name='Téléphone'),
        ),
        migrations.AddField(
            model_name='superadmin',
            name='photo_profil',
            field=models.ImageField(blank=True, null=True, upload_to='platform/admins/', verbose_name='Photo de profil'),
        ),
        # PlatformSettings: images de fond login
        migrations.AddField(
            model_name='platformsettings',
            name='login_bg_1',
            field=models.ImageField(blank=True, help_text='Première image de fond du diaporama sur la page de connexion.', null=True, upload_to='platform/login/', verbose_name='Image fond login 1'),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='login_bg_2',
            field=models.ImageField(blank=True, help_text='Deuxième image de fond (optionnel).', null=True, upload_to='platform/login/', verbose_name='Image fond login 2'),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='login_bg_3',
            field=models.ImageField(blank=True, help_text='Troisième image de fond (optionnel).', null=True, upload_to='platform/login/', verbose_name='Image fond login 3'),
        ),
        # PlatformSettings: page À propos
        migrations.AddField(
            model_name='platformsettings',
            name='about_titre',
            field=models.CharField(blank=True, default='À propos de nous', max_length=200, verbose_name='Titre — À propos'),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='about_description',
            field=models.TextField(blank=True, default='', verbose_name='Description générale'),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='about_mission',
            field=models.TextField(blank=True, default='', verbose_name='Notre mission'),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='about_vision',
            field=models.TextField(blank=True, default='', verbose_name='Notre vision'),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='about_valeurs',
            field=models.TextField(blank=True, default='', verbose_name='Nos valeurs (1 par ligne)'),
        ),
    ]
