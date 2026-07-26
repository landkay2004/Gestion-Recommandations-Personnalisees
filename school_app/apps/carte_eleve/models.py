from django.db import models


class CarteConfig(models.Model):
    MODELES = [
        ('classique',      'Classique'),
        ('moderne',        'Moderne'),
        ('institutionnel', 'Institutionnel'),
        ('minimaliste',    'Minimaliste'),
        ('premium',        'Premium'),
    ]

    modele             = models.CharField(max_length=20, choices=MODELES, default='classique',
                             verbose_name='Modèle de carte')
    couleur_principale = models.CharField(max_length=7, default='#1e3a5f',
                             verbose_name='Couleur principale',
                             help_text='Valeur hexadécimale, ex : #1e3a5f')
    couleur_secondaire = models.CharField(max_length=7, default='#2563eb',
                             verbose_name='Couleur secondaire',
                             help_text='Valeur hexadécimale, ex : #2563eb')
    devise             = models.CharField(max_length=200, blank=True,
                             default='Le savoir, la discipline et le travail',
                             verbose_name='Devise de l\'établissement')
    logo_override      = models.ImageField(upload_to='cartes/logos/', blank=True, null=True,
                             verbose_name='Logo spécifique aux cartes',
                             help_text='Laissez vide pour utiliser le logo de l\'établissement')

    # ── Champs visibles ──
    afficher_photo     = models.BooleanField(default=True,  verbose_name='Photo de l\'élève')
    afficher_matricule = models.BooleanField(default=True,  verbose_name='Matricule')
    afficher_classe    = models.BooleanField(default=True,  verbose_name='Classe')
    afficher_annee     = models.BooleanField(default=True,  verbose_name='Année scolaire')
    afficher_qr        = models.BooleanField(default=True,  verbose_name='QR Code')
    afficher_ddn       = models.BooleanField(default=False, verbose_name='Date de naissance')
    afficher_sexe      = models.BooleanField(default=False, verbose_name='Sexe')

    # ── Documents optionnels (verso) ──
    signature_prefet    = models.ImageField(upload_to='cartes/signatures/', blank=True, null=True,
                              verbose_name='Signature du préfet')
    signature_directeur = models.ImageField(upload_to='cartes/signatures/', blank=True, null=True,
                              verbose_name='Signature du directeur')
    cachet              = models.ImageField(upload_to='cartes/cachets/', blank=True, null=True,
                              verbose_name='Cachet de l\'établissement')

    class Meta:
        verbose_name = 'Configuration des cartes'

    @classmethod
    def get_config(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f'Configuration cartes — {self.get_modele_display()}'
