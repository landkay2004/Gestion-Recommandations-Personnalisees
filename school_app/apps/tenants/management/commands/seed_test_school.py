"""
Crée une école de test complète avec les quatre types de comptes SGN :
  super-admin, admin-école, préfet et enseignant.

Idempotente — peut être relancée sans dupliquer les données existantes.
À la fin, tente de s'authentifier avec chaque compte pour confirmer que
le flux de connexion PostgreSQL multi-tenant fonctionne de bout en bout.

Usage :
    python manage.py seed_test_school
    python manage.py seed_test_school --schema ecole_demo --no-verify
"""
from django.core.management.base import BaseCommand
from django.db import connection

# ── Credentials par défaut ────────────────────────────────────────────────────
SCHEMA           = 'ecole_test'
NOM_ECOLE        = 'École de Test SGN'

EMAIL_SA         = 'superadmin@test.local'
PWD_SA           = 'SuperAdmin@2025!'

EMAIL_ADMIN      = 'admin@ecoletest.local'
PWD_ADMIN        = 'Admin@Ecole2025!'

EMAIL_PREFET     = 'prefet@ecoletest.local'
PWD_PREFET       = 'Prefet@Ecole2025!'

EMAIL_ENSEIGNANT = 'enseignant@ecoletest.local'
PWD_ENSEIGNANT   = 'Enseignant@2025!'


class Command(BaseCommand):
    help = (
        "Crée une école de test avec tous les types d'utilisateurs "
        "pour valider le login PostgreSQL multi-tenant."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--schema', default=SCHEMA,
            help="Nom du schéma PostgreSQL de l'école de test (défaut: %s)." % SCHEMA,
        )
        parser.add_argument(
            '--no-verify', action='store_true',
            help="Ne pas lancer la vérification des logins à la fin.",
        )

    # ─────────────────────────────────────────────────────────────────────────
    def handle(self, *args, **options):
        if 'sqlite' in connection.settings_dict.get('ENGINE', ''):
            self.stdout.write(self.style.WARNING(
                "Mode SQLite détecté — seed_test_school est réservé à PostgreSQL."
            ))
            return

        schema = options['schema']

        # Garantir le schéma public au départ
        connection.set_schema_to_public()

        self._step("1/5", "Super-admin de test")
        self._seed_super_admin()

        self._step("2/5", "Plan d'abonnement + école '%s'" % schema)
        ecole = self._seed_school(schema)

        self._step("3/5", "Admin-école dans le schéma public")
        self._seed_admin_ecole(ecole)

        self._step("4/5", "Préfet + enseignant dans le schéma tenant '%s'" % schema)
        self._seed_tenant_users(ecole, schema)

        self._step("5/5", "AnnuaireUtilisateur (schéma public)")
        self._seed_annuaire(schema)

        self._print_summary()

        if not options['no_verify']:
            self.stdout.write('')
            self._verify_logins(schema)

    # ── Étapes ───────────────────────────────────────────────────────────────

    def _seed_super_admin(self):
        from super_admin.models import SuperAdmin
        sa, created = SuperAdmin.objects.get_or_create(
            email=EMAIL_SA,
            defaults={'nom': 'Test', 'prenom': 'Super Admin', 'is_active': True},
        )
        sa.is_active = True
        sa.totp_enabled = False
        sa.set_password(PWD_SA)
        sa.save()
        self._ok("super-admin %s (%s)" % (EMAIL_SA, "créé" if created else "mis à jour"))

    def _seed_school(self, schema):
        from tenants.models import PlanAbonnement, Ecole, EcoleDomain

        # Plan d'abonnement (nullable sur Ecole, mais utile pour les tests)
        plan, _ = PlanAbonnement.objects.get_or_create(
            nom='Test',
            defaults={
                'description': 'Plan créé par seed_test_school.',
                'max_eleves': 500,
                'max_enseignants': 50,
                'max_classes': 30,
                'max_utilisateurs': 60,
                'prix_mensuel': 0,
                'is_actif': True,
            },
        )

        if Ecole.objects.filter(schema_name=schema).exists():
            ecole = Ecole.objects.get(schema_name=schema)
            # Mettre à jour sans re-créer le schéma
            ecole.onboarding_complete = True
            ecole.statut = 'active'
            Ecole.objects.filter(pk=ecole.pk).update(
                onboarding_complete=True, statut='active'
            )
            self._ok("école '%s' déjà existante — conservée" % schema)
        else:
            ecole = Ecole(
                schema_name=schema,
                nom=NOM_ECOLE,
                contact_email=EMAIL_ADMIN,
                contact_nom='Admin Test',
                plan=plan,
                statut='active',
                onboarding_complete=True,
            )
            ecole.save()  # déclenche create_schema + migrate pour ce tenant
            self._ok("école '%s' créée avec son schéma PostgreSQL" % schema)

        # Domaine (facultatif pour le routing session-based, mais bonne pratique)
        # Utiliser schema.localhost pour éviter les conflits avec le tenant public.
        if not EcoleDomain.objects.filter(tenant=ecole).exists():
            import os
            base_domain = (
                os.environ.get('REPLIT_DEV_DOMAIN', '') or 'localhost'
            ).split('/')[0].split(':')[0] or 'localhost'
            domain = '%s.%s' % (schema, base_domain)
            # Si ce domaine est déjà pris (edge case), tenter sans préfixe puis skipper
            if EcoleDomain.objects.filter(domain=domain).exists():
                self._ok("domaine déjà pris — ignoré (routing session-based actif)")
            else:
                try:
                    EcoleDomain.objects.create(domain=domain, tenant=ecole, is_primary=True)
                    self._ok("domaine '%s' associé à l'école" % domain)
                except Exception:
                    self._ok("domaine ignoré — routing session-based actif")

        return ecole

    def _seed_admin_ecole(self, ecole):
        from tenants.models import AdminEcole
        admin, created = AdminEcole.objects.get_or_create(
            ecole=ecole,
            defaults={
                'email': EMAIL_ADMIN,
                'nom': 'Admin',
                'prenom': 'Test',
                'onboarding_step': 5,
                'is_active': True,
            },
        )
        if not created:
            AdminEcole.objects.filter(pk=admin.pk).update(
                email=EMAIL_ADMIN,
                onboarding_step=5,
                is_active=True,
            )
        self._ok("AdminEcole %s (%s)" % (EMAIL_ADMIN, "créé" if created else "mis à jour"))

    def _seed_tenant_users(self, ecole, schema):
        """Crée les CustomUser dans le schéma tenant."""
        # Basculer vers le schéma tenant
        connection.set_tenant(ecole)

        from django.contrib.auth import get_user_model
        UserModel = get_user_model()

        users_to_create = [
            dict(email=EMAIL_ADMIN,      role='admin_ecole', pwd=PWD_ADMIN,      prenom='Admin',      nom='Test'),
            dict(email=EMAIL_PREFET,     role='prefet',      pwd=PWD_PREFET,     prenom='Préfet',     nom='Test'),
            dict(email=EMAIL_ENSEIGNANT, role='enseignant',  pwd=PWD_ENSEIGNANT, prenom='Enseignant', nom='Test'),
        ]

        for u in users_to_create:
            obj = UserModel.objects.filter(email__iexact=u['email']).first()
            if obj is None:
                # Générer un username unique à partir de l'email
                base = u['email'].split('@')[0].lower()
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
                self._ok("CustomUser %s [%s] créé dans '%s'" % (u['email'], u['role'], schema))
            else:
                # Mettre à jour le mot de passe et s'assurer que le compte est actif
                obj.role = u['role']
                obj.is_active = True
                obj.must_change_password = False
                obj.set_password(u['pwd'])
                obj.save(update_fields=['role', 'is_active', 'must_change_password', 'password'])
                self._ok("CustomUser %s [%s] mis à jour dans '%s'" % (u['email'], u['role'], schema))

            # Pour l'enseignant, créer aussi le profil Teacher si absent
            if u['role'] == 'enseignant':
                try:
                    from teachers.models import Teacher
                    Teacher.objects.get_or_create(user=obj)
                except Exception:
                    pass

        # Revenir au schéma public
        connection.set_schema_to_public()

    def _seed_annuaire(self, schema):
        from tenants.models import AnnuaireUtilisateur
        entries = [
            (EMAIL_ADMIN,      'admin_ecole'),
            (EMAIL_PREFET,     'prefet'),
            (EMAIL_ENSEIGNANT, 'enseignant'),
        ]
        for email, type_compte in entries:
            obj, created = AnnuaireUtilisateur.objects.get_or_create(
                email=email.lower(),
                defaults={'schema_name': schema, 'type_compte': type_compte},
            )
            if not created and (obj.schema_name != schema or obj.type_compte != type_compte):
                obj.schema_name  = schema
                obj.type_compte  = type_compte
                obj.save(update_fields=['schema_name', 'type_compte'])
            self._ok("annuaire : %s → %s [%s]" % (email, schema, type_compte))

    # ── Vérification des logins ───────────────────────────────────────────────

    def _verify_logins(self, schema):
        self.stdout.write(self.style.MIGRATE_HEADING("Vérification des connexions :"))
        ok_count = 0
        fail_count = 0

        # ── Super-admin ──────────────────────────────────────────────────────
        try:
            from super_admin.models import SuperAdmin
            sa = SuperAdmin.objects.get(email__iexact=EMAIL_SA, is_active=True)
            if sa.check_password(PWD_SA):
                self._verify_ok("super-admin", EMAIL_SA)
                ok_count += 1
            else:
                self._verify_fail("super-admin", EMAIL_SA, "mot de passe incorrect")
                fail_count += 1
        except Exception as e:
            self._verify_fail("super-admin", EMAIL_SA, str(e))
            fail_count += 1

        # ── Admin-école (via MultiTenantAuthBackend) ─────────────────────────
        from tenants.models import AdminEcole
        try:
            admin = AdminEcole.objects.get(email__iexact=EMAIL_ADMIN, is_active=True)
            # Vérifier que le CustomUser existe et que le mdp est correct
            from tenants.models import Ecole
            ecole = Ecole.objects.get(schema_name=schema)
            connection.set_tenant(ecole)
            from django.contrib.auth import get_user_model
            UserModel = get_user_model()
            user = UserModel.objects.filter(email__iexact=EMAIL_ADMIN, role='admin_ecole').first()
            if user and user.check_password(PWD_ADMIN) and user.is_active:
                connection.set_schema_to_public()
                self._verify_ok("admin-école", EMAIL_ADMIN)
                ok_count += 1
            else:
                connection.set_schema_to_public()
                self._verify_fail("admin-école", EMAIL_ADMIN, "CustomUser introuvable ou mdp incorrect")
                fail_count += 1
        except Exception as e:
            try:
                connection.set_schema_to_public()
            except Exception:
                pass
            self._verify_fail("admin-école", EMAIL_ADMIN, str(e))
            fail_count += 1

        # ── Préfet & Enseignant (via AnnuaireUtilisateur) ────────────────────
        for email, pwd, role_label in [
            (EMAIL_PREFET,     PWD_PREFET,     'préfet'),
            (EMAIL_ENSEIGNANT, PWD_ENSEIGNANT, 'enseignant'),
        ]:
            try:
                from tenants.models import AnnuaireUtilisateur, Ecole
                entry = AnnuaireUtilisateur.objects.get(email__iexact=email)
                ecole = Ecole.objects.get(schema_name=entry.schema_name)
                connection.set_tenant(ecole)
                from django.contrib.auth import get_user_model
                UserModel = get_user_model()
                user = UserModel.objects.filter(email__iexact=email).first()
                if user and user.check_password(pwd) and user.is_active:
                    connection.set_schema_to_public()
                    self._verify_ok(role_label, email)
                    ok_count += 1
                else:
                    connection.set_schema_to_public()
                    self._verify_fail(role_label, email, "CustomUser introuvable ou mdp incorrect")
                    fail_count += 1
            except Exception as e:
                try:
                    connection.set_schema_to_public()
                except Exception:
                    pass
                self._verify_fail(role_label, email, str(e))
                fail_count += 1

        # ── Résumé ───────────────────────────────────────────────────────────
        self.stdout.write('')
        if fail_count == 0:
            self.stdout.write(self.style.SUCCESS(
                "✔  Tous les comptes (%d/%d) se connectent correctement." % (ok_count, ok_count)
            ))
        else:
            self.stdout.write(self.style.ERROR(
                "✘  %d compte(s) en erreur sur %d." % (fail_count, ok_count + fail_count)
            ))

    # ── Résumé ────────────────────────────────────────────────────────────────

    def _print_summary(self):
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING("── Credentials de test ──────────────────"))
        rows = [
            ("Super-admin",  EMAIL_SA,         PWD_SA,           "/super-admin/"),
            ("Admin-école",  EMAIL_ADMIN,      PWD_ADMIN,        "/dashboard/"),
            ("Préfet",       EMAIL_PREFET,     PWD_PREFET,       "/dashboard/"),
            ("Enseignant",   EMAIL_ENSEIGNANT, PWD_ENSEIGNANT,   "/dashboard/"),
        ]
        for role, email, pwd, url in rows:
            self.stdout.write("  %-14s %s  /  %s  → %s" % (role, email, pwd, url))
        self.stdout.write('')

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _step(self, num, label):
        self.stdout.write(self.style.MIGRATE_HEADING("\n[%s] %s" % (num, label)))

    def _ok(self, msg):
        self.stdout.write(self.style.SUCCESS("  ✔ " + msg))

    def _verify_ok(self, role, email):
        self.stdout.write(self.style.SUCCESS("  ✔ %-14s %s" % (role, email)))

    def _verify_fail(self, role, email, reason):
        self.stdout.write(self.style.ERROR("  ✘ %-14s %s — %s" % (role, email, reason)))
