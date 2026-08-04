import json
import logging
from functools import wraps
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.utils.text import slugify
from django.core.mail import send_mail
from django.conf import settings as django_settings
import mimetypes
import os
from email import encoders
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from django.core.mail import EmailMultiAlternatives


from tenants.models import (
    Ecole, PlanAbonnement, AdminEcole, AnnuaireUtilisateur, ModeMaintenance,
    AnnoncePlateforme, Abonnement, HistoriqueAbonnement,
)
from tenants.models import _gen_temp_password
from super_admin.models import SuperAdmin
from super_admin.forms import (
    LoginSuperAdminForm, ChangePasswordSuperAdminForm,
    Verify2FAForm, Setup2FAConfirmForm,
    PlanAbonnementForm, CreerEcoleForm, ModifierEcoleForm,
    SupprimerEcoleForm, MaintenanceForm,
    AnnoncePlateformeForm, PlatformSettingsForm,
    PublicContactForm,
)

logger     = logging.getLogger('sgn')
logger_sec = logging.getLogger('sgn.security')


def super_admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not getattr(request, 'super_admin', None):
            return redirect('super_admin:login')
        return view_func(request, *args, **kwargs)
    return wrapper


def _needs_2fa_verification(request):
    sa = getattr(request, 'super_admin', None)
    if not sa:
        return False
    return sa.totp_enabled and not request.session.get('sa_2fa_verified')


# ── Auth ──────────────────────────────────────────────────────────────────────
_SA_LOGIN_FAILS = {}   # {ip: [timestamp, …]}
_SA_MAX_FAILS   = 10
_SA_LOCKOUT_S   = 600  # 10 minutes


def _sa_is_locked(ip):
    import time
    now = time.time()
    attempts = [t for t in _SA_LOGIN_FAILS.get(ip, []) if now - t < _SA_LOCKOUT_S]
    _SA_LOGIN_FAILS[ip] = attempts
    return len(attempts) >= _SA_MAX_FAILS


def _sa_record_fail(ip):
    import time
    _SA_LOGIN_FAILS.setdefault(ip, []).append(time.time())


def _sa_clear_fails(ip):
    _SA_LOGIN_FAILS.pop(ip, None)


def login_view(request):
    if getattr(request, 'super_admin', None):
        return redirect('super_admin:dashboard')

    client_ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() \
                or request.META.get('REMOTE_ADDR', '')
    error = None
    form = LoginSuperAdminForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        # Rate limiting anti-brute-force
        if _sa_is_locked(client_ip):
            logger_sec.warning('SA_LOGIN_LOCKED ip=%s', client_ip)
            error = "Trop de tentatives. Réessayez dans 10 minutes."
        else:
            email    = form.cleaned_data['email'].lower().strip()
            password = form.cleaned_data['password']
            try:
                sa = SuperAdmin.objects.get(email__iexact=email, is_active=True)
                if sa.check_password(password):
                    _sa_clear_fails(client_ip)
                    request.session['super_admin_id']  = sa.pk
                    request.session['tenant_schema']   = 'public'
                    request.session['user_type']       = 'super_admin'
                    request.session['sa_2fa_verified'] = not sa.totp_enabled
                    sa.last_login = timezone.now()
                    sa.save(update_fields=['last_login'])
                    logger_sec.info('CONNEXION super_admin email=%s ip=%s', email, client_ip)
                    if sa.totp_enabled:
                        return redirect('super_admin:verify_2fa')
                    return redirect('super_admin:dashboard')
                else:
                    _sa_record_fail(client_ip)
                    logger_sec.warning('SA_LOGIN_FAIL email=%s ip=%s', email, client_ip)
                    error = "Email ou mot de passe incorrect."
            except SuperAdmin.DoesNotExist:
                _sa_record_fail(client_ip)
                logger_sec.warning('SA_LOGIN_UNKNOWNEMAIL email=%s ip=%s', email, client_ip)
                error = "Email ou mot de passe incorrect."

    from super_admin.models import PlatformSettings
    return render(request, 'super_admin/login.html', {
        'form': form,
        'error': error,
        'platform_settings': PlatformSettings.get_settings(),
    })


def logout_view(request):
    sa = getattr(request, 'super_admin', None)
    if sa:
        logger_sec.info('DECONNEXION super_admin email=%s', sa.email)
    for key in ['super_admin_id', 'tenant_schema', 'user_type', 'sa_2fa_verified']:
        request.session.pop(key, None)
    return redirect('super_admin:login')


def verify_2fa(request):
    sa = getattr(request, 'super_admin', None)
    if not sa:
        return redirect('super_admin:login')
    if request.session.get('sa_2fa_verified'):
        return redirect('super_admin:dashboard')

    form = Verify2FAForm(request.POST or None)
    error = None
    if request.method == 'POST' and form.is_valid():
        code = form.cleaned_data['code'].strip()
        if sa.verify_totp(code):
            request.session['sa_2fa_verified'] = True
            return redirect('super_admin:dashboard')
        elif sa.use_recovery_code(code):
            request.session['sa_2fa_verified'] = True
            messages.warning(request, "Code de recuperation utilise. Il vous reste %d codes." % sa.remaining_recovery_codes())
            return redirect('super_admin:dashboard')
        else:
            error = "Code invalide. Verifiez votre application d'authentification."

    return render(request, 'super_admin/verify_2fa.html', {'form': form, 'error': error})


# ── Dashboard ─────────────────────────────────────────────────────────────────
@super_admin_required
def dashboard(request):
    if _needs_2fa_verification(request):
        return redirect('super_admin:verify_2fa')

    today = timezone.now().date()
    stats = {
        'total_ecoles':      Ecole.objects.filter(is_deleted=False).count(),
        'ecoles_actives':    Ecole.objects.filter(statut='active', is_deleted=False).count(),
        'ecoles_suspendues': Ecole.objects.filter(statut='suspendue', is_deleted=False).count(),
        'ecoles_corbeille':  Ecole.objects.filter(statut='corbeille').count(),
        'total_plans':       PlanAbonnement.objects.filter(is_actif=True).count(),
        'maintenance_active': ModeMaintenance.objects.filter(is_active=True).count(),
        'onboarding_en_cours': Ecole.objects.filter(
            is_deleted=False, onboarding_complete=False
        ).count(),
        'abonnements_a_renouveler': Ecole.objects.filter(
            is_deleted=False,
            date_fin_abonnement__isnull=False,
            date_fin_abonnement__gte=today,
            date_fin_abonnement__lte=today + timedelta(days=30),
        ).count(),
    }
    ecoles_recentes  = Ecole.objects.filter(is_deleted=False).order_by('-created_at')[:8]
    maintenances     = ModeMaintenance.objects.filter(is_active=True).select_related('ecole')[:5]
    annonces_recentes = AnnoncePlateforme.objects.select_related('ecole')[:5]
    ecoles_onboarding = Ecole.objects.filter(
        is_deleted=False, onboarding_complete=False
    ).order_by('-created_at')[:5]

    # ── Données graphiques ────────────────────────────────────────────────
    mois_fr = ['Jan','Fév','Mar','Avr','Mai','Jun','Jul','Aoû','Sep','Oct','Nov','Déc']
    monthly_labels = []
    monthly_created = []
    monthly_active = []
    for i in range(5, -1, -1):
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1
        monthly_labels.append(mois_fr[month - 1])
        monthly_created.append(
            Ecole.objects.filter(created_at__year=year, created_at__month=month, is_deleted=False).count()
        )
        monthly_active.append(
            Ecole.objects.filter(statut='active', created_at__year__lte=year,
                                  created_at__month__lte=month if year == today.year else 12,
                                  is_deleted=False).count()
        )

    chart_data = json.dumps({
        'donut': {
            'labels': ['Actives', 'Suspendues', 'Onboarding'],
            'data': [
                stats['ecoles_actives'],
                stats['ecoles_suspendues'],
                stats['onboarding_en_cours'],
            ],
        },
        'monthly': {
            'labels': monthly_labels,
            'created': monthly_created,
        },
        'activity': {
            'labels': monthly_labels,
            'total': monthly_active,
            'created': monthly_created,
        },
    })

    return render(request, 'super_admin/dashboard.html', {
        'stats': stats,
        'ecoles_recentes': ecoles_recentes,
        'maintenances': maintenances,
        'annonces_recentes': annonces_recentes,
        'ecoles_onboarding': ecoles_onboarding,
        'chart_data': chart_data,
    })


# ── Communications ───────────────────────────────────────────────────────────
@super_admin_required
def communication_list(request):
    if _needs_2fa_verification(request):
        return redirect('super_admin:verify_2fa')
    annonces = AnnoncePlateforme.objects.select_related('ecole')
    return render(request, 'super_admin/communication_list.html', {
        'annonces': annonces,
    })


@super_admin_required
def communication_creer(request):
    if _needs_2fa_verification(request):
        return redirect('super_admin:verify_2fa')
    form = AnnoncePlateformeForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        annonce = form.save(commit=False)
        annonce.auteur_nom = request.super_admin.get_full_name()
        annonce.save()
        messages.success(
            request,
            "L'annonce a été publiée pour %s." % (
                annonce.ecole.nom if annonce.ecole else "toutes les écoles"
            ),
        )
        return redirect('super_admin:communication_list')
    return render(request, 'super_admin/communication_form.html', {'form': form})


@super_admin_required
def communication_supprimer(request, pk):
    if _needs_2fa_verification(request):
        return redirect('super_admin:verify_2fa')
    annonce = get_object_or_404(AnnoncePlateforme, pk=pk)
    if request.method == 'POST':
        annonce.delete()
        messages.success(request, "L'annonce a été supprimée avec succès.")
    return redirect('super_admin:communication_list')


# ── Ecoles ────────────────────────────────────────────────────────────────────
@super_admin_required
def ecole_list(request):
    if _needs_2fa_verification(request):
        return redirect('super_admin:verify_2fa')
    statut_filter = request.GET.get('statut', '')
    search        = request.GET.get('q', '')
    ecoles = Ecole.objects.filter(is_deleted=False).select_related('plan')
    if statut_filter:
        ecoles = ecoles.filter(statut=statut_filter)
    if search:
        ecoles = ecoles.filter(nom__icontains=search)
    ecoles = ecoles.order_by('-created_at')
    paginator = Paginator(ecoles, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'super_admin/ecole_list.html', {
        'ecoles': page_obj.object_list,
        'page_obj': page_obj,
        'statut_filter': statut_filter, 'search': search,
        'total': paginator.count,
    })


@super_admin_required
def ecole_creer(request):
    if _needs_2fa_verification(request):
        return redirect('super_admin:verify_2fa')

    form = CreerEcoleForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        schema_name = getattr(form, '_schema_name', slugify(d['nom'])[:50].replace('-', '_') or 'ecole')

        date_debut = timezone.now().date()
        date_fin = date_debut + timedelta(days=d['duree_abonnement_jours'])

        ecole = Ecole(
            schema_name=schema_name,
            nom=d['nom'],
            contact_nom=d['contact_nom'],
            contact_email=d['contact_email'],
            contact_telephone=d.get('contact_telephone', ''),
            adresse=d.get('adresse', ''),
            ville=d.get('ville', ''),
            pays=d.get('pays', 'RDC'),
            plan=d['plan'],
            date_debut_abonnement=date_debut,
            date_fin_abonnement=date_fin,
        )
        ecole.save()  # cree le schema PostgreSQL

        # Domaine factice requis par django-tenants
        from tenants.models import EcoleDomain
        EcoleDomain.objects.create(
            domain='%s.sgn.local' % schema_name, tenant=ecole, is_primary=True
        )

        # Creer le compte admin dans le schema tenant
        temp_pwd = _gen_temp_password()
        _create_admin_in_schema(ecole, d['contact_email'], d['contact_nom'], temp_pwd, schema_name)

        # Tracker dans le schema public
        admin = AdminEcole.objects.create(
            ecole=ecole,
            email=d['contact_email'],
            nom=d['contact_nom'],
            onboarding_step=0,
        )

        # Annuaire global
        AnnuaireUtilisateur.objects.get_or_create(
            email=d['contact_email'].lower(),
            defaults={'schema_name': schema_name, 'type_compte': 'admin_ecole'},
        )

        _envoyer_credentials(ecole, admin, temp_pwd, request)
        logger.info('ECOLE_CREEE schema=%s par %s', schema_name, request.super_admin.email)

        return render(request, 'super_admin/ecole_creee.html', {
            'ecole': ecole, 'admin': admin, 'temp_pwd': temp_pwd, 'email_sent': True,
        })

    return render(request, 'super_admin/ecole_form.html', {
        'form': form, 'titre': "Creer une nouvelle ecole", 'mode': 'creer',
    })


def _create_admin_in_schema(ecole, email, nom, temp_pwd, schema_name):
    """Cree un CustomUser role=admin_ecole dans le schema de l'ecole."""
    from django.db import connection
    try:
        if 'sqlite' not in connection.settings_dict.get('ENGINE', ''):
            from django_tenants.utils import get_tenant_model
            tenant = get_tenant_model().objects.get(schema_name=schema_name)
            connection.set_tenant(tenant)
        from accounts.models import CustomUser
        username = email.split('@')[0][:30]
        # Garantir unicite username
        base_username = username
        n = 1
        while CustomUser.objects.filter(username=username).exists():
            username = '%s%d' % (base_username, n)
            n += 1
        user = CustomUser(
            username=username,
            email=email,
            first_name=nom,
            role='admin_ecole',
            must_change_password=True,
        )
        user.set_password(temp_pwd)
        user.save()
    except Exception as e:
        logger.warning('_create_admin_in_schema error: %s', e)
    finally:
        # Retourner au schema public
        try:
            from django_tenants.utils import get_tenant_model
            pub = get_tenant_model().objects.get(schema_name='public')
            connection.set_tenant(pub)
        except Exception:
            pass


@super_admin_required
def ecole_detail(request, pk):
    if _needs_2fa_verification(request):
        return redirect('super_admin:verify_2fa')
    ecole = get_object_or_404(Ecole, pk=pk, is_deleted=False)
    admin = AdminEcole.objects.filter(ecole=ecole).first()
    return render(request, 'super_admin/ecole_detail.html', {'ecole': ecole, 'admin': admin})


@super_admin_required
def ecole_modifier(request, pk):
    if _needs_2fa_verification(request):
        return redirect('super_admin:verify_2fa')
    ecole = get_object_or_404(Ecole, pk=pk, is_deleted=False)
    form = ModifierEcoleForm(request.POST or None, instance=ecole)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "L'ecole \u00ab %s \u00bb a ete mise a jour." % ecole.nom)
        return redirect('super_admin:ecole_detail', pk=pk)
    return render(request, 'super_admin/ecole_form.html', {
        'form': form, 'ecole': ecole, 'titre': "Modifier \u2014 %s" % ecole.nom, 'mode': 'modifier',
    })


@super_admin_required
def ecole_suspendre(request, pk):
    ecole = get_object_or_404(Ecole, pk=pk, is_deleted=False)
    if request.method == 'POST':
        ecole.statut = 'suspendue'
        ecole.save(update_fields=['statut'])
        messages.warning(request, "L'ecole \u00ab %s \u00bb a ete suspendue." % ecole.nom)
        return redirect('super_admin:ecole_detail', pk=pk)
    return render(request, 'super_admin/ecole_confirm_action.html', {
        'ecole': ecole, 'action': 'suspendre', 'couleur': 'warning',
        'titre': "Suspendre l'acces a \u00ab %s \u00bb" % ecole.nom,
        'message': "Les utilisateurs de cette ecole ne pourront plus se connecter.",
    })


@super_admin_required
def ecole_reactiver(request, pk):
    ecole = get_object_or_404(Ecole, pk=pk)
    if request.method == 'POST':
        ecole.statut = 'active'
        ecole.save(update_fields=['statut'])
        messages.success(request, "L'ecole \u00ab %s \u00bb a ete reactivee." % ecole.nom)
        return redirect('super_admin:ecole_detail', pk=pk)
    return render(request, 'super_admin/ecole_confirm_action.html', {
        'ecole': ecole, 'action': 'reactiver', 'couleur': 'success',
        'titre': "Reactiver l'acces a \u00ab %s \u00bb" % ecole.nom,
        'message': "Les utilisateurs de cette ecole pourront de nouveau se connecter.",
    })


@super_admin_required
def ecole_supprimer(request, pk):
    ecole = get_object_or_404(Ecole, pk=pk)
    form = SupprimerEcoleForm(request.POST or None, ecole=ecole)
    if request.method == 'POST' and form.is_valid():
        ecole.marquer_suppression()
        messages.error(request, "L'ecole \u00ab %s \u00bb a ete placee en corbeille." % ecole.nom)
        return redirect('super_admin:ecole_list')
    return render(request, 'super_admin/ecole_supprimer.html', {'ecole': ecole, 'form': form})


@super_admin_required
def regenerer_mdp_admin(request, pk):
    ecole = get_object_or_404(Ecole, pk=pk, is_deleted=False)
    admin = get_object_or_404(AdminEcole, ecole=ecole)
    if request.method == 'POST':
        temp_pwd = _gen_temp_password()
        # Mettre a jour le mdp dans le schema tenant
        _update_password_in_schema(ecole.schema_name, admin.email, temp_pwd)
        _envoyer_credentials(ecole, admin, temp_pwd, request, regeneration=True)
        messages.success(request, "Nouveau mot de passe temporaire genere et envoye a %s." % admin.email)
        return render(request, 'super_admin/ecole_creee.html', {
            'ecole': ecole, 'admin': admin, 'temp_pwd': temp_pwd,
            'email_sent': True, 'regeneration': True,
        })
    return render(request, 'super_admin/regenerer_mdp.html', {'ecole': ecole, 'admin': admin})


def _update_password_in_schema(schema_name, email, new_pwd):
    from django.db import connection
    if 'sqlite' in connection.settings_dict.get('ENGINE', ''):
        from accounts.models import CustomUser
        user = CustomUser.objects.get(email__iexact=email)
        user.set_password(new_pwd)
        user.must_change_password = True
        user.save(update_fields=['password', 'must_change_password'])
        return
    try:
        from django_tenants.utils import get_tenant_model
        tenant = get_tenant_model().objects.get(schema_name=schema_name)
        connection.set_tenant(tenant)
        from accounts.models import CustomUser
        user = CustomUser.objects.get(email__iexact=email)
        user.set_password(new_pwd)
        user.must_change_password = True
        user.save(update_fields=['password', 'must_change_password'])
    except Exception as e:
        logger.warning('_update_password_in_schema error: %s', e)
    finally:
        try:
            from django_tenants.utils import get_tenant_model
            pub = get_tenant_model().objects.get(schema_name='public')
            connection.set_tenant(pub)
        except Exception:
            pass


# ── Plans ──────────────────────────────────────────────────────────────────────
@super_admin_required
def plan_list(request):
    if _needs_2fa_verification(request):
        return redirect('super_admin:verify_2fa')
    plans = PlanAbonnement.objects.all().order_by('ordre_affichage', 'prix_mensuel')
    paginator = Paginator(plans, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'super_admin/plan_list.html', {
        'plans': page_obj.object_list,
        'page_obj': page_obj,
        'total': paginator.count,
    })


@super_admin_required
def plan_creer(request):
    if _needs_2fa_verification(request):
        return redirect('super_admin:verify_2fa')
    form = PlanAbonnementForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        plan = form.save()
        messages.success(request, "Plan « %s » créé." % plan.nom)
        logger.info('PLAN_CREE slug=%s sa=%s', plan.slug, request.super_admin.email)
        return redirect('super_admin:plan_list')
    return render(request, 'super_admin/plan_form.html', {'form': form, 'titre': 'Créer un plan'})


@super_admin_required
def plan_modifier(request, pk):
    if _needs_2fa_verification(request):
        return redirect('super_admin:verify_2fa')
    plan = get_object_or_404(PlanAbonnement, pk=pk)
    form = PlanAbonnementForm(request.POST or None, instance=plan)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Plan « %s » mis à jour." % plan.nom)
        logger.info('PLAN_MODIFIE slug=%s sa=%s', plan.slug, request.super_admin.email)
        return redirect('super_admin:plan_list')
    return render(request, 'super_admin/plan_form.html', {
        'form': form, 'titre': "Modifier — %s" % plan.nom, 'plan': plan,
    })


@super_admin_required
def plan_supprimer(request, pk):
    if _needs_2fa_verification(request):
        return redirect('super_admin:verify_2fa')
    plan = get_object_or_404(PlanAbonnement, pk=pk)
    ecoles_count = plan.ecoles.filter(is_deleted=False).count()
    if request.method == 'POST':
        if ecoles_count > 0:
            messages.error(
                request,
                "Impossible de supprimer le plan « %s » : %d école(s) l'utilisent encore."
                % (plan.nom, ecoles_count)
            )
            return redirect('super_admin:plan_list')
        nom = plan.nom
        plan.delete()
        messages.success(request, "Plan « %s » supprimé." % nom)
        logger.info('PLAN_SUPPRIME nom=%s sa=%s', nom, request.super_admin.email)
        return redirect('super_admin:plan_list')
    return render(request, 'super_admin/plan_supprimer.html', {
        'plan': plan, 'ecoles_count': ecoles_count,
    })


@super_admin_required
def plan_toggle_actif(request, pk):
    """Active / désactive un plan (AJAX ou POST standard)."""
    if _needs_2fa_verification(request):
        return redirect('super_admin:verify_2fa')
    plan = get_object_or_404(PlanAbonnement, pk=pk)
    if request.method == 'POST':
        plan.is_actif = not plan.is_actif
        plan.save(update_fields=['is_actif'])
        etat = 'activé' if plan.is_actif else 'désactivé'
        messages.success(request, "Plan « %s » %s." % (plan.nom, etat))
    return redirect('super_admin:plan_list')


@super_admin_required
def quotas_view(request):
    """Vue des écoles approchant leurs limites de quotas."""
    if _needs_2fa_verification(request):
        return redirect('super_admin:verify_2fa')

    ecoles = (
        Ecole.objects.filter(is_deleted=False, statut='active')
        .select_related('plan')
        .order_by('nom')
    )

    ecoles_avec_plan = [e for e in ecoles if e.plan]
    paginator = Paginator(ecoles_avec_plan, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'super_admin/quotas.html', {
        'ecoles': page_obj.object_list,
        'page_obj': page_obj,
        'total': paginator.count,
    })


@super_admin_required
def abonnement_ecole(request, pk):
    """Détail abonnement d'une école + changement de plan."""
    if _needs_2fa_verification(request):
        return redirect('super_admin:verify_2fa')

    ecole = get_object_or_404(Ecole, pk=pk, is_deleted=False)
    admin = AdminEcole.objects.filter(ecole=ecole).first()

    # Récupérer ou créer l'Abonnement
    from tenants.models import Abonnement, HistoriqueAbonnement
    abonnement = None
    try:
        abonnement = ecole.abonnement_detail
    except Exception:
        pass

    plans = PlanAbonnement.objects.filter(is_actif=True).order_by('ordre_affichage', 'prix_mensuel')
    historique = []
    if abonnement:
        historique = abonnement.historique.select_related('ancien_plan', 'nouveau_plan')[:20]

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'changer_plan':
            plan_id = request.POST.get('plan_id')
            motif   = request.POST.get('motif', '').strip()
            try:
                nouveau_plan = PlanAbonnement.objects.get(pk=plan_id)
            except PlanAbonnement.DoesNotExist:
                messages.error(request, "Plan introuvable.")
                return redirect('super_admin:abonnement_ecole', pk=pk)

            if abonnement:
                abonnement.changer_plan(
                    nouveau_plan,
                    motif=motif or "Changement manuel super-admin",
                    modifie_par=request.super_admin.email,
                )
            else:
                # Créer l'Abonnement si inexistant
                from django.utils import timezone as tz
                abonnement = Abonnement.objects.create(
                    ecole=ecole,
                    plan=nouveau_plan,
                    date_debut=ecole.date_debut_abonnement or tz.now().date(),
                    date_fin=ecole.date_fin_abonnement,
                    statut='actif',
                )
                ecole.plan = nouveau_plan
                ecole.save(update_fields=['plan'])
            messages.success(request, "Plan changé vers « %s »." % nouveau_plan.nom)
            logger.info('ABONNEMENT_PLAN_CHANGE ecole=%s plan=%s sa=%s',
                        ecole.nom, nouveau_plan.nom, request.super_admin.email)

        elif action == 'changer_statut':
            statut  = request.POST.get('statut')
            motif   = request.POST.get('motif', '').strip()
            valides = ['actif', 'essai', 'expire', 'suspendu']
            if statut in valides and abonnement:
                abonnement.changer_statut(
                    statut,
                    motif=motif or "Changement manuel super-admin",
                    modifie_par=request.super_admin.email,
                )
                # Synchroniser statut Ecole
                mapping = {
                    'actif':    'active',
                    'essai':    'active',
                    'expire':   'expiree',
                    'suspendu': 'suspendue',
                }
                ecole.statut = mapping.get(statut, ecole.statut)
                ecole.save(update_fields=['statut'])
                messages.success(request, "Statut mis à jour : %s." % statut)

        elif action == 'init_abonnement':
            # Créer un Abonnement pour une école qui n'en a pas
            from django.utils import timezone as tz
            if ecole.plan and not abonnement:
                abonnement = Abonnement.objects.create(
                    ecole=ecole,
                    plan=ecole.plan,
                    date_debut=ecole.date_debut_abonnement or tz.now().date(),
                    date_fin=ecole.date_fin_abonnement,
                    statut='actif',
                )
                messages.success(request, "Abonnement initialisé avec succès.")
            elif not ecole.plan:
                messages.error(request, "Assignez d'abord un plan à cette école.")

        elif action == 'notes':
            if abonnement:
                abonnement.notes_internes = request.POST.get('notes_internes', '')
                abonnement.save(update_fields=['notes_internes', 'updated_at'])
                messages.success(request, "Notes enregistrées.")

        return redirect('super_admin:abonnement_ecole', pk=pk)

    return render(request, 'super_admin/abonnement_ecole.html', {
        'ecole':      ecole,
        'admin':      admin,
        'abonnement': abonnement,
        'plans':      plans,
        'historique': historique,
    })


# ── Maintenance ────────────────────────────────────────────────────────────────
@super_admin_required
def maintenance_list(request):
    if _needs_2fa_verification(request):
        return redirect('super_admin:verify_2fa')
    modes = ModeMaintenance.objects.select_related('ecole').order_by('-created_at')
    paginator = Paginator(modes, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'super_admin/maintenance_list.html', {
        'modes': page_obj.object_list,
        'page_obj': page_obj,
        'total': paginator.count,
    })


@super_admin_required
def maintenance_creer(request):
    form = MaintenanceForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        ecole = Ecole.objects.filter(pk=d.get('ecole_id')).first() if d.get('ecole_id') else None
        ModeMaintenance.objects.create(
            ecole=ecole, module=d.get('module', ''), message=d['message'],
            is_urgence=d.get('is_urgence', False), debut_prevu=d.get('debut_prevu'),
            fin_prevue=d.get('fin_prevue'), duree_estimee_minutes=d.get('duree_estimee_minutes', 60),
            is_active=False,
        )
        messages.success(request, "Mode maintenance cree (inactif). Activez-le quand vous etes pret.")
        return redirect('super_admin:maintenance_list')
    ecoles = Ecole.objects.filter(statut='active', is_deleted=False)
    return render(request, 'super_admin/maintenance_form.html', {'form': form, 'ecoles': ecoles})


@super_admin_required
def maintenance_toggle(request, pk):
    mode = get_object_or_404(ModeMaintenance, pk=pk)
    if request.method == 'POST':
        mode.is_active = not mode.is_active
        if mode.is_active:
            mode.activated_at = timezone.now()
        else:
            mode.deactivated_at = timezone.now()
        mode.save(update_fields=['is_active', 'activated_at', 'deactivated_at'])
        state = 'active' if mode.is_active else 'desactive'
        messages.success(request, "Mode maintenance %s." % state)
    return redirect('super_admin:maintenance_list')


# ── Profil & 2FA ──────────────────────────────────────────────────────────────
@super_admin_required
def profil(request):
    sa = request.super_admin
    from super_admin.forms import SuperAdminProfileForm

    action = request.POST.get('_action', '') if request.method == 'POST' else ''

    form_info = SuperAdminProfileForm(
        request.POST if action == 'profile' else None,
        request.FILES if action == 'profile' else None,
        sa_pk=sa.pk,
        initial={
            'prenom': sa.prenom, 'nom': sa.nom,
            'email': sa.email, 'telephone': getattr(sa, 'telephone', ''),
        }
    )
    form_pwd = ChangePasswordSuperAdminForm(
        request.POST if action == 'password' else None
    )

    if request.method == 'POST':
        if action == 'profile' and form_info.is_valid():
            sa.prenom    = form_info.cleaned_data.get('prenom', '')
            sa.nom       = form_info.cleaned_data.get('nom', '')
            sa.email     = form_info.cleaned_data['email']
            sa.telephone = form_info.cleaned_data.get('telephone', '')
            if form_info.cleaned_data.get('supprimer_photo') and sa.photo_profil:
                try:
                    sa.photo_profil.delete(save=False)
                except Exception:
                    pass
                sa.photo_profil = None
            elif form_info.cleaned_data.get('photo_profil'):
                sa.photo_profil = form_info.cleaned_data['photo_profil']
            sa.save(update_fields=['prenom', 'nom', 'email', 'telephone', 'photo_profil'])
            messages.success(request, "Profil mis à jour avec succès.")
            return redirect('super_admin:profil')

        elif action == 'password' and form_pwd.is_valid():
            if sa.check_password(form_pwd.cleaned_data['ancien_mdp']):
                sa.set_password(form_pwd.cleaned_data['nouveau_mdp'])
                sa.save(update_fields=['password'])
                messages.success(request, "Mot de passe mis à jour.")
                return redirect('super_admin:profil')
            else:
                messages.error(request, "Mot de passe actuel incorrect.")

    return render(request, 'super_admin/profil.html', {
        'sa': sa, 'form_pwd': form_pwd, 'form_info': form_info,
    })


@super_admin_required
def setup_2fa(request):
    import qrcode, io, base64
    sa = request.super_admin
    if not sa.totp_secret:
        sa.generate_totp_secret()

    form = Setup2FAConfirmForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        code = form.cleaned_data['code'].strip()
        if sa.verify_totp(code):
            sa.totp_enabled = True
            sa.save(update_fields=['totp_enabled'])
            recovery_codes = sa.generate_recovery_codes()
            request.session['sa_2fa_verified'] = True
            messages.success(request, "2FA active avec succes !")
            return render(request, 'super_admin/2fa_recovery_codes.html', {
                'sa': sa, 'recovery_codes': recovery_codes,
            })
        else:
            messages.error(request, "Code invalide. Reessayez.")

    qr_img = qrcode.make(sa.get_totp_uri())
    buf = io.BytesIO()
    qr_img.save(buf, format='PNG')
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    return render(request, 'super_admin/setup_2fa.html', {
        'sa': sa, 'qr_b64': qr_b64, 'form': form, 'secret': sa.totp_secret,
    })


@super_admin_required
def platform_settings(request):
    from super_admin.models import PlatformSettings
    settings_obj = PlatformSettings.get_settings()
    form = PlatformSettingsForm(request.POST or None, request.FILES or None, instance=settings_obj)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        # Conserver le mot de passe SMTP existant si le champ est laissé vide
        # (PasswordInput ne re-affiche jamais la valeur — un champ vide = "ne pas changer")
        if not form.cleaned_data.get('smtp_password'):
            obj.smtp_password = settings_obj.smtp_password
        obj.save()
        messages.success(request, "Paramètres de la plateforme enregistrés avec succès.")
        return redirect('super_admin:platform_settings')
    return render(request, 'super_admin/parametres.html', {
        'form': form, 'obj': settings_obj, 'platform_settings': settings_obj,
    })


@super_admin_required
def test_email(request):
    """Envoie un email de test via les paramètres SMTP configurés.
    Répond en JSON si la requête est AJAX, sinon redirige."""
    import json as _json
    from super_admin.models import PlatformSettings

    is_ajax = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )

    if request.method != 'POST':
        if is_ajax:
            from django.http import JsonResponse
            return JsonResponse({'ok': False, 'message': 'Méthode non autorisée.'}, status=405)
        return redirect('super_admin:platform_settings')

    dest = request.POST.get('email_test', '').strip()
    if not dest:
        if is_ajax:
            from django.http import JsonResponse
            return JsonResponse({'ok': False, 'message': 'Indiquez une adresse e-mail de destination.'})
        messages.error(request, "Indiquez une adresse de destination pour le test.")
        return redirect('super_admin:platform_settings')

    settings_obj = PlatformSettings.get_settings()

    # Permet de tester la configuration SMTP à partir des valeurs actuellement saisies
    # dans le formulaire, avant enregistrement.
    smtp_actif = request.POST.get('smtp_actif') in ('1', 'true', 'on', 'yes')
    smtp_host = request.POST.get('smtp_host', '').strip() or settings_obj.smtp_host
    smtp_port = request.POST.get('smtp_port', '').strip()
    smtp_port = int(smtp_port) if smtp_port.isdigit() else settings_obj.smtp_port
    smtp_use_tls = request.POST.get('smtp_use_tls') in ('1', 'true', 'on', 'yes')
    smtp_user = request.POST.get('smtp_user', '').strip() or settings_obj.smtp_user
    smtp_password = request.POST.get('smtp_password')
    if smtp_password is None or smtp_password == '':
        smtp_password = settings_obj.smtp_password
    smtp_from_email = request.POST.get('smtp_from_email', '').strip() or settings_obj.smtp_from_email or 'noreply@educnet.local'

    try:
        from django.core.mail import get_connection, EmailMessage
        mode = 'console'
        if smtp_actif and smtp_host:
            conn = get_connection(
                backend='django.core.mail.backends.smtp.EmailBackend',
                host=smtp_host,
                port=smtp_port,
                username=smtp_user,
                password=smtp_password,
                use_tls=smtp_use_tls,
                fail_silently=False,
            )
            from_email = smtp_from_email
            mode = 'smtp'
        else:
            conn = None
            from_email = django_settings.DEFAULT_FROM_EMAIL

        site_name = settings_obj.site_name or 'EducNet'
        msg = EmailMessage(
            subject="[%s] ✅ Test d'envoi e-mail — configuration OK" % site_name,
            body=(
                "Bonjour,\n\n"
                "Ceci est un e-mail de test envoyé depuis la console d'administration de %(site)s.\n\n"
                "✅ Si vous recevez ce message, la configuration %(mode)s est correcte.\n\n"
                "Détails :\n"
                "  Expéditeur  : %(from)s\n"
                "  Destinataire : %(to)s\n"
                "  Mode         : %(mode_label)s\n\n"
                "— Plateforme %(site)s"
            ) % {
                'site': site_name,
                'from': from_email,
                'to': dest,
                'mode': mode.upper(),
                'mode_label': 'SMTP réel (%s:%s)' % (settings_obj.smtp_host, settings_obj.smtp_port)
                              if mode == 'smtp' else 'Console (logs serveur)',
            },
            from_email=from_email,
            to=[dest],
            connection=conn,
        )
        msg.send()

        success_msg = (
            "✅ E-mail de test envoyé à <strong>%s</strong> via SMTP (%s)." % (dest, settings_obj.smtp_host)
            if mode == 'smtp'
            else "📋 E-mail de test affiché dans les <strong>logs serveur</strong> (mode console — SMTP non activé). Destinataire : %s." % dest
        )

        if is_ajax:
            from django.http import JsonResponse
            return JsonResponse({'ok': True, 'message': success_msg, 'mode': mode})
        messages.success(request, success_msg)

    except Exception as e:
        err_raw = str(e)
        # Traduire les erreurs techniques les plus courantes en messages clairs
        if 'getaddrinfo failed' in err_raw or 'getaddrinfo' in err_raw or 'Errno 11003' in err_raw or 'Errno 11001' in err_raw:
            err_msg = (
                "❌ Serveur SMTP introuvable : <strong>%s</strong> ne peut pas être résolu.<br>"
                "Le champ <em>Serveur SMTP</em> doit contenir un nom de domaine comme "
                "<code>smtp.gmail.com</code> ou <code>smtp.office365.com</code>, "
                "pas une adresse e-mail."
            ) % settings_obj.smtp_host
        elif 'Connection refused' in err_raw or 'Errno 111' in err_raw or 'Errno 10061' in err_raw:
            err_msg = (
                "❌ Connexion refusée par <strong>%s</strong> sur le port <strong>%s</strong>.<br>"
                "Vérifiez que le port est correct (587 pour TLS, 465 pour SSL) et que le serveur autorise les connexions SMTP."
            ) % (settings_obj.smtp_host, settings_obj.smtp_port)
        elif 'Authentication' in err_raw or 'auth' in err_raw.lower() or '535' in err_raw or '534' in err_raw:
            err_msg = (
                "❌ Authentification refusée.<br>"
                "Pour Gmail, utilisez un <strong>mot de passe d'application</strong> "
                "(pas votre mot de passe principal). "
                "<a href='https://myaccount.google.com/apppasswords' target='_blank'>Créer un mot de passe d'application →</a>"
            )
        elif 'timed out' in err_raw.lower() or 'timeout' in err_raw.lower():
            err_msg = (
                "❌ Délai dépassé — le serveur <strong>%s</strong> ne répond pas.<br>"
                "Vérifiez l'adresse du serveur et le port."
            ) % settings_obj.smtp_host
        else:
            err_msg = "❌ Échec de l'envoi : <code>%s</code>" % err_raw

        if is_ajax:
            from django.http import JsonResponse
            return JsonResponse({'ok': False, 'message': err_msg})
        messages.error(request, err_msg)

    return redirect('super_admin:platform_settings')


# ── Corbeille ─────────────────────────────────────────────────────────────────
@super_admin_required
def corbeille_list(request):
    if _needs_2fa_verification(request):
        return redirect('super_admin:verify_2fa')
    ecoles = Ecole.objects.filter(statut='corbeille').order_by('-deleted_at')
    paginator = Paginator(ecoles, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'super_admin/corbeille.html', {
        'ecoles': page_obj.object_list,
        'page_obj': page_obj,
        'total': paginator.count,
    })


@super_admin_required
def ecole_restaurer(request, pk):
    if _needs_2fa_verification(request):
        return redirect('super_admin:verify_2fa')
    ecole = get_object_or_404(Ecole, pk=pk, statut='corbeille')
    if request.method == 'POST':
        ecole.statut = 'suspendue'
        ecole.is_deleted = False
        ecole.deleted_at = None
        ecole.save(update_fields=['statut', 'is_deleted', 'deleted_at'])
        logger.info('ECOLE_RESTAUREE pk=%s nom=%s sa=%s', pk, ecole.nom,
                    request.super_admin.email)
        messages.success(request, "École « %s » restaurée (statut : suspendue)." % ecole.nom)
    return redirect('super_admin:corbeille_list')


@super_admin_required
def ecole_supprimer_definitif(request, pk):
    if _needs_2fa_verification(request):
        return redirect('super_admin:verify_2fa')
    ecole = get_object_or_404(Ecole, pk=pk, statut='corbeille')
    if request.method == 'POST':
        confirmation = request.POST.get('confirmation', '').strip()
        if confirmation != ecole.nom:
            messages.error(request,
                "Confirmez en tapant exactement le nom de l'école : « %s »." % ecole.nom)
            return redirect('super_admin:corbeille_list')
        nom = ecole.nom
        try:
            ecole.delete()
            logger.info('ECOLE_SUPPRIMEE_DEFINITIF nom=%s sa=%s', nom,
                        request.super_admin.email)
            messages.success(request, "École « %s » supprimée définitivement." % nom)
        except Exception as e:
            logger.error('ECOLE_SUPPRIMER_DEFINITIF_ERROR: %s', e)
            messages.error(request, "Erreur lors de la suppression : %s" % e)
    return redirect('super_admin:corbeille_list')


@super_admin_required
def disable_2fa(request):
    sa = request.super_admin
    form = Verify2FAForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        code = form.cleaned_data['code'].strip()
        if sa.verify_totp(code):
            sa.totp_enabled = False
            sa.save(update_fields=['totp_enabled'])
            messages.warning(request, "2FA desactive. Votre compte est moins protege.")
            return redirect('super_admin:profil')
        messages.error(request, "Code invalide.")
    return render(request, 'super_admin/disable_2fa.html', {'form': form})


# ── Email helper ──────────────────────────────────────────────────────────────
def _get_smtp_from_email():
    """Retourne l'adresse expéditrice depuis PlatformSettings si SMTP actif, sinon settings."""
    try:
        from super_admin.models import PlatformSettings
        ps = PlatformSettings.objects.get(pk=1)
        if ps.smtp_actif and ps.smtp_from_email:
            return ps.smtp_from_email
    except Exception:
        pass
    return django_settings.DEFAULT_FROM_EMAIL


def _envoyer_credentials(ecole, admin, temp_pwd, request, regeneration=False):
    from django.core.mail import get_connection, EmailMessage as DjangoEmailMessage
    from django.template.loader import render_to_string
    try:
        from super_admin.models import PlatformSettings
        ps = PlatformSettings.objects.get(pk=1)
        site_name = ps.site_name or 'EducNet'
    except Exception:
        ps = None
        site_name = 'EducNet'

    # Construire la connexion SMTP depuis PlatformSettings
    if ps and ps.smtp_actif and ps.smtp_host:
        conn = get_connection(
            backend='django.core.mail.backends.smtp.EmailBackend',
            host=ps.smtp_host,
            port=ps.smtp_port,
            username=ps.smtp_user,
            password=ps.smtp_password,
            use_tls=ps.smtp_use_tls,
            fail_silently=False,
        )
        from_email = ps.smtp_from_email or 'noreply@educnet.local'
    else:
        conn = None
        from_email = django_settings.DEFAULT_FROM_EMAIL

    login_url = request.build_absolute_uri('/login/')
    intro = (
        "Un nouveau mot de passe temporaire a été généré pour votre compte."
        if regeneration
        else "Votre école « %s » a été créée sur la plateforme %s." % (ecole.nom, site_name)
    )

    subject = ("[Renouvellement] " if regeneration else "") + "Vos identifiants — %s" % site_name

    # ── Logo ──────────────────────────────────────────────────────────────
    logo_url = ''
    logo_inline = False
    logo_cid = 'platform_logo'
    logo_path = None
    try:
        if ps and ps.site_logo:
            logo_url = request.build_absolute_uri(ps.site_logo.url)
            logo_path = ps.site_logo.path
            logo_inline = bool(logo_path)
    except Exception:
        pass

    # ── E-mail HTML ────────────────────────────────────────────────────────
    html_body = render_to_string('emails/credentials.html', {
        'site_name':    site_name,
        'site_slogan':  ps.site_slogan if ps else '',
        'site_web':     ps.site_web if ps else '',
        'couleur':      ps.couleur_principale if ps else '#4D44B5',
        'logo_url':     logo_url,
        'logo_inline':  logo_inline,
        'logo_cid':     logo_cid,
        'prenom_nom':   admin.get_full_name(),
        'intro':        intro,
        'email':        admin.email,
        'mot_de_passe': temp_pwd,
        'login_url':    login_url,
        'subject':      subject,
    })

    # ── Fallback texte brut ────────────────────────────────────────────────
    txt_body = (
        "Bonjour %(nom)s,\n\n"
        "%(intro)s\n\n"
        "Identifiants de connexion :\n"
        "  E-mail             : %(email)s\n"
        "  Mot de passe temp. : %(pwd)s\n\n"
        "Connexion : %(url)s\n"
        "Vous devrez changer votre mot de passe à la première connexion.\n\n"
        "— %(site)s"
    ) % {
        'nom':   admin.get_full_name(),
        'intro': intro,
        'email': admin.email,
        'pwd':   temp_pwd,
        'url':   login_url,
        'site':  site_name,
    }

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=txt_body,
            from_email=from_email,
            to=[admin.email],
            connection=conn,
        )
        msg.attach_alternative(html_body, 'text/html')
        if logo_inline and logo_path:
            try:
                with open(logo_path, 'rb') as f:
                    logo_data = f.read()
                content_type, _ = mimetypes.guess_type(logo_path)
                if content_type == 'image/svg+xml':
                    logo_img = MIMEBase('image', 'svg+xml')
                    logo_img.set_payload(logo_data)
                    encoders.encode_base64(logo_img)
                elif content_type and content_type.startswith('image/'):
                    subtype = content_type.split('/', 1)[1]
                    logo_img = MIMEImage(logo_data, _subtype=subtype)
                else:
                    logo_img = MIMEBase('application', 'octet-stream')
                    logo_img.set_payload(logo_data)
                    encoders.encode_base64(logo_img)
                logo_img.add_header('Content-ID', '<%s>' % logo_cid)
                logo_img.add_header('Content-Disposition', 'inline', filename=os.path.basename(logo_path))
                msg.attach(logo_img)
            except Exception:
                pass
        msg.send(fail_silently=False)
        logger.info('CREDENTIALS_EMAIL_SENT to=%s via=%s', admin.email,
                    ('%s:%s' % (ps.smtp_host, ps.smtp_port)) if conn else 'console')
    except Exception as e:
        logger.warning('CREDENTIALS_EMAIL_FAILED to=%s err=%s', admin.email, e)
        # Fallback console : logguer le corps texte brut
        logger.info(
            'CREDENTIALS_EMAIL_FALLBACK_BODY:\n%s', txt_body
        )


# ════════════════════════════════════════════════════════════════════════════
# DEMANDES D'ABONNEMENT
# ════════════════════════════════════════════════════════════════════════════

@super_admin_required
def demandes_abonnement(request):
    if _needs_2fa_verification(request):
        return redirect('super_admin:verify_2fa')

    from tenants.models import DemandeAbonnement
    filtre_statut = request.GET.get('statut', '')

    qs = DemandeAbonnement.objects.select_related(
        'ecole', 'plan_souhaite', 'plan_actuel'
    )
    if filtre_statut:
        qs = qs.filter(statut=filtre_statut)
    qs = qs.order_by('-created_at')

    nb_en_attente = DemandeAbonnement.objects.filter(statut='en_attente').count()

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'super_admin/demandes_abonnement.html', {
        'demandes':      page_obj.object_list,
        'page_obj':      page_obj,
        'filtre_statut': filtre_statut,
        'total':         paginator.count,
        'nb_en_attente': nb_en_attente,
    })


@super_admin_required
def demande_abonnement_detail(request, pk):
    if _needs_2fa_verification(request):
        return redirect('super_admin:verify_2fa')

    from tenants.models import DemandeAbonnement
    demande = get_object_or_404(
        DemandeAbonnement.objects.select_related('ecole', 'plan_souhaite', 'plan_actuel'),
        pk=pk,
    )

    if request.method == 'POST' and demande.statut == 'en_attente':
        action         = request.POST.get('action', '')
        reponse_admin  = request.POST.get('reponse_admin', '').strip()[:1000]
        appliquer_plan = request.POST.get('appliquer_plan') == '1'
        sa             = request.super_admin

        if action in ('approuver', 'rejeter'):
            demande.statut       = 'approuvee' if action == 'approuver' else 'rejetee'
            demande.reponse_admin = reponse_admin
            demande.traite_par   = sa.get_full_name() or sa.email
            demande.traite_le    = timezone.now()
            demande.save()

            if action == 'approuver' and appliquer_plan and demande.plan_souhaite:
                try:
                    ecole = demande.ecole
                    from tenants.models import Abonnement, HistoriqueAbonnement
                    abonnement = None
                    try:
                        abonnement = ecole.abonnement_detail
                    except Exception:
                        pass

                    if abonnement:
                        abonnement.changer_plan(
                            demande.plan_souhaite,
                            motif='Demande approuvée via console super-admin',
                            modifie_par=sa.get_full_name() or sa.email,
                        )
                    else:
                        from datetime import date, timedelta
                        Abonnement.objects.create(
                            ecole=ecole,
                            plan=demande.plan_souhaite,
                            statut='actif',
                            date_debut=date.today(),
                            date_fin=date.today() + timedelta(days=30),
                        )
                        ecole.plan = demande.plan_souhaite
                        ecole.save(update_fields=['plan', 'updated_at'])

                    logger.info(
                        'DEMANDE_APPROUVEE pk=%s ecole=%s plan=%s par=%s',
                        demande.pk, demande.ecole.nom,
                        demande.plan_souhaite.nom, sa.email
                    )
                    messages.success(
                        request,
                        f"Demande approuvée et plan « {demande.plan_souhaite.nom} » appliqué."
                    )
                except Exception as e:
                    logger.error('DEMANDE_PLAN_APPLY_FAIL pk=%s err=%s', demande.pk, e)
                    messages.warning(
                        request,
                        "Demande approuvée, mais impossible d'appliquer le plan : %s" % e
                    )
            else:
                msg = "Demande approuvée." if action == 'approuver' else "Demande rejetée."
                messages.success(request, msg)

            return redirect('super_admin:demande_abonnement_detail', pk=pk)

    return render(request, 'super_admin/demande_abonnement_detail.html', {
        'demande':         demande,
        'sa_2fa_enabled': request.super_admin.totp_enabled,
    })


# ════════════════════════════════════════════════════════════════════════════
# PAIEMENTS PLATEFORME (mobile money / virement)
# ════════════════════════════════════════════════════════════════════════════

@super_admin_required
def paiements_plateforme(request):
    if _needs_2fa_verification(request):
        return redirect('super_admin:verify_2fa')

    from tenants.models import PaiementPlatforme
    filtre_statut = request.GET.get('statut', '')
    qs = PaiementPlatforme.objects.select_related('ecole')
    if filtre_statut:
        qs = qs.filter(statut=filtre_statut)
    qs = qs.order_by('-created_at')

    nb_en_attente = PaiementPlatforme.objects.filter(statut='en_attente').count()

    return render(request, 'super_admin/paiements_plateforme.html', {
        'paiements':     qs,
        'filtre_statut': filtre_statut,
        'total':         qs.count(),
        'nb_en_attente': nb_en_attente,
    })


@super_admin_required
def paiement_plateforme_detail(request, pk):
    if _needs_2fa_verification(request):
        return redirect('super_admin:verify_2fa')

    from tenants.models import PaiementPlatforme
    paiement = get_object_or_404(
        PaiementPlatforme.objects.select_related('ecole'),
        pk=pk,
    )
    sa = request.super_admin

    if request.method == 'POST' and paiement.statut == 'en_attente':
        action = request.POST.get('action', '')

        # Vérification TOTP si 2FA activé
        if sa.totp_enabled:
            totp_code = request.POST.get('totp_code', '').strip()
            if not sa.verify_totp(totp_code) and not sa.use_recovery_code(totp_code):
                messages.error(
                    request,
                    "Code 2FA invalide. Validation annulée."
                )
                logger_sec.warning(
                    'PAIEMENT_PLATEFORME_2FA_FAIL pk=%s par=%s ip=%s',
                    pk, sa.email,
                    request.META.get('REMOTE_ADDR', ''),
                )
                return redirect('super_admin:paiement_plateforme_detail', pk=pk)

        if action == 'valider':
            notes_admin    = request.POST.get('notes_admin', '').strip()[:500]
            jours_accordes = int(request.POST.get('jours_accordes', '0') or 0)

            paiement.statut         = 'valide'
            paiement.valide_par     = sa.get_full_name() or sa.email
            paiement.valide_le      = timezone.now()
            paiement.notes_admin    = notes_admin
            paiement.jours_accordes = jours_accordes
            paiement.save()

            # Prolonger l'abonnement si jours_accordes > 0
            if jours_accordes > 0:
                try:
                    from datetime import date, timedelta
                    from tenants.models import Abonnement
                    ecole = paiement.ecole
                    abonnement = None
                    try:
                        abonnement = ecole.abonnement_detail
                    except Exception:
                        pass

                    if abonnement:
                        base = max(abonnement.date_fin or date.today(), date.today())
                        abonnement.date_fin = base + timedelta(days=jours_accordes)
                        abonnement.statut   = 'actif'
                        abonnement.save(update_fields=['date_fin', 'statut', 'updated_at'])
                        ecole.date_fin_abonnement = abonnement.date_fin
                        ecole.statut = 'active'
                        ecole.save(update_fields=['date_fin_abonnement', 'statut', 'updated_at'])
                except Exception as e:
                    logger.error('PAIEMENT_PROLONGER_ABONNEMENT_FAIL pk=%s err=%s', pk, e)

            logger_sec.info(
                'PAIEMENT_PLATEFORME_VALIDE pk=%s ecole=%s montant=%s par=%s',
                pk, paiement.ecole.nom, paiement.montant, sa.email,
            )
            messages.success(
                request,
                f"Paiement validé. {jours_accordes} jours accordés à « {paiement.ecole.nom} »."
            )

        elif action == 'rejeter':
            notes_admin = request.POST.get('notes_admin', '').strip()[:500]
            paiement.statut      = 'rejete'
            paiement.valide_par  = sa.get_full_name() or sa.email
            paiement.valide_le   = timezone.now()
            paiement.notes_admin = notes_admin
            paiement.save()

            logger_sec.info(
                'PAIEMENT_PLATEFORME_REJETE pk=%s ecole=%s par=%s',
                pk, paiement.ecole.nom, sa.email,
            )
            messages.warning(request, "Paiement rejeté.")

        return redirect('super_admin:paiement_plateforme_detail', pk=pk)

    return render(request, 'super_admin/paiement_plateforme_detail.html', {
        'paiement':       paiement,
        'sa_2fa_enabled': sa.totp_enabled,
    })


# ── Demandes d'inscription (formulaire public) ────────────────────────────────

@super_admin_required
def demandes_inscription(request):
    """Liste des demandes d'inscription soumises via le formulaire public."""
    from tenants.models import DemandeInscription
    statut = request.GET.get('statut', '')
    qs = DemandeInscription.objects.all()
    if statut:
        qs = qs.filter(statut=statut)
    nb_attente = DemandeInscription.objects.filter(statut='en_attente').count()
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'super_admin/demandes_inscription.html', {
        'demandes': page_obj.object_list,
        'page_obj': page_obj,
        'statut': statut,
        'nb_attente': nb_attente,
        'total': paginator.count,
    })


@super_admin_required
def demande_inscription_detail(request, pk):
    """Vue détaillée d'une demande d'inscription avec historique de traitement."""
    from tenants.models import DemandeInscription
    demande = get_object_or_404(DemandeInscription, pk=pk)
    return render(request, 'super_admin/demande_inscription_detail.html', {'demande': demande})


@super_admin_required
def demande_inscription_traiter(request, pk):
    """Approuver ou rejeter une demande d'inscription."""
    from tenants.models import DemandeInscription
    demande = get_object_or_404(DemandeInscription, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        sa = getattr(request, 'super_admin', None)
        traite_par = sa.email if sa else 'super-admin'
        if action == 'approuver':
            demande.statut = 'approuvee'
            demande.traite_par = traite_par
            demande.traite_le = timezone.now()
            demande.save(update_fields=['statut', 'traite_par', 'traite_le', 'updated_at'])
            logger.info('DEMANDE_INSCRIPTION_APPRouvee pk=%s ecole=%s par=%s', pk, demande.nom_ecole, traite_par)
            messages.success(request, f"Demande de « {demande.nom_ecole} » approuvée.")
        elif action == 'rejeter':
            demande.statut = 'rejetee'
            demande.traite_par = traite_par
            demande.traite_le = timezone.now()
            demande.save(update_fields=['statut', 'traite_par', 'traite_le', 'updated_at'])
            logger.info('DEMANDE_INSCRIPTION_REJETEE pk=%s ecole=%s par=%s', pk, demande.nom_ecole, traite_par)
            messages.warning(request, f"Demande de « {demande.nom_ecole} » rejetée.")
    return redirect('super_admin:demandes_inscription')


# ── Formulaire public (sans authentification) ─────────────────────────────────

def _build_public_inscription_form():
    from django import forms as dj_forms
    from tenants.models import PlanAbonnement
    from tenants.models import PlanAbonnement, DemandeInscription

    class DemandeInscriptionForm(dj_forms.ModelForm):
        plan_souhaite = dj_forms.ModelChoiceField(
            queryset=PlanAbonnement.objects.filter(is_actif=True, est_public=True).order_by('ordre_affichage', 'prix_mensuel'),
            required=False,
            empty_label="— Pas encore décidé —",
            label="Plan souhaité",
            widget=dj_forms.Select(attrs={'class': 'form-select'}),
        )
        class Meta:
            model = DemandeInscription
            fields = ['nom_ecole', 'type_ecole', 'nom_responsable', 'telephone', 'email', 'province', 'ville', 'message', 'plan_souhaite']
            widgets = {
                'nom_ecole':       dj_forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Institut Technique de Kinshasa'}),
                'type_ecole':      dj_forms.Select(attrs={'class': 'form-select'}),
                'nom_responsable': dj_forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Prénom et nom'}),
                'telephone':       dj_forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+243 …'}),
                'email':           dj_forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@exemple.com'}),
                'province':        dj_forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Kinshasa'}),
                'ville':           dj_forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Kinshasa'}),
                'message':         dj_forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': "Nombre d'élèves, besoins spécifiques, questions..."}),
            }

    return DemandeInscriptionForm


def rejoindre_educnet(request):
    """Landing page publique de présentation et d'inscription à la plateforme."""
    from tenants.models import PlanAbonnement
    from super_admin.models import PlatformSettings

    try:
        platform_settings = PlatformSettings.get_settings()
    except Exception as _e:
        logger.warning('rejoindre_educnet: PlatformSettings unavailable: %s', _e)
        platform_settings = None

    try:
        plans_publics = list(
            PlanAbonnement.objects.filter(is_actif=True, est_public=True)
            .order_by('ordre_affichage', 'prix_mensuel')
        )
    except Exception as _e:
        logger.warning('rejoindre_educnet: PlanAbonnement unavailable: %s', _e)
        plans_publics = []

    return render(request, 'public/rejoindre.html', {
        'plans': plans_publics,
        'platform_settings': platform_settings,
    })


def about_view(request):
    """Page publique À propos."""
    from super_admin.models import PlatformSettings
    try:
        ps = PlatformSettings.get_settings()
    except Exception as _e:
        logger.warning('about_view: PlatformSettings unavailable: %s', _e)
        ps = None
    valeurs = [v.strip() for v in ((ps.about_valeurs if ps else '') or '').splitlines() if v.strip()]
    return render(request, 'public/apropos.html', {
        'platform_settings': ps,
        'valeurs': valeurs,
    })


def contact_view(request):
    """Page publique Contact."""
    from super_admin.models import PlatformSettings
    try:
        ps = PlatformSettings.get_settings()
    except Exception as _e:
        logger.warning('contact_view: PlatformSettings unavailable: %s', _e)
        ps = None
    success = False
    error = None

    if request.method == 'POST':
        form = PublicContactForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            destinataire = ps.email_contact or ps.smtp_from_email or django_settings.DEFAULT_FROM_EMAIL
            from_email = ps.smtp_from_email or django_settings.DEFAULT_FROM_EMAIL
            sujet_choices = {
                'info': "Demande d'information sur la plateforme",
                'technique': 'Problème technique',
                'facturation': 'Facturation / abonnement',
                'partenariat': 'Partenariat / collaboration',
                'autre': 'Autre',
            }
            sujet_label = sujet_choices.get(data['sujet'], data['sujet'])
            sujet = "[%s] Nouveau message de contact : %s" % (
                ps.site_name or 'EducNet',
                sujet_label,
            )
            corps = (
                "Nom : %(nom)s\n"
                "E-mail : %(email)s\n"
                "Téléphone : %(telephone)s\n"
                "Sujet : %(sujet)s\n"
                "\n"
                "Message :\n%(message)s\n"
            ) % {
                'nom': data['nom'],
                'email': data['email'],
                'telephone': data.get('telephone', ''),
                'sujet': sujet_label,
                'message': data['message'],
            }
            try:
                connection = None
                if ps.smtp_actif and ps.smtp_host:
                    connection = django_settings.EMAIL_BACKEND
                    from django.core.mail import get_connection
                    conn = get_connection(
                        backend='django.core.mail.backends.smtp.EmailBackend',
                        host=ps.smtp_host,
                        port=ps.smtp_port,
                        username=ps.smtp_user,
                        password=ps.smtp_password,
                        use_tls=ps.smtp_use_tls,
                        fail_silently=False,
                    )
                else:
                    conn = None

                from django.core.mail import EmailMessage
                message_obj = EmailMessage(
                    subject=sujet,
                    body=corps,
                    from_email=from_email,
                    to=[destinataire],
                    reply_to=[data['email']],
                    connection=conn,
                )
                message_obj.send(fail_silently=False)
                success = True
                form = PublicContactForm()
            except Exception as exc:
                error = (
                    "Une erreur est survenue lors de l'envoi du message. "
                    "Vérifiez la configuration SMTP ou contactez l'administrateur."
                )
                logger.exception('CONTACT_FORM_SEND_ERROR: %s', exc)
        else:
            error = "Veuillez corriger les erreurs du formulaire." 
    else:
        form = PublicContactForm()

    return render(request, 'public/contact.html', {
        'platform_settings': ps,
        'form': form,
        'success': success,
        'error': error,
    })


def rejoindre_educnet_form(request):
    """Page dédiée au formulaire public d'inscription."""
    from super_admin.models import PlatformSettings
    from tenants.models import DemandeInscription

    try:
        platform_settings = PlatformSettings.get_settings()
    except Exception as _e:
        logger.warning('rejoindre_educnet_form: PlatformSettings unavailable: %s', _e)
        platform_settings = None
    DemandeInscriptionForm = _build_public_inscription_form()

    success = False
    nom_ecole = ''
    email_contact = ''
    initial_data = {}

    selected_plan_id = request.GET.get('plan')
    if selected_plan_id:
        from tenants.models import PlanAbonnement
        try:
            plan = PlanAbonnement.objects.get(pk=selected_plan_id, is_actif=True, est_public=True)
            initial_data['plan_souhaite'] = plan.pk
        except (PlanAbonnement.DoesNotExist, ValueError):
            initial_data = {}

    if request.method == 'POST':
        form = DemandeInscriptionForm(request.POST)
        if form.is_valid():
            demande = form.save(commit=False)
            x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
            demande.ip_soumission = x_forwarded.split(',')[0] if x_forwarded else request.META.get('REMOTE_ADDR')
            demande.save()
            success = True
            nom_ecole = demande.nom_ecole
            email_contact = demande.email
            form = DemandeInscriptionForm()
    else:
        form = DemandeInscriptionForm(initial=initial_data)

    return render(request, 'public/rejoindre_form.html', {
        'form': form,
        'success': success,
        'nom_ecole': nom_ecole,
        'email': email_contact,
        'platform_settings': platform_settings,
    })
