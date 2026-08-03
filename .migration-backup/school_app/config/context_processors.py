"""Context processors globaux."""
from django.db import connection


def school_info_safe(request):
    """Remplace school_settings.context_processors.school_info avec gestion du schéma public."""
    # Dans le schéma public (super-admin), pas de SchoolInfo
    if request.path.startswith('/super-admin/') or request.path.startswith('/onboarding/'):
        return {'school_info': None}
    if 'sqlite' not in connection.settings_dict.get('ENGINE', ''):
        schema = getattr(connection, 'schema_name', 'public')
        if schema == 'public':
            return {'school_info': None}
    try:
        from school_settings.models import SchoolInfo
        return {'school_info': SchoolInfo.get_info()}
    except Exception:
        return {'school_info': None}


def platform_settings_ctx(request):
    """Injecte PlatformSettings + corbeille_count dans tous les templates."""
    try:
        from super_admin.models import PlatformSettings
        ps = PlatformSettings.get_settings()
        corbeille_count = 0
        if request.path.startswith('/super-admin/'):
            try:
                from tenants.models import Ecole
                corbeille_count = Ecole.objects.filter(statut='corbeille').count()
            except Exception:
                pass
        return {'platform_settings': ps, 'corbeille_count': corbeille_count}
    except Exception:
        return {'platform_settings': None, 'corbeille_count': 0}


def tenant_context(request):
    ctx = {'is_super_admin': False, 'current_ecole': None}
    sa = getattr(request, 'super_admin', None)
    if sa:
        ctx['is_super_admin'] = True
        ctx['super_admin']    = sa

    schema = request.session.get('tenant_schema') if hasattr(request, 'session') else None
    if schema and schema != 'public' and 'sqlite' not in connection.settings_dict.get('ENGINE', ''):
        try:
            from tenants.models import Ecole
            ecole = Ecole.objects.get(schema_name=schema)
            ctx['current_ecole']       = ecole
            ctx['acces_lecture_seule'] = ecole.acces_lecture_seule
            ctx['abonnement_en_grace'] = ecole.en_grace
        except Exception:
            pass
    return ctx
