"""
Backend e-mail dynamique — SGN RDC
Utilise les paramètres SMTP de PlatformSettings quand smtp_actif=True,
sinon bascule sur le backend console (développement).
"""
from django.core.mail.backends.base import BaseEmailBackend


class DynamicEmailBackend(BaseEmailBackend):
    """Délègue à SMTP ou Console selon PlatformSettings.smtp_actif."""

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self._backend = self._build_backend(fail_silently)

    def _build_backend(self, fail_silently):
        try:
            from super_admin.models import PlatformSettings
            ps = PlatformSettings.objects.get(pk=1)
            if ps.smtp_actif and ps.smtp_host:
                from django.core.mail.backends.smtp import EmailBackend
                return EmailBackend(
                    host=ps.smtp_host,
                    port=ps.smtp_port,
                    username=ps.smtp_user or '',
                    password=ps.smtp_password or '',
                    use_tls=ps.smtp_use_tls,
                    fail_silently=fail_silently,
                )
        except Exception:
            pass
        from django.core.mail.backends.console import EmailBackend
        return EmailBackend(fail_silently=fail_silently)

    # ── Délégation complète vers le backend choisi ────────────────────────────

    def open(self):
        return self._backend.open()

    def close(self):
        return self._backend.close()

    def send_messages(self, email_messages):
        return self._backend.send_messages(email_messages)

    def __enter__(self):
        return self._backend.__enter__()

    def __exit__(self, *args):
        return self._backend.__exit__(*args)
