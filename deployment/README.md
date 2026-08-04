# 🚀 Déploiement EducNet sur Vercel

Guide complet pour déployer EducNet avec **Vercel + Neon (PostgreSQL) + Cloudflare R2 (médias)**.

---

## Structure du dossier `deployment/`

```
deployment/
├── vercel_wsgi.py   → Point d'entrée WSGI pour Vercel
├── build_files.sh   → Script de build (pip install + migrate + collectstatic)
├── .env.example     → Toutes les variables d'environnement requises
└── README.md        → Ce guide

vercel.json          → Configuration Vercel (à la racine du projet)
```

> **Note :** `vercel.json` est à la **racine du projet** (pas dans ce dossier) car
> Vercel le cherche automatiquement à cet endroit.

---

## Étape 1 — Préparer Neon (base de données)

1. Aller sur [console.neon.tech](https://console.neon.tech) → votre projet
2. Cliquer **"Connection string"** → copier l'URL (format `postgresql://...?sslmode=require`)
3. Garder cette URL pour l'étape 3

---

## Étape 2 — Préparer Cloudflare R2 (médias)

1. Aller sur [dash.cloudflare.com](https://dash.cloudflare.com) → **R2 Object Storage**
2. Créer un bucket (ex. `educnet-media`)
3. Dans le bucket → **Settings** → activer **"Public Access"** → noter l'URL publique
4. Aller dans **R2 → Manage R2 API Tokens** → créer un token avec permissions **Object Read & Write**
5. Noter : **Access Key ID**, **Secret Access Key**, **Endpoint URL** (`https://<ACCOUNT_ID>.r2.cloudflarestorage.com`)

---

## Étape 3 — Configurer les variables d'environnement sur Vercel

Dans **Vercel Dashboard → Project → Settings → Environment Variables**, ajouter :

| Variable               | Valeur                                              |
|------------------------|-----------------------------------------------------|
| `DJANGO_SECRET_KEY`    | Chaîne aléatoire longue (50+ caractères)            |
| `DJANGO_DEBUG`         | `False`                                             |
| `DJANGO_SITE_URL`      | `https://votre-projet.vercel.app`                   |
| `DATABASE_URL`         | URL de connexion Neon                               |
| `R2_ACCESS_KEY_ID`     | Clé d'accès R2                                      |
| `R2_SECRET_ACCESS_KEY` | Clé secrète R2                                      |
| `R2_BUCKET_NAME`       | Nom du bucket (ex. `educnet-media`)                 |
| `R2_ENDPOINT_URL`      | `https://ACCOUNT_ID.r2.cloudflarestorage.com`       |
| `R2_PUBLIC_URL`        | URL publique R2 (ex. `https://pub-xxxx.r2.dev`)     |

> Voir `deployment/.env.example` pour la liste complète avec descriptions.

---

## Étape 4 — Connecter et déployer sur Vercel

### Option A — Via GitHub (recommandée)
1. Pusher le code sur GitHub
2. Aller sur [vercel.com/new](https://vercel.com/new) → **Import Git Repository**
3. Sélectionner le dépôt → Vercel détecte `vercel.json` automatiquement
4. Cliquer **Deploy** → Vercel exécute `build_files.sh` et déploie

### Option B — Via Vercel CLI
```bash
npm i -g vercel
vercel login
vercel --prod
```

---

## Étape 5 — Créer le super-admin

Après le premier déploiement, ouvrir le terminal Vercel ou utiliser la console Neon :
```bash
# Via Vercel CLI
vercel env pull .env.local
cd school_app && python manage.py createsuperuser
```

Ou accéder directement à `https://votre-projet.vercel.app/super-admin/` pour l'inscription initiale.

---

## Architecture de déploiement

```
Navigateur
    │
    ▼
Vercel (serverless)
    │
    ├── /static/* ──────────► Fichiers statiques (servis par Vercel CDN)
    │                         Whitenoise collecte dans school_app/staticfiles/
    │
    ├── /media/* ───────────► Cloudflare R2 (images, documents, logos)
    │                         URLs directes depuis R2 Public Access
    │
    └── /* ────────────────► Django WSGI (deployment/vercel_wsgi.py)
                              ├── Tenant routing (django-tenants)
                              ├── Auth, Dashboard, Bulletins…
                              └── Neon PostgreSQL (DATABASE_URL)
```

---

## Dépannage

### Erreur `ALLOWED_HOSTS`
Ajouter `DJANGO_SITE_URL=https://votre-projet.vercel.app` dans les variables Vercel.

### Migrations non appliquées
Le script `build_files.sh` applique `migrate_schemas --shared` à chaque build.
Pour les migrations tenant, se connecter à l'école depuis le super-admin.

### Médias non affichés
Vérifier que `R2_PUBLIC_URL` est l'URL publique du bucket (pas l'endpoint API).
Dans R2 Dashboard → bucket → Settings → activer **Public Access**.

### Timeout Lambda (> 10s)
Vercel Hobby plan limite à 10s. Pour EducNet (génération bulletins/PDF), utiliser le plan **Pro** (60s max).
