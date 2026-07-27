"""
Modeles partages (schema public) - Tenant, plans abonnement, annuaire utilisateurs.
"""
import string
import secrets
import json
from datetime import timedelta

from django.db import models
from django.utils import timezone
from django_tenants.models import TenantMixin, DomainMixin


def _gen_temp_password(length=12):
    import re
    specials = '!@#$%&*'
    alphabet = string.ascii_letters + string.digits + specials
    while True:
        pwd = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
            secrets.choice(specials),
        ]
        pwd += [secrets.choice(alphabet) for _ in range(length - 4)]
        secrets.SystemRandom().shuffle(pwd)
        result = ''.join(pwd)
        if (len(result) >= length and re.search(r'[A-Z]', result)
                and re.search(r'[a-z]', result)
                and re.search(r'\d', result)
                and re.search(r'[!@#$%&*]', result)):
            return result


class PlanAbonnement(models.Model):
    nom = models.CharField("Nom du plan", max_length=100)
    description = models.TextField("Description", blank=True)
    max_eleves = models.IntegerField("Max eleves", default=150)
    max_enseignants = models.IntegerField("Max enseignants", default=30)
    max_classes = models.IntegerField("Max classes", default=15)
    max_utilisateurs = models.IntegerField("Max utilisateurs", default=35)
    prix_mensuel = models.DecimalField(
        "Prix mensuel (USD)", max_digits=10, decimal_places=2, default=0
    )
    is_actif = models.BooleanField("Actif", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'tenants'
        verbose_name = "Plan d'abonnement"
        verbose_name_plural = "Plans d'abonnement"
        ordering = ['prix_mensuel']

    def __str__(self):
        return self.nom


class Ecole(TenantMixin):
    """Chaque ecole = un schema PostgreSQL independant."""

    STATUT_CHOICES = [
        ('active',    'Active'),
        ('suspendue', 'Suspendue'),
        ('expiree',   'Expiree'),
        ('corbeille', 'Corbeille'),
    ]

    nom = models.CharField("Nom de l'ecole", max_length=200)
    contact_nom = models.CharField("Nom du responsable", max_length=200, blank=True)
    contact_email = models.EmailField("Email de contact")
    contact_telephone = models.CharField("Telephone", max_length=50, blank=True)
    adresse = models.TextField("Adresse", blank=True)
    ville = models.CharField("Ville", max_length=100, blank=True)
    pays = models.CharField("Pays", max_length=100, default='RDC')

    plan = models.ForeignKey(
        PlanAbonnement, on_delete=models.PROTECT,
        null=True, blank=True, related_name='ecoles'
    )
    date_debut_abonnement = models.DateField("Debut abonnement", null=True, blank=True)
    date_fin_abonnement = models.DateField("Fin abonnement", null=True, blank=True)
    jours_grace = models.IntegerField("Jours de grace", default=7)

    statut = models.CharField(
        max_length=20, choices=STATUT_CHOICES, default='active', db_index=True
    )

    onboarding_complete = models.BooleanField("Configuration terminee", default=False)

    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    auto_create_schema = True

    class Meta:
        app_label = 'tenants'
        verbose_name = 'Ecole'
        verbose_name_plural = 'Ecoles'
        ordering = ['-created_at']

    def __str__(self):
        return self.nom

    @property
    def abonnement_expire(self):
        if not self.date_fin_abonnement:
            return False
        return timezone.now().date() > self.date_fin_abonnement

    @property
    def en_grace(self):
        if not self.date_fin_abonnement:
            return False
        limit = self.date_fin_abonnement + timedelta(days=self.jours_grace)
        today = timezone.now().date()
        return self.date_fin_abonnement < today <= limit

    @property
    def acces_lecture_seule(self):
        if not self.date_fin_abonnement:
            return False
        limit = self.date_fin_abonnement + timedelta(days=self.jours_grace)
        return timezone.now().date() > limit

    def marquer_suppression(self):
        self.statut = 'corbeille'
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['statut', 'is_deleted', 'deleted_at'])


class EcoleDomain(DomainMixin):
    class Meta:
        app_label = 'tenants'


class AdminEcole(models.Model):
    """
    Tracker pour l'administrateur d'une ecole (schema public).
    Le mot de passe est dans CustomUser du schema tenant.
    """
    ONBOARDING_STEPS = [
        (0, 'Non commence'),
        (1, 'Mot de passe change'),
        (2, 'Ecole configuree'),
        (3, 'Recapitulatif valide'),
        (4, 'Conditions acceptees'),
        (5, 'Termine'),
    ]

    ecole = models.OneToOneField(Ecole, on_delete=models.CASCADE, related_name='admin')
    email = models.EmailField("Email", unique=True)

    nom = models.CharField("Nom", max_length=100, blank=True)
    prenom = models.CharField("Prenom", max_length=100, blank=True)
    telephone = models.CharField("Telephone", max_length=50, blank=True)

    onboarding_step = models.IntegerField("Etape onboarding", default=0)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField("Derniere connexion", null=True, blank=True)

    class Meta:
        app_label = 'tenants'
        verbose_name = "Administrateur d'ecole"
        verbose_name_plural = "Administrateurs d'ecole"

    def __str__(self):
        return "%s (%s)" % (self.email, self.ecole.nom)

    def get_full_name(self):
        return ("%s %s" % (self.prenom, self.nom)).strip() or self.email

    @property
    def onboarding_complete(self):
        return self.onboarding_step >= 5


class AnnuaireUtilisateur(models.Model):
    """
    Table de lookup partagee : email -> schema_name.
    Permet au login de trouver le bon schema.
    """
    TYPE_CHOICES = [
        ('admin_ecole', 'Admin Ecole'),
        ('prefet',      'Prefet'),
        ('enseignant',  'Enseignant'),
    ]
    email = models.EmailField(unique=True, db_index=True)
    schema_name = models.CharField(max_length=63)
    type_compte = models.CharField(max_length=20, choices=TYPE_CHOICES)

    class Meta:
        app_label = 'tenants'
        verbose_name = 'Annuaire utilisateur'

    def __str__(self):
        return "%s -> %s" % (self.email, self.schema_name)


class ModeMaintenance(models.Model):
    ecole = models.ForeignKey(
        Ecole, on_delete=models.CASCADE, null=True, blank=True,
        help_text="Null = maintenance globale"
    )
    module = models.CharField(
        max_length=50, blank=True,
        help_text="Ex: bulletins. Vide = tous les modules."
    )
    is_active = models.BooleanField("Actif", default=False)
    message = models.TextField(
        default="Le systeme est en maintenance. Veuillez reessayer plus tard."
    )
    is_urgence = models.BooleanField("Urgence", default=False)
    debut_prevu = models.DateTimeField("Debut prevu", null=True, blank=True)
    fin_prevue = models.DateTimeField("Fin prevue", null=True, blank=True)
    duree_estimee_minutes = models.IntegerField("Duree estimee (min)", default=60)
    notification_envoyee = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'tenants'
        verbose_name = 'Mode maintenance'

    def __str__(self):
        scope = self.ecole.nom if self.ecole else 'Global'
        mod = ' [%s]' % self.module if self.module else ''
        return "Maintenance %s%s - %s" % (scope, mod, 'Actif' if self.is_active else 'Inactif')


class AnnoncePlateforme(models.Model):
    """Communication publiée depuis le schéma public vers les écoles."""

    TYPE_CHOICES = [
        ('info', 'Information'),
        ('success', 'Bonne nouvelle'),
        ('warning', 'Important'),
        ('urgent', 'Urgent'),
    ]

    titre = models.CharField("Titre", max_length=180)
    message = models.TextField("Message")
    type_annonce = models.CharField(
        "Type", max_length=20, choices=TYPE_CHOICES, default='info'
    )
    ecole = models.ForeignKey(
        Ecole, on_delete=models.CASCADE, null=True, blank=True,
        related_name='annonces_plateforme',
        help_text="Vide = toutes les écoles"
    )
    publiee = models.BooleanField("Publiée", default=True)
    date_publication = models.DateTimeField("Date de publication", auto_now_add=True)
    date_expiration = models.DateTimeField("Date d'expiration", null=True, blank=True)
    auteur_nom = models.CharField("Auteur", max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'tenants'
        ordering = ['-date_publication', '-created_at']
        verbose_name = "Annonce plateforme"
        verbose_name_plural = "Annonces plateforme"

    def __str__(self):
        return self.titre
