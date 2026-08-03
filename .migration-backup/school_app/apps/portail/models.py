import secrets
from datetime import timedelta
from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone


def generate_token():
    return secrets.token_urlsafe(32)


class PortailConfig(models.Model):
    nom_portail = models.CharField(max_length=200, default="Portail des Résultats")
    logo = models.ImageField(upload_to='portail/', null=True, blank=True)
    url_portail = models.CharField(
        max_length=500, blank=True,
        help_text="URL complète du portail après hébergement (ex: https://monecole.com) — utilisée pour générer les QR Codes"
    )
    texte_accueil = models.TextField(default="Bienvenue sur le Portail des Résultats.")
    couleur_primaire = models.CharField(max_length=7, default="#2563EB")
    couleur_secondaire = models.CharField(max_length=7, default="#1E293B")

    class Meta:
        verbose_name = "Configuration du portail"

    def __str__(self):
        return self.nom_portail

    @classmethod
    def get_config(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class PortailAcces(models.Model):
    eleve = models.OneToOneField(
        'students.Student', on_delete=models.CASCADE, related_name='portail_acces'
    )
    token = models.CharField(max_length=64, unique=True, default=generate_token)
    code_acces_hash = models.CharField(max_length=256, null=True, blank=True)
    active = models.BooleanField(default=False)
    date_activation = models.DateTimeField(null=True, blank=True)
    tentatives_echec = models.IntegerField(default=0)
    bloque_jusqu = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Accès portail"
        verbose_name_plural = "Accès portail"

    def __str__(self):
        return f"Accès portail — {self.eleve}"

    def is_bloque(self):
        if self.bloque_jusqu and self.bloque_jusqu > timezone.now():
            return True
        if self.bloque_jusqu and self.bloque_jusqu <= timezone.now():
            # Débloquer automatiquement
            self.bloque_jusqu = None
            self.tentatives_echec = 0
            self.save(update_fields=['bloque_jusqu', 'tentatives_echec'])
        return False

    def verifier_code(self, code):
        if not self.code_acces_hash:
            return False
        return check_password(code, self.code_acces_hash)

    def definir_code(self, code):
        self.code_acces_hash = make_password(code)
        self.active = True
        self.date_activation = timezone.now()
        self.tentatives_echec = 0
        self.bloque_jusqu = None
        self.save()

    def incrementer_tentatives(self):
        self.tentatives_echec += 1
        if self.tentatives_echec >= 5:
            self.bloque_jusqu = timezone.now() + timedelta(minutes=15)
        self.save()

    def reset_acces(self):
        """Réinitialise l'accès — le parent devra créer un nouveau code."""
        self.code_acces_hash = None
        self.active = False
        self.date_activation = None
        self.tentatives_echec = 0
        self.bloque_jusqu = None
        self.save()

    @property
    def statut_label(self):
        if self.is_bloque():
            return "Bloqué"
        if self.active:
            return "Activé"
        return "Non activé"

    @property
    def statut_class(self):
        if self.is_bloque():
            return "danger"
        if self.active:
            return "success"
        return "warning"


class PublicationResultats(models.Model):
    PERIODE_CHOICES = [
        ('1P',     '1ère Période'),
        ('2P',     '2ème Période'),
        ('EXAM1',  'Examen S1'),
        ('3P',     '3ème Période'),
        ('4P',     '4ème Période'),
        ('EXAM2',  'Examen S2'),
        ('ANNUEL', 'Résultat annuel'),
    ]

    classe = models.ForeignKey(
        'classes.Classe', on_delete=models.CASCADE, related_name='publications'
    )
    annee_scolaire = models.ForeignKey(
        'classes.AnneeScolaire', on_delete=models.CASCADE
    )
    periode = models.CharField(max_length=20, choices=PERIODE_CHOICES)
    publie = models.BooleanField(default=False)
    date_publication = models.DateTimeField(null=True, blank=True)
    publie_par = models.ForeignKey(
        'accounts.CustomUser', on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        unique_together = ['classe', 'annee_scolaire', 'periode']
        verbose_name = "Publication des résultats"
        verbose_name_plural = "Publications des résultats"
        ordering = ['classe__nom', 'periode']

    def __str__(self):
        etat = 'Publié' if self.publie else 'Non publié'
        return f"{self.classe} — {self.get_periode_display()} — {etat}"

    def publier(self, user):
        self.publie = True
        self.date_publication = timezone.now()
        self.publie_par = user
        self.save()

    def depublier(self):
        self.publie = False
        self.date_publication = None
        self.save()
