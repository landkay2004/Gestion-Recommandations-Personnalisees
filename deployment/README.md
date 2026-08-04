# 🚀 Déploiement EducNet — Guide complet

**Stack de production :** Vercel (hébergement) · Neon (PostgreSQL) · Cloudinary (médias)

---

## 📋 Vue d'ensemble

```
Navigateur
    │
    ▼
Vercel  (Django serverless)
    ├── /static/*  →  CDN Vercel      (CSS, JS, images statiques)
    ├── /media/*   →  Cloudinary CDN  (photos, logos, bulletins — transformés à la volée)
    └── /*         →  Django WSGI     →  Neon PostgreSQL
```

---

## Étape 1 — Neon : créer la base de données

1. Aller sur **[console.neon.tech](https://console.neon.tech)** → **New Project**
2. Nom du projet : `educnet` | Région : la plus proche de vos utilisateurs
3. Cliquer **Create Project**
4. Dans **Dashboard → Connection Details** :
   - Sélectionner **Connection string** → format **psycopg2**
   - Copier la chaîne qui commence par `postgresql://`

**Exemple de chaîne de connexion Neon :**
```
postgresql://educnet_owner:AbCdEf123456@ep-cool-lab-a2b3c4d5.eu-west-2.aws.neon.tech/educnet?sslmode=require
```

> 💡 Neon propose un **plan gratuit** (0,5 Go, 1 branche). Largement suffisant pour démarrer.

---

## Étape 2 — Cloudinary : stockage et transformation des médias

Cloudinary stocke vos fichiers **et** les transforme à la volée (redimensionner, recadrer, optimiser).

1. Aller sur **[cloudinary.com](https://cloudinary.com)** → **Sign Up** (plan gratuit disponible)
2. Une fois connecté, aller dans **Dashboard**
3. Dans la section **"API Environment variable"**, copier la ligne qui commence par `cloudinary://`

**Exemple de CLOUDINARY_URL :**
```
cloudinary://123456789012345:AbCdEfGhIjKlMnOpQrStUvWxYz0123@mon-cloud-name
```

> 💡 Le plan gratuit Cloudinary offre **25 crédits/mois** = environ 25 000 transformations ou 25 Go de bande passante. Suffisant pour une école de taille normale.

---

## Étape 3 — Variables d'environnement Vercel

Dans **Vercel Dashboard → Project → Settings → Environment Variables**, ajouter ces variables :

| Variable | Exemple de valeur | Obligatoire |
|---|---|---|
| `DJANGO_SECRET_KEY` | `mK9#pL2@xR7vN4qZ8wY1uT5sA3jF6bH0eC` | ✅ |
| `DJANGO_DEBUG` | `False` | ✅ |
| `DJANGO_SITE_URL` | `https://educnet.vercel.app` | ✅ |
| `DATABASE_URL` | `postgresql://user:pass@ep-xxx.neon.tech/educnet?sslmode=require` | ✅ |
| `CLOUDINARY_URL` | `cloudinary://api_key:api_secret@cloud_name` | ✅ |

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
   git push origin main
   ```
2. Aller sur **[vercel.com/new](https://vercel.com/new)** → **Import Git Repository**
3. Sélectionner votre dépôt → Vercel détecte automatiquement `vercel.json`
4. Ne pas modifier les paramètres de build (déjà configurés)
5. Cliquer **Deploy** ✅

### Option B — Via Vercel CLI

```bash
npm install -g vercel
vercel login
vercel --prod
```

---

## Étape 5 — Créer le compte super-administrateur

Après le premier déploiement réussi :

1. Aller sur : `https://votre-projet.vercel.app/super-admin/`
2. Remplir le formulaire d'inscription initiale

**Données de test pour explorer la plateforme :**

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

Accès tableau de bord école → se connecter avec `j.kamga@excellence.cm` / `Ecole@2025!`

---

## Étape 7 — Données de test complets

Une fois connecté en tant qu'admin école :

**Classes à créer :**
| Nom | Niveau | Effectif cible |
|-----|--------|----------------|
| 3ème A | Collège | 45 élèves |
| 2nde C | Lycée | 38 élèves |
| Tle D | Lycée | 42 élèves |

**Élèves de test :**
```
Matricule : EXC-2025-001 | Nom : Fokou Marie      | Classe : 3ème A | Sexe : F
Matricule : EXC-2025-002 | Nom : Nkomo Pierre     | Classe : 3ème A | Sexe : M
Matricule : EXC-2025-003 | Nom : Belinga Sandra   | Classe : 2nde C | Sexe : F
Matricule : EXC-2025-004 | Nom : Essomba Rodrigue | Classe : Tle D  | Sexe : M
```

**Enseignant de test :**
```
Prénom : Paul | Nom : Mvogo | Matière : Mathématiques
Email  : p.mvogo@excellence.cm | Mot passe : Prof@2025!
```

**Tester Cloudinary — uploader une photo de profil :**
1. Se connecter en tant que `j.kamga@excellence.cm`
2. Aller dans **Profil** → **Changer la photo**
3. Uploader n'importe quelle image JPG
4. Vérifier que l'image s'affiche dans la sidebar — elle est maintenant hébergée sur Cloudinary, persistante même après redémarrage du serveur ✅

---

## ✅ Checklist de vérification post-déploiement

- [ ] `https://votre-projet.vercel.app/` → redirige vers `/login/`
- [ ] Connexion super-admin → `/super-admin/`
- [ ] Création d'une école → tenant créé dans Neon
- [ ] Upload photo de profil → URL Cloudinary (`res.cloudinary.com/...`) visible dans le code source
- [ ] Génération bulletin PDF → téléchargement réussi
- [ ] Dashboard avec graphiques → données réelles affichées

---

## 🛠️ Dépannage fréquent

### ❌ Erreur `DisallowedHost` au premier accès
**Cause :** `DJANGO_SITE_URL` manquant ou incorrect
**Fix :** Ajouter `DJANGO_SITE_URL=https://votre-projet.vercel.app` dans Vercel → Redéployer

### ❌ Photos non affichées après upload
**Cause :** `CLOUDINARY_URL` manquant ou mal copié
**Fix :**
1. Vérifier que `CLOUDINARY_URL` commence bien par `cloudinary://` (pas `CLOUDINARY_URL=`)
2. Dans Vercel Dashboard → Environment Variables → supprimer et recréer la variable
3. Redéployer

### ❌ Erreur 500 à la connexion école
**Cause :** Migration tenant non appliquée
**Fix :** Depuis le super-admin → désactiver puis réactiver l'école concernée

### ❌ Timeout dépassé (> 10 secondes)
**Cause :** Plan Vercel Hobby limité à 10s (génération PDF/bulletins peut dépasser)
**Fix :** Passer au plan **Vercel Pro** (60s max) ou héberger sur un VPS

---

## 📁 Fichiers de déploiement

```
vercel.json               → Config Vercel (à la racine — détectée automatiquement)
deployment/
├── README.md             → Ce guide
├── .env.example          → Toutes les variables à copier dans Vercel
├── vercel_wsgi.py        → Point d'entrée WSGI pour Vercel
└── build_files.sh        → Script de build (pip + migrate + collectstatic)
```
