"""
Modeles partages (schema public) - Tenant, plans abonnement, annuaire utilisateurs.
"""
import string
import secrets
import json
from datetime import timedelta

from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django_tenants.models import TenantMixin, DomainMixin


# ── Constantes modules / fonctionnalites ─────────────────────────────────────

MODULES_SGN = [
    ('notes',           'Saisie et consultation des notes'),
    ('bulletins',       'Bulletins officiels RDC'),
    ('classes',         'Gestion des classes et sections'),
    ('eleves',          'Gestion des élèves'),
    ('enseignants',     'Gestion des enseignants'),
    ('planning',        'Planning hebdomadaire'),
    ('portail_parents', 'Portail parents (QR + résultats)'),
    ('carte_eleve',     "Cartes d'élève"),
    ('rapports',        'Rapports et exports PDF'),
    ('notifications',   'Notifications in-app'),
]

FONCTIONNALITES_SGN = [
    ('export_pdf',          'Export PDF avancé'),
    ('marque_blanche',      'Marque blanche (votre logo)'),
    ('support_prioritaire', 'Support prioritaire'),
    ('multi_annees',        'Archives multi-années'),
    ('sms_notifications',   'Notifications SMS'),
    ('api_access',          'Accès API'),
]

MODULES_DICT        = dict(MODULES_SGN)
FONCTIONNALITES_DICT = dict(FONCTIONNALITES_SGN)


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
    # ── Identification ────────────────────────────────────────────────────────
    nom             = models.CharField("Nom du plan", max_length=100)
    slug            = models.SlugField("Slug", max_length=100, unique=True, blank=True)
    description     = models.TextField("Description", blank=True)

    # ── Tarification ─────────────────────────────────────────────────────────
    prix_mensuel    = models.DecimalField("Prix mensuel (USD)",  max_digits=10, decimal_places=2, default=0)
    prix_annuel     = models.DecimalField("Prix annuel (USD)",   max_digits=10, decimal_places=2, default=0,
                                          help_text="Laisser à 0 pour calculer automatiquement (×12).")
    essai_gratuit_jours = models.IntegerField("Jours d'essai gratuit", default=0)

    # ── Quotas ────────────────────────────────────────────────────────────────
    max_eleves       = models.IntegerField("Max élèves",       default=150)
    max_enseignants  = models.IntegerField("Max enseignants",  default=30)
    max_classes      = models.IntegerField("Max classes",      default=15)
    max_utilisateurs = models.IntegerField("Max utilisateurs", default=35)
    max_stockage_go  = models.IntegerField("Stockage max (Go)", default=1)
    quota_sms_mensuel = models.IntegerField("Quota SMS / mois", default=0)

    # ── Modules et fonctionnalités ────────────────────────────────────────────
    modules_inclus          = models.JSONField(
        "Modules inclus", default=list, blank=True,
        help_text="Liste des clés de modules autorisés. Vide = tous les modules."
    )
    fonctionnalites_incluses = models.JSONField(
        "Fonctionnalités incluses", default=list, blank=True,
        help_text="Liste des clés de fonctionnalités avancées."
    )

    # ── Visibilité & ordre ────────────────────────────────────────────────────
    is_actif          = models.BooleanField("Actif",           default=True)
    est_public        = models.BooleanField("Visible publiquement", default=True,
                                            help_text="Visible dans la page de tarification publique.")
    ordre_affichage   = models.IntegerField("Ordre d'affichage", default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'tenants'
        verbose_name = "Plan d'abonnement"
        verbose_name_plural = "Plans d'abonnement"
        ordering = ['ordre_affichage', 'prix_mensuel']

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.nom)[:95] or 'plan'
            candidate = base
            i = 1
            while PlanAbonnement.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = '%s-%d' % (base, i)
                i += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    @property
    def prix_annuel_effectif(self):
        """Prix annuel : valeur saisie ou prix_mensuel × 12."""
        if self.prix_annuel and self.prix_annuel > 0:
            return self.prix_annuel
        return self.prix_mensuel * 12

    def get_modules_labels(self):
        return [MODULES_DICT.get(k, k) for k in (self.modules_inclus or [])]

    def get_fonctionnalites_labels(self):
        return [FONCTIONNALITES_DICT.get(k, k) for k in (self.fonctionnalites_incluses or [])]

    def module_inclus(self, key):
        """Retourne True si le module est inclus (liste vide = tout autorisé)."""
        modules = self.modules_inclus or []
        return not modules or key in modules


class Ecole(TenantMixin):
    """Chaque ecole = un schema PostgreSQL independant."""

    STATUT_CHOICES = [
        ('active',    'Active'),
        ('suspendue', 'Suspendue'),
        ('expiree',   'Expirée'),
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
    date_fin_abonnement   = models.DateField("Fin abonnement",   null=True, blank=True)
    jours_grace           = models.IntegerField("Jours de grace", default=7)

    statut = models.CharField(
        max_length=20, choices=STATUT_CHOICES, default='active', db_index=True
    )

    onboarding_complete = models.BooleanField("Configuration terminee", default=False)

    is_deleted  = models.BooleanField(default=False)
    deleted_at  = models.DateTimeField(null=True, blank=True)

    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

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

    @property
    def jours_avant_expiration(self):
        if not self.date_fin_abonnement:
            return None
        return (self.date_fin_abonnement - timezone.now().date()).days

    @property
    def is_accessible(self):
        return not self.is_deleted and self.statut != 'corbeille'

    def marquer_suppression(self):
        self.statut = 'corbeille'
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['statut', 'is_deleted', 'deleted_at'])


class EcoleDomain(DomainMixin):
    class Meta:
        app_label = 'tenants'


class Abonnement(models.Model):
    """
    Enregistrement d'abonnement École ↔ Plan avec historique et statut dédié.
    """
    STATUT_CHOICES = [
        ('actif',    'Actif'),
        ('essai',    'Essai gratuit'),
        ('expire',   'Expiré'),
        ('suspendu', 'Suspendu'),
    ]

    ecole              = models.OneToOneField(
        Ecole, on_delete=models.CASCADE, related_name='abonnement_detail',
        verbose_name="École"
    )
    plan               = models.ForeignKey(
        PlanAbonnement, on_delete=models.PROTECT, related_name='abonnements',
        verbose_name="Plan"
    )
    date_debut         = models.DateField("Date de début")
    date_fin           = models.DateField("Date de fin", null=True, blank=True)
    statut             = models.CharField(
        max_length=20, choices=STATUT_CHOICES, default='actif', db_index=True,
        verbose_name="Statut"
    )
    renouvellement_auto = models.BooleanField("Renouvellement automatique", default=False)
    notes_internes     = models.TextField("Notes internes (super-admin)", blank=True)
    created_at         = models.DateTimeField(auto_now_add=True)
    updated_at         = models.DateTimeField(auto_now=True)

    class Meta:
        app_label  = 'tenants'
        verbose_name = "Abonnement"
        verbose_name_plural = "Abonnements"
        ordering = ['-created_at']

    def __str__(self):
        return "Abonnement %s — %s" % (self.ecole.nom, self.plan.nom)

    @property
    def jours_restants(self):
        if not self.date_fin:
            return None
        return (self.date_fin - timezone.now().date()).days

    @property
    def est_expire(self):
        if not self.date_fin:
            return False
        return timezone.now().date() > self.date_fin

    def changer_plan(self, nouveau_plan, motif='', modifie_par=''):
        """Change le plan et enregistre l'historique."""
        ancien = self.plan
        HistoriqueAbonnement.objects.create(
            abonnement=self,
            ancien_plan=ancien,
            nouveau_plan=nouveau_plan,
            ancien_statut=self.statut,
            nouveau_statut=self.statut,
            motif=motif,
            modifie_par=modifie_par,
        )
        self.plan = nouveau_plan
        self.save(update_fields=['plan', 'updated_at'])
        # Synchroniser sur l'Ecole
        self.ecole.plan = nouveau_plan
        self.ecole.save(update_fields=['plan', 'updated_at'])

    def changer_statut(self, nouveau_statut, motif='', modifie_par=''):
        """Change le statut et enregistre l'historique."""
        HistoriqueAbonnement.objects.create(
            abonnement=self,
            ancien_plan=self.plan,
            nouveau_plan=self.plan,
            ancien_statut=self.statut,
            nouveau_statut=nouveau_statut,
            motif=motif,
            modifie_par=modifie_par,
        )
        self.statut = nouveau_statut
        self.save(update_fields=['statut', 'updated_at'])


class HistoriqueAbonnement(models.Model):
    """Journal des changements de plan / statut d'un abonnement."""
    abonnement    = models.ForeignKey(Abonnement, on_delete=models.CASCADE, related_name='historique')
    ancien_plan   = models.ForeignKey(
        PlanAbonnement, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    nouveau_plan  = models.ForeignKey(
        PlanAbonnement, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    ancien_statut = models.CharField(max_length=20, blank=True)
    nouveau_statut = models.CharField(max_length=20, blank=True)
    date_changement = models.DateTimeField(auto_now_add=True)
    motif         = models.TextField(blank=True)
    modifie_par   = models.CharField(max_length=150, blank=True)

    class Meta:
        app_label = 'tenants'
        ordering = ['-date_changement']
        verbose_name = "Historique abonnement"
        verbose_name_plural = "Historiques abonnements"

    def __str__(self):
        return "Changement le %s — %s" % (self.date_changement.date(), self.abonnement.ecole.nom)


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

    nom    = models.CharField("Nom",    max_length=100, blank=True)
    prenom = models.CharField("Prenom", max_length=100, blank=True)
    telephone = models.CharField("Telephone", max_length=50, blank=True)

    onboarding_step = models.IntegerField("Etape onboarding", default=0)

    is_active  = models.BooleanField(default=True)
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
        ('admin_ecole',  'Admin Ecole'),
        ('prefet',       'Prefet'),
        ('enseignant',   'Enseignant'),
        ('secretariat',  'Secrétariat'),
        ('comptable',    'Comptable'),
    ]
    email        = models.EmailField(unique=True, db_index=True)
    schema_name  = models.CharField(max_length=63)
    type_compte  = models.CharField(max_length=20, choices=TYPE_CHOICES)

    class Meta:
        app_label = 'tenants'
        verbose_name = 'Annuaire utilisateur'

    def __str__(self):
        return "%s -> %s" % (self.email, self.schema_name)


class ModeMaintenance(models.Model):
    ecole  = models.ForeignKey(
        Ecole, on_delete=models.CASCADE, null=True, blank=True,
        help_text="Null = maintenance globale"
    )
    module = models.CharField(
        max_length=50, blank=True,
        help_text="Ex: bulletins. Vide = tous les modules."
    )
    is_active  = models.BooleanField("Actif", default=False)
    message    = models.TextField(
        default="Le systeme est en maintenance. Veuillez reessayer plus tard."
    )
    is_urgence = models.BooleanField("Urgence", default=False)
    debut_prevu = models.DateTimeField("Debut prevu", null=True, blank=True)
    fin_prevue  = models.DateTimeField("Fin prevue", null=True, blank=True)
    duree_estimee_minutes = models.IntegerField("Duree estimee (min)", default=60)
    notification_envoyee  = models.BooleanField(default=False)
    created_at     = models.DateTimeField(auto_now_add=True)
    activated_at   = models.DateTimeField(null=True, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'tenants'
        verbose_name = 'Mode maintenance'

    def __str__(self):
        scope = self.ecole.nom if self.ecole else 'Global'
        mod   = ' [%s]' % self.module if self.module else ''
        return "Maintenance %s%s - %s" % (scope, mod, 'Actif' if self.is_active else 'Inactif')


class AnnoncePlateforme(models.Model):
    """Communication publiée depuis le schéma public vers les écoles."""

    TYPE_CHOICES = [
        ('info',    'Information'),
        ('success', 'Bonne nouvelle'),
        ('warning', 'Important'),
        ('urgent',  'Urgent'),
    ]

    titre          = models.CharField("Titre", max_length=180)
    message        = models.TextField("Message")
    type_annonce   = models.CharField(
        "Type", max_length=20, choices=TYPE_CHOICES, default='info'
    )
    ecole          = models.ForeignKey(
        Ecole, on_delete=models.CASCADE, null=True, blank=True,
        related_name='annonces_plateforme',
        help_text="Vide = toutes les écoles"
    )
    publiee        = models.BooleanField("Publiée", default=True)
    date_publication = models.DateTimeField("Date de publication", auto_now_add=True)
    date_expiration  = models.DateTimeField("Date d'expiration", null=True, blank=True)
    auteur_nom       = models.CharField("Auteur", max_length=150, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'tenants'
        ordering = ['-date_publication', '-created_at']
        verbose_name = "Annonce plateforme"
        verbose_name_plural = "Annonces plateforme"

    def __str__(self):
        return self.titre


# ════════════════════════════════════════════════════════════════════════════
# DEMANDE D'ABONNEMENT (écoles → super admin)
# ════════════════════════════════════════════════════════════════════════════

class DemandeAbonnement(models.Model):
    """
    Demande de changement / renouvellement de plan soumise par l'admin-école.
    Visible dans le back-office super-admin avec badge de notification.
    """
    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('approuvee',  'Approuvée'),
        ('rejetee',    'Rejetée'),
        ('annulee',    'Annulée'),
    ]

    ecole          = models.ForeignKey(Ecole, on_delete=models.CASCADE,
                                        related_name='demandes_abonnement',
                                        verbose_name='École')
    plan_souhaite  = models.ForeignKey(PlanAbonnement, on_delete=models.SET_NULL,
                                        null=True, related_name='+',
                                        verbose_name='Plan souhaité')
    plan_actuel    = models.ForeignKey(PlanAbonnement, on_delete=models.SET_NULL,
                                        null=True, blank=True, related_name='+',
                                        verbose_name='Plan actuel')
    message        = models.TextField('Message de l\'école', blank=True)
    contact_email  = models.EmailField('Email contact', blank=True)
    contact_nom    = models.CharField('Nom contact', max_length=200, blank=True)
    statut         = models.CharField('Statut', max_length=20,
                                       choices=STATUT_CHOICES, default='en_attente',
                                       db_index=True)
    reponse_admin  = models.TextField('Réponse super-admin', blank=True)
    traite_par     = models.CharField('Traité par', max_length=200, blank=True)
    traite_le      = models.DateTimeField('Traité le', null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'tenants'
        ordering = ['-created_at']
        verbose_name = 'Demande d\'abonnement'
        verbose_name_plural = 'Demandes d\'abonnement'

    def __str__(self):
        return 'Demande %s — %s (%s)' % (
            self.ecole.nom,
            self.plan_souhaite.nom if self.plan_souhaite else '?',
            self.statut,
        )


# ════════════════════════════════════════════════════════════════════════════
# PAIEMENT PLATEFORME (mobile money / virement pour abonnement)
# ════════════════════════════════════════════════════════════════════════════

def _preuve_upload_path(instance, filename):
    import os, uuid
    ext = os.path.splitext(filename)[1].lower()
    return 'paiements_plateforme/%s%s' % (uuid.uuid4().hex, ext)


class PaiementPlatforme(models.Model):
    """
    Paiement soumis par l'école pour son abonnement plateforme.
    Inclut preuve (capture mobile money / reçu virement) validée par le super-admin.
    """
    MODE_CHOICES = [
        ('mobile_money', 'Mobile Money'),
        ('virement',     'Virement bancaire'),
        ('especes',      'Espèces'),
    ]
    STATUT_CHOICES = [
        ('en_attente', 'En attente de validation'),
        ('valide',     'Validé'),
        ('rejete',     'Rejeté'),
    ]

    ecole              = models.ForeignKey(Ecole, on_delete=models.CASCADE,
                                            related_name='paiements_plateforme',
                                            verbose_name='École')
    montant            = models.DecimalField('Montant (USD)', max_digits=10, decimal_places=2)
    mode               = models.CharField('Mode', max_length=20, choices=MODE_CHOICES)
    numero_transaction = models.CharField('N° transaction', max_length=100, blank=True)
    preuve             = models.FileField('Preuve', upload_to=_preuve_upload_path,
                                           null=True, blank=True)
    notes              = models.TextField('Notes école', blank=True)
    statut             = models.CharField('Statut', max_length=20,
                                           choices=STATUT_CHOICES, default='en_attente',
                                           db_index=True)
    # Validation super-admin
    valide_par         = models.CharField('Validé par', max_length=200, blank=True)
    valide_le          = models.DateTimeField('Validé le', null=True, blank=True)
    notes_admin        = models.TextField('Notes admin', blank=True)
    # Jours d'abonnement accordés suite à la validation
    jours_accordes     = models.IntegerField('Jours accordés', default=0)
    # Traçabilité sécurité
    ip_soumission      = models.GenericIPAddressField('IP soumission', null=True, blank=True)
    created_at         = models.DateTimeField(auto_now_add=True)
    updated_at         = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'tenants'
        ordering = ['-created_at']
        verbose_name = 'Paiement plateforme'
        verbose_name_plural = 'Paiements plateforme'

    def __str__(self):
        return 'Paiement %s — %s USD (%s)' % (
            self.ecole.nom, self.montant, self.statut
        )

    def get_mode_display_label(self):
        return dict(self.MODE_CHOICES).get(self.mode, self.mode)
