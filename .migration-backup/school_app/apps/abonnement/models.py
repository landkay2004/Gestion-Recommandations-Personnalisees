"""
Modèles de gestion des frais scolaires : TypeFrais, Paiement, Facture.
Ces modèles vivent dans le schéma tenant (par école).
"""
import uuid
from decimal import Decimal

from django.db import models
from django.utils import timezone


def _generer_reference():
    return uuid.uuid4().hex[:10].upper()


class TypeFrais(models.Model):
    """Type de frais paramétré par l'admin_ecole (ex : Minerval, Tenue, Examen…)."""
    nom = models.CharField("Nom", max_length=100)
    montant = models.DecimalField("Montant", max_digits=10, decimal_places=2)
    classe = models.ForeignKey(
        'classes.Classe',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='types_frais',
        verbose_name="Classe (optionnel)",
        help_text="Laisser vide pour appliquer à tous les élèves.",
    )
    actif = models.BooleanField("Actif", default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nom']
        verbose_name = "Type de frais"
        verbose_name_plural = "Types de frais"

    def __str__(self):
        if self.classe:
            return f"{self.nom} ({self.classe}) — {self.montant}"
        return f"{self.nom} (tous) — {self.montant}"

    @property
    def applicable_a_toutes_classes(self):
        return self.classe is None


class Paiement(models.Model):
    """Encaissement d'un frais pour un élève."""
    MODE_CHOICES = [
        ('especes',      'Espèces'),
        ('mobile_money', 'Mobile Money'),
        ('virement',     'Virement bancaire'),
    ]

    eleve = models.ForeignKey(
        'students.Student',
        on_delete=models.CASCADE,
        related_name='paiements',
        verbose_name="Élève",
    )
    type_frais = models.ForeignKey(
        TypeFrais,
        on_delete=models.PROTECT,
        related_name='paiements',
        verbose_name="Type de frais",
    )
    montant_paye = models.DecimalField("Montant payé", max_digits=10, decimal_places=2)
    date_paiement = models.DateTimeField("Date de paiement", default=timezone.now)
    comptable = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.PROTECT,
        related_name='paiements_encaisses',
        verbose_name="Comptable",
    )
    mode_paiement = models.CharField(
        "Mode de paiement", max_length=20,
        choices=MODE_CHOICES, default='especes',
    )
    reference = models.CharField(
        "Référence", max_length=20, unique=True,
        default=_generer_reference, editable=False,
    )

    class Meta:
        ordering = ['-date_paiement']
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"

    def __str__(self):
        return f"Paiement {self.reference} — {self.eleve} / {self.type_frais.nom}"

    @property
    def reste_du(self):
        """Reste à payer APRÈS ce paiement pour ce type de frais."""
        total = self.eleve.paiements.filter(
            type_frais=self.type_frais
        ).aggregate(s=models.Sum('montant_paye'))['s'] or Decimal('0')
        return max(self.type_frais.montant - total, Decimal('0'))


class Facture(models.Model):
    """Facture générée automatiquement après chaque paiement validé."""
    paiement = models.OneToOneField(
        Paiement,
        on_delete=models.CASCADE,
        related_name='facture',
        verbose_name="Paiement",
    )
    numero_facture = models.CharField("Numéro de facture", max_length=30, unique=True)
    date_emission = models.DateTimeField("Date d'émission", default=timezone.now)

    class Meta:
        ordering = ['-date_emission']
        verbose_name = "Facture"
        verbose_name_plural = "Factures"

    def __str__(self):
        return self.numero_facture

    @classmethod
    def generer_numero(cls):
        """Génère FAC-YYYY-NNNN unique dans le schéma courant."""
        annee = timezone.now().year
        prefix = f"FAC-{annee}-"
        last = (
            cls.objects.filter(numero_facture__startswith=prefix)
            .order_by('-numero_facture')
            .first()
        )
        if last:
            try:
                seq = int(last.numero_facture.split('-')[-1]) + 1
            except ValueError:
                seq = 1
        else:
            seq = 1
        return f"{prefix}{seq:04d}"
