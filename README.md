# EducNet — Système de Gestion des Notes

Plateforme web **multi-tenant** de gestion scolaire pour les établissements de la République Démocratique du Congo. Bulletins officiels MEPSP, planning, portail parents, carte élève, gestion multi-écoles.

---

## Nouveautés — Version 3.1 (Juillet 2026)

| Nouveauté | Description |
|---|---|
| **Rebrand EducNet** | La plateforme est renommée **EducNet** — tous les titres, e-mails et templates mis à jour |
| **Module Comptable** | Nouvelle app `comptable` : gestion des paiements scolaires, encaissement par élève, historique des paiements, tableau de bord comptable dédié |
| **Frais scolaires** | App `abonnement` enrichie : types de frais paramétrables, facturation, confirmation de paiements plateforme |
| **Seed automatique** | Le script `start.sh` déclenche `seed_test_school` (PostgreSQL) ou `seed_sqlite_users` (SQLite) **et** `seed_super_admin` à chaque démarrage |
| **Design — padding amélioré** | Espacement élargi dans les tableaux, cartes et en-têtes de page pour une meilleure lisibilité |
| **Journal des opérations** | Traçabilité complète des clôtures d'années, promotions et transferts d'élèves |
| **Niveaux & Promotions** | Gestion des niveaux d'étude, clôture d'année scolaire, promotion automatique des élèves |
| **Archives portail** | Consultation des bulletins des années précédentes via le portail parents |
| **Rate limiting login** | Protection anti-brute-force sur les routes de connexion (école + super-admin) |

---

## Table des matières

1. [Stack technique](#1-stack-technique)
2. [Prérequis](#2-prérequis)
3. [Installation rapide (Replit)](#3-installation-rapide-replit)
4. [Installation locale (hors Replit)](#4-installation-locale-hors-replit)
5. [Configuration des variables d'environnement](#5-configuration-des-variables-denvironnement)
6. [Base de données — PostgreSQL multi-tenant](#6-base-de-données--postgresql-multi-tenant)
7. [Configuration e-mail (SMTP)](#7-configuration-e-mail-smtp)
8. [Démarrage du serveur](#8-démarrage-du-serveur)
9. [Comptes de test](#9-comptes-de-test)
10. [Structure du projet](#10-structure-du-projet)
11. [Applications Django](#11-applications-django)
12. [Assistant de configuration initiale (Onboarding)](#12-assistant-de-configuration-initiale-onboarding)
13. [Planning hebdomadaire](#13-planning-hebdomadaire)
14. [Portail parents](#14-portail-parents)
15. [Super-admin — Console plateforme](#15-super-admin--console-plateforme)
16. [Déploiement en production](#16-déploiement-en-production)
17. [Procédures de test](#17-procédures-de-test)
18. [Problèmes courants (FAQ)](#18-problèmes-courants-faq)

---

## 1. Stack technique

| Composant | Technologie |
|---|---|
| Backend | Django 6.x (Python 3.12) |
| Multi-tenancy | django-tenants 3.x (schémas PostgreSQL) |
| Base de données | **PostgreSQL** (production) · SQLite (dev sans PG) |
| Frontend | HTML5 · Bootstrap 5.3 · Bootstrap Icons · JS minimal |
| PDF / Bulletins | ReportLab |
| Fichiers statiques | WhiteNoise |
| Authentification | Session Django + backend email personnalisé |
| 2FA super-admin | PyOTP (TOTP) |
| QR codes | qrcode (portail parents & carte élève) |
| E-mail | Backend dynamique : SMTP réel ou console selon config |

---

## 2. Prérequis

- **Python** ≥ 3.10
- **PostgreSQL** ≥ 14 avec l'extension `pg_trgm` (mode production)
- Git

> **Sur Replit** : Python et les dépendances sont gérés automatiquement — aucune installation manuelle requise.

---

## 3. Installation rapide (Replit)

Le projet tourne directement sur Replit via le workflow **`SGN Django`**.

1. Ouvrez le Repl.
2. Assurez-vous que les secrets nécessaires sont configurés (voir §5).
3. Le workflow `SGN Django` démarre automatiquement : migrations, données de test, serveur.
4. Accédez à l'aperçu dans l'onglet **Webview**.

```
Super-admin : /super-admin/login/
Connexion école : /login/
```

---

## 4. Installation locale (hors Replit)

```bash
# 1. Cloner le dépôt
git clone https://github.com/landrynet/Gestion-Recommandations-Personnalisees.git
cd Gestion-Recommandations-Personnalisees

# 2. Créer et activer un environnement virtuel
python3 -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate           # Windows

# 3. Installer les dépendances
pip install -r school_app/requirements.txt

# 4. Configurer les variables d'environnement (voir §5)
cp .env.example .env               # puis éditer .env

# 5. Lancer via le script de démarrage
bash scripts/start.sh
```

### Mode développement sans PostgreSQL (SQLite)

Omettez les variables `DB_HOST` / `DATABASE_URL` : le projet bascule automatiquement en mode SQLite (migrations simples, pas de multi-tenant).

```bash
# Lancer en mode SQLite
cd school_app
python3 manage.py migrate --noinput
python3 manage.py seed_sqlite_users
python3 manage.py runserver 0.0.0.0:8000
```

---

## 5. Configuration des variables d'environnement

Créez un fichier `.env` à la racine (ou configurez les **Secrets Replit**) :

```dotenv
# ── Sécurité ────────────────────────────────────────────────
DJANGO_SECRET_KEY=changez-cette-cle-en-production-minimum-50-caracteres
DJANGO_DEBUG=False                  # True en développement
DJANGO_SITE_URL=https://votre-domaine.com

# ── Base de données PostgreSQL ───────────────────────────────
# Option A — URL complète (recommandée)
DATABASE_URL=postgres://user:password@host:5432/sgn_db

# Option B — Variables séparées
DB_HOST=localhost
DB_PORT=5432
DB_NAME=sgn_db
DB_USER=postgres
DB_PASSWORD=votre_mot_de_passe
DB_SSLMODE=prefer               # prefer | require | disable

# ── E-mail (fallback env ; préférer la config UI §7) ─────────
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=votre@gmail.com
EMAIL_HOST_PASSWORD=votre_app_password
DEFAULT_FROM_EMAIL=noreply@votre-ecole.cd
```

> **Sur Replit** : utilisez l'onglet **Secrets** (clé 🔑) pour stocker ces valeurs — ne les commitez jamais dans le code.

---

## 6. Base de données — PostgreSQL multi-tenant

### Création de la base

```sql
-- Se connecter en tant que superuser PostgreSQL
CREATE DATABASE sgn_db;
CREATE USER sgn_user WITH PASSWORD 'mot_de_passe_fort';
GRANT ALL PRIVILEGES ON DATABASE sgn_db TO sgn_user;

-- Activer l'extension nécessaire
\c sgn_db
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

### Migrations initiales

```bash
cd school_app

# Migrations schéma public (tenants, super_admin, onboarding)
python3 manage.py migrate_schemas --shared

# Créer le tenant public
python3 manage.py init_public_tenant

# Créer des données de test (école + comptes)
python3 manage.py seed_test_school
```

### Architecture multi-tenant

Chaque école possède son **propre schéma PostgreSQL** (ex: `ecole_test`, `inst_bungulu`). Le schéma `public` contient les données communes (super-admin, annuaire, plans d'abonnement).

| Schéma | Contenu |
|---|---|
| `public` | SuperAdmin, AdminEcole, Ecole, AnnuaireUtilisateur, PlatformSettings |
| `<schema_ecole>` | Élèves, Notes, Bulletins, Enseignants, Classes, Planning, Notifications |

---

## 7. Configuration e-mail (SMTP)

### Via l'interface super-admin (recommandé)

1. Connectez-vous sur `/super-admin/login/`
2. Allez dans **Paramètres** → section **Configuration e-mail (SMTP)**
3. Activez le switch **« Activer l'envoi SMTP réel »**
4. Renseignez :
   - **Serveur SMTP** : `smtp.gmail.com` (Gmail) ou `smtp.office365.com` (Outlook)
   - **Port** : `587` (TLS/STARTTLS) ou `465` (SSL)
   - **TLS** : activé
   - **Identifiant** : votre adresse e-mail complète
   - **Mot de passe** : mot de passe d'application (voir ci-dessous)
   - **Adresse From** : `noreply@votre-ecole.cd`
5. Cliquez **« Envoyer un e-mail test »** pour vérifier
6. Enregistrez

### Gmail — Mot de passe d'application

1. Activez la **validation en 2 étapes** sur votre compte Google
2. Accédez à [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Créez une app password pour **« Autre (EducNet) »**
4. Copiez le mot de passe généré (16 caractères) dans le champ SMTP Password

### Configuration Outlook / Office 365

```
Serveur : smtp.office365.com
Port    : 587
TLS     : Activé
Login   : votre@organisation.com
```

### Mode console (développement)

Sans configuration SMTP active, tous les e-mails sont affichés dans les **logs du serveur** (terminal / console Replit). Aucun e-mail réel n'est envoyé.

```
[CONSOLE EMAIL]
From: noreply@educnet.local
To: admin@ecole.cd
Subject: Vos identifiants - Plateforme EducNet
...
```

---

## 8. Démarrage du serveur

### Script de démarrage complet (recommandé)

```bash
bash scripts/start.sh
```

Ce script effectue dans l'ordre :
1. Détection de Python
2. Vérification des dépendances
3. Connexion à la base de données
4. Migrations (PostgreSQL multi-tenant ou SQLite)
5. Seeding des données initiales
6. Collecte des fichiers statiques
7. Démarrage de Django sur `0.0.0.0:$PORT`

### Variables de contrôle du script

```bash
PORT=8000                    # Port d'écoute (défaut: 8000)
SKIP_DB_CHECK=1              # Sauter la vérification DB
SKIP_COLLECTSTATIC=1         # Sauter collectstatic
```

### Démarrage minimal (développement)

```bash
cd school_app
python3 manage.py runserver 0.0.0.0:8000
```

### Réinitialisation complète (développement)

```bash
# Recréer les comptes de test
cd school_app
python3 manage.py seed_test_school        # Mode PostgreSQL
python3 manage.py seed_sqlite_users       # Mode SQLite

# Créer/mettre à jour le super-admin
python3 manage.py seed_super_admin
```

---

## 9. Comptes de test

Ces comptes sont créés automatiquement au démarrage (via `seed_test_school`).

| Rôle | E-mail | Mot de passe | URL de connexion |
|---|---|---|---|
| **Super-admin** | `superadmin@test.local` | `SuperAdmin@2025!` | `/super-admin/login/` |
| **Admin-école** | `admin@ecoletest.local` | `Admin@Ecole2025!` | `/login/` |
| **Préfet** | `prefet@ecoletest.local` | `Prefet@Ecole2025!` | `/login/` |
| **Enseignant** | `enseignant@ecoletest.local` | `Enseignant@2025!` | `/login/` |
| **Secrétariat** | `secretariat@ecoletest.local` | `Secretariat@2025!` | `/login/` |

> ⚠️ Changez tous ces mots de passe avant tout déploiement en production.

---

## 10. Structure du projet

```
Gestion-Recommandations-Personnalisees/
├── school_app/                    # Racine Django
│   ├── apps/                      # Applications Django
│   │   ├── accounts/              # Auth, rôles, middleware
│   │   ├── bulletin/              # Bulletins officiels RDC
│   │   ├── carte_eleve/           # Carte d'élève + QR
│   │   ├── classes/               # Années, sections, classes
│   │   ├── dashboard/             # Tableau de bord
│   │   ├── grades/                # Saisie des notes
│   │   ├── notifications/         # Système de notifications
│   │   ├── onboarding/            # Assistant config initiale
│   │   ├── planning/              # Planning hebdomadaire
│   │   ├── portail/               # Portail parents
│   │   ├── reports/               # Rapports et exports
│   │   ├── school_settings/       # Paramètres école (SchoolInfo)
│   │   ├── students/              # Gestion des élèves
│   │   ├── subjects/              # Matières et affectations
│   │   ├── super_admin/           # Console super-administrateur
│   │   ├── teachers/              # Gestion des enseignants
│   │   └── tenants/               # Modèles multi-tenant (Ecole, Domaine…)
│   ├── config/                    # Configuration Django
│   │   ├── settings.py            # Paramètres principaux
│   │   ├── urls.py                # Routage principal
│   │   ├── middleware.py          # Middlewares (tenant, onboarding, abonnement…)
│   │   ├── context_processors.py  # Inject. SchoolInfo, PlatformSettings
│   │   └── email_backend.py       # Backend e-mail dynamique (SMTP / console)
│   ├── templates/                 # Templates HTML globaux
│   ├── static/                    # Fichiers statiques sources
│   ├── staticfiles/               # Fichiers statiques collectés (généré)
│   ├── media/                     # Uploads (logos, photos…)
│   ├── logs/                      # Logs applicatifs
│   ├── manage.py
│   └── requirements.txt
├── scripts/
│   └── start.sh                   # Script de démarrage complet
├── requirements.txt               # Alias → school_app/requirements.txt
└── README.md                      # Ce fichier
```

---

## 11. Applications Django

### Applications schéma public (partagées)

| App | Rôle |
|---|---|
| `tenants` | Modèles Ecole, EcoleDomain, AdminEcole, AnnuaireUtilisateur, PlanAbonnement |
| `super_admin` | Console super-admin, PlatformSettings (SMTP, identité plateforme), corbeille |
| `onboarding` | Assistant de configuration initiale (5 étapes) |

### Applications schéma tenant (par école)

| App | Rôle |
|---|---|
| `accounts` | CustomUser, rôles (admin_ecole, préfet, enseignant, secrétariat) |
| `dashboard` | Tableau de bord avec statistiques |
| `students` | Élèves, tuteurs |
| `teachers` | Enseignants et profils |
| `classes` | AnneeScolaire, Section, Niveau, Classe |
| `subjects` | Matières, MatiereClasse (affectation matière→classe→enseignant) |
| `bulletin` | Modèles de bulletins officiels RDC (maxima 20/30/60) |
| `grades` | Saisie des notes (4 périodes + examens) |
| `reports` | Rapports PDF, résultats, classements |
| `school_settings` | SchoolInfo (identité école, logo, PWA) |
| `planning` | CreneauHoraire, SeanceHoraire, Salle |
| `notifications` | Notifications in-app avec cloche et drawer |
| `portail` | Portail parents (QR, activation, consultation bulletins) |
| `carte_eleve` | Génération de cartes d'élèves |

---

## 12. Assistant de configuration initiale (Onboarding)

Déclenché automatiquement à la **première connexion** de l'administrateur d'école.

| Étape | Page | Description |
|---|---|---|
| 1 | `/onboarding/etape1/` | Changement du mot de passe temporaire |
| 2 | `/onboarding/etape2/` | Nom, type d'établissement, année scolaire, localisation, logo |
| 3 | `/onboarding/etape3/` | Récapitulatif et vérification des données saisies |
| 4 | `/onboarding/etape4/` | Lecture et acceptation des CGU (v3.0) |
| 5 | `/onboarding/termine/` | Page de bienvenue + accès au tableau de bord |

La progression est persistante (reprise à l'étape courante si interruption). Les données de l'étape 2 sont sauvegardées dans `SchoolInfo` **dans le schéma propre à l'école**.

---

## 13. Planning hebdomadaire

Accessible via **Planning → Créneaux horaires** (réservé au préfet et au secrétariat).

### Flux de configuration

1. **Définir les créneaux** (`/planning/creneaux/`) :
   - Sélectionnez le jour et le type (Cours / Repos / Récréation / Prière / Repas)
   - Indiquez l'heure de début et de fin
   - Utilisez les **raccourcis horaires typiques RDC** pour aller vite
   - Le libellé est généré automatiquement si laissé vide

2. **Créer les salles** (`/planning/salles/`) : optionnel mais recommandé

3. **Affecter les cours** (`/planning/`) :
   - Vue grille hebdomadaire filtrée par classe ou enseignant
   - Cliquez sur **Nouvelle séance** pour affecter une matière/classe à un créneau
   - Détection automatique des **conflits** (même classe, même enseignant, même salle)

### Types de créneaux

| Type | Couleur | Comportement |
|---|---|---|
| Cours | Bleu | Peut accueillir une séance |
| Repos / Pause | Gris | **Bloqué** — pas d'affectation possible |
| Récréation | Vert | Bloqué |
| Prière / Recueillement | Violet | Bloqué |
| Repas | Ambre | Bloqué |

---

## 14. Portail parents

Accessible sur `/portail/` (domaine de l'école ou sous-domaine configuré).

### Flux d'activation

1. L'élève reçoit sa **carte élève** avec un QR code
2. Le parent scanne le QR → page d'activation du compte
3. Il choisit un code d'accès à 4 chiffres
4. Il peut ensuite consulter les résultats et bulletins

---

## 15. Super-admin — Console plateforme

URL : `/super-admin/login/`

| Section | Description |
|---|---|
| **Dashboard** | Statistiques réseau (écoles, onboarding, incidents) |
| **Écoles** | CRUD + suspension + envoi des identifiants par e-mail |
| **Corbeille** | Écoles supprimées — restauration ou suppression définitive |
| **Plans** | Gestion des plans d'abonnement |
| **Communications** | Annonces plateforme |
| **Maintenance** | Mode maintenance global |
| **Paramètres** | Identité plateforme, logo, SMTP e-mail, couleur principale |
| **Profil** | 2FA (TOTP), codes de récupération |

### Paramètres plateforme

Toutes les modifications des paramètres (nom du site, logo, couleur, SMTP) sont **appliquées immédiatement** sur l'ensemble de la plateforme via le context processor `platform_settings_ctx`.

---

## 16. Déploiement en production

### Variables obligatoires

```dotenv
DJANGO_SECRET_KEY=<clé-secrète-aléatoire-50+-caractères>
DJANGO_DEBUG=False
DJANGO_SITE_URL=https://votre-domaine.com
DATABASE_URL=postgres://user:password@host:5432/sgn_db
```

### Checklist pré-déploiement

- [ ] `DJANGO_DEBUG=False`
- [ ] `DJANGO_SECRET_KEY` unique et sécurisée
- [ ] HTTPS configuré (HTTPS obligatoire pour les cookies de session)
- [ ] SMTP configuré et testé via la console super-admin
- [ ] Tous les mots de passe de test changés
- [ ] `python3 manage.py collectstatic` exécuté
- [ ] Backup de la base de données configuré

### Déploiement Replit

1. Assurez-vous que tous les Secrets sont configurés
2. Cliquez sur **Publish** dans le menu Replit
3. La plateforme crée un environnement de production isolé

---

## 17. Procédures de test

### Test de la connexion super-admin

```bash
curl -c cookies.txt -b cookies.txt \
  -X POST http://localhost:8000/super-admin/login/ \
  -d "email=superadmin@test.local&password=SuperAdmin@2025!"
```

### Test des endpoints de notification (AJAX)

```bash
# Depuis un navigateur connecté — ou via curl avec session cookie
curl -b cookies.txt http://localhost:8000/notifications/count/
# Réponse attendue : {"count": 0}

curl -b cookies.txt http://localhost:8000/notifications/recentes/
# Réponse attendue : {"notifications": [...], "nb_non_lues": 0}
```

### Test de l'envoi e-mail

Via l'interface super-admin :
1. `/super-admin/parametres/` → section SMTP
2. Renseignez une adresse de test
3. Cliquez **Envoyer un e-mail test**
4. Vérifiez votre boîte de réception

En ligne de commande :
```bash
cd school_app
python3 manage.py shell -c "
from django.core.mail import send_mail
send_mail('Test SGN', 'Bonjour depuis EducNet', 'noreply@test.local', ['votre@email.com'])
print('OK')
"
```

### Test de l'onboarding

1. Connectez-vous avec `admin@ecoletest.local` / `Admin@Ecole2025!`
2. Si l'onboarding est marqué complet, réinitialisez via :
```bash
cd school_app
python3 manage.py shell -c "
from tenants.models import AdminEcole
a = AdminEcole.objects.get(email='admin@ecoletest.local')
a.onboarding_step = 0
a.ecole.onboarding_complete = False
a.ecole.save()
a.save()
print('Onboarding réinitialisé')
"
```

### Vérification migrations

```bash
cd school_app
python3 manage.py showmigrations          # Lister toutes les migrations
python3 manage.py migrate --check         # Vérifier sans appliquer
```

### Lancer les system checks Django

```bash
cd school_app
python3 manage.py check
# Résultat attendu : System check identified no issues (0 silenced).
```

---

## 18. Problèmes courants (FAQ)

### `ModuleNotFoundError: No module named 'django'`

```bash
pip install -r school_app/requirements.txt
```

Sur Replit, utilisez le panneau **Packages** pour installer les dépendances.

### La page affiche une erreur 500 après modification des paramètres

Vérifiez les logs : `school_app/logs/sgn.log`

```bash
tail -50 school_app/logs/sgn.log
```

### Les e-mails n'arrivent pas (SMTP configuré)

1. Vérifiez que **smtp_actif = True** dans les paramètres super-admin
2. Pour Gmail : utilisez un **mot de passe d'application** (pas votre mot de passe principal)
3. Pour Gmail : activez l'accès IMAP dans les paramètres Google
4. Testez avec le bouton **Envoyer un e-mail test** dans `/super-admin/parametres/`
5. Consultez les logs : `school_app/logs/sgn.log`

### `django_tenants` — Erreur de schéma

```
ProgrammingError: relation "..." does not exist
```

Le schéma tenant n'est pas créé. Relancez :
```bash
cd school_app
python3 manage.py seed_test_school
```

### La cloche de notifications ne se met pas à jour

Vérifiez que vous êtes connecté avec un compte Django classique (préfet, enseignant, secrétariat). Le super-admin utilise son propre système de session et n'a pas accès aux notifications école.

### `CSRF verification failed`

Vérifiez que `CSRF_TRUSTED_ORIGINS` dans `settings.py` contient votre domaine de production.

---

## Licence

Usage interne — Plateforme EducNet © 2025–2026. Tous droits réservés.

---

*Généré le 30 juillet 2026 — Version 3.1 — EducNet*
