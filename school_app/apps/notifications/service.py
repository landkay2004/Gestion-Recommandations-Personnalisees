"""
Service central de notifications SGN.

Usage :
    from notifications.service import notify, notify_tous_enseignants, notify_prefets

    notify(user, "Titre", "Description", categorie='ADMIN', priorite='SUCCES',
           type_notif='COMPTE_CREE', lien='/login/users/')
"""
from django.db import transaction


def notify(destinataires, titre, description='', categorie='SYSTEME', priorite='INFO',
           type_notif='SYSTEME', lien='', expediteur=None, annee=None):
    """
    Crée une notification pour chaque destinataire.

    `destinataires` peut être :
      - un utilisateur unique (CustomUser instance)
      - une liste / queryset d'utilisateurs
    """
    from .models import Notification

    if destinataires is None:
        return

    # Normaliser en liste
    if hasattr(destinataires, 'pk'):          # single user
        users = [destinataires]
    elif hasattr(destinataires, 'iterator'): # queryset
        users = list(destinataires)
    else:
        users = list(destinataires)

    if not users:
        return

    notifs = [
        Notification(
            destinataire=u,
            expediteur=expediteur,
            titre=titre,
            description=description,
            categorie=categorie,
            priorite=priorite,
            type_notif=type_notif,
            lien=lien,
            annee_scolaire=annee,
        )
        for u in users
    ]
    try:
        with transaction.atomic():
            Notification.objects.bulk_create(notifs, ignore_conflicts=True)
    except Exception:
        pass  # Les notifications ne doivent jamais bloquer le flux principal


# ── Raccourcis ────────────────────────────────────────────────────────────────

def notify_tous_enseignants(titre, description='', categorie='SCOLAIRE', priorite='INFO',
                             type_notif='SYSTEME', lien='', expediteur=None, annee=None):
    from accounts.models import CustomUser
    teachers = CustomUser.objects.filter(role='enseignant', is_active=True)
    notify(teachers, titre, description, categorie, priorite, type_notif, lien, expediteur, annee)


def notify_prefets(titre, description='', categorie='ADMIN', priorite='INFO',
                   type_notif='SYSTEME', lien='', expediteur=None, annee=None):
    from accounts.models import CustomUser
    prefets = CustomUser.objects.filter(role='prefet', is_active=True)
    notify(prefets, titre, description, categorie, priorite, type_notif, lien, expediteur, annee)


def notify_tous(titre, description='', categorie='SYSTEME', priorite='INFO',
                type_notif='SYSTEME', lien='', expediteur=None, annee=None):
    from accounts.models import CustomUser
    users = CustomUser.objects.filter(is_active=True)
    notify(users, titre, description, categorie, priorite, type_notif, lien, expediteur, annee)
