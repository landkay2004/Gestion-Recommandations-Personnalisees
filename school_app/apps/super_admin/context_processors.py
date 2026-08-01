"""Context processors pour les templates super admin."""
from django.utils import timezone
from django.db.models import Q


def platform_settings(request):
    """Injecte PlatformSettings, annonces actives, et badges demandes/paiements."""
    ctx = {
        'platform_settings': None,
        'annonces_count': 0,
        'annonces_list': [],
        'demandes_abonnement_count': 0,
        'paiements_plateforme_count': 0,
        'corbeille_count': 0,
    }
    # PlatformSettings (singleton)
    try:
        from super_admin.models import PlatformSettings
        ctx['platform_settings'] = PlatformSettings.get_settings()
    except Exception:
        pass

    # Seulement pour les super admins connectés
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

        # Badge demandes d'abonnement en attente
        try:
            from tenants.models import DemandeAbonnement
            ctx['demandes_abonnement_count'] = DemandeAbonnement.objects.filter(
                statut='en_attente'
            ).count()
        except Exception:
            pass

        # Badge paiements plateforme en attente
        try:
            from tenants.models import PaiementPlatforme
            ctx['paiements_plateforme_count'] = PaiementPlatforme.objects.filter(
                statut='en_attente'
            ).count()
        except Exception:
            pass

        # Badge demandes d'inscription (formulaire public)
        try:
            from tenants.models import DemandeInscription
            ctx['demandes_inscription_count'] = DemandeInscription.objects.filter(
                statut='en_attente'
            ).count()
        except Exception:
            pass

        # Corbeille
        try:
            from tenants.models import Ecole
            ctx['corbeille_count'] = Ecole.objects.filter(statut='corbeille').count()
        except Exception:
            pass

    return ctx
