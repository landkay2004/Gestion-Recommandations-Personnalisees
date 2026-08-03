from django.core.management.base import BaseCommand
from django.db import transaction

from super_admin.models import SuperAdmin
from tenants.models import PlanAbonnement


class Command(BaseCommand):
    help = "Crée ou met à jour les données minimales de démonstration de la plateforme."

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            default="superadmin@test.local",
            help="Adresse du compte super-admin de test.",
        )
        parser.add_argument(
            "--password",
            default="SuperAdmin@2025!",
            help="Mot de passe du compte super-admin de test.",
        )
        parser.add_argument(
            "--skip-plan",
            action="store_true",
            help="Ne pas créer le plan d'abonnement de démonstration.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        password = options["password"]

        admin, created = SuperAdmin.objects.get_or_create(
            email=email,
            defaults={
                "nom": "Plateforme",
                "prenom": "Super Admin",
                "is_active": True,
            },
        )
        admin.nom = admin.nom or "Plateforme"
        admin.prenom = admin.prenom or "Super Admin"
        admin.is_active = True
        admin.set_password(password)
        admin.save()

        plan = None
        if not options["skip_plan"]:
            plan, _ = PlanAbonnement.objects.get_or_create(
                nom="Démonstration",
                defaults={
                    "description": "Plan de test pour vérifier le flux de création d'une école.",
                    "max_eleves": 150,
                    "max_enseignants": 30,
                    "max_classes": 15,
                    "max_utilisateurs": 35,
                    "prix_mensuel": 0,
                    "is_actif": True,
                },
            )

        state = "créé" if created else "mis à jour"
        self.stdout.write(self.style.SUCCESS(
            "Super-admin de test %s : %s" % (state, email)
        ))
        self.stdout.write("Mot de passe de test : %s" % password)
        if plan:
            self.stdout.write("Plan disponible : %s" % plan.nom)