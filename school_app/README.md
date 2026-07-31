# EducNet — Système de Gestion Scolaire

Plateforme web **multi-tenant** de gestion scolaire pour les établissements de la République Démocratique du Congo.  
Bulletins officiels MEPSP · Planning hebdomadaire · Portail parents · Carte élève · Module comptable · Gestion multi-écoles.

**Version 3.1 — Juillet 2026**

---

## Sommaire

1. [Stack technique](#1-stack-technique)
2. [Démarrage rapide (Replit)](#2-démarrage-rapide-replit)
3. [Variables d'environnement](#3-variables-denvironnement)
4. [Architecture multi-tenant](#4-architecture-multi-tenant)
5. [Modules disponibles](#5-modules-disponibles)
6. [Comptes de test](#6-comptes-de-test)
7. [Données de démonstration](#7-données-de-démonstration)
8. [Structure du projet](#8-structure-du-projet)
9. [Déploiement production](#9-déploiement-production)
10. [FAQ](#10-faq)

---

## 1. Stack technique

| Composant | Technologie |
|---|---|
| Backend | Django 6.x (Python 3.12) |
| Multi-tenancy | django-tenants 3.x (schémas PostgreSQL) |
| Base de données | PostgreSQL (production) · SQLite (dev) |
| Frontend | Bootstrap 5.3 · Bootstrap Icons · JS minimal |
| PDF | ReportLab |
| Fichiers statiques | WhiteNoise |
| Auth | Session Django + backend email |
| 2FA super-admin | PyOTP (TOTP) |
| QR codes | qrcode |
| E-mail | SMTP configurable ou console |

---

## 2. Démarrage rapide (Replit)

Le workflow **`SGN Django`** démarre tout automatiquement :
1. Installation des dépendances Python
2. Migrations (schémas public + tenant)
3. Seed des données de test
4. Collecte des fichiers statiques
5. Démarrage du serveur sur `$PORT`

Aucune configuration manuelle requise. Consultez la Webview directement.

---

## 3. Variables d'environnement

| Variable | Description | Défaut |
|---|---|---|
| `DATABASE_URL` | URL PostgreSQL complète | — (SQLite si absent) |
| `SECRET_KEY` | Clé secrète Django | — (obligatoire en prod) |
| `SESSION_SECRET` | Secret sessions | idem SECRET_KEY |
| `DEBUG` | Mode debug | `True` en dev |
| `ALLOWED_HOSTS` | Hôtes autorisés | `*` en dev |
| `EMAIL_HOST` | Serveur SMTP | console si absent |
| `EMAIL_HOST_USER` | Utilisateur SMTP | — |
| `EMAIL_HOST_PASSWORD` | Mot de passe SMTP | — |
| `EMAIL_PORT` | Port SMTP | `587` |
| `EMAIL_USE_TLS` | TLS | `True` |

> Sur Replit, `DATABASE_URL` est fourni par l'intégration PostgreSQL.

---

## 4. Architecture multi-tenant

```
PostgreSQL
├── Schéma public  (données plateforme)
│   ├── Tenant / Ecole
│   ├── AdminEcole
│   ├── SuperAdmin
│   ├── AnnuaireUtilisateur
│   ├── PlanAbonnement
│   └── DemandeAbonnement / PaiementPlateforme
│
└── Schéma ecole_<slug>  (données par école)
    ├── CustomUser  (préfet, enseignant, secrétariat, comptable)
    ├── Eleve, Classe, Matiere, Note
    ├── TypeFrais, Paiement, Facture
    ├── SeanceHoraire, CreneauHoraire, Salle
    ├── PortailAcces, CarteConfig
    └── SchoolInfo, AnneeScolaire
```

Chaque école est **strictement isolée** dans son schéma. Les données d'une école ne sont jamais accessibles depuis une autre.

---

## 5. Modules disponibles

### Côté école

| Module | Rôles | Description |
|---|---|---|
| **Dashboard** | Tous | Vue d'ensemble : stat-cards, alertes, accès rapide |
| **Élèves** | Préfet, Secrétariat | CRUD élèves, photo, matricule, inscription |
| **Classes** | Préfet | Sections, niveaux, classes, année scolaire |
| **Matières** | Préfet | Matières, maxima, affectations enseignant–classe |
| **Notes** | Enseignant | Saisie des notes par période (1P/2P/3P/4P/EXAM) |
| **Bulletins** | Préfet, Secrétariat | Génération PDF officielle MEPSP, clôture d'année |
| **Planning** | Préfet | Grille horaire hebdomadaire, salles, séances |
| **Comptable** | Comptable | Types de frais, encaissement, historique, factures PDF |
| **Portail parents** | Préfet | QR code → activation → code PIN → résultats |
| **Carte élève** | Secrétariat | Génération de cartes élèves (3 modèles) |
| **Paramètres** | Admin | Infos école, logo, SMTP, thème |
| **Onboarding** | Admin | Assistant de configuration initiale (4 étapes) |

### Côté plateforme (super-admin)

| Module | Description |
|---|---|
| **Gestion des écoles** | Créer, suspendre, renouveler les tenants |
| **Plans d'abonnement** | CRUD plans (mensuel, trimestriel, annuel) |
| **Paiements plateforme** | Suivi des paiements d'abonnement |
| **Annonces** | Diffusion aux administrateurs d'école |
| **Journal des opérations** | Audit trail complet |

---

## 6. Comptes de test

### PostgreSQL (seed_test_school)

| Rôle | Email | Mot de passe | Accès |
|---|---|---|---|
| Super-admin | superadmin@test.local | SuperAdmin@2025! | `/super-admin/` |
| Admin-école | admin@ecoletest.local | Admin@Ecole2025! | `/dashboard/` |
| Préfet | prefet@ecoletest.local | Prefet@Ecole2025! | `/dashboard/` |
| Enseignant | enseignant@ecoletest.local | Enseignant@2025! | `/dashboard/` |
| Secrétariat | secretariat@ecoletest.local | Secretariat@2025! | `/dashboard/` |
| Comptable | comptable@ecoletest.local | Comptable@2025! | `/dashboard/` |

### SQLite (seed_sqlite_users)

Mêmes credentials, adaptés pour fonctionner sans PostgreSQL.

---

## 7. Données de démonstration

Le script `seed_test_school` crée automatiquement :

- **École** : École Primaire Saint-Gabriel (Kinshasa/Ngaliema)
- **Année scolaire** : 2025-2026
- **3 sections** : Scientifique, Littéraire, Commerciale et Gestion
- **6 niveaux** : 1ère à 6ème Année
- **8 classes** + **12 matières** + **37 affectations**
- **20 élèves** avec notes réalistes (1P + 2P)
- **5 types de frais** (Minerval, Examen, Tenue, Bibliothèque, APEEP)
- **Paiements** : historique réaliste pour tous les élèves (partiels et complets)
- **Factures** générées automatiquement
- **Planning** : 6 salles, 27 créneaux horaires, séances planifiées
- **Paramètres école** : infos complètes (SchoolInfo)

---

## 8. Structure du projet

```
school_app/
├── apps/
│   ├── abonnement/      # TypeFrais, Paiement, Facture
│   ├── accounts/        # CustomUser, authentification email
│   ├── bulletin/        # Génération bulletins PDF MEPSP
│   ├── carte_eleve/     # Cartes élèves (3 modèles)
│   ├── classes/         # AnneeScolaire, Section, Niveau, Classe
│   ├── comptable/       # Module caisse : encaissement, historique
│   ├── dashboard/       # Vue d'accueil par rôle
│   ├── grades/          # Modèle Note
│   ├── notifications/   # Système de notifications internes
│   ├── onboarding/      # Assistant de configuration initiale (4 étapes)
│   ├── planning/        # Grille horaire, salles, séances
│   ├── portail/         # Portail parents QR
│   ├── reports/         # Rapports analytiques
│   ├── school_settings/ # SchoolInfo, configuration SMTP
│   ├── students/        # Student, Tuteur
│   ├── subjects/        # Matiere, MatiereClasse
│   ├── super_admin/     # Console plateforme
│   ├── teachers/        # Profil enseignant
│   └── tenants/         # Ecole, AdminEcole, AnnuaireUtilisateur
├── config/
│   └── settings.py      # Configuration Django
├── templates/           # Templates globaux (base.html, sidebars par rôle)
├── static/              # CSS, JS, images
└── manage.py
```

---

## 9. Déploiement production

1. Configurer les secrets : `SECRET_KEY`, `DATABASE_URL`, variables SMTP
2. `DEBUG=False`, `ALLOWED_HOSTS=votre-domaine.com`
3. Lancer : `python manage.py migrate --run-syncdb`
4. Lancer : `python manage.py collectstatic --noinput`
5. Serveur WSGI recommandé : **Gunicorn** + **Nginx**

> Sur Replit : cliquer **Déployer** — le workflow gère tout automatiquement.

---

## 10. FAQ

**Q : L'application démarre sur SQLite mais les schémas multi-tenant ne fonctionnent pas.**  
R : `django-tenants` nécessite PostgreSQL. En SQLite, la multi-tenancy est simulée par le seed `seed_sqlite_users`. Pour un vrai test multi-tenant, utilisez une base PostgreSQL.

**Q : Comment créer une nouvelle école ?**  
R : Connectez-vous en tant que super-admin → Console plateforme → Créer une école. L'assistant onboarding guide l'admin de la nouvelle école.

**Q : Les emails ne partent pas.**  
R : Vérifiez les variables `EMAIL_HOST*`. Sans configuration, les emails s'affichent dans la console du serveur.

**Q : Comment régénérer les données de test ?**  
R : `python manage.py seed_test_school` est idempotent — relancez-le sans risque de duplication.

**Q : Le portail parents ne s'active pas.**  
R : Le portail nécessite que le préfet publie les résultats d'une classe. Allez dans Portail → Publications → activer une classe et une période.
