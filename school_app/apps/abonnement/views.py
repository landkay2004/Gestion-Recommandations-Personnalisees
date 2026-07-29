"""
Vues côté école : consultation et demande de changement d'abonnement.
"""
import logging
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils import timezone
from django.template.loader import render_to_string

logger = logging.getLogger('sgn')


# ── Page suspension ───────────────────────────────────────────────────────────

def ecole_suspendue(request):
    """Page affichée quand l'école est suspendue ou expirée."""
    schema = request.session.get('tenant_schema', '')
    ecole = None
    if schema and schema != 'public':
        try:
            from tenants.models import Ecole
            ecole = Ecole.objects.get(schema_name=schema)
        except Exception:
            pass
    return render(request, 'abonnement/ecole_suspendue.html', {
        'ecole': ecole,
        'ecole_statut': ecole.statut if ecole else '',
        'lecture_seule': ecole.en_grace if ecole else False,
    })


# ── Mon abonnement (vue école) ────────────────────────────────────────────────

@login_required
def mon_abonnement(request):
    """
    Vue principale : l'administrateur ou le préfet consulte l'abonnement
    en cours, les quotas utilisés, et peut soumettre une demande de changement.
    """
    schema = request.session.get('tenant_schema', '')
    ecole = None
    abonnement = None
    quotas = {}
    historique = []

    if schema and schema != 'public':
        try:
            from tenants.models import Ecole, Abonnement
            ecole = Ecole.objects.select_related('plan').get(schema_name=schema)
        except Exception:
            pass

    if ecole:
        try:
            abonnement = ecole.abonnement_detail
            historique = abonnement.historique.select_related(
                'ancien_plan', 'nouveau_plan'
            )[:10]
        except Exception:
            abonnement = None

        try:
            from tenants.utils.quotas import get_quotas_usage
            quotas = get_quotas_usage(ecole)
        except Exception:
            pass

    plans_publics = []
    try:
        from tenants.models import PlanAbonnement
        plans_publics = PlanAbonnement.objects.filter(
            is_actif=True, est_public=True
        ).order_by('ordre_affichage', 'prix_mensuel')
    except Exception:
        pass

    return render(request, 'abonnement/mon_abonnement.html', {
        'ecole':        ecole,
        'abonnement':   abonnement,
        'quotas':       quotas,
        'historique':   historique,
        'plans_publics': plans_publics,
    })


@login_required
def demande_changement(request):
    """
    Formulaire de demande de changement de plan.
    Envoie un e-mail au super-admin et enregistre un message dans les logs.
    """
    schema = request.session.get('tenant_schema', '')
    ecole = None
    if schema and schema != 'public':
        try:
            from tenants.models import Ecole
            ecole = Ecole.objects.select_related('plan').get(schema_name=schema)
        except Exception:
            pass

    if not ecole:
        messages.error(request, "Impossible de trouver les informations de votre école.")
        return redirect('mon_abonnement')

    from tenants.models import PlanAbonnement
    plans = PlanAbonnement.objects.filter(
        is_actif=True, est_public=True
    ).order_by('ordre_affichage', 'prix_mensuel')

    if request.method == 'POST':
        plan_souhaite_id = request.POST.get('plan_id')
        message_libre = request.POST.get('message', '').strip()

        plan_souhaite = None
        if plan_souhaite_id:
            try:
                plan_souhaite = PlanAbonnement.objects.get(pk=plan_souhaite_id, is_actif=True)
            except PlanAbonnement.DoesNotExist:
                pass

        if not plan_souhaite:
            messages.error(request, "Veuillez sélectionner un plan valide.")
            return render(request, 'abonnement/demande_changement.html', {
                'ecole': ecole, 'plans': plans,
            })

        # Notifier le super-admin par e-mail
        _envoyer_demande_email(request, ecole, plan_souhaite, message_libre)

        logger.info(
            'DEMANDE_CHANGEMENT_PLAN ecole=%s plan_actuel=%s plan_souhaite=%s',
            ecole.nom,
            ecole.plan.nom if ecole.plan else 'aucun',
            plan_souhaite.nom,
        )

        messages.success(
            request,
            "Votre demande de changement vers le plan « %s » a été envoyée à l'administrateur. "
            "Vous serez contacté dans les plus brefs délais." % plan_souhaite.nom
        )
        return redirect('mon_abonnement')

    return render(request, 'abonnement/demande_changement.html', {
        'ecole': ecole,
        'plans': plans,
    })


def _envoyer_demande_email(request, ecole, plan_souhaite, message_libre):
    """Envoie un e-mail de notification au super-admin."""
    try:
        from django.core.mail import send_mail
        from django.conf import settings as django_settings

        sujet = "[SGN] Demande de changement de plan — %s" % ecole.nom
        corps = (
            "Demande de changement de plan reçue.\n\n"
            "École           : %s\n"
            "Plan actuel     : %s\n"
            "Plan souhaité   : %s (%.2f USD/mois)\n"
            "Contact         : %s <%s>\n"
        ) % (
            ecole.nom,
            ecole.plan.nom if ecole.plan else 'Aucun',
            plan_souhaite.nom,
            plan_souhaite.prix_mensuel,
            ecole.contact_nom,
            ecole.contact_email,
        )
        if message_libre:
            corps += "\nMessage de l'école :\n%s\n" % message_libre

        send_mail(
            sujet, corps,
            django_settings.DEFAULT_FROM_EMAIL,
            [django_settings.DEFAULT_FROM_EMAIL],
            fail_silently=True,
        )
    except Exception as e:
        logger.warning('DEMANDE_EMAIL_FAILED ecole=%s err=%s', ecole.nom, e)
