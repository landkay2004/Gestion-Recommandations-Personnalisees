"""
Backend e-mail dynamique — SGN RDC
Utilise les paramètres SMTP de PlatformSettings quand smtp_actif=True,
sinon bascule sur le backend console (développement).

Améliorations :
- Support SSL (port 465) en plus de TLS/STARTTLS (port 587)
- Timeout configurable
- Journalisation des erreurs
- Pas de connexion partagée entre threads (thread-safe)
"""
import logging
import threading
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger('sgn.security')

# Timeout (secondes) pour la connexion SMTP
_SMTP_TIMEOUT = 10

# Lock pour la construction du backend (évite les races au démarrage)
_lock = threading.Lock()


def _build_smtp_backend(ps, fail_silently):
    """Construit un backend SMTP réel à partir des PlatformSettings."""
    use_ssl = getattr(ps, 'smtp_use_ssl', False)
    use_tls = getattr(ps, 'smtp_use_tls', True) and not use_ssl

    if use_ssl:
        from django.core.mail.backends.smtp import EmailBackend
        return EmailBackend(
            host=ps.smtp_host,
            port=ps.smtp_port or 465,
            username=ps.smtp_user or '',
            password=ps.smtp_password or '',
            use_tls=False,
            use_ssl=True,
            timeout=_SMTP_TIMEOUT,
            fail_silently=fail_silently,
        )
    else:
        from django.core.mail.backends.smtp import EmailBackend
        return EmailBackend(
            host=ps.smtp_host,
            port=ps.smtp_port or 587,
            username=ps.smtp_user or '',
            password=ps.smtp_password or '',
            use_tls=use_tls,
            use_ssl=False,
            timeout=_SMTP_TIMEOUT,
            fail_silently=fail_silently,
        )


class DynamicEmailBackend(BaseEmailBackend):
    """
    Délègue à SMTP ou Console selon PlatformSettings.smtp_actif.

    Le backend est reconstruit à chaque appel send_messages() afin de toujours
    refléter la configuration courante (pas de connexion SMTP dormante).
    """

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self._fail_silently = fail_silently
        # Backend courant (peut être None — reconstruit à la demande)
        self._backend = None

    # ── Construction du backend ───────────────────────────────────────────────

    def _get_backend(self):
        """Renvoie le backend approprié (SMTP ou Console)."""
        try:
            from super_admin.models import PlatformSettings
            ps = PlatformSettings.objects.get(pk=1)
            if ps.smtp_actif and ps.smtp_host:
                return _build_smtp_backend(ps, self._fail_silently)
        except Exception as exc:
            logger.debug('DynamicEmailBackend: SMTP non disponible — %s', exc)

        from django.core.mail.backends.console import EmailBackend
        return EmailBackend(fail_silently=self._fail_silently)

    # ── Interface BaseEmailBackend ────────────────────────────────────────────

    def open(self):
        self._backend = self._get_backend()
        return self._backend.open()

    def close(self):
        if self._backend:
            return self._backend.close()

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        backend = self._get_backend()
        try:
            with backend:
                sent = backend.send_messages(email_messages)
                if sent:
                    logger.info(
                        'EMAIL_SENT count=%d recipients=%s',
                        sent,
                        [m.to for m in email_messages[:5]],
                    )
                return sent
        except Exception as exc:
            logger.error('EMAIL_ERROR %s', exc)
            if not self._fail_silently:
                raise
            return 0

    def __enter__(self):
        self._backend = self._get_backend()
        self._backend.__enter__()
        return self

    def __exit__(self, *args):
        if self._backend:
            self._backend.__exit__(*args)
