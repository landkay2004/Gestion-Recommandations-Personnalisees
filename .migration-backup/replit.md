# EducNet — Système de Gestion Scolaire

Multi-tenant school management platform for schools in the DRC (Congo).

## Stack

- **Backend**: Django 6.x
- **Database**: PostgreSQL (required — multi-tenancy via django-tenants)
- **Frontend**: Bootstrap 5 + Django templates
- **PDF/reports**: ReportLab
- **QR codes**: qrcode + Pillow
- **Static files**: WhiteNoise

## Project layout

```
school_app/          ← Django project root
  apps/
    accounts/        ← Users, roles, profiles
    abonnement/      ← School-level fees & student payments
    bulletin/        ← Report cards (PDF MEPSP)
    carte_eleve/     ← Student ID cards
    classes/         ← Classes & sections
    comptable/       ← School accounting & invoices
    dashboard/       ← Role-based dashboards
    grades/          ← Grades & marks
    notifications/   ← In-app notification system
    onboarding/      ← School setup wizard (5 steps)
    planning/        ← Timetable/schedule
    portail/         ← Parent portal (QR / access code)
    reports/         ← Export & reports
    school_settings/ ← Per-school configuration
    students/        ← Student management
    subjects/        ← Subjects/courses
    super_admin/     ← Platform super-admin (plans, schools, payments)
    teachers/        ← Teacher management
    tenants/         ← Multi-tenant models (Ecole, PlanAbonnement, etc.)
  config/
    settings.py      ← Main settings
  templates/         ← All HTML templates
  static/            ← CSS/JS/images
  manage.py
```

## Running locally

Requires a PostgreSQL database (SQLite works but multi-tenancy is limited).

```bash
cd school_app
pip install -r requirements.txt
# Set DATABASE_URL env var, then:
python manage.py migrate_schemas --shared
python manage.py migrate_schemas
python manage.py seed_test_school   # optional test data
python manage.py runserver
```

## Environment variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (required) |
| `SECRET_KEY` / `SESSION_SECRET` | Django secret key |
| `DEBUG` | `True` in dev |
| `ALLOWED_HOSTS` | `*` in dev |
| `EMAIL_HOST*` | SMTP config (optional) |

## Test accounts (after seeding)

| Role | Email | Password |
|---|---|---|
| Super-admin | superadmin@test.local | SuperAdmin@2025! |
| School admin | admin@ecoletest.local | Admin@Ecole2025! |
| Préfet | prefet@ecoletest.local | Prefet@Ecole2025! |
| Teacher | enseignant@ecoletest.local | Enseignant@2025! |
| Secretary | secretariat@ecoletest.local | Secretariat@2025! |
| Accountant | comptable@ecoletest.local | Comptable@2025! |

## Key known issues (to be fixed)

1. Profile/account images don't save or display (likely missing `enctype` or media serving issue)
2. Student card photos appear blurry (no image optimisation)
3. Notification module exists but is non-functional (silent `except: pass` swallows errors)
4. Mobile payment UI is in the accountant view but should be in super-admin subscription flow
5. Onboarding templates need a modern interactive redesign
6. Subscription plan cards need a professional redesign

## User preferences

- Keep the existing Django/Bootstrap stack — no migrations to other frameworks
- Push finished work to GitHub
