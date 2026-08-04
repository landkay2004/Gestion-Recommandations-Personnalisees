# 🚀 Déploiement EducNet — Guide complet

**Stack de production :** Vercel (hébergement) · Neon (PostgreSQL) · Cloudflare R2 (médias)

---

## 📋 Vue d'ensemble

```
Navigateur
    │
    ▼
Vercel  (Django serverless)
    ├── /static/*  →  CDN Vercel   (CSS, JS, images statiques)
    ├── /media/*   →  Cloudflare R2  (photos, logos, bulletins)
    └── /*         →  Django WSGI   →  Neon PostgreSQL
```

---

## Étape 1 — Neon : créer la base de données

1. Aller sur **[console.neon.tech](https://console.neon.tech)** → **New Project**
2. Nom du projet : `educnet` | Région : la plus proche de vos utilisateurs
3. Cliquer **Create Project**
4. Dans **Dashboard → Connection Details** :
   - Sélectionner **Connection string** → format **psycopg2**
   - Copier la chaîne (commence par `postgresql://`)

**Exemple de chaîne de connexion Neon :**
```
postgresql://educnet_owner:AbCdEf123456@ep-cool-lab-a2b3c4d5.eu-west-2.aws.neon.tech/educnet?sslmode=require
```

> **Important :** Neon propose un plan gratuit (0,5 Go, 1 branche). Largement suffisant pour démarrer.

---

## Étape 2 — Cloudflare R2 : stockage des médias

1. Aller sur **[dash.cloudflare.com](https://dash.cloudflare.com)** → **R2 Object Storage** → **Create bucket**
2. Nom du bucket : `educnet-media` | Région : automatique
3. Activer l'accès public : bucket → **Settings** → **Public Access** → **Allow Access** → Copier l'URL publique

   **Exemple d'URL publique R2 :**
   ```
   https://pub-a1b2c3d4e5f6789012345678abcdef01.r2.dev
   ```

4. Créer les clés d'API : **R2 → Manage R2 API Tokens** → **Create API Token**
   - Permissions : **Object Read & Write**
   - Bucket : `educnet-media` (spécifique)
   - Cliquer **Create API Token**

   **Exemple de token R2 généré :**
   ```
   Access Key ID     : a1b2c3d4e5f6789012345678abcdef01a2b3c4d5
   Secret Access Key : a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8s9T0u1V2w3X4y5Z6
   Endpoint URL      : https://abc123def456.r2.cloudflarestorage.com
   ```

---

## Étape 3 — Variables d'environnement Vercel

Dans **Vercel Dashboard → Project → Settings → Environment Variables**, ajouter **exactement** ces variables (adapter les valeurs) :

| Variable | Exemple de valeur | Obligatoire |
|---|---|---|
| `DJANGO_SECRET_KEY` | `mK9#pL2@xR7vN4qZ8wY1uT5sA3jF6bH0eC` | ✅ |
| `DJANGO_DEBUG` | `False` | ✅ |
| `DJANGO_SITE_URL` | `https://educnet.vercel.app` | ✅ |
| `DATABASE_URL` | `postgresql://user:pass@ep-xxx.region.aws.neon.tech/educnet?sslmode=require` | ✅ |
| `R2_ACCESS_KEY_ID` | `a1b2c3d4e5f6789012345678abcdef01a2b3c4d5` | ✅ |
| `R2_SECRET_ACCESS_KEY` | `a1B2c3D4...y5Z6` | ✅ |
| `R2_BUCKET_NAME` | `educnet-media` | ✅ |
| `R2_ENDPOINT_URL` | `https://abc123def456.r2.cloudflarestorage.com` | ✅ |
| `R2_PUBLIC_URL` | `https://pub-a1b2c3d4e5f6789012345678abcdef01.r2.dev` | ✅ |

> 💡 **Générer `DJANGO_SECRET_KEY`** — exécuter dans un terminal Python :
> ```python
> python -c "import secrets; print(secrets.token_urlsafe(50))"
> ```
> Résultat exemple : `mK9pL2xR7vN4qZ8wY1uT5sA3jF6bH0eCdGiMoQs_tWy`

---

## Étape 4 — Connecter et déployer sur Vercel

### Option A — Via GitHub *(recommandée — déploiement automatique à chaque push)*

1. Pousser le code sur GitHub :
   ```bash
   git add .
   git commit -m "feat: configuration déploiement Vercel"
   git push origin main
   ```

2. Aller sur **[vercel.com/new](https://vercel.com/new)** → **Import Git Repository**
3. Sélectionner votre dépôt → Vercel détecte automatiquement `vercel.json`
4. **Ne pas modifier** les paramètres de build (déjà configurés dans `vercel.json`)
5. Cliquer **Deploy** ✅

### Option B — Via Vercel CLI

```bash
# Installer Vercel CLI
npm install -g vercel

# Se connecter
vercel login

# Déployer en production
vercel --prod
```

---

## Étape 5 — Créer le compte super-administrateur

Après le premier déploiement réussi :

1. Aller sur : `https://votre-projet.vercel.app/super-admin/`
2. Page d'inscription initiale → remplir avec vos infos réelles

**Données de test pour voir la plateforme en action :**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SUPER ADMIN (gestionnaire plateforme)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Prénom    : Admin
  Nom       : EducNet
  Email     : admin@educnet.app
  Mot passe : Admin@2025!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Étape 6 — Créer une école de test

Depuis le dashboard super-admin → **Écoles** → **Nouvelle école** :

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ÉCOLE DE TEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Nom de l'école   : Lycée Excellence
  Sous-domaine     : excellence
  Abonnement       : Standard (ou Essai)
  Nombre d'élèves  : 150
  Ville            : Douala
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Admin de l'école (préfet)
  ───────────────────────────
  Prénom    : Jean
  Nom       : Kamga
  Email     : j.kamga@excellence.cm
  Mot passe : Ecole@2025!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Accès tableau de bord école : `https://votre-projet.vercel.app/` → se connecter avec `j.kamga@excellence.cm`

---

## Étape 7 — Ajouter des élèves et classes (test complet)

Une fois connecté en tant qu'admin école :

**Classes à créer :**
| Nom | Niveau | Effectif |
|-----|--------|----------|
| 3ème A | Collège | 45 élèves |
| 2nde C | Lycée | 38 élèves |
| Tle D | Lycée | 42 élèves |

**Élèves de test :**
```
Matricule : EXC-2025-001 | Nom : Fokou Marie     | Classe : 3ème A | Sexe : F
Matricule : EXC-2025-002 | Nom : Nkomo Pierre    | Classe : 3ème A | Sexe : M
Matricule : EXC-2025-003 | Nom : Belinga Sandra  | Classe : 2nde C | Sexe : F
Matricule : EXC-2025-004 | Nom : Essomba Rodrigue| Classe : Tle D  | Sexe : M
```

**Enseignant de test :**
```
Prénom : Paul | Nom : Mvogo | Matière : Mathématiques
Email  : p.mvogo@excellence.cm | Mot passe : Prof@2025!
```

---

## ✅ Checklist de vérification post-déploiement

- [ ] `https://votre-projet.vercel.app/` → redirige vers `/login/`
- [ ] Connexion super-admin fonctionne → `/super-admin/`
- [ ] Création d'une école → tenant créé dans Neon
- [ ] Upload photo de profil → image stockée sur R2 et affichée
- [ ] Génération bulletin PDF → téléchargement réussi
- [ ] Dashboard avec graphiques → données réelles affichées

---

## 🛠️ Dépannage fréquent

### ❌ Erreur `DisallowedHost` au premier accès
**Cause :** `DJANGO_SITE_URL` manquant ou incorrect
**Fix :** Ajouter `DJANGO_SITE_URL=https://votre-projet.vercel.app` dans Vercel → Redéployer

### ❌ Médias (photos, logos) non affichés
**Cause :** Variables R2 manquantes ou URL publique non activée
**Fix :**
1. Vérifier que `R2_PUBLIC_URL` pointe vers l'URL publique du bucket (pas l'endpoint API)
2. Dans R2 Dashboard → bucket → Settings → activer **Public Access**

### ❌ Erreur 500 à la connexion école
**Cause :** Migration tenant non appliquée
**Fix :** Depuis le super-admin → activer/réinitialiser l'école concernée

### ❌ Timeout dépassé (> 10 secondes)
**Cause :** Plan Vercel Hobby limité à 10s (génération PDF/bulletins prend plus de temps)
**Fix :** Passer au plan **Vercel Pro** (60s max) ou auto-héberger sur un VPS

---

## 📁 Structure du dossier `deployment/`

```
deployment/
├── README.md          → Ce guide
├── .env.example       → Toutes les variables d'environnement
├── vercel_wsgi.py     → Point d'entrée WSGI Vercel
└── build_files.sh     → Script de build (pip + migrate + collectstatic)

vercel.json            → Config Vercel (à la racine — Vercel le cherche là)
```
