from django.db import models


class Maxima(models.Model):
    """Valeur de maxima configurable par le préfet (ex: 10, 20, 30, 60, 100…)."""
    valeur = models.PositiveIntegerField(unique=True)

    class Meta:
        ordering = ['valeur']
        verbose_name = "Maxima"
        verbose_name_plural = "Maxima"

    def __str__(self):
        return f"MAXIMA {self.valeur}"


class Matiere(models.Model):
    nom = models.CharField(max_length=100, unique=True)
    maxima = models.PositiveIntegerField(default=20)

    class Meta:
        ordering = ['maxima', 'nom']
        verbose_name = "Matière"
        verbose_name_plural = "Matières"

    def __str__(self):
        return self.nom

    @property
    def maxima_label(self):
        return f"MAXIMA {self.maxima}"


class MatiereClasse(models.Model):
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE, related_name='affectations')
    classe = models.ForeignKey('classes.Classe', on_delete=models.CASCADE, related_name='matieres')
    enseignant = models.ForeignKey(
        'teachers.Teacher',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='matieres_enseignees'
    )

    class Meta:
        unique_together = ['matiere', 'classe']
        ordering = ['matiere__maxima', 'matiere__nom']
        verbose_name = "Affectation matière-classe"

    def __str__(self):
        return f"{self.matiere} → {self.classe}"
