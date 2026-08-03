"""
Utilitaire partagé — chemins de médias tenant-aware pour EducNet.

Chaque école possède son espace isolé :
    tenants/{schema_name}/{type}/{fichier}

Ce module est importé par tous les modèles Django qui définissent
des champs ImageField / FileField afin de centraliser la logique
de nommage et de garantir l'isolation des médias par école.
"""
from __future__ import annotations

import os
import uuid

from django.db import connection


# ─────────────────────────────────────────────────────────────────────────────
# Utilitaire de base
# ─────────────────────────────────────────────────────────────────────────────

def get_tenant_schema() -> str:
    """
    Retourne le schema_name du tenant courant.
    Renvoie 'public' en mode sans tenant (développement sans DB, tests, etc.).
    """
    try:
        schema = connection.tenant.schema_name
        return schema or 'public'
    except AttributeError:
        return 'public'


def _ext(filename: str) -> str:
    """Extrait l'extension en minuscules, ex. '.jpg'."""
    _, raw_ext = os.path.splitext(filename)
    return raw_ext.lower() or '.bin'


def _uid() -> str:
    """UUID court (16 caractères hex)."""
    return uuid.uuid4().hex[:16]
