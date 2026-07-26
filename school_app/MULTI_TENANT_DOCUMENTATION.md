# 🏢 TRANSFORMATION MULTI-TENANT - DOCUMENTATION COMPLÈTE

## 📋 Table des matières
1. [Architecture Multi-Tenant](#architecture)
2. [Modèles de données](#modeles)
3. [Authentification & Autorisation](#auth)
4. [Gestion des abonnements](#abonnements)
5. [Super-Admin Dashboard](#super-admin)
6. [Plan d'implémentation](#plan)
7. [Migrations & Déploiement](#migrations)

---

## 🏗️ Architecture Multi-Tenant {#architecture}

### Concept actuel (Mono-tenant)
- ✅ Une seule école (UDBL)
- ✅ Une seule base de données
- ❌ Pas de séparation des données entre clients

### Concept futur (Multi-tenant)
- ✅ Plusieurs écoles/établissements
- ✅ Données isolées par établissement
- ✅ Abonnements avec différents plans
- ✅ Super-admin centralisé
- ✅ Facturation & maintenance

### Approches Multi-Tenant

#### **Option 1 : Shared Database + Schema Isolation (Row-Level Tenant ID)**
```
┌─────────────────────────────────────┐
│    PostgreSQL Database              │
├─────────────────────────────────────┤
│  - Students (tenant_id = 1)         │
│  - Students (tenant_id = 2)         │
│  - Students (tenant_id = 3)         │
└─────────────────────────────────────┘
✅ Simple | ✅ Performant | ⚠️ Moins isolé
```

#### **Option 2 : Separate Schemas (PostgreSQL Native)**
```
┌──────────────────┬──────────────────┬──────────────────┐
│   public schema   │  school_1 schema │  school_2 schema │
│  (superadmin)    │   (tables)       │   (tables)       │
└──────────────────┴──────────────────┴──────────────────┘
✅ Sécurisé | ⚠️ Complex | ✅ Maintenance aisée
```

#### **Option 3 : Separate Databases**
```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ school_1_db │  │ school_2_db │  │ school_3_db │
└─────────────┘  └─────────────┘  └─────────────┘
✅ Maximum isolation | ❌ Complexe | ❌ Coûteux
```

### **Recommandation : Option 1 (Row-Level Tenant ID)**
- ✅ Requiert peu de changements
- ✅ Performance maintenue
- ✅ Facile à scaler

---

## 📊 Modèles de données {#modeles}

### 1. Modèle Tenant

```python
# new_app: "tenants" / models.py

from django.db import models
from django.utils.timezone import now

class Organization(models.Model):
    """Représente une école/établissement (tenant)"""
    
    SUBSCRIPTION_PLANS = [
        ('free', 'Gratuit'),
        ('basic', 'Basic'),
        ('premium', 'Premium'),
        ('enterprise', 'Enterprise'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Actif'),
        ('suspended', 'Suspendu'),
        ('inactive', 'Inactif'),
    ]
    
    # Identifiant
    id = models.BigAutoField(primary_key=True)
    slug = models.SlugField(unique=True, max_length=100)
    
    # Informations de base
    name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    website = models.URLField(blank=True)
    
    # Adresse
    city = models.CharField(max_length=100)
    province = models.CharField(max_length=100)
    country = models.CharField(max_length=100, default='RDC')
    
    # Logo & Branding
    logo = models.ImageField(upload_to='organizations/', null=True, blank=True)
    theme_color = models.CharField(max_length=7, default='#1E293B')
    
    # Abonnement
    plan = models.CharField(max_length=20, choices=SUBSCRIPTION_PLANS, default='free')
    subscription_start = models.DateField()
    subscription_end = models.DateField(null=True, blank=True)
    subscription_active = models.BooleanField(default=True)
    
    # Statut
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Limites (selon plan)
    max_students = models.IntegerField(default=500)
    max_teachers = models.IntegerField(default=50)
    max_classes = models.IntegerField(default=30)
    max_users = models.IntegerField(default=100)
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    @property
    def days_remaining(self):
        if self.subscription_end:
            return (self.subscription_end - now().date()).days
        return None
    
    @property
    def is_trial(self):
        return self.plan == 'free'
```

### 2. Modèle Utilisateur Multi-Tenant

```python
# accounts/models.py (MODIFIÉ)

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('super_admin', 'Super Administrateur'),      # NEW
        ('admin', 'Administrateur'),                   # NEW
        ('prefet', 'Préfet des études'),
        ('enseignant', 'Enseignant'),
    ]
    
    # ── Tenant ──
    organization = models.ForeignKey(
        'tenants.Organization', 
        on_delete=models.CASCADE, 
        related_name='users',
        null=True,
        blank=True
    )
    
    # Le super_admin n'a pas d'organization
    # Les autres utilisateurs DOIVENT avoir une organization
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='enseignant', db_index=True)
    is_super_admin = models.BooleanField(default=False, db_index=True)
    
    # ── Existants ──
    telephone = models.CharField(max_length=20, blank=True)
    must_change_password = models.BooleanField(default=False)
    photo_profil = models.ImageField(upload_to='profils/', blank=True, null=True)
    bio = models.TextField(blank=True, default='')
    
    class Meta:
        indexes = [
            models.Index(fields=['organization', 'role']),
            models.Index(fields=['is_super_admin']),
        ]
    
    def is_super_admin(self):
        return self.role == 'super_admin'
    
    def is_organization_admin(self):
        return self.role == 'admin' and self.organization is not None
    
    def can_manage_organization(self):
        return self.is_super_admin() or self.is_organization_admin()
```

### 3. Ajouter tenant_id aux modèles existants

```python
# Tous les modèles doivent avoir :
from django.db import models
from tenants.models import Organization

class Student(models.Model):
    # ── NOUVEAU ──
    organization = models.ForeignKey(
        Organization, 
        on_delete=models.CASCADE, 
        related_name='students'
    )
    
    # ── Existants ──
    nom = models.CharField(max_length=100)
    postnom = models.CharField(max_length=100, blank=True)
    prenom = models.CharField(max_length=100, blank=True)
    # ... autres champs
    
    class Meta:
        ordering = ['nom', 'postnom', 'prenom']
        indexes = [
            models.Index(fields=['organization', 'classe']),
            models.Index(fields=['organization', 'matricule']),
        ]
        # Garantir l'unicité du matricule par tenant
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'matricule'],
                name='unique_student_matricule_per_org'
            )
        ]
```

### Modèles à modifier :
- ✅ `Student`
- ✅ `Teacher`
- ✅ `Classe`
- ✅ `Matiere`
- ✅ `Grade` (Note)
- ✅ `SchoolInfo` → `OrganizationSettings`
- ✅ Autres (Bulletin, Portail, etc.)

---

## 🔐 Authentification & Autorisation {#auth}

### Middleware Multi-Tenant

```python
# tenants/middleware.py

from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from .models import Organization

class TenantMiddleware(MiddlewareMixin):
    """
    Détermine le tenant à partir de :
    1. Sous-domaine (school1.app.com)
    2. Paramètre URL (/school/slug/)
    3. Session utilisateur
    """
    
    def process_request(self, request):
        # Ignorer les chemins statiques et admin
        if request.path.startswith(('/static/', '/media/', '/admin/')):
            return None
        
        # 1. Vérifier le sous-domaine
        host = request.get_host().split(':')[0]
        if '.' in host and host != 'localhost':
            subdomain = host.split('.')[0]
            try:
                organization = Organization.objects.get(slug=subdomain)
                request.organization = organization
                return None
            except Organization.DoesNotExist:
                return redirect('/404/')
        
        # 2. Vérifier l'URL (ex: /school/slug/)
        if 'org_slug' in request.resolver_match.kwargs:
            slug = request.resolver_match.kwargs['org_slug']
            try:
                organization = Organization.objects.get(slug=slug)
                request.organization = organization
                return None
            except Organization.DoesNotExist:
                return redirect('/404/')
        
        # 3. Vérifier la session (utilisateur connecté)
        if request.user.is_authenticated:
            if request.user.is_super_admin:
                request.organization = None
            else:
                request.organization = request.user.organization
            return None
        
        # Pas de tenant trouvé
        return redirect('/accounts/login/')
```

### Queryset Filtering

```python
# tenants/utils.py

def get_organization_from_request(request):
    """Helper pour obtenir le tenant depuis la requête"""
    return getattr(request, 'organization', None)

# Utilisation dans les vues
def student_list(request):
    org = get_organization_from_request(request)
    
    if not org:
        return redirect('/accounts/login/')
    
    students = Student.objects.filter(organization=org)
    # ...
```

### Permissions personnalisées

```python
# tenants/permissions.py

from rest_framework import permissions

class IsOrganizationAdmin(permissions.BasePermission):
    """Peut gérer l'organisation"""
    def has_permission(self, request, view):
        return (request.user.is_authenticated and 
                request.user.can_manage_organization())

class IsSuperAdmin(permissions.BasePermission):
    """Seulement super-admin"""
    def has_permission(self, request, view):
        return request.user.is_super_admin

class IsInSameOrganization(permissions.BasePermission):
    """L'utilisateur et l'objet appartiennent à la même org"""
    def has_object_permission(self, request, view, obj):
        user_org = request.user.organization
        obj_org = getattr(obj, 'organization', None)
        return user_org == obj_org
```

---

## 💳 Gestion des abonnements {#abonnements}

### Modèle Subscription

```python
# tenants/models.py

class SubscriptionPlan(models.Model):
    """Plans d'abonnement disponibles"""
    
    name = models.CharField(max_length=50)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    
    # Limites
    max_students = models.IntegerField()
    max_teachers = models.IntegerField()
    max_classes = models.IntegerField()
    max_users = models.IntegerField()
    
    # Durée (en jours)
    duration_days = models.IntegerField(default=365)
    
    # Fonctionnalités
    features = models.JSONField(default=dict)
    
    class Meta:
        ordering = ['price']
    
    def __str__(self):
        return self.name


class Subscription(models.Model):
    """Abonnement actif d'une organisation"""
    
    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name='subscription'
    )
    
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    
    # Dates
    start_date = models.DateField(auto_now_add=True)
    end_date = models.DateField()
    renewed_at = models.DateTimeField(null=True, blank=True)
    
    # Paiement
    payment_method = models.CharField(
        max_length=20,
        choices=[
            ('stripe', 'Stripe'),
            ('paypal', 'PayPal'),
            ('manual', 'Manuel'),
        ]
    )
    stripe_subscription_id = models.CharField(max_length=200, blank=True)
    
    # Statut
    is_active = models.BooleanField(default=True)
    auto_renew = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.organization.name} - {self.plan.name}"
    
    @property
    def is_expired(self):
        from django.utils.timezone import now
        return self.end_date < now().date()
    
    @property
    def days_remaining(self):
        from django.utils.timezone import now
        return (self.end_date - now().date()).days
    
    def renew(self, days=None):
        """Renouveler l'abonnement"""
        if days is None:
            days = self.plan.duration_days
        
        from datetime import timedelta
        from django.utils.timezone import now
        
        if self.is_expired:
            self.start_date = now().date()
        
        self.end_date = self.end_date + timedelta(days=days)
        self.renewed_at = now()
        self.save()
```

### Invoice & Payment Tracking

```python
# tenants/models.py

class Invoice(models.Model):
    """Facture d'abonnement"""
    
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='invoices'
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True
    )
    
    # Identifiant
    number = models.CharField(max_length=50, unique=True)
    
    # Montant
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    
    # Dates
    date_issued = models.DateField(auto_now_add=True)
    date_due = models.DateField()
    date_paid = models.DateField(null=True, blank=True)
    
    # Statut
    STATUS_CHOICES = [
        ('draft', 'Brouillon'),
        ('sent', 'Envoyée'),
        ('paid', 'Payée'),
        ('overdue', 'Retard'),
        ('cancelled', 'Annulée'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Items
    description = models.TextField()
    
    def __str__(self):
        return f"Invoice {self.number}"
    
    def mark_as_paid(self):
        from django.utils.timezone import now
        self.status = 'paid'
        self.date_paid = now().date()
        self.save()
```

---

## 👑 Super-Admin Dashboard {#super-admin}

### URL Structure

```python
# school_app/urls.py

urlpatterns = [
    # ── Super-Admin (pas de tenant) ──
    path('admin/superadmin/', include('superadmin.urls')),
    
    # ── Tenant-specific ──
    path('org/<slug:org_slug>/', include('tenants.urls')),
    
    # ── Routing multi-domaine ──
    path('dashboard/', include('tenants.tenant_urls')),
]
```

### Super-Admin Views

```python
# superadmin/views.py

from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, DetailView, UpdateView
from tenants.models import Organization, Subscription, Invoice
from django.utils.decorators import method_decorator

@method_decorator(login_required, name='dispatch')
class SuperAdminDashboard(ListView):
    """Dashboard principal super-admin"""
    template_name = 'superadmin/dashboard.html'
    context_object_name = 'organizations'
    
    def get_queryset(self):
        if not self.request.user.is_super_admin:
            raise PermissionDenied()
        return Organization.objects.all()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_organizations'] = Organization.objects.count()
        context['active_subscriptions'] = Subscription.objects.filter(is_active=True).count()
        context['revenue'] = Invoice.objects.filter(status='paid').aggregate(
            total=models.Sum('amount')
        )['total'] or 0
        context['pending_payments'] = Invoice.objects.filter(status='overdue').count()
        return context


class OrganizationManagementView(DetailView):
    """Gérer une organisation spécifique"""
    model = Organization
    template_name = 'superadmin/organization_detail.html'
    slug_field = 'slug'
    slug_url_kwarg = 'org_slug'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        org = self.get_object()
        context['subscription'] = org.subscription
        context['invoices'] = org.invoices.all()
        context['total_users'] = org.users.count()
        context['total_students'] = org.students.count()
        return context


class InvoiceListView(ListView):
    """Lister toutes les factures"""
    model = Invoice
    template_name = 'superadmin/invoices.html'
    context_object_name = 'invoices'
    paginate_by = 50
    
    def get_queryset(self):
        if not self.request.user.is_super_admin:
            raise PermissionDenied()
        return Invoice.objects.select_related('organization')
```

### Super-Admin Templates

```html
<!-- templates/superadmin/dashboard.html -->

{% extends "base.html" %}

{% block title %}Super-Admin Dashboard{% endblock %}

{% block content %}
<div class="container-fluid mt-4">
    <h1>📊 Super-Admin Dashboard</h1>
    
    <!-- KPIs -->
    <div class="row mb-4">
        <div class="col-md-3">
            <div class="card">
                <div class="card-body">
                    <h5 class="card-title">Organisations</h5>
                    <h2>{{ total_organizations }}</h2>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card">
                <div class="card-body">
                    <h5 class="card-title">Abonnements Actifs</h5>
                    <h2>{{ active_subscriptions }}</h2>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card">
                <div class="card-body">
                    <h5 class="card-title">Revenu Total</h5>
                    <h2>${{ revenue }}</h2>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card">
                <div class="card-body">
                    <h5 class="card-title">Paiements En Retard</h5>
                    <h2>{{ pending_payments }}</h2>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Organisations -->
    <h3>Organisations Enregistrées</h3>
    <table class="table">
        <thead>
            <tr>
                <th>Nom</th>
                <th>Plan</th>
                <th>Utilisateurs</th>
                <th>Statut</th>
                <th>Expiration</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for org in organizations %}
            <tr>
                <td>{{ org.name }}</td>
                <td><span class="badge">{{ org.plan }}</span></td>
                <td>{{ org.users.count }}</td>
                <td>
                    <span class="badge {% if org.status == 'active' %}badge-success{% else %}badge-danger{% endif %}">
                        {{ org.get_status_display }}
                    </span>
                </td>
                <td>{{ org.subscription_end }}</td>
                <td>
                    <a href="{% url 'superadmin:organization_detail' org.slug %}" class="btn btn-sm btn-primary">
                        Gérer
                    </a>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
```

---

## 📋 Plan d'implémentation {#plan}

### Phase 1 : Préparation (1-2 semaines)

**Tâches :**
- [ ] Créer app `tenants`
- [ ] Créer modèles Organization, SubscriptionPlan, Subscription, Invoice
- [ ] Migration initiale
- [ ] Créer super-admin seed data

**Commandes :**
```bash
python manage.py startapp tenants
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser --superuser
```

### Phase 2 : Modification des modèles existants (2-3 semaines)

**Tâches :**
- [ ] Ajouter `organization` ForeignKey à tous les modèles
- [ ] Créer des migrations progressives
- [ ] Mettre à jour les modèles en ordre de dépendance

**Ordre de modification :**
1. `Student`
2. `Teacher`
3. `Classe`
4. `Matiere`
5. `Grade`
6. `Bulletin`
7. Autres modèles

**Migration strategy :**
```bash
# Ajouter le champ nullable d'abord
python manage.py makemigrations
python manage.py migrate

# Créer une migration data pour assigner les organizations
python manage.py makemigrations --empty tenants --name assign_default_org

# Rendre le champ obligatoire
python manage.py makemigrations
python manage.py migrate
```

### Phase 3 : Authentification & Autorisation (1-2 semaines)

**Tâches :**
- [ ] Implémenter TenantMiddleware
- [ ] Créer permissions personnalisées
- [ ] Modifier les views existantes
- [ ] Ajouter tenant_id aux querysets

**Fichiers à créer :**
- `tenants/middleware.py`
- `tenants/permissions.py`
- `tenants/utils.py`

### Phase 4 : Super-Admin Interface (1-2 semaines)

**Tâches :**
- [ ] Créer app `superadmin`
- [ ] Implémenter views/dashboard
- [ ] Templates super-admin
- [ ] Admin customization (Jazzmin)

### Phase 5 : Facturation & Paiements (2-3 semaines)

**Intégrations :**
- [ ] Stripe integration
- [ ] PayPal integration
- [ ] Webhook handling
- [ ] Email notifications

### Phase 6 : Tests & Déploiement (1-2 semaines)

**Tâches :**
- [ ] Tests unitaires
- [ ] Tests d'intégration
- [ ] Tests de performance
- [ ] Documentation
- [ ] Déploiement staging
- [ ] Déploiement production

---

## 🔄 Migrations & Déploiement {#migrations}

### Migration Data (Exemple)

```python
# tenants/migrations/0002_migrate_existing_data.py

from django.db import migrations
from django.utils.text import slugify

def assign_default_org(apps, schema_editor):
    Organization = apps.get_model('tenants', 'Organization')
    Student = apps.get_model('students', 'Student')
    
    # Créer une org par défaut pour les données existantes
    default_org, created = Organization.objects.get_or_create(
        slug='default',
        defaults={
            'name': 'UDBL - Université Don Bosco',
            'email': 'contact@udbl.cd',
            'phone': '+243812345678',
            'city': 'Lubumbashi',
            'province': 'Katanga',
            'plan': 'enterprise',
        }
    )
    
    # Assigner tous les students à cette org
    Student.objects.filter(organization__isnull=True).update(
        organization=default_org
    )

def reverse_migrate(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('students', '0003_student_organization'),
        ('tenants', '0001_initial'),
    ]
    
    operations = [
        migrations.RunPython(assign_default_org, reverse_migrate),
    ]
```

### Déploiement Checklist

```
PRE-DEPLOYMENT
☐ Backup complet de la base de données
☐ Snapshot du serveur
☐ Tests en staging
☐ Documentation mise à jour

DEPLOYMENT STEPS
☐ 1. Deployer code
☐ 2. Installer dépendances: pip install -r requirements.txt
☐ 3. Migrations: python manage.py migrate
☐ 4. Seed data (optional): python manage.py init_tenants_data
☐ 5. Collectstatic: python manage.py collectstatic --noinput
☐ 6. Restart workers
☐ 7. Health checks
☐ 8. Monitor logs

POST-DEPLOYMENT
☐ Valider les données
☐ Tester workflows critiques
☐ Monitor performance
☐ Support notifications
```

---

## 🎯 Étapes suivantes

1. **Commencer Phase 1** :
   ```bash
   python manage.py startapp tenants
   ```

2. **Créer les modèles tenant** (copier du document)

3. **Faire les migrations**

4. **Tester avec postman/curl**

5. **Implémenter le middleware**

6. **Créer views super-admin**

---

## 📚 Ressources

- [Django Multi-tenancy Best Practices](https://docs.djangoproject.com/en/5.0/topics/db/multi-db/)
- [PostgreSQL Schemas](https://www.postgresql.org/docs/current/ddl-schemas.html)
- [Stripe Django Integration](https://stripe.com/docs/billing/quickstart)

---

**Questions ?** Continuons ! 🚀
