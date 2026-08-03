"""
Backend e-mail dynamique — EducNet
Utilise les paramètres SMTP de PlatformSettings quand smtp_actif=True,
sinon se replie sur les variables d'environnement, puis sur le backend console.

Ordre de priorité pour le mot de passe SMTP :
  1. Variable d'env EMAIL_HOST_PASSWORD (plus stable sur Vercel / Replit)
  2. PlatformSettings.smtp_password (DB)

Cela évite de perdre la configuration SMTP si la BDD est réinitialisée ou
si le mot de passe applicatif Gmail est saisi dans les env vars du déploiement.
"""
import logging
import os
import threading

from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger('sgn.security')

# Timeout (secondes) pour la connexion SMTP
_SMTP_TIMEOUT = 10

# Lock pour la construction du backend (évite les races au démarrage)
_lock = threading.Lock()


def _build_smtp_backend(host, port, user, password, use_ssl, use_tls, fail_silently):
    """Construit un backend SMTP Django à partir des paramètres fournis."""
    from django.core.mail.backends.smtp import EmailBackend
    return EmailBackend(
        host=host,
        port=port,
        username=user or '',
        password=password or '',
        use_tls=use_tls and not use_ssl,
        use_ssl=use_ssl,
        timeout=_SMTP_TIMEOUT,
        fail_silently=fail_silently,
    )


class DynamicEmailBackend(BaseEmailBackend):
    """
    Délègue à SMTP ou Console selon la configuration disponible.

    Ordre de résolution :
      1. PlatformSettings (DB) si smtp_actif=True et smtp_host non vide.
      2. Variables d'environnement EMAIL_HOST / EMAIL_HOST_USER /
         EMAIL_HOST_PASSWORD si EMAIL_HOST est défini.
      3. Backend Console Django (développement).

    Le mot de passe est toujours préféré depuis EMAIL_HOST_PASSWORD (env var)
    sur le champ DB, afin de survivre aux réinitialisations de la base.
    Le backend est reconstruit à chaque appel (thread-safe, pas de connexion
    SMTP dormante partagée entre requêtes).
    """

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self._fail_silently = fail_silently

    # ── Résolution du backend ─────────────────────────────────────────────────

    def _get_backend(self):
        """
        Retourne le backend e-mail adapté.
        Priorité : DB > env vars > console.
        """
        # ── 1. Tentative via PlatformSettings (DB) ───────────────────────────
        try:
            from super_admin.models import PlatformSettings
            ps = PlatformSettings.get_settings()  # get_or_create pk=1 — jamais DoesNotExist

            if ps.smtp_actif and ps.smtp_host:
                # Le mot de passe env var prend la priorité sur le champ DB
                # pour résister aux réinitialisations de BDD sur Vercel/Replit.
                password = (
                    os.environ.get('EMAIL_HOST_PASSWORD', '').strip()
                    or ps.smtp_password
                    or ''
                )
                use_ssl = getattr(ps, 'smtp_use_ssl', False)
                use_tls = getattr(ps, 'smtp_use_tls', True)
                backend = _build_smtp_backend(
                    host=ps.smtp_host,
                    port=ps.smtp_port or (465 if use_ssl else 587),
                    user=ps.smtp_user or '',
                    password=password,
                    use_ssl=use_ssl,
                    use_tls=use_tls,
                    fail_silently=self._fail_silently,
                )
                logger.debug(
                    'DynamicEmailBackend: SMTP DB actif (host=%s, user=%s, pwd_src=%s).',
                    ps.smtp_host, ps.smtp_user,
                    'env' if os.environ.get('EMAIL_HOST_PASSWORD') else 'db',
                )
                return backend

        except Exception as exc:
            logger.warning(
                'DynamicEmailBackend: impossible de charger PlatformSettings — %s', exc
            )

        # ── 2. Repli sur les variables d'environnement ───────────────────────
        env_host = os.environ.get('EMAIL_HOST', '').strip()
        if env_host:
            port     = int(os.environ.get('EMAIL_PORT', 587))
            user     = os.environ.get('EMAIL_HOST_USER', '').strip()
            password = os.environ.get('EMAIL_HOST_PASSWORD', '').strip()
            use_ssl  = os.environ.get('EMAIL_USE_SSL', 'False').strip().lower() == 'true'
            use_tls  = os.environ.get('EMAIL_USE_TLS', 'True').strip().lower() == 'true'
            logger.info(
                'DynamicEmailBackend: SMTP depuis env vars (host=%s).', env_host
            )
            return _build_smtp_backend(
                host=env_host, port=port, user=user, password=password,
                use_ssl=use_ssl, use_tls=use_tls,
                fail_silently=self._fail_silently,
            )

        # ── 3. Backend console (développement) ───────────────────────────────
        logger.debug('DynamicEmailBackend: aucune config SMTP — backend console.')
        from django.core.mail.backends.console import EmailBackend as ConsoleBackend
        return ConsoleBackend(fail_silently=self._fail_silently)

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
