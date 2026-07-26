from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class EmailBackend(ModelBackend):
    """Authentification par adresse e-mail au lieu du nom d'utilisateur."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        try:
            user = User.objects.get(email__iexact=username)
        except User.DoesNotExist:
            # Fallback : tenter par nom d'utilisateur (compatibilité compte préfet existant)
            try:
                user = User.objects.get(username__iexact=username)
            except User.DoesNotExist:
                return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
