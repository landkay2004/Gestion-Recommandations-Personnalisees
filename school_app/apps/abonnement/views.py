"""
Vues côté école : abonnement plateforme, frais scolaires.
Les vues comptable (caisse, encaissement, factures) sont dans l'app `comptable`.
"""
import logging
import os

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Q

from accounts.views import admin_ecole_required

logger = logging.getLogger('sgn')


# ════════════════════════════════════════════════════════════════════════════
# ABONNEMENT PLATEFORME
# ════════════════════════════════════════════════════════════════════════════

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


@login_required
def mon_abonnement(request):
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

    # Demandes en cours
    demandes_en_cours = []
    try:
        from tenants.models import DemandeAbonnement
        if ecole:
            demandes_en_cours = DemandeAbonnement.objects.filter(
                ecole=ecole, statut='en_attente'
            ).order_by('-created_at')[:3]
    except Exception:
        pass

    # Paiements plateforme en cours
    paiements_en_attente = []
    try:
        from tenants.models import PaiementPlatforme
        if ecole:
            paiements_en_attente = PaiementPlatforme.objects.filter(
                ecole=ecole, statut='en_attente'
            ).order_by('-created_at')[:3]
    except Exception:
        pass

    return render(request, 'abonnement/mon_abonnement.html', {
        'ecole':                ecole,
        'abonnement':           abonnement,
        'quotas':               quotas,
        'historique':           historique,
        'plans_publics':        plans_publics,
        'demandes_en_cours':    demandes_en_cours,
        'paiements_en_attente': paiements_en_attente,
    })


@login_required
def demande_changement(request):
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
        return redirect('abonnement:mon_abonnement')

    from tenants.models import PlanAbonnement
    plans = PlanAbonnement.objects.filter(
        is_actif=True, est_public=True
    ).order_by('ordre_affichage', 'prix_mensuel')

    if request.method == 'POST':
        plan_souhaite_id = request.POST.get('plan_id')
        message_libre = request.POST.get('message', '').strip()[:2000]

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

        # Vérifier qu'il n'y a pas déjà une demande en attente pour ce plan
        try:
            from tenants.models import DemandeAbonnement
            demande_existante = DemandeAbonnement.objects.filter(
                ecole=ecole,
                plan_souhaite=plan_souhaite,
                statut='en_attente',
            ).exists()
            if demande_existante:
                messages.warning(
                    request,
                    "Une demande pour ce plan est déjà en cours. "
                    "Le super-administrateur va la traiter prochainement."
                )
                return redirect('abonnement:mon_abonnement')

            # Enregistrer la demande en base (notifie super admin)
            DemandeAbonnement.objects.create(
                ecole=ecole,
                plan_souhaite=plan_souhaite,
                plan_actuel=ecole.plan,
                message=message_libre,
                contact_email=ecole.contact_email or '',
                contact_nom=ecole.contact_nom or '',
                statut='en_attente',
            )
            logger.info(
                'DEMANDE_ABONNEMENT ecole=%s plan=%s',
                ecole.nom, plan_souhaite.nom
            )
        except Exception as e:
            logger.warning('DEMANDE_ABONNEMENT_SAVE_FAILED ecole=%s err=%s', ecole.nom, e)

        # Envoyer e-mail (best-effort)
        _envoyer_demande_email(request, ecole, plan_souhaite, message_libre)

        messages.success(
            request,
            f"Votre demande de changement vers le plan « {plan_souhaite.nom} » a été envoyée. "
            "Le super-administrateur va la traiter prochainement."
        )
        return redirect('abonnement:mon_abonnement')

    return render(request, 'abonnement/demande_changement.html', {
        'ecole': ecole, 'plans': plans,
    })


@login_required
@admin_ecole_required
def soumettre_paiement(request):
    """L'admin-école soumet une preuve de paiement d'abonnement (mobile money / virement)."""
    schema = request.session.get('tenant_schema', '')
    ecole = None
    if schema and schema != 'public':
        try:
            from tenants.models import Ecole
            ecole = Ecole.objects.select_related('plan').get(schema_name=schema)
        except Exception:
            pass

    if not ecole:
        messages.error(request, "École introuvable.")
        return redirect('abonnement:mon_abonnement')

    # Anti-abus : une seule demande en attente à la fois
    try:
        from tenants.models import PaiementPlatforme
        if PaiementPlatforme.objects.filter(ecole=ecole, statut='en_attente').exists():
            messages.warning(
                request,
                "Un paiement est déjà en attente de validation. "
                "Patientez que le super-administrateur le traite."
            )
            return redirect('abonnement:mon_abonnement')
    except Exception:
        pass

    from .forms import PaiementPlateformeForm
    form = PaiementPlateformeForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        try:
            from tenants.models import PaiementPlatforme

            # Validation du fichier preuve
            fichier = form.cleaned_data.get('preuve')
            if fichier:
                _valider_fichier_preuve(fichier)

            paiement = PaiementPlatforme(
                ecole=ecole,
                montant=form.cleaned_data['montant'],
                mode=form.cleaned_data['mode'],
                numero_transaction=form.cleaned_data.get('numero_transaction', ''),
                notes=form.cleaned_data.get('notes', ''),
                preuve=fichier,
                statut='en_attente',
                ip_soumission=_get_client_ip(request),
            )
            paiement.save()

            logger.info(
                'PAIEMENT_PLATEFORME_SOUMIS ecole=%s montant=%s mode=%s',
                ecole.nom, paiement.montant, paiement.mode
            )
            messages.success(
                request,
                "Votre preuve de paiement a été soumise. "
                "Le super-administrateur va valider et activer votre abonnement."
            )
            return redirect('abonnement:mon_abonnement')

        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            logger.error('PAIEMENT_PLATEFORME_SAVE_ERROR ecole=%s err=%s', ecole.nom, e)
            messages.error(request, "Une erreur est survenue. Réessayez.")

    return render(request, 'abonnement/soumettre_paiement.html', {
        'form': form, 'ecole': ecole,
    })


def _valider_fichier_preuve(fichier):
    """Valide la preuve de paiement : type et taille."""
    MAX_SIZE_MB = 5
    EXTENSIONS_AUTORISEES = {'.jpg', '.jpeg', '.png', '.pdf', '.webp'}

    ext = os.path.splitext(fichier.name)[1].lower()
    if ext not in EXTENSIONS_AUTORISEES:
        raise ValueError(
            f"Format non autorisé ({ext}). "
            f"Formats acceptés : {', '.join(EXTENSIONS_AUTORISEES)}"
        )

    if fichier.size > MAX_SIZE_MB * 1024 * 1024:
        raise ValueError(
            f"Fichier trop volumineux ({fichier.size // (1024*1024)} Mo). "
            f"Maximum autorisé : {MAX_SIZE_MB} Mo."
        )

    # Vérification de la signature magic bytes (anti-spoofing extension)
    header = fichier.read(8)
    fichier.seek(0)
    MAGIC = {
        b'\xff\xd8\xff':   'jpeg',
        b'\x89PNG\r\n':    'png',
        b'%PDF':           'pdf',
        b'RIFF':           'webp',
    }
    detected = None
    for sig, name in MAGIC.items():
        if header.startswith(sig):
            detected = name
            break
    if detected is None:
        raise ValueError("Le contenu du fichier ne correspond pas à un format reconnu.")


def _get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def _envoyer_demande_email(request, ecole, plan_souhaite, message_libre):
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

        dest = getattr(django_settings, 'SUPER_ADMIN_EMAIL', None) or \
               getattr(django_settings, 'DEFAULT_FROM_EMAIL', '')

        send_mail(sujet, corps, django_settings.DEFAULT_FROM_EMAIL, [dest], fail_silently=True)
    except Exception as e:
        logger.warning('DEMANDE_EMAIL_FAILED ecole=%s err=%s', ecole.nom, e)


# ════════════════════════════════════════════════════════════════════════════
# TYPES DE FRAIS (admin_ecole)
# ════════════════════════════════════════════════════════════════════════════

@login_required
@admin_ecole_required
def frais_list(request):
    from .models import TypeFrais
    frais = TypeFrais.objects.select_related('classe').all()
    return render(request, 'abonnement/frais_list.html', {'frais': frais})


@login_required
@admin_ecole_required
def frais_create(request):
    from .forms import TypeFraisForm
    form = TypeFraisForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Type de frais créé avec succès.")
        return redirect('abonnement:frais_list')
    return render(request, 'abonnement/frais_form.html', {
        'form': form, 'titre': 'Ajouter un type de frais',
    })


@login_required
@admin_ecole_required
def frais_update(request, pk):
    from .models import TypeFrais
    from .forms import TypeFraisForm
    obj = get_object_or_404(TypeFrais, pk=pk)
    form = TypeFraisForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Type de frais modifié.")
        return redirect('abonnement:frais_list')
    return render(request, 'abonnement/frais_form.html', {
        'form': form, 'titre': 'Modifier le type de frais', 'obj': obj,
    })


@login_required
@admin_ecole_required
def frais_delete(request, pk):
    from .models import TypeFrais
    obj = get_object_or_404(TypeFrais, pk=pk)
    if request.method == 'POST':
        try:
            obj.delete()
            messages.success(request, "Type de frais supprimé.")
        except Exception:
            messages.error(
                request,
                "Impossible de supprimer ce type de frais : des paiements y sont liés."
            )
        return redirect('abonnement:frais_list')
    return render(request, 'abonnement/frais_confirm_delete.html', {'obj': obj})
