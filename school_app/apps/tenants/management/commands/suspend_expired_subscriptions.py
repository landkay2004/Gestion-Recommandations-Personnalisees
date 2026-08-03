"""
Commande de gestion : suspend_expired_subscriptions

Parcourt tous les abonnements actifs dont la date de fin est dépassée
(y compris le délai de grâce) et met à jour le statut de l'école.

Usage :
    python manage.py suspend_expired_subscriptions
    python manage.py suspend_expired_subscriptions --dry-run
    python manage.py suspend_expired_subscriptions --grace 3   # délai de grâce additionnel (jours)

À planifier via cron (ex. : tous les jours à 2h00) :
    0 2 * * * cd /path/to/school_app && python manage.py suspend_expired_subscriptions
"""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger('sgn')


class Command(BaseCommand):
    help = (
        "Suspend automatiquement les abonnements expirés "
        "et met à jour les statuts des écoles correspondantes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Affiche les changements sans les appliquer."
        )
        parser.add_argument(
            '--grace', type=int, default=0,
            help="Jours de grâce additionnels au-delà du délai configuré sur l'école (défaut : 0)."
        )

    def handle(self, *args, **options):
        dry_run       = options['dry_run']
        extra_grace   = options['grace']
        today         = timezone.now().date()

        from tenants.models import Ecole, Abonnement

        self.stdout.write(self.style.MIGRATE_HEADING(
            "\n═══ Suspension des abonnements expirés — %s ═══\n" % today.isoformat()
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING("  Mode DRY-RUN : aucune modification ne sera enregistrée.\n"))

        # ── 1. Mettre à jour les statuts Abonnement expirés ──────────────────
        abonnements = (
            Abonnement.objects
            .select_related('ecole', 'plan')
            .filter(statut__in=['actif', 'essai'])
            .exclude(date_fin__isnull=True)
        )

        nb_expire   = 0
        nb_suspendu = 0

        for ab in abonnements:
            ecole       = ab.ecole
            grace_total = ecole.jours_grace + extra_grace
            grace_limit = ab.date_fin + timedelta(days=grace_total)

            if today <= ab.date_fin:
                continue  # encore actif

            if today <= grace_limit:
                # Dans le délai de grâce : marquer comme expiré (lecture seule)
                if ab.statut != 'expire':
                    self._log_change(ecole, 'expire', dry_run)
                    if not dry_run:
                        ab.changer_statut(
                            'expire',
                            motif="Expiration automatique (dans le délai de grâce)",
                            modifie_par='système',
                        )
                        ecole.statut = 'expiree'
                        ecole.save(update_fields=['statut'])
                    nb_expire += 1
            else:
                # Au-delà du délai de grâce : suspendre
                if ab.statut != 'suspendu':
                    self._log_change(ecole, 'suspendu', dry_run)
                    if not dry_run:
                        ab.changer_statut(
                            'suspendu',
                            motif="Suspension automatique (délai de grâce dépassé)",
                            modifie_par='système',
                        )
                        ecole.statut = 'suspendue'
                        ecole.save(update_fields=['statut'])
                    nb_suspendu += 1

        # ── 2. Synchroniser les Ecoles sans Abonnement (rétrocompat) ────────
        ecoles_sans_ab = (
            Ecole.objects
            .filter(is_deleted=False, statut='active')
            .exclude(abonnement_detail__isnull=False)
            .filter(date_fin_abonnement__isnull=False)
        )
        nb_sync = 0
        for ecole in ecoles_sans_ab:
            grace_limit = ecole.date_fin_abonnement + timedelta(
                days=ecole.jours_grace + extra_grace
            )
            if today > grace_limit:
                self.stdout.write(
                    self.style.WARNING(
                        "  [SYNC] École sans Abonnement expirée : %s" % ecole.nom
                    )
                )
                if not dry_run:
                    ecole.statut = 'suspendue'
                    ecole.save(update_fields=['statut'])
                nb_sync += 1

        # ── 3. Réactiver les abonnements essai encore valides ────────────────
        nb_essai_expire = 0
        essais = (
            Abonnement.objects
            .select_related('ecole', 'plan')
            .filter(statut='essai', date_fin__isnull=False)
        )
        for ab in essais:
            if today > ab.date_fin:
                self._log_change(ab.ecole, 'expire (essai terminé)', dry_run)
                if not dry_run:
                    ab.changer_statut(
                        'expire',
                        motif="Fin de période d'essai",
                        modifie_par='système',
                    )
                    ab.ecole.statut = 'expiree'
                    ab.ecole.save(update_fields=['statut'])
                nb_essai_expire += 1

        # ── Résumé ───────────────────────────────────────────────────────────
        self.stdout.write("\n  Résumé :")
        self.stdout.write("    Abonnements expirés (grâce)  : %d" % nb_expire)
        self.stdout.write("    Abonnements suspendus        : %d" % nb_suspendu)
        self.stdout.write("    Essais terminés              : %d" % nb_essai_expire)
        self.stdout.write("    Écoles synchronisées (legacy): %d" % nb_sync)

        if dry_run:
            self.stdout.write(self.style.WARNING("\n  DRY-RUN : aucune modification appliquée.\n"))
        else:
            self.stdout.write(self.style.SUCCESS(
                "\n  ✔ Traitement terminé. Total modifié : %d\n"
                % (nb_expire + nb_suspendu + nb_essai_expire + nb_sync)
            ))
            logger.info(
                'CMD_SUSPEND_EXPIRED: expire=%d suspendu=%d essai=%d sync=%d',
                nb_expire, nb_suspendu, nb_essai_expire, nb_sync,
            )

    def _log_change(self, ecole, nouveau_statut, dry_run):
        prefix = "[DRY] " if dry_run else ""
        self.stdout.write(
            "  %s%s → statut : %s" % (prefix, ecole.nom, nouveau_statut)
        )
