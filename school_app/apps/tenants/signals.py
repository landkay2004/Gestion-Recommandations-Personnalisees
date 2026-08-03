"""
Signaux pour l'app tenants — EducNet.

• Création automatique des sous-dossiers médias d'une école lors de son
  inscription (mode stockage local).
• En mode Cloudinary, les dossiers distants sont créés automatiquement
  au premier upload — aucune action n'est nécessaire.
"""
from __future__ import annotations

import logging
import os

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger('sgn.tenants')


@receiver(post_save, sender='tenants.Ecole')
def initialiser_dossiers_media_ecole(sender, instance, created, **kwargs):
    """
    À la création d'une école, initialise l'arborescence médias tenant-aware.

    Stockage local uniquement — Cloudinary crée ses répertoires à la demande.
    """
    if not created:
        return

    schema = instance.schema_name

    # Cloudinary gère les dossiers dynamiquement
    storage_backend = getattr(settings, 'DEFAULT_FILE_STORAGE', '')
    if 'cloudinary' in storage_backend.lower():
        logger.info(
            '[tenants] École "%s" (schema=%s) créée — Cloudinary actif, '
            'dossiers distants générés au premier upload.',
            instance.nom, schema,
        )
        return

    media_root = settings.MEDIA_ROOT

    sous_dossiers = [
        f'tenants/{schema}/students',
        f'tenants/{schema}/profils',
        f'tenants/{schema}/school',
        f'tenants/{schema}/cartes',
        f'tenants/{schema}/portail',
        f'tenants/{schema}/documents',
    ]

    created_dirs = []
    for dossier in sous_dossiers:
        chemin = os.path.join(media_root, dossier)
        try:
            os.makedirs(chemin, exist_ok=True)
            created_dirs.append(dossier)
        except OSError as exc:
            logger.warning(
                '[tenants] Impossible de créer le dossier %s : %s', chemin, exc
            )

    if created_dirs:
        logger.info(
            '[tenants] Dossiers médias créés pour l\'école "%s" (schema=%s) : %s',
            instance.nom, schema, ', '.join(created_dirs),
        )
