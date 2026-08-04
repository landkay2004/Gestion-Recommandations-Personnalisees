# EducNet — Plateforme de gestion scolaire multi-tenant

A Django 6 multi-tenant school management platform for Congolese schools (DRC). Built with `django-tenants`, deployed on Vercel, with a PostgreSQL database.

## Stack

- **Backend**: Django 6.0.7, Python 3.12
- **Database**: PostgreSQL (required — no SQLite fallback)
- **Multi-tenancy**: `django-tenants` (each school gets an isolated schema)
- **Storage**: Cloudinary (production) or local filesystem (dev)
- **Deployment**: Vercel (serverless, entry point: `deployment/vercel_wsgi.py`)

## Running locally on Replit

This app requires PostgreSQL. Set `DATABASE_URL` or `DB_HOST` in Replit Secrets, then start the **Django School App** workflow which runs `school_app/start.sh`.

The workflow:
1. Checks the DB connection
2. Runs `migrate_schemas --noinput`
3. Collects static files
4. Starts `manage.py runserver 0.0.0.0:8000`

## Vercel deployment

Config lives in `vercel.json`. Key points:
- Entry point: `deployment/vercel_wsgi.py`
- Build script: `deployment/build_files.sh`
- Templates are bundled via `includeFiles: ["school_app/**"]`

**Required Vercel environment variables:**
| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `DJANGO_SECRET_KEY` | Must be static — auto-generated keys corrupt sessions across serverless workers |
| `DJANGO_DEBUG` | Set to `False` in production |

## Project structure

```
school_app/
  apps/           — Django apps (accounts, students, teachers, bulletin, etc.)
  config/         — Settings, URLs, middleware, WSGI
  templates/      — All HTML templates (project-level)
  static/         — Static assets
deployment/
  vercel_wsgi.py  — Vercel WSGI entry point
  build_files.sh  — Vercel build script
vercel.json       — Vercel configuration
```

## User preferences

- Language: French (app UI, comments, and error messages are in French)
- Keep existing project structure — do not reorganize
