from django.db import models
from django.utils import timezone


class Notification(models.Model):

    # ── Catégories ────────────────────────────────────────────────────────────
    CATEGORIE_CHOICES = [
        ('SCOLAIRE',    'Scolaire'),
        ('ADMIN',       'Administrative'),
        ('PEDAGOGIQUE', 'Pédagogique'),
        ('PARENT',      'Parents'),
        ('SYSTEME',     'Système'),
    ]

    # ── Priorités ─────────────────────────────────────────────────────────────
    PRIORITE_CHOICES = [
        ('INFO',      'Information'),
        ('SUCCES',    'Succès'),
        ('AVERT',     'Avertissement'),
        ('IMPORTANT', 'Important'),
        ('CRITIQUE',  'Critique'),
    ]

    # ── Types (extensible) ────────────────────────────────────────────────────
    TYPE_CHOICES = [
        # Scolaire
        ('SEMESTRE_ACTIF',     "Semestre activé"),
        ('SEMESTRE_PUBLIE',    "Semestre publié"),
        ('SEMESTRE_ARCHIVE',   "Semestre archivé"),
        ('REPECHAGE_ACTIF',    "Repêchage activé"),
        ('REPECHAGE_INACTIF',  "Repêchage désactivé"),
        ('ANNEE_ACTIVEE',      "Nouvelle année scolaire"),
        ('ANNEE_CLOTUREE',     "Année scolaire clôturée"),
        ('RESULTATS_PUBLIES',  "Résultats publiés"),
        ('BULLETIN_DISPO',     "Bulletin disponible"),
        ('PROMOTION_ELEVES',   "Promotion des élèves"),
        # Admin
        ('COMPTE_CREE',        "Compte créé"),
        ('MDP_REINIT',         "Mot de passe réinitialisé"),
        ('MDP_CHANGE',         "Mot de passe modifié"),
        # Pédagogique
        ('MATIERE_AFFECTEE',   "Matière affectée"),
        ('MATIERE_RETIREE',    "Matière retirée"),
        # Système
        ('SYSTEME',            "Système"),
    ]

    # ── Config visuelle par priorité ──────────────────────────────────────────
    _PRIORITE_STYLE = {
        'INFO':      ('info',    'bi-info-circle-fill'),
        'SUCCES':    ('success', 'bi-check-circle-fill'),
        'AVERT':     ('warning', 'bi-exclamation-triangle-fill'),
        'IMPORTANT': ('primary', 'bi-star-fill'),
        'CRITIQUE':  ('danger',  'bi-exclamation-octagon-fill'),
    }

    # ── Champs ────────────────────────────────────────────────────────────────
    destinataire  = models.ForeignKey(
        'accounts.CustomUser', on_delete=models.CASCADE, related_name='notifications'
    )
    expediteur    = models.ForeignKey(
        'accounts.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='notifications_envoyees'
    )
    titre         = models.CharField(max_length=200)
    description   = models.TextField(blank=True)
    categorie     = models.CharField(max_length=20, choices=CATEGORIE_CHOICES, default='SYSTEME')
    priorite      = models.CharField(max_length=20, choices=PRIORITE_CHOICES, default='INFO')
    type_notif    = models.CharField(max_length=30, choices=TYPE_CHOICES, blank=True, default='SYSTEME')
    lue           = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_lecture  = models.DateTimeField(null=True, blank=True)
    lien          = models.CharField(max_length=500, blank=True)
    annee_scolaire = models.ForeignKey(
        'classes.AnneeScolaire', on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['destinataire', 'lue'],           name='notif_dest_lue_idx'),
            models.Index(fields=['destinataire', '-date_creation'], name='notif_dest_date_idx'),
        ]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return f"[{self.get_priorite_display()}] {self.titre} → {self.destinataire}"

    # ── Helpers ───────────────────────────────────────────────────────────────
    @property
    def couleur(self):
        return self._PRIORITE_STYLE.get(self.priorite, ('info', ''))[0]

    @property
    def icone(self):
        return self._PRIORITE_STYLE.get(self.priorite, ('', 'bi-bell-fill'))[1]

    def lire(self):
        if not self.lue:
            self.lue = True
            self.date_lecture = timezone.now()
            self.save(update_fields=['lue', 'date_lecture'])
