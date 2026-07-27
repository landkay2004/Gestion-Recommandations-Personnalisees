import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import CustomUser, generate_temp_password
from .forms import (
    LoginForm, UserCreateForm, UserUpdateForm,
    ForcePasswordChangeForm, ProfileForm, ChangePasswordForm,
)
from teachers.models import Teacher

logger_sec = logging.getLogger('sgn.security')
logger     = logging.getLogger('sgn')


# ── Authentification ──────────────────────────────────────────────────────────
def login_view(request):
    if request.user.is_authenticated:
        if request.user.must_change_password:
            return redirect('force_change_password')
        return redirect('dashboard')

    # Super-admin a sa propre page de login
    if getattr(request, 'super_admin', None):
        return redirect('super_admin:dashboard')

    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST':
        identifier = request.POST.get('username', '').strip()
        password   = request.POST.get('password', '')

        # 1. Tentative via MultiTenantAuthBackend (super-admin, admin-école, tenant users)
        from config.backends import MultiTenantAuthBackend
        mt_backend = MultiTenantAuthBackend()
        user = mt_backend.authenticate(request, username=identifier, password=password)

        # 2. Super-admin : géré par sa propre session, rediriger
        if getattr(request, '_super_admin_authenticated', None):
            sa = request._super_admin_authenticated
            request.session['super_admin_id']  = sa.pk
            request.session['tenant_schema']   = 'public'
            request.session['user_type']       = 'super_admin'
            request.session['sa_2fa_verified'] = not sa.totp_enabled
            sa_url = '/super-admin/2fa/' if sa.totp_enabled else '/super-admin/'
            return redirect(sa_url)

        # 3. Admin-école : session-based, pas de Django user
        if getattr(request, '_admin_ecole_authenticated', None):
            admin = request._admin_ecole_authenticated
            request.session['admin_ecole_id'] = admin.pk
            request.session['tenant_schema']  = admin.ecole.schema_name
            request.session['user_type']      = 'admin_ecole'
            if not admin.onboarding_complete:
                return redirect('onboarding:etape_courante')
            # Admin avec onboarding terminé → se connecte via son compte CustomUser
            _switch_tenant_schema(admin.ecole.schema_name)
            try:
                user_obj = CustomUser.objects.get(email__iexact=admin.email, role='admin_ecole')
                login(request, user_obj, backend='accounts.backends.EmailBackend')
            except CustomUser.DoesNotExist:
                pass
            return redirect('dashboard')

        # 4. Utilisateur école normal (préfet / enseignant)
        if user:
            login(request, user)
            ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '?'))
            logger_sec.info('CONNEXION user=%s role=%s ip=%s', user.username, user.role, ip)
            if user.must_change_password:
                return redirect('force_change_password')
            return redirect('dashboard')

        # 5. Fallback Django auth standard (SQLite sans multi-tenant)
        if form.is_valid():
            std_user = form.get_user()
            login(request, std_user)
            if std_user.must_change_password:
                return redirect('force_change_password')
            return redirect('dashboard')

        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '?'))
        logger_sec.warning('ECHEC_CONNEXION identifier=%s ip=%s', identifier, ip)

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    if request.user.is_authenticated:
        logger_sec.info('DECONNEXION user=%s', request.user.username)
    # Nettoyer toutes les clés de session multi-tenant
    for key in ['tenant_schema', 'user_type', 'super_admin_id', 'admin_ecole_id', 'sa_2fa_verified']:
        request.session.pop(key, None)
    logout(request)
    return redirect('login')


# ── Changement de mot de passe forcé ─────────────────────────────────────────
@login_required
def force_change_password(request):
    if not request.user.must_change_password:
        return redirect('dashboard')

    form = ForcePasswordChangeForm(user=request.user, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        request.user.set_password(form.cleaned_data['new_password'])
        request.user.must_change_password = False
        request.user.save(update_fields=['password', 'must_change_password'])
        update_session_auth_hash(request, request.user)
        messages.success(request, 'Mot de passe mis à jour. Bienvenue !')
        return redirect('dashboard')

    return render(request, 'accounts/force_password_change.html', {'form': form, 'hide_sidebar': True})


# ── Décorateurs de rôle ───────────────────────────────────────────────────────
def prefet_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_prefet():
            messages.error(request, "Accès réservé au préfet des études.")
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


# ── Gestion des utilisateurs ──────────────────────────────────────────────────
@login_required
@prefet_required
def user_list(request):
    users = CustomUser.objects.all().order_by('last_name', 'first_name')
    return render(request, 'accounts/user_list.html', {'users': users})


@login_required
@prefet_required
def user_create(request):
    form = UserCreateForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save(commit=False)
        temp_pwd = generate_temp_password()
        user.set_password(temp_pwd)
        user.must_change_password = True
        user.save()
        if user.role == 'enseignant':
            Teacher.objects.get_or_create(user=user)
        try:
            from tenants.models import AnnuaireUtilisateur
            AnnuaireUtilisateur.objects.get_or_create(
                email=user.email.lower(),
                defaults={
                    'schema_name': request.session.get('tenant_schema', 'public'),
                    'type_compte': user.role,
                }
            )
        except Exception:
            pass
        messages.success(request, f'Utilisateur créé. Mot de passe temporaire : {temp_pwd}')
        return render(request, 'accounts/user_created.html', {'new_user': user, 'temp_pwd': temp_pwd})
    return render(request, 'accounts/user_form.html', {'form': form, 'mode': 'create'})


@login_required
@prefet_required
def user_update(request, pk):
    user = get_object_or_404(CustomUser, pk=pk)
    form = UserUpdateForm(request.POST or None, instance=user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Utilisateur mis à jour.')
        return redirect('user_list')
    return render(request, 'accounts/user_form.html', {'form': form, 'mode': 'update', 'obj': user})


@login_required
@prefet_required
def user_delete(request, pk):
    user = get_object_or_404(CustomUser, pk=pk)
    if request.method == 'POST':
        user.delete()
        messages.success(request, 'Utilisateur supprimé.')
        return redirect('user_list')
    return render(request, 'accounts/user_confirm_delete.html', {'obj': user})


@login_required
@prefet_required
def reset_user_password(request, pk):
    user = get_object_or_404(CustomUser, pk=pk)
    if request.method == 'POST':
        temp_pwd = generate_temp_password()
        user.set_password(temp_pwd)
        user.must_change_password = True
        user.save(update_fields=['password', 'must_change_password'])
        messages.success(request, f'Mot de passe réinitialisé : {temp_pwd}')
        return render(request, 'accounts/reset_confirm.html', {'obj': user, 'temp_pwd': temp_pwd})
    return render(request, 'accounts/reset_confirm.html', {'obj': user})


@login_required
def profile_view(request):
    active_tab = request.GET.get('tab', 'info')
    profile_form = ProfileForm(instance=request.user)
    password_form = ChangePasswordForm(user=request.user)

    if request.method == 'POST':
        action    = request.POST.get('_action', 'profile')
        active_tab = request.POST.get('_tab', 'info')

        if action == 'profile':
            profile_form = ProfileForm(request.POST, request.FILES, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Profil mis à jour.')
                return redirect('profile_view')
        elif action == 'password':
            password_form = ChangePasswordForm(user=request.user, data=request.POST)
            if password_form.is_valid():
                request.user.set_password(password_form.cleaned_data['new_password'])
                request.user.save(update_fields=['password'])
                update_session_auth_hash(request, request.user)
                messages.success(request, 'Mot de passe changé.')
                return redirect(f'{request.path}?tab=password')

    # Profil enseignant (classes enseignées)
    teacher_profile = None
    if request.user.is_enseignant():
        try:
            teacher_profile = Teacher.objects.get(user=request.user)
        except Teacher.DoesNotExist:
            pass

    return render(request, 'accounts/profile.html', {
        'profile_form': profile_form,
        'password_form': password_form,
        'active_tab': active_tab,
        'teacher_profile': teacher_profile,
    })


# ── Utilitaire ────────────────────────────────────────────────────────────────
def _switch_tenant_schema(schema_name: str):
    from django.db import connection
    if 'sqlite' in connection.settings_dict.get('ENGINE', ''):
        return
    try:
        from django_tenants.utils import get_tenant_model
        tenant = get_tenant_model().objects.get(schema_name=schema_name)
        connection.set_tenant(tenant)
    except Exception:
        pass
