"""
Crée ou met à jour les comptes utilisateurs de test pour le mode SQLite
(développement local sans multi-tenant PostgreSQL).

Usage :
    python manage.py seed_sqlite_users
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Crée les comptes utilisateurs de test en mode SQLite."

    def handle(self, *args, **options):
        if 'postgresql' in connection.settings_dict.get('ENGINE', '').lower():
            self.stdout.write(self.style.WARNING(
                "Mode PostgreSQL détecté — utilisez seed_test_school à la place."
            ))
            return

        from django.contrib.auth import get_user_model
        UserModel = get_user_model()

        users = [
            dict(email='admin@ecoletest.local',       role='admin_ecole',  pwd='Admin@Ecole2025!',    prenom='Admin',       nom='Test'),
            dict(email='prefet@ecoletest.local',       role='prefet',       pwd='Prefet@Ecole2025!',   prenom='Préfet',      nom='Test'),
            dict(email='enseignant@ecoletest.local',   role='enseignant',   pwd='Enseignant@2025!',    prenom='Enseignant',  nom='Test'),
            dict(email='secretariat@ecoletest.local',  role='secretariat',  pwd='Secretariat@2025!',   prenom='Secrétariat', nom='Test'),
        ]

        for u in users:
            base = u['email'].split('@')[0].lower()
            obj = UserModel.objects.filter(email__iexact=u['email']).first()
            if obj is None:
                username = base
                suffix = 1
                while UserModel.objects.filter(username=username).exists():
                    username = '%s%d' % (base, suffix)
                    suffix += 1
                obj = UserModel(
                    email=u['email'],
                    username=username,
                    first_name=u['prenom'],
                    last_name=u['nom'],
                    role=u['role'],
                    must_change_password=False,
                    is_active=True,
                )
                obj.set_password(u['pwd'])
                obj.save()
                self.stdout.write(self.style.SUCCESS(
                    "  ✔ Créé : %s [%s]" % (u['email'], u['role'])
                ))
            else:
                obj.role = u['role']
                obj.is_active = True
                obj.must_change_password = False
                obj.set_password(u['pwd'])
                obj.save(update_fields=['role', 'is_active', 'must_change_password', 'password'])
                self.stdout.write(self.style.SUCCESS(
                    "  ✔ Mis à jour : %s [%s]" % (u['email'], u['role'])
                ))

            # Créer le profil Teacher pour l'enseignant
            if u['role'] == 'enseignant':
                try:
                    from teachers.models import Teacher
                    Teacher.objects.get_or_create(user=obj)
                except Exception:
                    pass

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING("── Credentials SQLite ────────────────────"))
        rows = [
            ("Admin-école",  "admin@ecoletest.local",       "Admin@Ecole2025!"),
            ("Préfet",       "prefet@ecoletest.local",      "Prefet@Ecole2025!"),
            ("Enseignant",   "enseignant@ecoletest.local",  "Enseignant@2025!"),
            ("Secrétariat",  "secretariat@ecoletest.local", "Secretariat@2025!"),
        ]
        for role, email, pwd in rows:
            self.stdout.write("  %-14s %s  /  %s" % (role, email, pwd))
        self.stdout.write('')
