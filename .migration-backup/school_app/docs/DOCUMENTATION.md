# EducNet — Documentation technique complète

> Version 3.1 · Juillet 2026

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture système](#2-architecture-système)
3. [Authentification et sécurité](#3-authentification-et-sécurité)
4. [Module comptable](#4-module-comptable)
5. [Module onboarding](#5-module-onboarding)
6. [Portail parents](#6-portail-parents)
7. [Bulletins officiels MEPSP](#7-bulletins-officiels-mepsp)
8. [Planning hebdomadaire](#8-planning-hebdomadaire)
9. [Gestion des notes](#9-gestion-des-notes)
10. [Super-admin / Console plateforme](#10-super-admin--console-plateforme)
11. [Performance et optimisations](#11-performance-et-optimisations)
12. [Seed et données de test](#12-seed-et-données-de-test)
13. [Procédures de maintenance](#13-procédures-de-maintenance)

---

## 1. Vue d'ensemble

EducNet est une plateforme SaaS multi-tenant de gestion scolaire conçue pour les établissements de la RDC suivant les normes **MEPSP** (Ministère de l'Enseignement Primaire, Secondaire et Professionnel).

### Principes de conception

- **Isolation stricte** : chaque école vit dans son propre schéma PostgreSQL
- **Rôles clairs** : admin_ecole, préfet, enseignant, secrétariat, comptable
- **Zéro admin Django** : toute l'administration passe par l'interface personnalisée
- **Mobile-first** : Bootstrap 5.3, responsive sur tous les écrans
- **Offline-capable** : PWA avec manifest par école

---

## 2. Architecture système

### Schémas PostgreSQL

```
public
  Tenant (Ecole)           ← identifie chaque école
  AdminEcole               ← compte admin (public)
  SuperAdmin               ← compte plateforme
  AnnuaireUtilisateur      ← index email → schema pour la connexion
  PlanAbonnement
  DemandeAbonnement
  PaiementPlateforme

ecole_<slug>
  CustomUser               ← tous les comptes de l'école
  Student / Tuteur
  Classe / Section / Niveau / AnneeScolaire
  Matiere / MatiereClasse
  Note
  TypeFrais / Paiement / Facture
  CreneauHoraire / Salle / SeanceHoraire
  PortailConfig / PortailAcces / PublicationResultats
  CarteConfig
  SchoolInfo
  Notification
  JournalOperation
```

### Flux de connexion multi-tenant

```
1. POST /login/ { email, password }
2. Lookup AnnuaireUtilisateur.email → schema_name, type_compte
3. connection.set_tenant(ecole)
4. CustomUser.objects.get(email=...) dans le schéma tenant
5. Session : tenant_schema, user_id, user_role
6. Redirect → dashboard
```

---

## 3. Authentification et sécurité

### Comptes et rôles

| Rôle | Description | Accès |
|---|---|---|
| `super_admin` | Plateforme entière | Console super-admin |
| `admin_ecole` | Administrateur de l'école | Dashboard + tous modules |
| `prefet` | Gestion pédagogique | Élèves, classes, bulletins, planning, portail |
| `enseignant` | Saisie des notes | Notes de ses matières-classes |
| `secretariat` | Secrétariat | Élèves, cartes, bulletins |
| `comptable` | Finance | Frais, encaissement, historique |

### Décorateurs de protection

```python
@admin_ecole_required    # accounts/views.py
@prefet_required
@enseignant_required
@secretariat_required
@comptable_required
```

### Rate limiting

- Connexion école : 10 tentatives / 5 minutes par IP
- Connexion super-admin : 5 tentatives / 5 minutes par IP
- Implémenté avec un middleware simple (cache Django)

### 2FA super-admin

- TOTP via PyOTP (compatible Google Authenticator, Authy)
- Activé/désactivé depuis la console super-admin
- QR code de configuration généré à l'activation

---

## 4. Module comptable

### Workflow de paiement

```
1. Comptable → Recherche élève (AJAX dynamique)
2. Sélection de l'élève → Page encaissement
3. Affichage : état des frais (payés + impayés) + historique
4. Si frais impayés → formulaire de paiement
5. Validation → Paiement enregistré + Facture générée (FAC-YYYY-NNNN)
6. Redirect → Détail facture (avec PDF téléchargeable)
```

### Recherche dynamique (AJAX)

La vue `recherche_eleve` supporte deux modes :
- **HTML** (GET classique) : rendu complet de la page
- **JSON** (GET + `X-Requested-With: XMLHttpRequest`) : résultats instantanés

Debounce de 220ms côté client. Requête annulée si une nouvelle frappe intervient (AbortController).

### Calcul des frais — optimisation

`get_frais_a_payer(eleve)` utilise **2 requêtes SQL** au lieu de N :
1. Récupération des TypeFrais applicables (filtrage classe)
2. Agrégation des totaux payés en une seule requête via `values('type_frais_id').annotate(total=Sum(...))`

### Factures PDF

Générées avec ReportLab. Contenu :
- En-tête école (nom, logo)
- Infos élève (nom, matricule, classe)
- Tableau : désignation, montant total, payé ce jour, total payé, reste dû
- Mode de paiement + référence
- Signature automatique "Reçu officiel"

---

## 5. Module onboarding

### Étapes du wizard

| Étape | Page | Description |
|---|---|---|
| 1 | `etape1_password` | Changement du mot de passe temporaire |
| 2 | `etape2_config` | Configuration de l'école (nom, type, localisation, contact, logo) |
| 3 | `etape3_recapitulatif` | Vérification récapitulative |
| 4 | `etape4_conditions` | Acceptation des CGU |
| 5 | `termine` | Bienvenue + connexion automatique |

### Navigation (correction v3.1)

La navigation **Précédent** fonctionne correctement à toutes les étapes :
- Les vues ne redirigent plus automatiquement vers l'étape suivante si déjà complétée
- L'admin peut revenir à l'étape 1 ou 2 depuis n'importe quelle étape suivante
- Les modifications sont resauvegardées sans créer de doublons
- En cas d'erreur de sauvegarde à l'étape 2, le formulaire reste affiché avec le message d'erreur

### Persistance

`AdminEcole.onboarding_step` (entier 0–5) :
- `0` : pas commencé
- `1–4` : étapes validées
- `5` : onboarding complet (`onboarding_complete=True` sur l'Ecole)

---

## 6. Portail parents

### Flux d'activation

```
1. Préfet génère un QR code pour un élève
2. Parent scanne le QR → Page d'activation
3. Parent choisit un code PIN (4–8 chiffres)
4. Activation → PortailAcces créé (code haché bcrypt)
5. Parent accède aux résultats via code PIN
```

### Contrôle de publication

Le préfet contrôle finement ce qui est visible :
- Par classe (ex : uniquement 6ème Scientifique A)
- Par période (ex : uniquement résultats S1)
- Par année scolaire (archives disponibles)

### Sécurité

- Codes PIN hashés (bcrypt, jamais stockés en clair)
- Tokens QR à usage unique (invalidés après activation)
- Accès limité aux données de l'élève concerné uniquement

---

## 7. Bulletins officiels MEPSP

### Structure officielle

| Maxima | Matières |
|---|---|
| **20** | Religion, Éd. Civique, Éd. à la Vie, Informatique, Anglais, Dessin, Éd. Physique, Musique |
| **30** | Géographie, Histoire, Sciences, Technologie |
| **60** | Français, Mathématique |

### Colonnes du bulletin

`1P / 2P / EXAM / TOT(S1)` + `3P / 4P / EXAM / TOT(S2)` + `T.G.` + `Repêchage`

### Clôture d'année

1. Préfet lance la clôture → vérification que toutes les notes sont saisies
2. Calcul automatique des moyennes et décisions (admis/refusé/repêchage)
3. Promotion automatique vers le niveau supérieur (si option activée)
4. Journal d'opération créé (audit trail)

---

## 8. Planning hebdomadaire

### Modèles

- **Salle** : nom, capacité
- **CreneauHoraire** : jour (Lundi–Samedi), heure début/fin, type (cours/récré/repos/prière/repas)
- **SeanceHoraire** : créneau + matière-classe + salle + année scolaire

### Contraintes automatiques

- Conflit de classe : une classe ne peut avoir deux cours sur le même créneau
- Conflit d'enseignant : un enseignant ne peut enseigner dans deux classes simultanément

### Grille d'affichage

Vue HTML interactive : tableau jours × créneaux, colorisée par classe ou par enseignant.

---

## 9. Gestion des notes

### Périodes

`1P`, `2P`, `3P`, `4P`, `EXAM_S1`, `EXAM_S2`

### Workflow de saisie (enseignant)

1. Sélectionner la matière-classe
2. Saisir les notes par élève et par période
3. Enregistrement avec validation (0 ≤ note ≤ maxima)
4. Le préfet peut consulter en temps réel

### Validation

- Note ne peut pas dépasser le maxima de la matière
- Seul l'enseignant affecté à la matière-classe peut saisir
- Le préfet peut corriger toute note

---

## 10. Super-admin / Console plateforme

### Fonctionnalités

- **Écoles** : créer, éditer, suspendre, réactiver, renouveler l'abonnement
- **Plans** : créer/éditer les plans tarifaires
- **Annonces** : diffuser une notification à tous les admins d'école
- **Paiements** : suivi des paiements d'abonnement reçus
- **Journal** : historique complet des opérations plateforme

### Connexion super-admin

Route dédiée : `/super-admin/login/`  
Ne passe pas par l'AnnuaireUtilisateur — authentification directe sur `SuperAdmin`.  
2FA TOTP optionnel.

---

## 11. Performance et optimisations

### select_related / prefetch_related

Tous les querysets critiques utilisent `select_related` ou `prefetch_related` :

```python
# Historique paiements
Paiement.objects.select_related('eleve', 'eleve__classe', 'type_frais', 'facture', 'comptable')

# Recherche élèves
Student.objects.select_related('classe')

# Dashboard
Paiement.objects.select_related('eleve', 'type_frais', 'facture')
```

### Calcul frais optimisé

Avant : N requêtes (une par TypeFrais).  
Après : 2 requêtes (tous les types + agrégation groupée).

### Pagination

Toutes les listes utilisent `Paginator` avec `PER_PAGE = 20`.

### Indexes recommandés (production)

```sql
CREATE INDEX idx_paiement_eleve      ON paiement(eleve_id);
CREATE INDEX idx_paiement_date       ON paiement(date_paiement);
CREATE INDEX idx_student_nom         ON student(nom, postnom);
CREATE INDEX idx_student_matricule   ON student(matricule);
CREATE INDEX idx_note_eleve_periode  ON note(eleve_id, periode);
```

---

## 12. Seed et données de test

### Commandes disponibles

| Commande | Base | Description |
|---|---|---|
| `seed_test_school` | PostgreSQL | École complète avec tous les modules |
| `seed_sqlite_users` | SQLite | Comptes uniquement pour dev local |
| `seed_super_admin` | Les deux | Super-admin de test (idempotent) |

### Données créées par seed_test_school

- École, domaine, admin-école, 5 comptes utilisateurs
- Structure académique : 3 sections, 6 niveaux, 8 classes, 12 matières
- 20 élèves avec notes (1P + 2P)
- SchoolInfo configurée
- 5 types de frais + paiements historiques + factures
- 6 salles + 27 créneaux horaires + séances planifiées

### Idempotence

Toutes les opérations utilisent `get_or_create` — la commande peut être relancée sans risque.

---

## 13. Procédures de maintenance

### Réinitialiser les données de test

```bash
python manage.py seed_test_school
```

### Appliquer de nouvelles migrations

```bash
python manage.py migrate_schemas --shared      # schéma public
python manage.py migrate_schemas               # tous les tenants
```

### Créer une migration pour un modèle tenant

```bash
python manage.py makemigrations <app>
python manage.py migrate_schemas
```

### Exporter les données d'une école

```bash
python manage.py dumpdata --schema=ecole_<slug> > backup_ecole.json
```

### Logs applicatifs

- Fichier : `school_app/logs/sgn.log`
- Niveau INFO : connexions, paiements, opérations critiques
- Niveau WARNING : erreurs récupérables, données manquantes
- Niveau ERROR : erreurs non récupérables

### Vérifier la santé de l'application

```bash
python manage.py check --deploy
python manage.py seed_test_school --no-data --no-verify
```
