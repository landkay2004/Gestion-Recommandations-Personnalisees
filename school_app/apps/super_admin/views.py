import logging
from functools import wraps
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.utils.text import slugify
from django.core.mail import send_mail
from django.conf import settings as django_settings

from tenants.models import (
    Ecole, PlanAbonnement, AdminEcole, AnnuaireUtilisateur, ModeMaintenance,
    AnnoncePlateforme,
)
from tenants.models import _gen_temp_password
from super_admin.models import SuperAdmin
from super_admin.forms import (
    LoginSuperAdminForm, ChangePasswordSuperAdminForm,
    Verify2FAForm, Setup2FAConfirmForm,
    PlanAbonnementForm, CreerEcoleForm, ModifierEcoleForm,
    SupprimerEcoleForm, MaintenanceForm,
    AnnoncePlateformeForm, PlatformSettingsForm,
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
def login_view(request):
    if getattr(request, 'super_admin', None):
        return redirect('super_admin:dashboard')

    error = None
    form = LoginSuperAdminForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        email    = form.cleaned_data['email'].lower().strip()
        password = form.cleaned_data['password']
        try:
            sa = SuperAdmin.objects.get(email__iexact=email, is_active=True)
            if sa.check_password(password):
                request.session['super_admin_id']  = sa.pk
                request.session['tenant_schema']   = 'public'
                request.session['user_type']       = 'super_admin'
                request.session['sa_2fa_verified'] = not sa.totp_enabled
                sa.last_login = timezone.now()
                sa.save(update_fields=['last_login'])
                logger_sec.info('CONNEXION super_admin email=%s', email)
                if sa.totp_enabled:
                    return redirect('super_admin:verify_2fa')
                return redirect('super_admin:dashboard')
            else:
                error = "Email ou mot de passe incorrect."
        except SuperAdmin.DoesNotExist:
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

    return render(request, 'super_admin/dashboard.html', {
        'stats': stats,
        'ecoles_recentes': ecoles_recentes,
        'maintenances': maintenances,
        'annonces_recentes': annonces_recentes,
        'ecoles_onboarding': ecoles_onboarding,
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
    return render(request, 'super_admin/ecole_list.html', {
        'ecoles': ecoles.order_by('-created_at'),
        'statut_filter': statut_filter, 'search': search,
    })


@super_admin_required
def ecole_creer(request):
    if _needs_2fa_verification(request):
        return redirect('super_admin:verify_2fa')

    form = CreerEcoleForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        schema_name = getattr(form, '_schema_name', slugify(d['nom'])[:50].replace('-', '_') or 'ecole')

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
            date_debut_abonnement=timezone.now().date(),
            date_fin_abonnement=d.get('date_fin_abonnement'),
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
    plans = PlanAbonnement.objects.all().order_by('prix_mensuel')
    return render(request, 'super_admin/plan_list.html', {'plans': plans})


@super_admin_required
def plan_creer(request):
    form = PlanAbonnementForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        plan = form.save()
        messages.success(request, "Plan \u00ab %s \u00bb cree." % plan.nom)
        return redirect('super_admin:plan_list')
    return render(request, 'super_admin/plan_form.html', {'form': form, 'titre': 'Creer un plan'})


@super_admin_required
def plan_modifier(request, pk):
    plan = get_object_or_404(PlanAbonnement, pk=pk)
    form = PlanAbonnementForm(request.POST or None, instance=plan)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Plan \u00ab %s \u00bb mis a jour." % plan.nom)
        return redirect('super_admin:plan_list')
    return render(request, 'super_admin/plan_form.html', {'form': form, 'titre': "Modifier \u2014 %s" % plan.nom, 'plan': plan})


# ── Maintenance ────────────────────────────────────────────────────────────────
@super_admin_required
def maintenance_list(request):
    if _needs_2fa_verification(request):
        return redirect('super_admin:verify_2fa')
    modes = ModeMaintenance.objects.select_related('ecole').order_by('-created_at')
    return render(request, 'super_admin/maintenance_list.html', {'modes': modes})


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
    form_pwd = ChangePasswordSuperAdminForm(request.POST or None)
    if request.method == 'POST' and form_pwd.is_valid():
        if sa.check_password(form_pwd.cleaned_data['ancien_mdp']):
            sa.set_password(form_pwd.cleaned_data['nouveau_mdp'])
            sa.save(update_fields=['password'])
            messages.success(request, "Mot de passe mis a jour.")
            return redirect('super_admin:profil')
        else:
            messages.error(request, "Mot de passe actuel incorrect.")
    return render(request, 'super_admin/profil.html', {'sa': sa, 'form_pwd': form_pwd})


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
        form.save()
        messages.success(request, "Paramètres de la plateforme enregistrés.")
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
    try:
        from django.core.mail import get_connection, EmailMessage
        mode = 'console'
        if settings_obj.smtp_actif and settings_obj.smtp_host:
            conn = get_connection(
                backend='django.core.mail.backends.smtp.EmailBackend',
                host=settings_obj.smtp_host,
                port=settings_obj.smtp_port,
                username=settings_obj.smtp_user,
                password=settings_obj.smtp_password,
                use_tls=settings_obj.smtp_use_tls,
                fail_silently=False,
            )
            from_email = settings_obj.smtp_from_email or 'noreply@sgn-rdc.local'
            mode = 'smtp'
        else:
            conn = None
            from_email = django_settings.DEFAULT_FROM_EMAIL

        site_name = settings_obj.site_name or 'SGN RDC'
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
        err_msg = "Échec de l'envoi : %s" % str(e)
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
    return render(request, 'super_admin/corbeille.html', {'ecoles': ecoles})


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
    try:
        from super_admin.models import PlatformSettings
        ps = PlatformSettings.objects.get(pk=1)
        site_name = ps.site_name or 'SGN RDC'
    except Exception:
        site_name = 'SGN RDC'

    subject = ("[Renouvellement] " if regeneration else "") + "Vos identifiants - Plateforme %s" % site_name
    message = (
        "Bonjour %s,\n\n"
        "%s\n\n"
        "Identifiants de connexion :\n"
        "  Email              : %s\n"
        "  Mot de passe temp. : %s\n\n"
        "Connexion : %s\n"
        "Vous devrez changer votre mot de passe a la premiere connexion.\n\n"
        "-- %s"
    ) % (
        admin.get_full_name(),
        "Un nouveau mot de passe temporaire a ete genere pour votre compte." if regeneration
            else ("Votre ecole \u00ab %s \u00bb a ete creee sur la plateforme %s." % (ecole.nom, site_name)),
        admin.email,
        temp_pwd,
        request.build_absolute_uri('/login/'),
        site_name,
    )
    try:
        send_mail(subject, message, _get_smtp_from_email(), [admin.email], fail_silently=False)
        logger.info('CREDENTIALS_EMAIL_SENT to=%s', admin.email)
    except Exception as e:
        logger.warning('CREDENTIALS_EMAIL_FAILED to=%s err=%s', admin.email, e)
