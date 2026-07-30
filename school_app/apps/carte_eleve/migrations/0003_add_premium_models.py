from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('carte_eleve', '0002_add_new_card_modeles'),
    ]

    operations = [
        migrations.AlterField(
            model_name='carteconfig',
            name='modele',
            field=models.CharField(
                choices=[
                    ('classique',      'Classique'),
                    ('moderne',        'Moderne'),
                    ('institutionnel', 'Institutionnel'),
                    ('minimaliste',    'Minimaliste'),
                    ('premium',        'Premium'),
                    ('horizon',        'Horizon ✦'),
                    ('congo',          'Congo ✦'),
                    ('emeraude',       'Émeraude ✦'),
                    ('crepuscule',     'Crépuscule ✦'),
                    ('rubis',          'Rubis ✦'),
                    ('ocean',          'Océan ✦'),
                    ('aurore',         'Aurore ✦'),
                ],
                default='classique',
                max_length=20,
                verbose_name='Modèle de carte',
            ),
        ),
    ]
