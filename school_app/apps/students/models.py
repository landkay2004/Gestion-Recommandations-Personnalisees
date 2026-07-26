from django.db import models
from classes.models import Classe
import uuid


def student_photo_path(instance, filename):
    ext = filename.split('.')[-1]
    return f'students/{instance.matricule}/photo.{ext}'


class Student(models.Model):
    SEXE_CHOICES = [('M', 'Masculin'), ('F', 'Féminin')]

    nom = models.CharField(max_length=100)
    postnom = models.CharField(max_length=100, blank=True)
    prenom = models.CharField(max_length=100, blank=True)
    sexe = models.CharField(max_length=1, choices=SEXE_CHOICES)
    date_naissance = models.DateField()
    lieu_naissance = models.CharField(max_length=100)
    adresse = models.TextField(blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    nom_parent = models.CharField(max_length=200, blank=True, verbose_name="Nom du parent/tuteur")
    classe = models.ForeignKey(Classe, on_delete=models.SET_NULL, null=True, related_name='eleves')
    photo = models.ImageField(upload_to=student_photo_path, null=True, blank=True)
    matricule = models.CharField(max_length=50, unique=True)
    date_inscription = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ['nom', 'postnom', 'prenom']
        verbose_name = "Élève"
        verbose_name_plural = "Élèves"
        indexes = [
            models.Index(fields=['classe'], name='student_classe_idx'),
            models.Index(fields=['nom', 'postnom'], name='student_nom_idx'),
        ]

    def __str__(self):
        return self.nom_complet

    @property
    def nom_complet(self):
        parts = [self.nom, self.postnom, self.prenom]
        return ' '.join(p for p in parts if p).strip()

    def save(self, *args, **kwargs):
        if not self.matricule:
            self.matricule = f"EL{str(uuid.uuid4().int)[:8].upper()}"
        super().save(*args, **kwargs)
