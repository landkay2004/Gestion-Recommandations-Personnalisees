"""
Middleware multi-tenant SGN :
  1. SessionTenantMiddleware  — routing PostgreSQL schema par session
  2. SuperAdminAuthMiddleware — injecte request.super_admin
  3. OnboardingMiddleware     — redirige wizard si non terminé
  4. AbonnementMiddleware     — lecture seule / suspension
  5. MaintenanceMiddleware    — mode maintenance
"""
import logging
from django.conf import settings
from django.shortcuts import redirect
from django.http import HttpResponseForbidden
from django.utils import timezone

logger = logging.getLogger('sgn')

# ────────────────────────────────────────────────────────────────────────────
# 1. SessionTenantMiddleware
# ────────────────────────────────────────────────────────────────────────────

_SUPER_ADMIN_PREFIX = '/super-admin/'
_STATIC_PREFIXES    = ('/static/', '/media/', '/favicon', '/sw.js', '/manifest')


class SessionTenantMiddleware:
    """
    Identifie le tenant (école) depuis la session Django et bascule
    le search_path PostgreSQL sur le bon schéma.
    Routes /super-admin/* → toujours schéma public.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self._set_tenant(request)
        response = self.get_response(request)
        return response

    def _set_tenant(self, request):
        # Pas de multi-tenant en SQLite
        from django.db import connection
        if 'sqlite' in connection.settings_dict.get('ENGINE', ''):
            return

        try:
            from django_tenants.utils import get_tenant_model
            TenantModel = get_tenant_model()

            # Super-admin → schéma public
            if request.path.startswith(_SUPER_ADMIN_PREFIX):
                self._use_public(connection, TenantModel)
                return

            # Fichiers statiques/media → pas de changement
            for prefix in _STATIC_PREFIXES:
                if request.path.startswith(prefix):
                    return

            # Lire le schéma depuis la session (sans passer par SessionMiddleware)
            tenant_schema = None
            session_key = request.COOKIES.get(settings.SESSION_COOKIE_NAME)
            if session_key:
                try:
                    from django.contrib.sessions.backends.db import SessionStore
                    # Sessions sont dans le schéma public → lecture sans changer le schéma
                    s = SessionStore(session_key)
                    tenant_schema = s.get('tenant_schema')
                except Exception:
                    pass

            if tenant_schema:
                try:
                    tenant = TenantModel.objects.get(schema_name=tenant_schema)
                    connection.set_tenant(tenant)
                    return
                except TenantModel.DoesNotExist:
                    pass

            # Par défaut : schéma public
            self._use_public(connection, TenantModel)

        except Exception as e:
            logger.warning('SessionTenantMiddleware error: %s', e)

    def _use_public(self, connection, TenantModel):
        try:
            tenant = TenantModel.objects.get(schema_name='public')
            connection.set_tenant(tenant)
        except Exception:
            try:
                connection.set_schema_to_public()
            except Exception:
                pass


# ────────────────────────────────────────────────────────────────────────────
# 2. SuperAdminAuthMiddleware
# ────────────────────────────────────────────────────────────────────────────

class SuperAdminAuthMiddleware:
    """
    Injecte request.super_admin depuis la session super-admin.
    Ne touche pas à request.user (Django auth).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.super_admin = None
        sa_id = request.session.get('super_admin_id')
        if sa_id:
            try:
                from super_admin.models import SuperAdmin
                request.super_admin = SuperAdmin.objects.get(pk=sa_id, is_active=True)
            except Exception:
                request.session.pop('super_admin_id', None)
        return self.get_response(request)


# ────────────────────────────────────────────────────────────────────────────
# 3. OnboardingMiddleware
# ────────────────────────────────────────────────────────────────────────────

_ONBOARDING_EXEMPT = (
    '/login/', '/logout/', '/super-admin/',
    '/static/', '/media/', '/favicon', '/sw.js',
    '/onboarding/',
)


class OnboardingMiddleware:
    """
    Si l'admin d'une école est connecté et que l'onboarding n'est pas terminé,
    le redirige vers l'étape correcte de l'assistant de configuration.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._must_redirect_to_onboarding(request):
            return redirect('onboarding:etape_courante')
        return self.get_response(request)

    def _must_redirect_to_onboarding(self, request):
        for prefix in _ONBOARDING_EXEMPT:
            if request.path.startswith(prefix):
                return False

        admin_ecole_id = request.session.get('admin_ecole_id')
        if not admin_ecole_id:
            return False

        try:
            from tenants.models import AdminEcole
            admin = AdminEcole.objects.get(pk=admin_ecole_id, is_active=True)
            return not admin.onboarding_complete
        except Exception:
            return False


# ────────────────────────────────────────────────────────────────────────────
# 4. AbonnementMiddleware
# ────────────────────────────────────────────────────────────────────────────

_ABONNEMENT_EXEMPT = (
    '/login/', '/logout/', '/super-admin/',
    '/static/', '/media/', '/favicon',
    '/abonnement/', '/onboarding/',
)

_READONLY_SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS'}


class AbonnementMiddleware:
    """
    - Abonnement expiré (hors grâce) → lecture seule (bloque POST/PUT/DELETE)
    - École suspendue → accès bloqué sauf admin école qui voit page suspension
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        for prefix in _ABONNEMENT_EXEMPT:
            if request.path.startswith(prefix):
                return self.get_response(request)

        schema = getattr(request, 'session', {}).get('tenant_schema')
        if not schema or schema == 'public':
            return self.get_response(request)

        try:
            from tenants.models import Ecole
            ecole = Ecole.objects.get(schema_name=schema)
        except Exception:
            return self.get_response(request)

        # École suspendue
        if ecole.statut == 'suspendue':
            if request.session.get('admin_ecole_id'):
                return redirect('abonnement:suspendue')
            from django.template.loader import render_to_string
            from django.http import HttpResponse
            html = render_to_string('abonnement/ecole_suspendue.html', {'ecole': ecole})
            return HttpResponse(html, status=403)

        # Lecture seule
        if ecole.acces_lecture_seule and request.method not in _READONLY_SAFE_METHODS:
            from django.contrib import messages
            messages.warning(request,
                "Votre abonnement a expiré. L'école est en mode lecture seule. "
                "Contactez l'administrateur pour renouveler.")
            return redirect(request.path)

        return self.get_response(request)


# ────────────────────────────────────────────────────────────────────────────
# 5. MaintenanceMiddleware
# ────────────────────────────────────────────────────────────────────────────

_MAINTENANCE_EXEMPT = (
    '/super-admin/', '/static/', '/media/',
)


class MaintenanceMiddleware:
    """
    Vérifie le mode maintenance (global ou par école).
    Le dashboard super-admin reste toujours accessible.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        for prefix in _MAINTENANCE_EXEMPT:
            if request.path.startswith(prefix):
                return self.get_response(request)

        schema = request.session.get('tenant_schema', 'public') if hasattr(request, 'session') else 'public'

        try:
            from django.db import connection
            from tenants.models import ModeMaintenance, Ecole

            # Maintenance globale
            globale = ModeMaintenance.objects.filter(
                ecole=None, module='', is_active=True
            ).first()
            if globale:
                from django.template.loader import render_to_string
                from django.http import HttpResponse
                html = render_to_string('maintenance/maintenance.html', {'mode': globale})
                return HttpResponse(html, status=503)

            # Maintenance par école
            if schema and schema != 'public':
                try:
                    ecole = Ecole.objects.get(schema_name=schema)
                    maintenance_ecole = ModeMaintenance.objects.filter(
                        ecole=ecole, module='', is_active=True
                    ).first()
                    if maintenance_ecole:
                        from django.template.loader import render_to_string
                        from django.http import HttpResponse
                        html = render_to_string('maintenance/maintenance.html', {'mode': maintenance_ecole})
                        return HttpResponse(html, status=503)
                except Exception:
                    pass
        except Exception:
            pass

        return self.get_response(request)
