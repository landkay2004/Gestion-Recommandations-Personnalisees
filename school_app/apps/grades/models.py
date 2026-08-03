from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from students.models import Student
from subjects.models import MatiereClasse


class Note(models.Model):
    PERIODE_CHOICES = [
        ('1P', '1ère Période'),
        ('2P', '2ème Période'),
        ('EXAM1', 'Examen S1'),
        ('3P', '3ème Période'),
        ('4P', '4ème Période'),
        ('EXAM2', 'Examen S2'),
        ('REPECHAGE', 'Repêchage'),
    ]

    eleve = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='notes')
    matiere_classe = models.ForeignKey(MatiereClasse, on_delete=models.CASCADE, related_name='notes')
    periode = models.CharField(max_length=20, choices=PERIODE_CHOICES)
    valeur = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        validators=[MinValueValidator(0)]
    )

    class Meta:
        unique_together = ['eleve', 'matiere_classe', 'periode']
        verbose_name = "Note"
        indexes = [
            models.Index(fields=['eleve', 'periode'], name='note_eleve_periode_idx'),
            models.Index(fields=['matiere_classe', 'periode'], name='note_mc_periode_idx'),
            models.Index(fields=['eleve'], name='note_eleve_idx'),
        ]

    def __str__(self):
        return f"{self.eleve} — {self.matiere_classe.matiere} — {self.periode}: {self.valeur}"
