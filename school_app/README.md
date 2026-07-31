# EducNet — Système de Gestion Scolaire

Plateforme web multi-tenant de gestion scolaire pour les écoles en RDC.

**Version 3.1 — Juillet 2026**

---

## Ce que fait le projet

- Gestion multi-tenant d’écoles
- Portail parents avec QR / code d’accès
- Bulletins PDF MEPSP
- Comptabilité scolaire et facturation
- Planning, élèves, matières, notes
- Super-admin plateforme

---

## Rapide

- Backend : Django 6.x
- Base : PostgreSQL en prod, SQLite en dev
- Multi-tenancy : django-tenants
- Frontend : Bootstrap 5

---

## Prise en main locale

1. Créer un environnement Python
   - Windows PowerShell : `python -m venv .venv` puis `.\.venv\Scripts\Activate.ps1`
   - Linux/macOS : `python3 -m venv .venv` puis `source .venv/bin/activate`
2. Installer les dépendances
   - `pip install -r requirements.txt`
3. Configurer la base de données
   - `DATABASE_URL=postgres://user:pass@host:5432/dbname`
   - ou ne rien définir pour utiliser SQLite local
4. Appliquer les migrations
   - PostgreSQL multi-tenant :
     - `python manage.py migrate_schemas --shared`
     - `python manage.py migrate_schemas`
   - SQLite local :
     - `python manage.py migrate`
5. Charger les données de test
   - PostgreSQL : `python manage.py seed_test_school`
   - SQLite : `python manage.py seed_sqlite_users`
6. Démarrer le serveur
   - `python manage.py runserver`

---

## Comptes de test

### PostgreSQL (seed_test_school)

- Super-admin : `superadmin@test.local` / `SuperAdmin@2025!`
- Admin-école : `admin@ecoletest.local` / `Admin@Ecole2025!`
- Préfet : `prefet@ecoletest.local` / `Prefet@Ecole2025!`
- Enseignant : `enseignant@ecoletest.local` / `Enseignant@2025!`
- Secrétariat : `secretariat@ecoletest.local` / `Secretariat@2025!`
- Comptable : `comptable@ecoletest.local` / `Comptable@2025!`

### SQLite local (seed_sqlite_users)

- Admin-école : `admin@ecoletest.local` / `Admin@Ecole2025!`
- Préfet : `prefet@ecoletest.local` / `Prefet@Ecole2025!`
- Enseignant : `enseignant@ecoletest.local` / `Enseignant@2025!`
- Secrétariat : `secretariat@ecoletest.local` / `Secretariat@2025!`

---

## Variables clés

- `DATABASE_URL` : PostgreSQL (prod)
- `SECRET_KEY` : secret Django
- `DEBUG` : `True` en dev
- `ALLOWED_HOSTS` : `*` en dev
- `EMAIL_HOST*` : SMTP si besoin

---

## Architecture

- `public` : données de plateforme
- `ecole_<slug>` : données par école
- Chaque école est isolée dans son propre schéma

---

## Modules principaux

- Dashboard
- Élèves
- Classes
- Matières
- Notes
- Bulletins
- Planning
- Comptable
- Portail parents
- Carte élève
- Paramètres
- Onboarding
- Super-admin plateforme

---

## Structure du dépôt

```
school_app/
├── apps/
│   ├── abonnement/
│   ├── accounts/
│   ├── bulletin/
│   ├── carte_eleve/
│   ├── classes/
│   ├── comptable/
│   ├── dashboard/
│   ├── grades/
│   ├── notifications/
│   ├── onboarding/
│   ├── planning/
│   ├── portail/
│   ├── reports/
│   ├── school_settings/
│   ├── students/
│   ├── subjects/
│   ├── super_admin/
│   ├── teachers/
│   └── tenants/
├── config/
│   └── settings.py
├── templates/
├── static/
└── manage.py
```

---

## Déploiement simple

- `DEBUG=False`
- Configurer `ALLOWED_HOSTS`
- `python manage.py migrate --run-syncdb`
- `python manage.py collectstatic --noinput`
- Utiliser Gunicorn / Nginx

---

## Important

- En local, SQLite fonctionne mais le vrai multi-tenant requiert PostgreSQL.
- Le portail mobile futur doit utiliser l’API Django, pas un accès direct à la base.
- Garder backend et mobile séparés, mais dans le même dépôt si nécessaire.
