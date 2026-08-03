from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_customuser_photo_profil_tenant'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='sexe',
            field=models.CharField(
                blank=True,
                choices=[('M', 'Masculin'), ('F', 'Féminin')],
                default='',
                max_length=1,
                verbose_name='Sexe',
            ),
        ),
    ]
