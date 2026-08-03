from django.db import models
from django.core.exceptions import ValidationError


class Salle(models.Model):
    nom = models.CharField("Nom / Numéro", max_length=60, unique=True)
    capacite = models.PositiveSmallIntegerField("Capacité", null=True, blank=True)
    description = models.CharField("Description", max_length=200, blank=True)

    class Meta:
        ordering = ['nom']
        verbose_name = 'Salle'
        verbose_name_plural = 'Salles'

    def __str__(self):
        return self.nom


class CreneauHoraire(models.Model):
    JOUR_CHOICES = [
        (1, 'Lundi'),
        (2, 'Mardi'),
        (3, 'Mercredi'),
        (4, 'Jeudi'),
        (5, 'Vendredi'),
        (6, 'Samedi'),
    ]
    TYPE_CHOICES = [
        ('cours',      'Cours'),
        ('repos',      'Repos / Pause'),
        ('recreation', 'Récréation'),
        ('priere',     'Prière / Recueillement'),
        ('repas',      'Repas'),
    ]
    jour = models.PositiveSmallIntegerField("Jour", choices=JOUR_CHOICES)
    heure_debut = models.TimeField("Heure de début")
    heure_fin = models.TimeField("Heure de fin")
    libelle = models.CharField("Libellé", max_length=60, blank=True,
                               help_text="Ex : « 08h00–09h00 ». Généré automatiquement si vide.")
    type_creneau = models.CharField(
        "Type", max_length=20, choices=TYPE_CHOICES, default='cours',
        help_text="'Repos' bloque la case dans la grille sans permettre d'y affecter un cours."
    )

    class Meta:
        ordering = ['jour', 'heure_debut']
        unique_together = [('jour', 'heure_debut', 'heure_fin')]
        verbose_name = 'Créneau horaire'
        verbose_name_plural = 'Créneaux horaires'

    def clean(self):
        if self.heure_debut and self.heure_fin and self.heure_debut >= self.heure_fin:
            raise ValidationError("L'heure de début doit être antérieure à l'heure de fin.")

    def save(self, *args, **kwargs):
        if not self.libelle:
            self.libelle = (
                f"{self.heure_debut.strftime('%Hh%M')}–{self.heure_fin.strftime('%Hh%M')}"
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_jour_display()} {self.libelle}"


class SeanceHoraire(models.Model):
    """Un cours placé dans le planning : créneau + matière/classe/enseignant + salle."""
    annee_scolaire = models.ForeignKey(
        'classes.AnneeScolaire',
        on_delete=models.CASCADE,
        related_name='seances',
        verbose_name="Année scolaire",
    )
    creneau = models.ForeignKey(
        CreneauHoraire,
        on_delete=models.CASCADE,
        related_name='seances',
        verbose_name="Créneau",
    )
    matiere_classe = models.ForeignKey(
        'subjects.MatiereClasse',
        on_delete=models.CASCADE,
        related_name='seances',
        verbose_name="Matière / Classe",
    )
    salle = models.ForeignKey(
        Salle,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='seances',
        verbose_name="Salle",
    )

    class Meta:
        ordering = ['creneau__jour', 'creneau__heure_debut']
        verbose_name = 'Séance horaire'
        verbose_name_plural = 'Séances horaires'

    def clean(self):
        errors = {}
        qs = SeanceHoraire.objects.filter(
            annee_scolaire=self.annee_scolaire,
            creneau=self.creneau,
        ).exclude(pk=self.pk)

        # Conflit de classe
        if qs.filter(matiere_classe__classe=self.matiere_classe.classe_id).exists():
            errors['matiere_classe'] = (
                f"Conflit : la classe {self.matiere_classe.classe} a déjà un cours "
                f"sur ce créneau."
            )

        # Conflit d'enseignant
        if self.matiere_classe.enseignant_id:
            if qs.filter(
                matiere_classe__enseignant=self.matiere_classe.enseignant_id
            ).exists():
                msg = (
                    f"Conflit : l'enseignant "
                    f"{self.matiere_classe.enseignant} a déjà un cours sur ce créneau."
                )
                errors.setdefault('matiere_classe', msg)

        # Conflit de salle
        if self.salle_id:
            if qs.filter(salle=self.salle_id).exists():
                errors['salle'] = (
                    f"Conflit : la salle {self.salle} est déjà occupée sur ce créneau."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.creneau} — {self.matiere_classe.matiere} "
            f"({self.matiere_classe.classe})"
        )
