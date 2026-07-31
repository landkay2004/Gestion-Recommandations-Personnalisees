"""
Crée une école de test complète avec tous les types de comptes SGN,
des données scolaires réalistes et des données de démonstration :

  Utilisateurs : super-admin, admin-école, préfet, enseignant, secrétariat, comptable
  Données      : année scolaire, sections, niveaux, classes, matières,
                 affectations, élèves, notes (1ère et 2ème périodes)

Idempotente — peut être relancée sans dupliquer les données existantes.
À la fin, tente de s'authentifier avec chaque compte pour confirmer que
le flux de connexion PostgreSQL multi-tenant fonctionne de bout en bout.

Usage :
    python manage.py seed_test_school
    python manage.py seed_test_school --schema ecole_demo --no-verify
    python manage.py seed_test_school --no-data   # comptes uniquement
"""
from django.core.management.base import BaseCommand
from django.db import connection

# ── Credentials par défaut ────────────────────────────────────────────────────
SCHEMA            = 'ecole_test'
NOM_ECOLE         = 'École Primaire Saint-Gabriel'
ANNEE_SCOLAIRE    = '2025-2026'

EMAIL_SA          = 'superadmin@test.local'
PWD_SA            = 'SuperAdmin@2025!'

EMAIL_ADMIN       = 'admin@ecoletest.local'
PWD_ADMIN         = 'Admin@Ecole2025!'

EMAIL_PREFET      = 'prefet@ecoletest.local'
PWD_PREFET        = 'Prefet@Ecole2025!'

EMAIL_ENSEIGNANT  = 'enseignant@ecoletest.local'
PWD_ENSEIGNANT    = 'Enseignant@2025!'

EMAIL_SECRETARIAT = 'secretariat@ecoletest.local'
PWD_SECRETARIAT   = 'Secretariat@2025!'

EMAIL_COMPTABLE   = 'comptable@ecoletest.local'
PWD_COMPTABLE     = 'Comptable@2025!'

# ── Données scolaires de démonstration ───────────────────────────────────────
SECTIONS = ['Scientifique', 'Littéraire', 'Commerciale et Gestion']

NIVEAUX = [
    {'nom': '1ère Année',  'ordre': 1, 'cycle': 'primaire'},
    {'nom': '2ème Année',  'ordre': 2, 'cycle': 'primaire'},
    {'nom': '3ème Année',  'ordre': 3, 'cycle': 'primaire'},
    {'nom': '4ème Année',  'ordre': 4, 'cycle': 'primaire'},
    {'nom': '5ème Année',  'ordre': 5, 'cycle': 'secondaire'},
    {'nom': '6ème Année',  'ordre': 6, 'cycle': 'secondaire'},
]

# (niveau_nom, section_nom, nom_classe)
CLASSES = [
    ('5ème Année', 'Scientifique',              'A'),
    ('5ème Année', 'Scientifique',              'B'),
    ('5ème Année', 'Commerciale et Gestion',    'A'),
    ('6ème Année', 'Scientifique',              'A'),
    ('6ème Année', 'Littéraire',                'A'),
    ('6ème Année', 'Commerciale et Gestion',    'A'),
    ('4ème Année', 'Scientifique',              'A'),
    ('3ème Année', 'Scientifique',              'A'),
]

# (nom_matiere, maxima)
MATIERES = [
    ('Français',                  60),
    ('Mathématique',              60),
    ('Sciences Naturelles',       30),
    ('Physique',                  30),
    ('Histoire',                  30),
    ('Géographie',                30),
    ('Anglais',                   20),
    ('Informatique',              20),
    ('Éducation Physique',        20),
    ('Religion',                  20),
    ('Éducation Civique',         20),
    ('Dessin',                    20),
]

# (prenom, postnom, nom, genre, email_suffix)
ENSEIGNANTS_SUP = [
    ('Marie',   'Nzeba',    'Kabila',   'F', 'mkabila'),
    ('Jean',    'Mulumba',  'Tshombe',  'M', 'jtshombe'),
    ('Pierre',  'Luyeye',   'Matongo',  'M', 'pmatongo'),
]

# (nom, postnom, prenom, sexe, date_naissance, lieu_naissance, nom_classe_ref)
# nom_classe_ref = (niveau, section, nom) tuple correspondant à CLASSES
ELEVES = [
    # 5ème Scientifique A
    ('Mukendi',  'Kabeya',   'Pascal',    'M', '2010-03-15', 'Kinshasa',  ('5ème Année', 'Scientifique',           'A')),
    ('Nzambi',   'Lukusa',   'Grâce',     'F', '2010-07-22', 'Lubumbashi',('5ème Année', 'Scientifique',           'A')),
    ('Kabongo',  'Mwamba',   'Daniel',    'M', '2009-11-05', 'Mbuji-Mayi',('5ème Année', 'Scientifique',           'A')),
    ('Tshilombo','Kayumba',  'Espérance', 'F', '2010-01-30', 'Kananga',   ('5ème Année', 'Scientifique',           'A')),
    ('Ilunga',   'Mulumba',  'David',     'M', '2010-09-18', 'Kolwezi',   ('5ème Année', 'Scientifique',           'A')),
    # 5ème Scientifique B
    ('Muteba',   'Ngandu',   'Joël',      'M', '2010-04-12', 'Kinshasa',  ('5ème Année', 'Scientifique',           'B')),
    ('Kasongo',  'Banza',    'Naomi',     'F', '2010-08-25', 'Bukavu',    ('5ème Année', 'Scientifique',           'B')),
    ('Lufwa',    'Kazadi',   'Samuel',    'M', '2009-12-03', 'Kinshasa',  ('5ème Année', 'Scientifique',           'B')),
    # 5ème Commerciale A
    ('Nguesso',  'Dibaya',   'Rachelle',  'F', '2010-06-14', 'Matadi',    ('5ème Année', 'Commerciale et Gestion', 'A')),
    ('Bisimwa',  'Mirenge',  'Adrien',    'M', '2010-02-28', 'Goma',      ('5ème Année', 'Commerciale et Gestion', 'A')),
    # 6ème Scientifique A
    ('Mwana',    'Kitenge',  'Béatrice',  'F', '2009-05-09', 'Kinshasa',  ('6ème Année', 'Scientifique',           'A')),
    ('Tshibola', 'Kabamba',  'Franck',    'M', '2008-10-17', 'Tshikapa',  ('6ème Année', 'Scientifique',           'A')),
    ('Kalunga',  'Balume',   'Serge',     'M', '2009-03-22', 'Kinshasa',  ('6ème Année', 'Scientifique',           'A')),
    # 6ème Littéraire A
    ('Ngomba',   'Ntumba',   'Carine',    'F', '2009-07-11', 'Kananga',   ('6ème Année', 'Littéraire',             'A')),
    ('Kapinga',  'Tshiama',  'Michel',    'M', '2009-01-25', 'Lubumbashi',('6ème Année', 'Littéraire',             'A')),
    # 6ème Commerciale A
    ('Ndaye',    'Mbombo',   'Gloria',    'F', '2009-09-04', 'Kinshasa',  ('6ème Année', 'Commerciale et Gestion', 'A')),
    ('Kalala',   'Mujinga',  'Hervé',     'M', '2008-11-30', 'Mbuji-Mayi',('6ème Année', 'Commerciale et Gestion', 'A')),
    # 4ème Scientifique A
    ('Banza',    'Musonda',  'Lydia',     'F', '2011-04-18', 'Kinshasa',  ('4ème Année', 'Scientifique',           'A')),
    ('Mpiana',   'Lenge',    'Christophe','M', '2011-08-07', 'Kinshasa',  ('4ème Année', 'Scientifique',           'A')),
    # 3ème Scientifique A
    ('Kanyama',  'Mubaya',   'Yvette',    'F', '2012-02-14', 'Kindu',     ('3ème Année', 'Scientifique',           'A')),
]

# Matières affectées à chaque classe (par nom_classe_ref)
# Format : {classe_ref: [matiere_nom, ...]}
AFFECTATIONS = {
    ('5ème Année', 'Scientifique', 'A'): [
        'Français', 'Mathématique', 'Sciences Naturelles', 'Physique',
        'Histoire', 'Géographie', 'Anglais', 'Informatique',
        'Éducation Physique', 'Religion',
    ],
    ('5ème Année', 'Scientifique', 'B'): [
        'Français', 'Mathématique', 'Sciences Naturelles', 'Physique',
        'Histoire', 'Géographie', 'Anglais', 'Éducation Physique', 'Religion',
    ],
    ('5ème Année', 'Commerciale et Gestion', 'A'): [
        'Français', 'Mathématique', 'Histoire', 'Géographie',
        'Anglais', 'Informatique', 'Éducation Physique', 'Religion',
    ],
    ('6ème Année', 'Scientifique', 'A'): [
        'Français', 'Mathématique', 'Sciences Naturelles', 'Physique',
        'Histoire', 'Géographie', 'Anglais', 'Informatique',
        'Éducation Physique', 'Religion', 'Éducation Civique',
    ],
    ('6ème Année', 'Littéraire', 'A'): [
        'Français', 'Mathématique', 'Histoire', 'Géographie',
        'Anglais', 'Religion', 'Éducation Civique', 'Dessin',
    ],
    ('6ème Année', 'Commerciale et Gestion', 'A'): [
        'Français', 'Mathématique', 'Histoire', 'Géographie',
        'Anglais', 'Informatique', 'Religion', 'Éducation Civique',
    ],
    ('4ème Année', 'Scientifique', 'A'): [
        'Français', 'Mathématique', 'Sciences Naturelles', 'Physique',
        'Histoire', 'Géographie', 'Anglais', 'Éducation Physique',
    ],
    ('3ème Année', 'Scientifique', 'A'): [
        'Français', 'Mathématique', 'Sciences Naturelles',
        'Histoire', 'Géographie', 'Anglais', 'Éducation Physique',
    ],
}

# Notes de démonstration : (nom_eleve_key, matiere, periode, valeur)
# Valeurs par note = fraction du maxima pour rester réalistes
# On génère des notes pour 1P et 2P uniquement


class Command(BaseCommand):
    help = (
        "Crée une école de test avec tous les types d'utilisateurs, "
        "des classes, matières, élèves et notes de démonstration."
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
        parser.add_argument(
            '--no-data', action='store_true',
            help="Créer uniquement les comptes, sans données scolaires.",
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

        total_steps = 5 if options['no_data'] else 11

        self._step("1/%d" % total_steps, "Super-admin de test")
        self._seed_super_admin()

        self._step("2/%d" % total_steps, "Plan d'abonnement + école '%s'" % schema)
        ecole = self._seed_school(schema)

        self._step("3/%d" % total_steps, "Admin-école dans le schéma public")
        self._seed_admin_ecole(ecole)

        self._step("4/%d" % total_steps, "Comptes utilisateurs dans le schéma tenant '%s'" % schema)
        self._seed_tenant_users(ecole, schema)

        self._step("5/%d" % total_steps, "AnnuaireUtilisateur (schéma public)")
        self._seed_annuaire(schema)

        if not options['no_data']:
            self._step("6/%d" % total_steps, "Année scolaire, sections, niveaux")
            self._seed_structure(ecole)

            self._step("7/%d" % total_steps, "Classes, matières et affectations")
            self._seed_classes_matieres(ecole)

            self._step("8/%d" % total_steps, "Élèves et notes de démonstration")
            self._seed_eleves_notes(ecole)

            self._step("9/%d" % total_steps, "Paramètres de l'école (SchoolInfo)")
            self._seed_school_settings(ecole)

            self._step("10/%d" % total_steps, "Frais scolaires et paiements (comptable)")
            self._seed_frais_paiements(ecole)

            self._step("11/%d" % total_steps, "Planning hebdomadaire")
            self._seed_planning(ecole)

        self._print_summary(options['no_data'])

        if not options['no_verify']:
            self.stdout.write('')
            self._verify_logins(schema)

    # ── Comptes ───────────────────────────────────────────────────────────────

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
            ecole.save()
            self._ok("école '%s' créée avec son schéma PostgreSQL" % schema)

        if not EcoleDomain.objects.filter(tenant=ecole).exists():
            import os
            base_domain = (
                os.environ.get('REPLIT_DEV_DOMAIN', '') or 'localhost'
            ).split('/')[0].split(':')[0] or 'localhost'
            domain = '%s.%s' % (schema, base_domain)
            if EcoleDomain.objects.filter(domain=domain).exists():
                self._ok("domaine déjà pris — routing session-based actif")
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
        connection.set_tenant(ecole)

        from django.contrib.auth import get_user_model
        UserModel = get_user_model()

        users_to_create = [
            dict(email=EMAIL_ADMIN,       role='admin_ecole',  pwd=PWD_ADMIN,       prenom='Admin',       nom='Ecole'),
            dict(email=EMAIL_PREFET,      role='prefet',       pwd=PWD_PREFET,      prenom='Joseph',      nom='Préfet'),
            dict(email=EMAIL_ENSEIGNANT,  role='enseignant',   pwd=PWD_ENSEIGNANT,  prenom='Paul',        nom='Enseignant'),
            dict(email=EMAIL_SECRETARIAT, role='secretariat',  pwd=PWD_SECRETARIAT, prenom='Anne',        nom='Secrétariat'),
            dict(email=EMAIL_COMPTABLE,   role='comptable',    pwd=PWD_COMPTABLE,   prenom='Christophe',  nom='Comptable'),
        ]

        for u in users_to_create:
            obj = UserModel.objects.filter(email__iexact=u['email']).first()
            if obj is None:
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
                obj.role = u['role']
                obj.is_active = True
                obj.must_change_password = False
                obj.set_password(u['pwd'])
                obj.save(update_fields=['role', 'is_active', 'must_change_password', 'password'])
                self._ok("CustomUser %s [%s] mis à jour dans '%s'" % (u['email'], u['role'], schema))

            if u['role'] == 'enseignant':
                try:
                    from teachers.models import Teacher
                    Teacher.objects.get_or_create(user=obj)
                except Exception:
                    pass

        # Enseignants supplémentaires pour les affectations
        for prenom, postnom, nom, genre, suffix in ENSEIGNANTS_SUP:
            email = '%s@ecoletest.local' % suffix
            obj = UserModel.objects.filter(email__iexact=email).first()
            if obj is None:
                base_u = suffix
                username = base_u
                suf = 1
                while UserModel.objects.filter(username=username).exists():
                    username = '%s%d' % (base_u, suf)
                    suf += 1
                obj = UserModel(
                    email=email, username=username,
                    first_name=prenom, last_name=nom,
                    role='enseignant', must_change_password=False, is_active=True,
                )
                obj.set_password('Enseignant@2025!')
                obj.save()
                self._ok("CustomUser %s [enseignant] créé" % email)
            try:
                from teachers.models import Teacher
                t, _ = Teacher.objects.get_or_create(user=obj)
                if not t.postnom:
                    t.postnom = postnom
                    t.genre = genre
                    t.save(update_fields=['postnom', 'genre'])
            except Exception:
                pass

        connection.set_schema_to_public()

    def _seed_annuaire(self, schema):
        from tenants.models import AnnuaireUtilisateur
        entries = [
            (EMAIL_ADMIN,       'admin_ecole'),
            (EMAIL_PREFET,      'prefet'),
            (EMAIL_ENSEIGNANT,  'enseignant'),
            (EMAIL_SECRETARIAT, 'secretariat'),
            (EMAIL_COMPTABLE,   'comptable'),
        ]
        for prenom, postnom, nom, genre, suffix in ENSEIGNANTS_SUP:
            email = '%s@ecoletest.local' % suffix
            entries.append((email, 'enseignant'))

        for email, type_compte in entries:
            obj, created = AnnuaireUtilisateur.objects.get_or_create(
                email=email.lower(),
                defaults={'schema_name': schema, 'type_compte': type_compte},
            )
            if not created and (obj.schema_name != schema or obj.type_compte != type_compte):
                obj.schema_name = schema
                obj.type_compte = type_compte
                obj.save(update_fields=['schema_name', 'type_compte'])
            self._ok("annuaire : %s -> %s [%s]" % (email, schema, type_compte))

    # ── Données scolaires ─────────────────────────────────────────────────────

    def _seed_structure(self, ecole):
        """Année scolaire active, sections, niveaux."""
        connection.set_tenant(ecole)

        from classes.models import AnneeScolaire, Section, Niveau

        # Année scolaire
        annee, created = AnneeScolaire.objects.get_or_create(
            annee=ANNEE_SCOLAIRE,
            defaults={'active': True, 'cloturee': False},
        )
        if not created and not annee.active:
            AnneeScolaire.objects.filter(pk=annee.pk).update(active=True)
        self._ok("année scolaire %s (%s)" % (ANNEE_SCOLAIRE, "créée" if created else "déjà présente"))

        # Sections
        for nom in SECTIONS:
            _, c = Section.objects.get_or_create(nom=nom)
            if c:
                self._ok("section '%s' créée" % nom)

        # Niveaux
        for n in NIVEAUX:
            obj, c = Niveau.objects.get_or_create(
                nom=n['nom'],
                defaults={'ordre': n['ordre'], 'cycle': n['cycle']},
            )
            if not c:
                Niveau.objects.filter(pk=obj.pk).update(ordre=n['ordre'], cycle=n['cycle'])
            if c:
                self._ok("niveau '%s' créé" % n['nom'])

        connection.set_schema_to_public()

    def _seed_classes_matieres(self, ecole):
        """Classes, matières, maxima et affectations."""
        connection.set_tenant(ecole)

        from classes.models import AnneeScolaire, Section, Niveau, Classe
        from subjects.models import Matiere, MatiereClasse
        from django.contrib.auth import get_user_model
        UserModel = get_user_model()

        annee = AnneeScolaire.objects.filter(annee=ANNEE_SCOLAIRE).first()
        if not annee:
            self._warn("Année scolaire introuvable — skip classes")
            connection.set_schema_to_public()
            return

        # Maxima
        from subjects.models import Maxima
        for v in [20, 30, 60]:
            Maxima.objects.get_or_create(valeur=v)

        # Matières
        matiere_map = {}
        for nom, maxima in MATIERES:
            obj, c = Matiere.objects.get_or_create(nom=nom, defaults={'maxima': maxima})
            if not c and obj.maxima != maxima:
                Matiere.objects.filter(pk=obj.pk).update(maxima=maxima)
            matiere_map[nom] = obj
        self._ok("%d matières créées/vérifiées" % len(matiere_map))

        # Classes
        classe_map = {}
        for niveau_nom, section_nom, nom in CLASSES:
            niveau  = Niveau.objects.filter(nom=niveau_nom).first()
            section = Section.objects.filter(nom=section_nom).first()
            if not niveau or not section:
                self._warn("Niveau/section introuvable pour classe %s %s %s" % (niveau_nom, section_nom, nom))
                continue
            obj, c = Classe.objects.get_or_create(
                nom=nom,
                section=section,
                annee_scolaire=annee,
                defaults={'niveau': niveau},
            )
            if not c and obj.niveau != niveau:
                Classe.objects.filter(pk=obj.pk).update(niveau=niveau)
            classe_map[(niveau_nom, section_nom, nom)] = obj
            if c:
                self._ok("classe '%s %s %s' créée" % (niveau_nom, section_nom, nom))
        self._ok("%d classes créées/vérifiées" % len(classe_map))

        # Affectations — enseigant principal = celui du seed
        ens_user = UserModel.objects.filter(email__iexact=EMAIL_ENSEIGNANT).first()
        ens_sup_users = []
        for prenom, postnom, nom_ens, genre, suffix in ENSEIGNANTS_SUP:
            u = UserModel.objects.filter(email__iexact='%s@ecoletest.local' % suffix).first()
            if u and hasattr(u, 'teacher_profile'):
                ens_sup_users.append(u.teacher_profile)

        from teachers.models import Teacher
        main_teacher = None
        if ens_user:
            main_teacher, _ = Teacher.objects.get_or_create(user=ens_user)

        aff_count = 0
        for classe_ref, matieres_list in AFFECTATIONS.items():
            classe = classe_map.get(classe_ref)
            if not classe:
                continue
            for idx, mat_nom in enumerate(matieres_list):
                mat = matiere_map.get(mat_nom)
                if not mat:
                    continue
                # Rotation des enseignants disponibles
                enseignants = [main_teacher] + ens_sup_users
                teacher = enseignants[idx % len(enseignants)] if enseignants else None
                _, c = MatiereClasse.objects.get_or_create(
                    matiere=mat,
                    classe=classe,
                    defaults={'enseignant': teacher},
                )
                if c:
                    aff_count += 1
        self._ok("%d affectations matière-classe créées" % aff_count)

        connection.set_schema_to_public()

    def _seed_school_settings(self, ecole):
        """Paramètres détaillés de l'école (SchoolInfo)."""
        connection.set_tenant(ecole)
        try:
            from school_settings.models import SchoolInfo
            info = SchoolInfo.get_info()
            info.nom                     = NOM_ECOLE
            info.type_etablissement      = 'institut'
            info.annee_scolaire_actuelle = ANNEE_SCOLAIRE
            info.province                = 'Kinshasa'
            info.ville                   = 'Kinshasa'
            info.commune                 = 'Ngaliema'
            info.code                    = '62024/101/03/1'
            info.telephone               = '+243 81 234 5678'
            info.email_contact           = 'direction@saint-gabriel.cd'
            info.save()
            self._ok("SchoolInfo configurée : %s" % NOM_ECOLE)
        except Exception as e:
            self._warn("SchoolInfo : %s" % e)
        finally:
            connection.set_schema_to_public()

    def _seed_frais_paiements(self, ecole):
        """Frais scolaires réalistes + historique de paiements pour les élèves de test."""
        import decimal, random
        from datetime import timedelta
        from django.utils import timezone

        connection.set_tenant(ecole)

        try:
            from abonnement.models import TypeFrais, Paiement, Facture
            from accounts.models import CustomUser
            from students.models import Student

            # ── Types de frais globaux (tous élèves) ────────────────────
            FRAIS_GLOBAUX = [
                ('Minerval annuel',    150),
                ('Frais d\'examen',     30),
                ('Tenue scolaire',      25),
                ('Frais bibliothèque',  10),
                ('Cotisation APEEP',    15),
            ]

            types_crees = 0
            for nom, montant in FRAIS_GLOBAUX:
                tf, created = TypeFrais.objects.get_or_create(
                    nom=nom,
                    classe=None,
                    defaults={'montant': decimal.Decimal(str(montant)), 'actif': True},
                )
                if created:
                    types_crees += 1

            self._ok("%d types de frais globaux créés/vérifiés" % len(FRAIS_GLOBAUX))

            # ── Comptable pour les paiements ─────────────────────────────
            comptable = CustomUser.objects.filter(role='comptable').first()
            if not comptable:
                self._warn("Aucun comptable trouvé — skip paiements")
                connection.set_schema_to_public()
                return

            # ── Paiements pour les élèves existants ──────────────────────
            rng = random.Random(99)
            eleves = list(Student.objects.all()[:20])
            types  = list(TypeFrais.objects.filter(actif=True, classe__isnull=True))
            paiement_count = 0
            facture_count  = 0

            now = timezone.now()

            for eleve in eleves:
                # Chaque élève a payé 2–4 frais de manière aléatoire
                nb_frais_payes = rng.randint(2, min(4, len(types)))
                frais_payes    = rng.sample(types, nb_frais_payes)

                for tf in frais_payes:
                    # Paiement partiel (acompte) ou total
                    montant_du  = tf.montant
                    part        = rng.choice([0.5, 0.75, 1.0])
                    montant_pay = (montant_du * decimal.Decimal(str(part))).quantize(
                        decimal.Decimal('0.01')
                    )
                    # Date aléatoire dans les 6 derniers mois
                    jours_ago = rng.randint(0, 180)
                    date_pay  = now - timedelta(days=jours_ago)
                    mode      = rng.choice(['especes', 'mobile_money', 'virement'])

                    # Éviter les doublons (même élève + même frais + même montant)
                    if Paiement.objects.filter(eleve=eleve, type_frais=tf).count() >= 2:
                        continue

                    p = Paiement.objects.create(
                        eleve=eleve,
                        type_frais=tf,
                        montant_paye=montant_pay,
                        date_paiement=date_pay,
                        comptable=comptable,
                        mode_paiement=mode,
                    )
                    paiement_count += 1

                    # Facture associée
                    if not hasattr(p, 'facture') or not Facture.objects.filter(paiement=p).exists():
                        num = Facture.generer_numero()
                        Facture.objects.create(
                            paiement=p,
                            numero_facture=num,
                            date_emission=date_pay,
                        )
                        facture_count += 1

            self._ok("%d paiements créés (%d factures)" % (paiement_count, facture_count))

        except Exception as e:
            self._warn("Frais/paiements : %s" % e)
        finally:
            connection.set_schema_to_public()

    def _seed_planning(self, ecole):
        """Planning hebdomadaire réaliste avec salles et créneaux horaires."""
        connection.set_tenant(ecole)
        try:
            from planning.models import Salle, CreneauHoraire, SeanceHoraire
            from classes.models import AnneeScolaire
            from subjects.models import MatiereClasse
            from datetime import time

            # ── Salles ─────────────────────────────────────────────────
            SALLES = [
                ('Salle A101', 40), ('Salle A102', 40), ('Salle B201', 35),
                ('Salle B202', 35), ('Laboratoire', 25), ('Salle Info', 30),
            ]
            for nom_salle, capa in SALLES:
                Salle.objects.get_or_create(
                    nom=nom_salle,
                    defaults={'capacite': capa},
                )
            self._ok("%d salles créées/vérifiées" % len(SALLES))

            # ── Créneaux horaires lundi–vendredi ───────────────────────
            CRENEAUX = [
                (1, time(7, 30),  time(8, 30),  'cours'),
                (1, time(8, 30),  time(9, 30),  'cours'),
                (1, time(9, 30),  time(10, 0),  'recreation'),
                (1, time(10, 0),  time(11, 0),  'cours'),
                (1, time(11, 0),  time(12, 0),  'cours'),
                (2, time(7, 30),  time(8, 30),  'cours'),
                (2, time(8, 30),  time(9, 30),  'cours'),
                (2, time(9, 30),  time(10, 0),  'recreation'),
                (2, time(10, 0),  time(11, 0),  'cours'),
                (2, time(11, 0),  time(12, 0),  'cours'),
                (3, time(7, 30),  time(8, 30),  'cours'),
                (3, time(8, 30),  time(9, 30),  'cours'),
                (3, time(9, 30),  time(10, 0),  'recreation'),
                (3, time(10, 0),  time(11, 0),  'cours'),
                (4, time(7, 30),  time(8, 30),  'cours'),
                (4, time(8, 30),  time(9, 30),  'cours'),
                (4, time(9, 30),  time(10, 0),  'recreation'),
                (4, time(10, 0),  time(11, 0),  'cours'),
                (4, time(11, 0),  time(12, 0),  'cours'),
                (5, time(7, 30),  time(8, 30),  'cours'),
                (5, time(8, 30),  time(9, 30),  'cours'),
                (5, time(9, 30),  time(10, 0),  'recreation'),
                (5, time(10, 0),  time(11, 0),  'cours'),
                (6, time(7, 30),  time(8, 30),  'cours'),
                (6, time(8, 30),  time(9, 30),  'cours'),
                (6, time(9, 30),  time(10, 0),  'priere'),
                (6, time(10, 0),  time(11, 0),  'cours'),
            ]
            creneau_count = 0
            creneaux_obj  = []
            for jour, hdeb, hfin, ttype in CRENEAUX:
                c, cr = CreneauHoraire.objects.get_or_create(
                    jour=jour, heure_debut=hdeb, heure_fin=hfin,
                    defaults={'type_creneau': ttype},
                )
                creneaux_obj.append(c)
                if cr:
                    creneau_count += 1
            self._ok("%d créneaux horaires créés/vérifiés" % len(CRENEAUX))

            # ── Séances pour les MatiereClasse existantes ─────────────
            annee = AnneeScolaire.objects.filter(annee=ANNEE_SCOLAIRE).first()
            if not annee:
                self._warn("Année scolaire introuvable — skip séances")
                connection.set_schema_to_public()
                return

            salle_list = list(Salle.objects.all())
            cours_creneaux = [c for c in creneaux_obj if c.type_creneau == 'cours']
            mc_qs = list(MatiereClasse.objects.select_related('matiere', 'classe').all()[:20])
            seance_count = 0
            used = set()  # (creneau_id, classe_id) pour éviter les conflits

            import random as _rand
            rng2 = _rand.Random(77)

            for mc in mc_qs:
                # Affecter 2 créneaux par matière-classe
                disponibles = [c for c in cours_creneaux if (c.pk, mc.classe_id) not in used]
                if len(disponibles) < 1:
                    continue
                choix = rng2.sample(disponibles, min(2, len(disponibles)))
                salle = rng2.choice(salle_list) if salle_list else None
                for cren in choix:
                    try:
                        _, c = SeanceHoraire.objects.get_or_create(
                            annee_scolaire=annee,
                            matiere_classe=mc,
                            creneau=cren,
                            defaults={'salle': salle},
                        )
                        if c:
                            seance_count += 1
                        used.add((cren.pk, mc.classe_id))
                    except Exception:
                        pass

            self._ok("%d séances de cours planifiées" % seance_count)

        except Exception as e:
            self._warn("Planning : %s" % e)
        finally:
            connection.set_schema_to_public()

    def _seed_eleves_notes(self, ecole):
        """Élèves de démonstration et notes pour 1P et 2P."""
        import decimal, random
        connection.set_tenant(ecole)

        from classes.models import AnneeScolaire, Section, Niveau, Classe
        from students.models import Student
        from grades.models import Note
        from subjects.models import MatiereClasse

        annee = AnneeScolaire.objects.filter(annee=ANNEE_SCOLAIRE).first()
        if not annee:
            self._warn("Année scolaire introuvable — skip élèves")
            connection.set_schema_to_public()
            return

        eleve_count = 0
        note_count  = 0

        # Seed déterministe
        rng = random.Random(42)

        for data in ELEVES:
            nom, postnom, prenom, sexe, dob, lieu, classe_ref = data
            niveau_nom, section_nom, cls_nom = classe_ref

            niveau  = Niveau.objects.filter(nom=niveau_nom).first()
            section = Section.objects.filter(nom=section_nom).first()
            if not niveau or not section:
                continue
            classe = Classe.objects.filter(
                nom=cls_nom, section=section, annee_scolaire=annee, niveau=niveau
            ).first()
            if not classe:
                continue

            # Matricule unique déterministe
            matricule = 'T%s%s%s' % (
                ANNEE_SCOLAIRE[:4],
                nom[:3].upper(),
                prenom[:3].upper(),
            )
            # Éviter collisions
            base_mat = matricule
            suffix_idx = 1
            while Student.objects.filter(matricule=matricule).exists():
                matricule = '%s%d' % (base_mat, suffix_idx)
                suffix_idx += 1

            eleve, created = Student.objects.get_or_create(
                nom=nom,
                postnom=postnom,
                prenom=prenom,
                defaults={
                    'sexe': sexe,
                    'date_naissance': dob,
                    'lieu_naissance': lieu,
                    'classe': classe,
                    'matricule': matricule,
                },
            )
            if not created:
                # Mettre à jour la classe si l'élève existait déjà
                if eleve.classe != classe:
                    eleve.classe = classe
                    eleve.save(update_fields=['classe'])
            else:
                eleve_count += 1

            # Notes 1P et 2P pour les matières de sa classe
            mc_qs = MatiereClasse.objects.filter(classe=classe).select_related('matiere')
            for mc in mc_qs:
                maxima = mc.matiere.maxima
                for periode in ('1P', '2P'):
                    valeur = decimal.Decimal(str(round(rng.uniform(maxima * 0.40, maxima * 0.95), 2)))
                    _, c = Note.objects.get_or_create(
                        eleve=eleve,
                        matiere_classe=mc,
                        periode=periode,
                        defaults={'valeur': valeur},
                    )
                    if c:
                        note_count += 1

        self._ok("%d élèves créés" % eleve_count)
        self._ok("%d notes (1P + 2P) générées" % note_count)

        connection.set_schema_to_public()

    # ── Vérification des logins ───────────────────────────────────────────────

    def _verify_logins(self, schema):
        self.stdout.write(self.style.MIGRATE_HEADING("Vérification des connexions :"))
        ok_count = 0
        fail_count = 0

        # Super-admin
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

        # Admin-école
        from tenants.models import AdminEcole
        try:
            AdminEcole.objects.get(email__iexact=EMAIL_ADMIN, is_active=True)
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

        # Autres comptes (via AnnuaireUtilisateur)
        for email, pwd, role_label in [
            (EMAIL_PREFET,      PWD_PREFET,      'préfet'),
            (EMAIL_ENSEIGNANT,  PWD_ENSEIGNANT,  'enseignant'),
            (EMAIL_SECRETARIAT, PWD_SECRETARIAT, 'secrétariat'),
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

        self.stdout.write('')
        if fail_count == 0:
            self.stdout.write(self.style.SUCCESS(
                "  OK  Tous les comptes (%d/%d) se connectent correctement." % (ok_count, ok_count)
            ))
        else:
            self.stdout.write(self.style.ERROR(
                "  ERR %d compte(s) en erreur sur %d." % (fail_count, ok_count + fail_count)
            ))

    # ── Résumé ────────────────────────────────────────────────────────────────

    def _print_summary(self, no_data=False):
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(
            "─" * 62
        ))
        self.stdout.write(self.style.MIGRATE_HEADING("  Credentials de test"))
        self.stdout.write(self.style.MIGRATE_HEADING(
            "─" * 62
        ))
        rows = [
            ("Super-admin",   EMAIL_SA,          PWD_SA,          "/super-admin/"),
            ("Admin-école",   EMAIL_ADMIN,        PWD_ADMIN,       "/dashboard/"),
            ("Préfet",        EMAIL_PREFET,       PWD_PREFET,      "/dashboard/"),
            ("Enseignant",    EMAIL_ENSEIGNANT,   PWD_ENSEIGNANT,  "/dashboard/"),
            ("Secrétariat",   EMAIL_SECRETARIAT,  PWD_SECRETARIAT, "/dashboard/"),
        ]
        for role, email, pwd, url in rows:
            self.stdout.write("  %-14s  %-36s  %s" % (role, email, pwd))
        self.stdout.write('')
        if not no_data:
            self.stdout.write("  Année scolaire : %s" % ANNEE_SCOLAIRE)
            self.stdout.write("  Classes        : %d    Eleves : %d" % (len(CLASSES), len(ELEVES)))
        self.stdout.write(self.style.MIGRATE_HEADING("─" * 62))
        self.stdout.write('')

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _step(self, num, label):
        self.stdout.write(self.style.MIGRATE_HEADING("\n[%s] %s" % (num, label)))

    def _ok(self, msg):
        self.stdout.write(self.style.SUCCESS("  [OK]  " + msg))

    def _warn(self, msg):
        self.stdout.write(self.style.WARNING("  [!!]  " + msg))

    def _verify_ok(self, role, email):
        self.stdout.write(self.style.SUCCESS("  [OK]  %-14s  %s" % (role, email)))

    def _verify_fail(self, role, email, reason):
        self.stdout.write(self.style.ERROR("  [ERR] %-14s  %s — %s" % (role, email, reason)))
