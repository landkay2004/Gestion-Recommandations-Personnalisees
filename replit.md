# Système de Gestion des Notes — RDC

Application web Django de gestion des notes et de publication des bulletins scolaires officiels pour les établissements de la République Démocratique du Congo.

## Run & Operate

- **Démarrer le serveur** : workflow `SGN Django` — `cd school_app && python3 manage.py runserver 0.0.0.0:8000`
- **Démarrage complet** : `bash scripts/start.sh` — vérifie la base, applique les migrations, collecte les fichiers statiques et démarre le serveur.
- **Migrations** : `cd school_app && python3 manage.py makemigrations && python3 manage.py migrate`
- **Données initiales** : déjà chargées (préfet, enseignant, classes, matières officielles)
- **Compte super-admin de test** : `cd school_app && python3 manage.py seed_super_admin` crée ou met à jour `superadmin@test.local` avec le mot de passe `SuperAdmin@2025!`.

## Stack

- Backend : **Django 6.0.7 (Python)**
- Frontend : **HTML5 + Bootstrap 5.3 + Bootstrap Icons**
- Base de données : **SQLite** (migratable vers PostgreSQL)
- PDF : ReportLab (prêt à implémenter)
- Fichiers statiques : WhiteNoise

## Comptes par défaut

| Utilisateur | Mot de passe | Rôle |
|---|---|---|
| `prefet` | `prefet2024` | Préfet des études |
| `enseignant1` | `ens2024` | Enseignant |

## Applications Django

| App | Rôle |
|---|---|
| `accounts` | Authentification, rôles (prefet / enseignant) |
| `dashboard` | Tableau de bord avec statistiques |
| `students` | Gestion des élèves |
| `teachers` | Gestion des enseignants |
| `classes` | Années scolaires, sections, classes |
| `subjects` | Matières et affectations matière→classe |
| `bulletin` | Modèles de bulletins officiels RDC |
| `grades` | Saisie et consultation des notes |
| `reports` | Rapports élèves / enseignants / résultats |
| `school_settings` | Informations de l'établissement |

## Structure bulletin officiel RDC

- **MAXIMA 20** : Religion, Éducation Civique & Morale, Éducation à la Vie, Informatique, Anglais, Dessin, Éducation Physique, Musique → TG max = 160
- **MAXIMA 30** : Géographie, Histoire, Sciences, Technologie → TG max = 240
- **MAXIMA 60** : Français, Mathématique → TG max = 480

Colonnes : 1ère P / 2ème P / EXAM / TOT (S1) + 3ème P / 4ème P / EXAM / TOT (S2) + T.G. + Repêchage

## Palette de couleurs

- Bleu foncé : `#0F172A`
- Bleu principal : `#2563EB`
- Blanc : `#FFFFFF`
- Gris clair : `#F8FAFC`

## User preferences

- Technologies obligatoires : Django (Python), HTML5, CSS3, Bootstrap 5, Bootstrap Icons, JavaScript minimal, SQLite
- Pas de panneau Django `/admin`
- Tout l'administration via interface personnalisée
