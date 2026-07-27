"""
Wizard d'onboarding obligatoire pour les administrateurs d'école.
5 étapes persistantes (reprises si interruption).
Aucun header/sidebar affiché pendant l'assistant.
"""
import logging
from functools import wraps

from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone

from tenants.models import AdminEcole
from onboarding.forms import (
    ChangePasswordOnboardingForm,
    ConfigurationEcoleForm,
    ConditionsForm,
)

logger = logging.getLogger('sgn')


# ── Décorateur ─────────────────────────────────────────────────────────────────
def admin_ecole_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('admin_ecole_id'):
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


def _get_admin(request):
    pk = request.session.get('admin_ecole_id')
    if not pk:
        return None
    try:
        return AdminEcole.objects.select_related('ecole').get(pk=pk, is_active=True)
    except AdminEcole.DoesNotExist:
        return None


ETAPE_URLS = {
    1: 'onboarding:etape1_password',
    2: 'onboarding:etape2_config',
    3: 'onboarding:etape3_recapitulatif',
    4: 'onboarding:etape4_conditions',
    5: 'onboarding:termine',
}


def _etape_url(step):
    return ETAPE_URLS.get(step, 'onboarding:etape1_password')


# ── Vue de dispatch ──────────────────────────────────────────────────────────
@admin_ecole_required
def etape_courante(request):
    admin = _get_admin(request)
    if not admin:
        return redirect('login')
    if admin.onboarding_complete:
        return redirect('dashboard')
    step = max(1, admin.onboarding_step + 1) if admin.onboarding_step < 5 else 5
    return redirect(_etape_url(step))


# ── Étape 1 : Changement de mot de passe ─────────────────────────────────────
@admin_ecole_required
def etape1_password(request):
    admin = _get_admin(request)
    if not admin:
        return redirect('login')
    if admin.onboarding_step >= 1:
        return redirect(_etape_url(2))

    form = ChangePasswordOnboardingForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        new_pwd = form.cleaned_data['nouveau_mdp']
        _switch_tenant_schema(admin.ecole.schema_name)
        from accounts.models import CustomUser
        user = CustomUser.objects.get(email__iexact=admin.email, role='admin_ecole')
        user.set_password(new_pwd)
        user.must_change_password = False
        user.save(update_fields=['password', 'must_change_password'])
        _switch_public_schema()
        admin.onboarding_step = 1
        admin.save(update_fields=['onboarding_step'])
        logger.info('ONBOARDING_STEP1_DONE admin=%s', admin.email)
        return redirect(_etape_url(2))

    return render(request, 'onboarding/etape1_password.html', {
        'admin': admin,
        'form': form,
        'etape': 1,
        'total_etapes': 4,
    })


# ── Étape 2 : Configuration de l'école ──────────────────────────────────────
@admin_ecole_required
def etape2_config(request):
    admin = _get_admin(request)
    if not admin:
        return redirect('login')
    if admin.onboarding_step < 1:
        return redirect(_etape_url(1))
    if admin.onboarding_step >= 2:
        return redirect(_etape_url(3))

    # Basculer vers le schéma de l'école pour charger SchoolInfo
    _switch_tenant_schema(admin.ecole.schema_name)

    initial = {}
    try:
        from school_settings.models import SchoolInfo
        info = SchoolInfo.get_info()
        initial = {
            'nom_ecole': info.nom,
            'province': info.province,
            'ville': info.ville,
            'commune': info.commune,
            'code_ecole': info.code,
        }
    except Exception:
        pass

    form = ConfigurationEcoleForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        _switch_tenant_schema(admin.ecole.schema_name)
        try:
            from school_settings.models import SchoolInfo
            info = SchoolInfo.get_info()
            info.nom      = d['nom_ecole']
            info.province = d.get('province', '')
            info.ville    = d.get('ville', '')
            info.commune  = d.get('commune', '')
            info.code     = d.get('code_ecole', '')
            if 'logo' in request.FILES:
                info.logo = request.FILES['logo']
            info.save()
        except Exception as e:
            logger.warning('ONBOARDING_STEP2_SAVE_ERROR: %s', e)

        _switch_public_schema()
        admin.onboarding_step = 2
        admin.save(update_fields=['onboarding_step'])
        return redirect(_etape_url(3))

    return render(request, 'onboarding/etape2_config.html', {
        'admin': admin, 'form': form, 'etape': 2, 'total_etapes': 4,
    })


# ── Étape 3 : Récapitulatif ──────────────────────────────────────────────────
@admin_ecole_required
def etape3_recapitulatif(request):
    admin = _get_admin(request)
    if not admin:
        return redirect('login')
    if admin.onboarding_step < 2:
        return redirect(_etape_url(admin.onboarding_step + 1))
    if admin.onboarding_step >= 3:
        return redirect(_etape_url(4))

    _switch_tenant_schema(admin.ecole.schema_name)
    school_info = None
    try:
        from school_settings.models import SchoolInfo
        school_info = SchoolInfo.get_info()
    except Exception:
        pass

    if request.method == 'POST':
        _switch_public_schema()
        admin.onboarding_step = 3
        admin.save(update_fields=['onboarding_step'])
        return redirect(_etape_url(4))

    return render(request, 'onboarding/etape3_recapitulatif.html', {
        'admin': admin,
        'ecole': admin.ecole,
        'school_info': school_info,
        'etape': 3,
        'total_etapes': 4,
    })


# ── Étape 4 : Conditions d'utilisation ──────────────────────────────────────
@admin_ecole_required
def etape4_conditions(request):
    admin = _get_admin(request)
    if not admin:
        return redirect('login')
    if admin.onboarding_step < 3:
        return redirect(_etape_url(admin.onboarding_step + 1))
    if admin.onboarding_step >= 4:
        return redirect(_etape_url(5))

    form = ConditionsForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        _switch_public_schema()
        admin.onboarding_step = 5      # Marquer complet
        admin.ecole.onboarding_complete = True
        admin.ecole.save(update_fields=['onboarding_complete'])
        admin.save(update_fields=['onboarding_step'])
        logger.info('ONBOARDING_TERMINE admin=%s ecole=%s', admin.email, admin.ecole.schema_name)
        return redirect(_etape_url(5))

    return render(request, 'onboarding/etape4_conditions.html', {
        'admin': admin, 'form': form, 'etape': 4, 'total_etapes': 4,
    })


# ── Étape 5 : Bienvenue ───────────────────────────────────────────────────────
@admin_ecole_required
def termine(request):
    admin = _get_admin(request)
    if not admin or not admin.onboarding_complete:
        return redirect('onboarding:etape_courante')
    # Connecter l'admin via Django auth pour qu'il puisse accéder aux vues
    # protégées (paramètres, dashboard…) directement depuis cette page.
    if not request.user.is_authenticated:
        _switch_tenant_schema(admin.ecole.schema_name)
        try:
            from accounts.models import CustomUser
            from django.contrib.auth import login as django_login
            user_obj = CustomUser.objects.get(email__iexact=admin.email, role='admin_ecole')
            django_login(request, user_obj, backend='accounts.backends.EmailBackend')
        except Exception:
            pass
        _switch_public_schema()
    return render(request, 'onboarding/termine.html', {'admin': admin, 'ecole': admin.ecole})


# ── Utilitaire ────────────────────────────────────────────────────────────────
def _switch_tenant_schema(schema_name):
    from django.db import connection
    if 'sqlite' in connection.settings_dict.get('ENGINE', ''):
        return
    try:
        from django_tenants.utils import get_tenant_model
        tenant = get_tenant_model().objects.get(schema_name=schema_name)
        connection.set_tenant(tenant)
    except Exception:
        pass


def _switch_public_schema():
    """Retourne au schéma public après une opération dans un tenant."""
    from django.db import connection
    if 'sqlite' in connection.settings_dict.get('ENGINE', ''):
        return
    try:
        connection.set_schema_to_public()
    except Exception:
        pass
