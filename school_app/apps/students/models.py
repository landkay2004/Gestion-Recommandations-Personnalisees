from django.db import models
from classes.models import Classe
import uuid

from config.tenant_media import get_tenant_schema, _ext, _uid


def student_photo_path(instance, filename):
    """Photo d'élève organisée par tenant et matricule."""
    schema = get_tenant_schema()
    matricule = getattr(instance, 'matricule', None) or _uid()
    return f'tenants/{schema}/students/{matricule}/photo{_ext(filename)}'


class Tuteur(models.Model):
    """Parent ou tuteur légal d'un ou plusieurs élèves."""
    nom = models.CharField(max_length=100, verbose_name="Nom")
    postnom = models.CharField(max_length=100, blank=True, verbose_name="Postnom")
    prenom = models.CharField(max_length=100, blank=True, verbose_name="Prénom")
    telephone = models.CharField(max_length=20, blank=True, verbose_name="Téléphone")
    adresse = models.TextField(blank=True, verbose_name="Adresse")
    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        ordering = ['nom', 'postnom']
        verbose_name = "Tuteur"
        verbose_name_plural = "Tuteurs"
        indexes = [
            models.Index(fields=['nom', 'postnom'], name='tuteur_nom_idx'),
        ]

    def __str__(self):
        return self.nom_complet

    @property
    def nom_complet(self):
        parts = [self.nom, self.postnom, self.prenom]
        return ' '.join(p for p in parts if p).strip()


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
    nom_parent = models.CharField(max_length=200, blank=True, verbose_name="Nom du parent/tuteur (ancien)")
    tuteur = models.ForeignKey(
        Tuteur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='enfants',
        verbose_name="Tuteur",
    )
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
            try:
                from school_settings.models import MatriculeConfig
                config = MatriculeConfig.get_config()
                self.matricule = config.generer_matricule()
            except Exception:
                # Repli UUID si la configuration n'est pas accessible
                self.matricule = f"EL{str(uuid.uuid4().int)[:8].upper()}"
        super().save(*args, **kwargs)
