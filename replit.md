# Système de Gestion des Notes — EducNet

Application web Django multi-tenant de gestion scolaire pour les établissements de la République Démocratique du Congo.  
Fonctionnalités : notes, bulletins officiels, planning, cartes d'élèves, portail parents, frais scolaires, abonnements.

---

## Run & Operate

- **Démarrer le serveur** : workflow `SGN Django` → `bash scripts/start.sh`
- **Démarrage complet** : `bash scripts/start.sh` — vérifie la base, applique les migrations, seed les comptes de test (étape séparée), collecte les fichiers statiques et démarre le serveur.
- **Migrations** : `cd school_app && python3 manage.py makemigrations && python3 manage.py migrate`
- **Seed PostgreSQL** : `cd school_app && python3 manage.py seed_test_school`
- **Seed SQLite** : `cd school_app && python3 manage.py seed_sqlite_users`
- **Super-admin** : `cd school_app && python3 manage.py seed_super_admin`

---

## Stack

- Backend  : **Django 6.0.7 (Python 3.12)**
- Frontend : **HTML5 + Bootstrap 5.3 + Bootstrap Icons + Inter**
- Base de données : **SQLite** (dev) / **PostgreSQL + django-tenants** (prod)
- Multi-tenant : **django-tenants** — schéma `public` (plateforme) + schéma par école
- PDF : ReportLab
- Fichiers statiques : WhiteNoise
- Email : backend SMTP configurable (TLS/STARTTLS 587 ou SSL 465)

---

## Comptes de test

| Rôle | Email | Mot de passe | URL |
|---|---|---|---|
| Super-admin | superadmin@test.local | SuperAdmin@2025! | /super-admin/ |
| Admin-école | admin@ecoletest.local | Admin@Ecole2025! | /dashboard/ |
| Préfet | prefet@ecoletest.local | Prefet@Ecole2025! | /dashboard/ |
| Enseignant | enseignant@ecoletest.local | Enseignant@2025! | /dashboard/ |
| Secrétariat | secretariat@ecoletest.local | Secretariat@2025! | /dashboard/ |
| Comptable | comptable@ecoletest.local | Secretariat@2025! | /comptable/ |

---

## Applications Django

| App | Rôle |
|---|---|
| `accounts` | Authentification, rôles, profils |
| `dashboard` | Tableau de bord avec statistiques |
| `students` | Gestion des élèves (photo, tuteurs) |
| `teachers` | Gestion des enseignants |
| `classes` | Années scolaires, sections, niveaux, classes |
| `subjects` | Matières, affectations, maxima |
| `bulletin` | Modèles de bulletins officiels RDC |
| `grades` | Saisie et consultation des notes |
| `reports` | Rapports élèves / enseignants / résultats |
| `planning` | Planning horaire avec filtre par classe |
| `school_settings` | Informations et paramètres de l'établissement |
| `portail` | Portail parents — QR code, activation, résultats |
| `carte_eleve` | Cartes élèves imprimables (12 modèles dont 7 premium) |
| `abonnement` | Frais scolaires, paiements, types de frais |
| `comptable` | Module comptable séparé — encaissement, historique |
| `tenants` | Gestion multi-tenant : écoles, plans, abonnements |
| `super_admin` | Interface plateforme (super-admin) |
| `notifications` | Système de notifications internes |

---

## Nouvelles fonctionnalités (v2)

### 🎨 Cartes élèves — 12 modèles (7 premium)
- **Modèles standard** : Classique, Moderne, Institutionnel, Minimaliste, Premium
- **Modèles premium** : Horizon ✦, Congo ✦, Émeraude ✦, Crépuscule ✦, **Rubis ✦**, **Océan ✦**, **Aurore ✦**
- Photo élève visible 80×98 px avec ombre portée
- Sélecteur visuel avec swatches + badge ✦ sur les modèles premium
- Modèles personnalisables (couleur principale + accent)
- Impression recto/verso au format carte de crédit exact

### 📅 Planning horaire — filtre dynamique par classe
- Sélecteur de classe en tête de formulaire
- Chargement AJAX des matières filtrées par classe sélectionnée
- Bouton "Ajouter une séance" conserve la classe filtrée (`?classe=…`)
- Clic sur case vide du planning pré-sélectionne la classe et le créneau

### 🔒 Sécurité renforcée
- `SECRET_KEY` aléatoire si absente (plus de clé insécurisée en dur)
- `ALLOWED_HOSTS` restreint en production
- Cookies sécurisés (`Secure`, `HttpOnly`, `SameSite`) en prod
- HSTS activé en production
- `SECURE_REFERRER_POLICY = strict-origin-when-cross-origin`
- Validateur `UserAttributeSimilarityValidator` sur les mots de passe

### 📧 Backend email amélioré
- Support SSL (port 465) et TLS/STARTTLS (port 587) auto-détecté
- Timeout SMTP configurable (10 s par défaut)
- Connexion recréée à chaque batch (thread-safe, pas de connexion dormante)
- Journalisation des envois et erreurs via `sgn.security`

### 💰 Module comptable séparé
- App `comptable` indépendante avec namespace `comptable:*`
- Dashboard comptable, nouveau paiement, historique
- Encaissement par élève avec reçu
- Rate limiting sur la page de login

### 🧾 Portail parents
- Activation QR code → code PIN → consultation résultats
- Accès manuel par le préfet (génération de lien portail)
- Archive des résultats par année scolaire

### 📊 Phase 3 — Clôture & archives
- Gestion des niveaux scolaires (niveaux par section)
- Clôture d'année avec promotion automatique
- Journal des opérations (audit trail)
- Archives des résultats du portail

---

## Structure bulletin officiel RDC

- **MAXIMA 20** : Religion, Éducation Civique & Morale, Éducation à la Vie, Informatique, Anglais, Dessin, Éducation Physique, Musique → TG max = 160
- **MAXIMA 30** : Géographie, Histoire, Sciences, Technologie → TG max = 240
- **MAXIMA 60** : Français, Mathématique → TG max = 480

Colonnes : 1ère P / 2ème P / EXAM / TOT (S1) + 3ème P / 4ème P / EXAM / TOT (S2) + T.G. + Repêchage

---

## Architecture multi-tenant

```
public (schéma PostgreSQL)
  ├── Tenant (école)
  ├── PlanAbonnement
  ├── AnnuaireUtilisateur
  └── AdminEcole / SuperAdmin

ecole_<slug> (schéma par école)
  ├── CustomUser (préfet, enseignant, secrétariat, comptable)
  ├── Eleve, Classe, Matiere, Note
  ├── Paiement, Facture (frais scolaires)
  └── CarteConfig, PortailAcces
```

---

## Design System

- Couleur principale : **Indigo #4D44B5** (Akademi-inspired)
- Font : **Inter** (Google Fonts)
- Thème clair/sombre (CSS variables + `data-theme="dark"`)
- Composants : stat-cards, tables, toasts, skeleton, progress bar, sidebars par rôle

---

## User preferences

- Technologies obligatoires : Django (Python), HTML5, CSS3, Bootstrap 5, Bootstrap Icons, JavaScript minimal, SQLite
- Pas de panneau Django `/admin`
- Tout l'administration via interface personnalisée
- Templates globaux dans `school_app/templates/` (pas dans les apps)
- App `comptable` utilise namespace `comptable:*`, templates dans `templates/comptable/`
