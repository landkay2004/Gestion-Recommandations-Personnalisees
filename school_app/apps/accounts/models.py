import secrets
import string
import re

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


def generate_temp_password(length=12):
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


class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('admin_ecole', "Administrateur d'ecole"),
        ('prefet',      'Prefet des etudes'),
        ('enseignant',  'Enseignant'),
    ]
    role = models.CharField(
        max_length=20, choices=ROLE_CHOICES, default='enseignant', db_index=True
    )
    telephone = models.CharField("Telephone", max_length=20, blank=True)
    must_change_password = models.BooleanField(
        "Doit changer le mot de passe", default=False,
        help_text="Oblige la personne a changer son mot de passe a la prochaine connexion.",
    )
    photo_profil = models.ImageField(
        "Photo de profil", upload_to='profils/', blank=True, null=True,
    )
    bio = models.TextField("Biographie / Note", blank=True, default='')

    def is_admin_ecole(self):
        return self.role == 'admin_ecole'

    def is_prefet(self):
        return self.role in ('prefet', 'admin_ecole')

    def is_enseignant(self):
        return self.role == 'enseignant'

    def get_initiales(self):
        parts = self.get_full_name().split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        if parts:
            return parts[0][:2].upper()
        return self.username[:2].upper()

    def __str__(self):
        return "%s (%s)" % (
            self.get_full_name() or self.email or self.username,
            self.get_role_display()
        )


@receiver(user_logged_in)
def disable_last_login_update(sender, user, request, **kwargs):
    """Évite la mise à jour de last_login dans le schéma public lors d'un login multi-tenant."""
    return None
