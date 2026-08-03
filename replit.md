# EducNet — Système de Gestion Scolaire

Plateforme web multi-tenant de gestion scolaire pour les écoles en RDC (Congo). Gère les élèves, classes, notes, bulletins PDF, planning, comptabilité, portail parents et un super-admin plateforme.

## Run & Operate

- **Démarrer l'app** : workflow `Start application` (lancé automatiquement)
  - Exécute `bash school_app/start.sh` : migrations → collectstatic → `runserver 0.0.0.0:8000`
- **Migrations** : `cd school_app && python manage.py migrate_schemas --noinput`
- **Seed de test** : `cd school_app && python manage.py seed_test_school`
- **Shell Django** : `cd school_app && python manage.py shell`
- Required env: `DATABASE_URL` — fourni automatiquement par Replit (PostgreSQL managé)

## Stack

- **Backend** : Django 6.x, Python
- **Base de données** : PostgreSQL (Replit managed) + django-tenants (multi-tenant par schéma)
- **Frontend** : Bootstrap 5 + templates Django (server-rendered)
- **PDF/reports** : ReportLab
- **QR codes** : qrcode + Pillow
- **Fichiers statiques** : WhiteNoise
- **Déploiement Vercel** : `@vercel/python` + `build.sh` (migrations + collectstatic auto)

## Where things live

```
school_app/          ← Racine du projet Django (manage.py ici)
  apps/              ← Modules métier (accounts, students, super_admin, …)
  config/
    settings.py      ← Configuration principale (DATABASE_URL ou DB_* vars)
    wsgi.py          ← Point d'entrée WSGI (Vercel)
  templates/         ← Templates HTML Bootstrap 5
  static/            ← CSS/JS/images source
  staticfiles/       ← Générés par collectstatic (ne pas éditer)
  build.sh           ← Script de build Vercel (pip + migrate_schemas --shared + collectstatic)
  start.sh           ← Script de démarrage Replit (migrate_schemas + runserver)
vercel.json          ← Config déploiement Vercel (buildCommand → build.sh)
```

## Architecture decisions

- **Multi-tenancy par schéma PostgreSQL** : chaque école a son propre schéma via django-tenants. Le schéma `public` contient les données plateforme (super_admin, tenants). Les migrations doivent être appliquées avec `migrate_schemas --shared` (schéma public) puis `migrate_schemas` (tous les tenants).
- **Pas de venv sur Replit** : `start.sh` détecte `REPL_ID` et utilise directement l'environnement Python géré par Replit (`.pythonlibs`).
- **DATABASE_URL auto** : Replit injecte `DATABASE_URL` automatiquement — aucune config manuelle nécessaire. `settings.py` le détecte et active le mode multi-tenant.
- **Build Vercel + migrations** : `vercel.json` appelle `school_app/build.sh` comme `buildCommand`, qui exécute `migrate_schemas --shared` avant de servir — les nouvelles colonnes sont appliquées à chaque déploiement.

## Product

- **Super-admin** : gestion des plans d'abonnement, des écoles, paramètres plateforme, images de fond login
- **Admin école** : onboarding 5 étapes, élèves, classes, matières, notes, bulletins PDF MEPSP
- **Portail parents** : accès via QR code ou code d'accès
- **Comptabilité** : facturation, paiements mobiles
- **Planning** : emploi du temps

## User preferences

- Garder le stack Django/Bootstrap — pas de migration vers d'autres frameworks
- Pousser le travail terminé sur GitHub

## Comptes de test (après seed_test_school)

| Rôle | Email | Mot de passe |
|---|---|---|
| Super-admin | superadmin@test.local | SuperAdmin@2025! |
| Admin-école | admin@ecoletest.local | Admin@Ecole2025! |
| Préfet | prefet@ecoletest.local | Prefet@Ecole2025! |
| Enseignant | enseignant@ecoletest.local | Enseignant@2025! |
| Secrétariat | secretariat@ecoletest.local | Secretariat@2025! |
| Comptable | comptable@ecoletest.local | Comptable@2025! |

## Gotchas

- Ne jamais lancer `pnpm dev` à la racine — l'app tourne via le workflow Django, pas pnpm.
- Les migrations multi-tenant : toujours `migrate_schemas --shared` d'abord (schéma public), puis `migrate_schemas` pour les tenants existants.
- Sur Vercel, le `build.sh` n'applique que `--shared` (les tenants se migrent à la demande).
- `staticfiles/` est généré — ne pas versionner son contenu si possible.
