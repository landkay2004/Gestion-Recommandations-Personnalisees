from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='students.Student')
def create_portail_acces(sender, instance, created, **kwargs):
    """Crée automatiquement un accès portail lors de la création d'un élève."""
    if created:
        from .models import PortailAcces
        PortailAcces.objects.get_or_create(eleve=instance)
