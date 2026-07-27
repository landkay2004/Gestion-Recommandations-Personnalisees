"""Context processors pour les templates super admin."""
from django.utils import timezone
from django.db.models import Q


def platform_settings(request):
    """Injecte PlatformSettings et le compteur d'annonces actives dans tous les templates."""
    ctx = {
        'platform_settings': None,
        'annonces_count': 0,
        'annonces_list': [],
    }
    # PlatformSettings (singleton)
    try:
        from super_admin.models import PlatformSettings
        ctx['platform_settings'] = PlatformSettings.get_settings()
    except Exception:
        pass

    # Annonces actives (publiées et non expirées) — seulement pour les super admins connectés
    if getattr(request, 'super_admin', None):
        try:
            from tenants.models import AnnoncePlateforme
            now = timezone.now()
            qs = AnnoncePlateforme.objects.filter(publiee=True).filter(
                Q(date_expiration__isnull=True) | Q(date_expiration__gt=now)
            ).select_related('ecole').order_by('-date_publication')[:10]
            ctx['annonces_list']  = list(qs)
            ctx['annonces_count'] = len(ctx['annonces_list'])
        except Exception:
            pass
    return ctx
