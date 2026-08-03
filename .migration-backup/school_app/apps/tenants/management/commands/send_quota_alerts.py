"""
Commande de gestion : send_quota_alerts

Vérifie les quotas de toutes les écoles actives.
Pour chaque ressource (élèves, enseignants, classes, utilisateurs) dont l'utilisation
dépasse le seuil configuré dans PlatformSettings, envoie :
  - Un e-mail à l'administrateur de l'école (si alerte_quota_email_actif)
  - Une notification in-app à l'admin de l'école (si alerte_quota_app_actif)

Usage :
    python manage.py send_quota_alerts
    python manage.py send_quota_alerts --dry-run
    python manage.py send_quota_alerts --seuil 75   # override du seuil (%)

À planifier via cron (ex. : tous les jours à 6h00) :
    0 6 * * * cd /path/to/school_app && python manage.py send_quota_alerts
"""
import logging
from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger('sgn')

_RESSOURCE_LABELS = {
    'eleves':       'Élèves',
    'enseignants':  'Enseignants',
    'classes':      'Classes',
    'utilisateurs': 'Utilisateurs',
}


class Command(BaseCommand):
    help = "Envoie des alertes e-mail et in-app aux écoles dont les quotas approchent de la limite."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Affiche les alertes sans les envoyer ni les créer.",
        )
        parser.add_argument(
            '--seuil', type=int, default=None,
            help="Seuil d'alerte en pourcentage (surcharge le paramètre PlatformSettings).",
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        seuil_override = options['seuil']

        from tenants.models import Ecole
        from super_admin.models import PlatformSettings
        from tenants.utils.quotas import get_quotas_usage

        ps = PlatformSettings.get_settings()
        seuil = seuil_override if seuil_override is not None else ps.alerte_quota_seuil

        self.stdout.write(self.style.MIGRATE_HEADING(
            "\n═══ Alertes de quota — %s (seuil : %d%%) ═══\n" % (date.today().isoformat(), seuil)
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING("  Mode DRY-RUN : aucune alerte ne sera envoyée.\n"))

        ecoles = Ecole.objects.filter(
            is_deleted=False,
            statut='active',
        ).select_related('plan')

        nb_alertes_email = 0
        nb_alertes_app   = 0
        nb_ecoles        = 0

        for ecole in ecoles:
            if not ecole.plan:
                continue

            try:
                quotas = get_quotas_usage(ecole)
            except Exception as e:
                logger.warning('QUOTA_ALERT_SKIP ecole=%s err=%s', ecole.nom, e)
                continue

            # Quotas dépassant le seuil
            quotas_en_alerte = []
            for key, label in _RESSOURCE_LABELS.items():
                q = quotas.get(key)
                if not q:
                    continue
                if q.get('maximum', 0) <= 0:
                    continue
                pct = q.get('pourcentage', 0)
                if pct >= seuil:
                    quotas_en_alerte.append({
                        'key':         key,
                        'label':       label,
                        'usage':       q.get('usage', 0),
                        'maximum':     q.get('maximum', 0),
                        'pourcentage': pct,
                    })

            if not quotas_en_alerte:
                continue

            nb_ecoles += 1
            self.stdout.write(
                "  École : %s — %d quota(s) en alerte" % (ecole.nom, len(quotas_en_alerte))
            )
            for q in quotas_en_alerte:
                self.stdout.write(
                    "    · %s : %d/%d (%d%%)" % (
                        q['label'], q['usage'], q['maximum'], q['pourcentage']
                    )
                )

            # ── Récupérer l'admin de l'école ──────────────────────────────
            admin = self._get_admin_ecole(ecole)
            if not admin:
                self.stdout.write(
                    self.style.WARNING("    ⚠ Aucun admin trouvé pour %s" % ecole.nom)
                )
                continue

            # ── Envoyer e-mail ────────────────────────────────────────────
            if ps.alerte_quota_email_actif and not dry_run:
                try:
                    self._envoyer_email_alerte(ps, ecole, admin, quotas_en_alerte)
                    nb_alertes_email += 1
                    self.stdout.write(
                        self.style.SUCCESS("    ✓ E-mail envoyé à %s" % admin.email)
                    )
                except Exception as e:
                    logger.warning(
                        'QUOTA_ALERT_EMAIL_FAILED ecole=%s err=%s', ecole.nom, e
                    )
                    self.stdout.write(
                        self.style.ERROR("    ✗ E-mail échoué : %s" % e)
                    )
            elif dry_run:
                self.stdout.write("    [DRY] E-mail → %s" % admin.email)

            # ── Créer notification in-app ──────────────────────────────────
            if ps.alerte_quota_app_actif and not dry_run:
                try:
                    nb_crees = self._creer_notifications_app(
                        ps, ecole, admin, quotas_en_alerte
                    )
                    nb_alertes_app += nb_crees
                    self.stdout.write(
                        self.style.SUCCESS(
                            "    ✓ %d notification(s) in-app créée(s)" % nb_crees
                        )
                    )
                except Exception as e:
                    logger.warning(
                        'QUOTA_ALERT_NOTIF_FAILED ecole=%s err=%s', ecole.nom, e
                    )
                    self.stdout.write(
                        self.style.ERROR("    ✗ Notification in-app échouée : %s" % e)
                    )
            elif dry_run:
                self.stdout.write("    [DRY] Notification in-app pour l'admin")

        # ── Résumé ────────────────────────────────────────────────────────
        self.stdout.write("\n  Résumé :")
        self.stdout.write("    Écoles avec alertes       : %d" % nb_ecoles)
        self.stdout.write("    E-mails envoyés           : %d" % nb_alertes_email)
        self.stdout.write("    Notifications in-app      : %d" % nb_alertes_app)
        if dry_run:
            self.stdout.write(self.style.WARNING("\n  DRY-RUN terminé — rien envoyé.\n"))
        else:
            self.stdout.write(self.style.SUCCESS("\n  ✔ Alertes traitées.\n"))
            logger.info(
                'CMD_QUOTA_ALERTS: ecoles=%d emails=%d notifs=%d',
                nb_ecoles, nb_alertes_email, nb_alertes_app,
            )

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _get_admin_ecole(self, ecole):
        """Retourne l'AdminEcole principal de l'école (schéma public)."""
        try:
            from tenants.models import AdminEcole
            return (
                AdminEcole.objects
                .filter(ecole=ecole, is_active=True)
                .order_by('created_at')
                .first()
            )
        except Exception:
            return None

    def _envoyer_email_alerte(self, ps, ecole, admin, quotas_en_alerte):
        """Envoie l'e-mail d'alerte quota à l'admin de l'école."""
        from django.core.mail import get_connection, EmailMessage
        from django.template.loader import render_to_string
        from django.conf import settings as django_settings

        site_name = ps.site_name or 'EducNet'

        # ── Connexion SMTP ──────────────────────────────────────────────
        if ps.smtp_actif and ps.smtp_host:
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

        # ── Message personnalisé ──────────────────────────────────────
        premier_quota = quotas_en_alerte[0]
        variables = {
            'ecole':        ecole.nom,
            'ressource':    premier_quota['label'],
            'usage':        premier_quota['usage'],
            'maximum':      premier_quota['maximum'],
            'pourcentage':  premier_quota['pourcentage'],
            'site':         site_name,
        }
        if ps.alerte_quota_message_email:
            try:
                intro = ps.alerte_quota_message_email.format(**variables)
            except (KeyError, ValueError):
                intro = ps.alerte_quota_message_email
        else:
            nb = len(quotas_en_alerte)
            intro = (
                "Votre école « %(ecole)s » a atteint le seuil d'alerte sur %(nb)d quota%(s)s. "
                "Nous vous recommandons de consulter votre abonnement et de contacter "
                "l'administrateur de la plateforme si vous souhaitez augmenter vos limites."
            ) % {'ecole': ecole.nom, 'nb': nb, 's': 's' if nb > 1 else ''}

        # ── Logo ──────────────────────────────────────────────────────
        logo_url = ''
        try:
            if ps.site_logo:
                logo_url = ps.site_logo.url
        except Exception:
            pass

        ctx = {
            'site_name':          site_name,
            'site_slogan':        ps.site_slogan or '',
            'site_web':           ps.site_web or '',
            'couleur':            ps.couleur_principale or '#4D44B5',
            'logo_url':           logo_url,
            'ecole_nom':          ecole.nom,
            'prenom_nom':         admin.get_full_name(),
            'intro':              intro,
            'message_personnalise': '',
            'quotas_en_alerte':   quotas_en_alerte,
            'abonnement_url':     '/abonnement/',
            'date_envoi':         timezone.now().strftime('%d/%m/%Y à %H:%M'),
        }

        html_body = render_to_string('emails/quota_alert.html', ctx)
        subject   = (
            "[%(site)s] ⚠️ Alerte quota — %(ecole)s (%(nb)d ressource%(s)s en limite)"
        ) % {
            'site':  site_name,
            'ecole': ecole.nom,
            'nb':    len(quotas_en_alerte),
            's':     's' if len(quotas_en_alerte) > 1 else '',
        }

        msg = EmailMessage(
            subject=subject,
            body=html_body,
            from_email=from_email,
            to=[admin.email],
            connection=conn,
        )
        msg.content_subtype = 'html'
        msg.send(fail_silently=False)
        logger.info(
            'QUOTA_ALERT_EMAIL_SENT ecole=%s admin=%s quotas=%s',
            ecole.nom, admin.email,
            [q['key'] for q in quotas_en_alerte],
        )

    def _creer_notifications_app(self, ps, ecole, admin, quotas_en_alerte):
        """
        Crée des notifications in-app dans le schéma tenant de l'école.
        Retourne le nombre de notifications créées.
        """
        from django.db import connection

        site_name = ps.site_name or 'EducNet'
        nb_crees  = 0

        # Basculer vers le schéma de l'école pour accéder aux modèles tenant
        original_schema = connection.schema_name
        try:
            connection.set_schema(ecole.schema_name)
            from notifications.models import Notification
            from accounts.models import CustomUser

            # Trouver le user admin dans le schéma tenant (par email)
            try:
                user = CustomUser.objects.get(email=admin.email)
            except CustomUser.DoesNotExist:
                # Fallback : premier admin_ecole dans le tenant
                try:
                    user = CustomUser.objects.filter(role='admin_ecole').first()
                except Exception:
                    user = None

            if not user:
                return 0

            for q in quotas_en_alerte:
                variables = {
                    'ecole':       ecole.nom,
                    'ressource':   q['label'],
                    'usage':       q['usage'],
                    'maximum':     q['maximum'],
                    'pourcentage': q['pourcentage'],
                }

                # Titre
                titre = "⚠️ Quota %s : %d%% utilisé" % (q['label'], q['pourcentage'])

                # Description personnalisée ou par défaut
                if ps.alerte_quota_message_app:
                    try:
                        description = ps.alerte_quota_message_app.format(**variables)
                    except (KeyError, ValueError):
                        description = ps.alerte_quota_message_app
                else:
                    description = (
                        "Quota %(ressource)s : %(usage)d/%(maximum)d (%(pourcentage)d%% utilisé). "
                        "Consultez votre abonnement pour augmenter cette limite."
                    ) % variables

                priorite = 'CRITIQUE' if q['pourcentage'] >= 95 else 'AVERT'

                Notification.objects.create(
                    destinataire=user,
                    titre=titre,
                    description=description,
                    categorie='SYSTEME',
                    priorite=priorite,
                    type_notif='SYSTEME',
                    lien='/abonnement/',
                )
                nb_crees += 1

        finally:
            connection.set_schema(original_schema)

        return nb_crees
