from django.shortcuts import redirect
from django.urls import reverse


_ALLOWED_PATHS = None


def _get_allowed():
    global _ALLOWED_PATHS
    if _ALLOWED_PATHS is None:
        try:
            _ALLOWED_PATHS = {
                reverse('login'),
                reverse('logout'),
                reverse('force_change_password'),
            }
        except Exception:
            _ALLOWED_PATHS = {'/login/', '/logout/', '/changer-mot-de-passe/'}
    return _ALLOWED_PATHS


class ForcePasswordChangeMiddleware:
    """Redirige vers la page de changement de mot de passe si must_change_password est True."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and getattr(request.user, 'must_change_password', False)
            and request.path not in _get_allowed()
            and not request.path.startswith('/static/')
            and not request.path.startswith('/media/')
            and not request.path.startswith('/portail/')
            and not request.path.startswith('/super-admin/')
            and not request.path.startswith('/onboarding/')
        ):
            return redirect('force_change_password')
        return self.get_response(request)
