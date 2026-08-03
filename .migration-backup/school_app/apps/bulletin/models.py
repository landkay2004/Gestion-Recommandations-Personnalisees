from django.db import models
from classes.models import Classe, AnneeScolaire
from subjects.models import Matiere


class ModeleBulletin(models.Model):
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name='modeles_bulletin')
    annee_scolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE)
    publie = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_publication = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['classe', 'annee_scolaire']
        ordering = ['-annee_scolaire__annee', 'classe__nom']
        verbose_name = "Modèle de bulletin"
        verbose_name_plural = "Modèles de bulletins"

    def __str__(self):
        return f"Bulletin {self.classe} — {self.annee_scolaire}"

    def matieres_by_maxima(self):
        result = {20: [], 30: [], 60: []}
        for bm in self.matieres.select_related('matiere').order_by('matiere__maxima', 'ordre'):
            result[bm.matiere.maxima].append(bm.matiere)
        return result


class ModeleBulletinMatiere(models.Model):
    modele = models.ForeignKey(ModeleBulletin, on_delete=models.CASCADE, related_name='matieres')
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE)
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['matiere__maxima', 'ordre']
        unique_together = ['modele', 'matiere']
        verbose_name = "Matière du bulletin"

    def __str__(self):
        return f"{self.modele} — {self.matiere}"
