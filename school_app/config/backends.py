"""
Backend d'authentification multi-tenant.
Ordre de vérification :
  1. SuperAdmin (schéma public, table super_admin)
  2. AdminEcole (schéma public, table tenants_adminecole)
  3. Utilisateurs école (prefet/enseignant dans le schéma tenant via AnnuaireUtilisateur)
"""
import logging
from django.db import connection

logger_sec = logging.getLogger('sgn.security')


class MultiTenantAuthBackend:

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None

        email = username.strip().lower()

        # ── 1. SuperAdmin ──────────────────────────────────────────────────
        try:
            from super_admin.models import SuperAdmin
            sa = SuperAdmin.objects.get(email__iexact=email, is_active=True)
            if sa.check_password(password):
                if request:
                    request.session['user_type']     = 'super_admin'
                    request.session['tenant_schema']  = 'public'
                    request.session['super_admin_id'] = sa.pk
                logger_sec.info('CONNEXION super_admin email=%s', email)
                # On retourne None ici car SuperAdmin n'est pas un AbstractUser Django
                # La vue super-admin gère elle-même la session
                request._super_admin_authenticated = sa
                return None
        except Exception:
            pass

        # ── 2. AdminEcole ──────────────────────────────────────────────────
        try:
            from tenants.models import AdminEcole
            admin = AdminEcole.objects.get(email__iexact=email, is_active=True)
            if admin.check_password(password):
                if request:
                    request.session['user_type']      = 'admin_ecole'
                    request.session['tenant_schema']  = admin.ecole.schema_name
                    request.session['admin_ecole_id'] = admin.pk
                logger_sec.info('CONNEXION admin_ecole email=%s ecole=%s', email, admin.ecole.schema_name)
                request._admin_ecole_authenticated = admin
                return None
        except Exception:
            pass

        # ── 3. Utilisateurs école (préfet/enseignant) ─────────────────────
        try:
            from tenants.models import AnnuaireUtilisateur
            entry = AnnuaireUtilisateur.objects.get(email__iexact=email)
            schema_name = entry.schema_name

            # Basculer vers le bon schéma
            _switch_schema(schema_name)

            from django.contrib.auth import get_user_model
            UserModel = get_user_model()
            try:
                user = UserModel.objects.get(email__iexact=email)
            except UserModel.DoesNotExist:
                try:
                    user = UserModel.objects.get(username__iexact=email)
                except UserModel.DoesNotExist:
                    return None

            if user.check_password(password) and user.is_active:
                if request:
                    request.session['user_type']    = entry.type_compte
                    request.session['tenant_schema'] = schema_name
                logger_sec.info(
                    'CONNEXION user email=%s schema=%s role=%s',
                    email, schema_name, getattr(user, 'role', '?')
                )
                return user

        except Exception as e:
            logger_sec.debug('MultiTenantAuthBackend lookup error: %s', e)

        return None

    def get_user(self, user_id):
        from django.contrib.auth import get_user_model
        UserModel = get_user_model()
        try:
            return UserModel.objects.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None


def _switch_schema(schema_name: str):
    """Bascule la connexion PostgreSQL vers le schéma donné."""
    if 'sqlite' in connection.settings_dict.get('ENGINE', ''):
        return
    try:
        from django_tenants.utils import get_tenant_model
        tenant = get_tenant_model().objects.get(schema_name=schema_name)
        connection.set_tenant(tenant)
    except Exception:
        pass
