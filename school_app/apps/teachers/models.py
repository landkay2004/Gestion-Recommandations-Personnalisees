from django.db import models
from accounts.models import CustomUser


class Teacher(models.Model):
    GENRE_CHOICES = [
        ('M', 'Masculin'),
        ('F', 'Féminin'),
    ]

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='teacher_profile')
    postnom = models.CharField('Post-nom', max_length=100, blank=True)
    genre = models.CharField('Genre', max_length=1, choices=GENRE_CHOICES, blank=True)
    telephone = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ['user__last_name', 'user__first_name']
        verbose_name = "Enseignant"
        verbose_name_plural = "Enseignants"

    def __str__(self):
        return self.nom_complet

    @property
    def nom_complet(self):
        parts = [self.user.first_name, self.postnom, self.user.last_name]
        full = ' '.join(p for p in parts if p)
        return full or self.user.username

    @property
    def email(self):
        return self.user.email

    @property
    def classes_enseignees(self):
        from subjects.models import MatiereClasse
        return MatiereClasse.objects.filter(enseignant=self).select_related('classe', 'matiere')
