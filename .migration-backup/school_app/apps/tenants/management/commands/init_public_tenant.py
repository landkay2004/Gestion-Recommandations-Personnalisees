"""
Crée le tenant public (schema_name='public') si il n'existe pas.
Ce tenant est requis par SessionTenantMiddleware pour appeler
connection.set_tenant(public_tenant) au lieu de set_schema_to_public().

À exécuter une seule fois après la première migrate_schemas.
"""
import os
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Initialise le tenant public (schema_name='public') pour django-tenants."

    def handle(self, *args, **options):
        # Ne rien faire en mode SQLite
        if 'sqlite' in connection.settings_dict.get('ENGINE', ''):
            self.stdout.write("Mode SQLite détecté — init_public_tenant ignoré.")
            return

        from django.db import transaction
        from tenants.models import Ecole, EcoleDomain

        # S'assurer d'être dans le schéma public
        try:
            connection.set_schema_to_public()
        except Exception:
            pass

        with transaction.atomic():
            try:
                ecole = Ecole.objects.get(schema_name='public')
                self.stdout.write("Tenant public déjà existant — aucune action.")
                created = False
            except Ecole.DoesNotExist:
                # Créer l'instance sans passer auto_create_schema (ce n'est pas
                # un champ DB) et le désactiver sur l'instance avant le save()
                # pour éviter que django-tenants tente de recréer le schéma
                # public (qui existe déjà en PostgreSQL).
                ecole = Ecole(
                    schema_name='public',
                    nom='Plateforme SGN',
                    contact_email='admin@sgn.local',
                    contact_nom='Super Admin',
                    statut='active',
                    onboarding_complete=True,
                )
                ecole.auto_create_schema = False  # attribut d'instance, non-DB
                ecole.save()
                created = True
                self.stdout.write(self.style.SUCCESS(
                    "Tenant public créé (schema_name='public')."
                ))

            # Créer un domaine par défaut si absent
            domain = os.environ.get('REPLIT_DEV_DOMAIN', '') or \
                     os.environ.get('DJANGO_SITE_URL', '').replace('https://', '').replace('http://', '') or \
                     'localhost'
            # Garder seulement le hostname (sans chemin ni port)
            domain = domain.split('/')[0].split(':')[0] or 'localhost'

            if not EcoleDomain.objects.filter(tenant=ecole).exists():
                EcoleDomain.objects.create(
                    domain=domain,
                    tenant=ecole,
                    is_primary=True,
                )
                self.stdout.write("Domaine '%s' associé au tenant public." % domain)
