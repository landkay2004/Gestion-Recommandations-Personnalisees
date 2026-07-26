# 🚀 PLAN D'ACTION MULTI-TENANT (Démarrage rapide)

## 📊 Vue d'ensemble

**Objectif** : Transformer votre app mono-tenant UDBL en **plateforme multi-tenant** avec super-admin

**Durée estimée** : 6-10 semaines (par phase)

**Effort** : 🔴🔴🔴 Modéré à Important

---

## ⏭️ Phase 1 : Foundation (Semaine 1-2)

### Étape 1 : Créer l'app "tenants"

```bash
python manage.py startapp tenants
```

### Étape 2 : Ajouter à INSTALLED_APPS

```python
# settings.py
INSTALLED_APPS = [
    # ...
    'tenants',  # NOUVEAU
]
```

### Étape 3 : Copier les modèles

📁 Créer : `tenants/models.py`

Copier depuis `MULTI_TENANT_DOCUMENTATION.md` :
- ✅ Model `Organization`
- ✅ Model `SubscriptionPlan`
- ✅ Model `Subscription`
- ✅ Model `Invoice`

### Étape 4 : Migrations

```bash
python manage.py makemigrations tenants
python manage.py migrate tenants
```

---

## ⏭️ Phase 2 : Modifier les modèles existants (Semaine 3-5)

### ÉTAPE A : Mettre à jour CustomUser

**Fichier** : `accounts/models.py`

```python
# Ajouter à CustomUser :

organization = models.ForeignKey(
    'tenants.Organization', 
    on_delete=models.CASCADE, 
    related_name='users',
    null=True,
    blank=True
)

ROLE_CHOICES = [
    ('super_admin', 'Super Administrateur'),  # NOUVEAU
    ('admin', 'Administrateur'),               # NOUVEAU
    ('prefet', 'Préfet des études'),
    ('enseignant', 'Enseignant'),
]

is_super_admin = models.BooleanField(default=False, db_index=True)  # NOUVEAU
```

Migration :

```bash
python manage.py makemigrations accounts
python manage.py migrate
```

---

### ÉTAPE B : Ajouter `organization` aux modèles clés

**Ordre d'exécution :**

#### 1️⃣ Student

```python
# students/models.py

class Student(models.Model):
    organization = models.ForeignKey(
        'tenants.Organization',
        on_delete=models.CASCADE,
        related_name='students'
    )
    # ... reste du modèle
```

```bash
python manage.py makemigrations students
python manage.py migrate
```

#### 2️⃣ Teacher

```python
# teachers/models.py

class Teacher(models.Model):
    organization = models.ForeignKey(
        'tenants.Organization',
        on_delete=models.CASCADE,
        related_name='teachers'
    )
    # ... reste du modèle
```

```bash
python manage.py makemigrations teachers
python manage.py migrate
```

#### 3️⃣ Classe

```python
# classes/models.py

class Classe(models.Model):
    organization = models.ForeignKey(
        'tenants.Organization',
        on_delete=models.CASCADE,
        related_name='classes'
    )
    # ... reste du modèle
```

#### 4️⃣ Autres modèles importants

- Grade (grades/models.py)
- Matiere (subjects/models.py)
- Bulletin (bulletin/models.py)
- Note (grades/models.py)

**Commande complète** :

```bash
# Faire toutes les migrations
python manage.py makemigrations

# Migrer
python manage.py migrate
```

---

## ⏭️ Phase 3 : Middleware & Permissions (Semaine 6)

### Fichier 1 : `tenants/middleware.py`

```python
from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from .models import Organization

class TenantMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Ignorer les chemins statiques
        if request.path.startswith(('/static/', '/media/')):
            return None
        
        # Pour utilisateurs connectés
        if request.user.is_authenticated:
            if hasattr(request.user, 'is_super_admin') and request.user.is_super_admin:
                request.organization = None
            else:
                request.organization = request.user.organization
        else:
            request.organization = None
        
        return None
```

### Fichier 2 : `tenants/permissions.py`

```python
from rest_framework import permissions

class IsOrganizationAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return (request.user.is_authenticated and 
                request.user.organization and
                request.user.role == 'admin')

class IsSuperAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return (request.user.is_authenticated and 
                hasattr(request.user, 'is_super_admin') and
                request.user.is_super_admin)

class IsInSameOrganization(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.organization == request.user.organization
```

### Fichier 3 : `tenants/utils.py`

```python
def get_organization_from_request(request):
    return getattr(request, 'organization', None)

def filter_by_organization(queryset, request):
    org = get_organization_from_request(request)
    if org:
        return queryset.filter(organization=org)
    return queryset
```

### Ajouter Middleware à settings.py

```python
# settings.py

MIDDLEWARE = [
    # ... middlewares existants
    'tenants.middleware.TenantMiddleware',  # AJOUTER ICI
]
```

---

## ⏭️ Phase 4 : Super-Admin (Semaine 7-8)

### Créer l'app super-admin

```bash
python manage.py startapp superadmin
```

### Fichier : `superadmin/views.py`

```python
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, DetailView
from django.core.exceptions import PermissionDenied
from tenants.models import Organization, Subscription, Invoice

@login_required
def dashboard(request):
    if not request.user.is_super_admin:
        raise PermissionDenied()
    
    context = {
        'total_organizations': Organization.objects.count(),
        'active_subscriptions': Subscription.objects.filter(is_active=True).count(),
        'organizations': Organization.objects.all(),
        'invoices': Invoice.objects.all().order_by('-date_issued')[:10],
    }
    return render(request, 'superadmin/dashboard.html', context)
```

### Fichier : `superadmin/urls.py`

```python
from django.urls import path
from . import views

app_name = 'superadmin'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('organizations/', views.organization_list, name='org_list'),
    path('organizations/<slug:slug>/', views.organization_detail, name='org_detail'),
    path('invoices/', views.invoice_list, name='invoices'),
]
```

### Ajouter à `school_app/urls.py`

```python
urlpatterns = [
    # ... URLs existantes
    path('superadmin/', include('superadmin.urls')),
]
```

---

## ⏭️ Phase 5 : Données de test (Semaine 8)

### Fichier : `tenants/management/commands/init_tenants.py`

```python
from django.core.management.base import BaseCommand
from tenants.models import Organization, SubscriptionPlan, Subscription
from accounts.models import CustomUser
from datetime import date, timedelta

class Command(BaseCommand):
    help = 'Initialise les données multi-tenant'
    
    def handle(self, *args, **options):
        # Créer plans
        plans = {
            'free': SubscriptionPlan.objects.get_or_create(
                name='Free',
                defaults={
                    'description': 'Plan gratuit',
                    'price': 0,
                    'max_students': 100,
                    'max_teachers': 5,
                    'max_classes': 5,
                    'max_users': 10,
                }
            )[0],
            'premium': SubscriptionPlan.objects.get_or_create(
                name='Premium',
                defaults={
                    'description': 'Plan premium',
                    'price': 99.99,
                    'max_students': 1000,
                    'max_teachers': 50,
                    'max_classes': 50,
                    'max_users': 100,
                }
            )[0],
        }
        
        # Créer une org test
        org, created = Organization.objects.get_or_create(
            slug='udbl-test',
            defaults={
                'name': 'UDBL Test',
                'email': 'test@udbl.cd',
                'phone': '+243812345678',
                'city': 'Lubumbashi',
                'plan': 'premium',
            }
        )
        
        # Créer subscription
        Subscription.objects.get_or_create(
            organization=org,
            defaults={
                'plan': plans['premium'],
                'end_date': date.today() + timedelta(days=365),
                'payment_method': 'manual',
            }
        )
        
        # Créer super-admin
        CustomUser.objects.get_or_create(
            username='superadmin',
            defaults={
                'email': 'admin@system.com',
                'is_super_admin': True,
                'role': 'super_admin',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        
        self.stdout.write(self.style.SUCCESS('✅ Données initialisées'))
```

### Commande

```bash
python manage.py init_tenants
```

---

## 🧪 Tests (Semaine 9)

### Créer `tenants/tests.py`

```python
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from .models import Organization, Subscription, SubscriptionPlan
from datetime import date, timedelta

User = get_user_model()

class OrganizationTestCase(TestCase):
    def setUp(self):
        self.plan = SubscriptionPlan.objects.create(
            name='Test Plan',
            price=50,
            max_students=100,
            max_teachers=10,
        )
        
        self.org = Organization.objects.create(
            slug='test-org',
            name='Test Organization',
            email='test@org.com',
            phone='1234567890',
            city='Test City',
        )
        
        self.subscription = Subscription.objects.create(
            organization=self.org,
            plan=self.plan,
            end_date=date.today() + timedelta(days=365),
        )
    
    def test_organization_creation(self):
        self.assertEqual(self.org.name, 'Test Organization')
        self.assertTrue(self.org.subscription.is_active)
    
    def test_subscription_days_remaining(self):
        days = self.subscription.days_remaining
        self.assertIsNotNone(days)
        self.assertGreater(days, 0)
```

### Lancer les tests

```bash
python manage.py test tenants
python manage.py test accounts
python manage.py test students
# etc...
```

---

## 📋 Checklist finale

### Avant déploiement

- [ ] Toutes les migrations appliquées
- [ ] Tests unitaires passent
- [ ] Super-admin dashboard fonctionnel
- [ ] Middleware fonctionne
- [ ] Permissions appliquées
- [ ] Données test créées
- [ ] Documentation mise à jour
- [ ] Backup BD complète

### Après déploiement

- [ ] Vérifier les logs
- [ ] Tester workflows critiques
- [ ] Monitor performance
- [ ] Support en place

---

## 🎯 Prochaines étapes optionnelles

### Phase 6 : Facturation Stripe (+ 3 semaines)
- Intégration Stripe
- Webhooks
- Factures PDF
- Email notifications

### Phase 7 : API REST (+ 2 semaines)
- Django REST Framework
- Token authentication
- Rate limiting

### Phase 8 : Frontend Multi-Tenant (+ 4 semaines)
- Organization selector
- Dashboard tenant-aware
- User management UI

---

## 💬 Questions avant de commencer ?

1. Voulez-vous garder les données UDBL existantes ?
2. URL structure : sous-domaines ou chemins ?
3. Intégration paiement dès le départ ?
4. Export de données pour clients ?

