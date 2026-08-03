import json
import secrets

import pyotp
from django.contrib.auth.hashers import make_password, check_password
from django.db import models
from django.utils import timezone


class SuperAdmin(models.Model):
    email = models.EmailField("Email", unique=True)
    password = models.CharField("Mot de passe (hache)", max_length=255)
    nom = models.CharField("Nom", max_length=100, blank=True)
    prenom = models.CharField("Prenom", max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    # 2FA
    totp_secret = models.CharField(max_length=100, blank=True)
    totp_enabled = models.BooleanField("2FA active", default=False)
    totp_recovery_codes = models.TextField(blank=True, default='[]')

    must_change_password = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField("Derniere connexion", null=True, blank=True)

    class Meta:
        app_label = 'super_admin'
        verbose_name = 'Super-Administrateur'

    def __str__(self):
        return "SuperAdmin: %s" % self.email

    def get_full_name(self):
        return ("%s %s" % (self.prenom, self.nom)).strip() or self.email

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def generate_totp_secret(self):
        self.totp_secret = pyotp.random_base32()
        self.save(update_fields=['totp_secret'])
        return self.totp_secret

    def get_totp_uri(self):
        return pyotp.totp.TOTP(self.totp_secret).provisioning_uri(
            name=self.email,
            issuer_name='EducNet Platform'
        )

    def verify_totp(self, code):
        if not self.totp_secret:
            return False
        return pyotp.TOTP(self.totp_secret).verify(code, valid_window=1)

    def generate_recovery_codes(self):
        codes = [secrets.token_hex(8) for _ in range(8)]
        self.totp_recovery_codes = json.dumps(codes)
        self.save(update_fields=['totp_recovery_codes'])
        return codes

    def use_recovery_code(self, code):
        codes = json.loads(self.totp_recovery_codes or '[]')
        if code in codes:
            codes.remove(code)
            self.totp_recovery_codes = json.dumps(codes)
            self.save(update_fields=['totp_recovery_codes'])
            return True
        return False

    def remaining_recovery_codes(self):
        return len(json.loads(self.totp_recovery_codes or '[]'))

    def get_initiales(self):
        parts = self.get_full_name().split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        if parts:
            return parts[0][:2].upper()
        return self.email[:2].upper()

    @property
    def is_authenticated(self):
        return True

    @property
    def is_super_admin(self):
        return True


class PlatformSettings(models.Model):
    """Paramètres globaux de la plateforme EducNet (singleton pk=1)."""
    site_name    = models.CharField("Nom du site",    max_length=200, default="EducNet")
    site_slogan  = models.CharField("Slogan",         max_length=300, blank=True, default="School Governance Network")
    site_devise  = models.CharField("Devise",         max_length=300, blank=True)
    site_logo    = models.ImageField("Logo plateforme", upload_to='platform/', null=True, blank=True)
    adresse      = models.TextField("Adresse",        blank=True)
    email_contact = models.EmailField("E-mail contact", blank=True)
    telephone    = models.CharField("Téléphone",      max_length=50, blank=True)
    site_web     = models.URLField("Site web",        blank=True)
    couleur_principale = models.CharField("Couleur principale", max_length=7, default="#4D44B5")

    # ── Email / SMTP ──────────────────────────────────────────────────────────
    smtp_actif       = models.BooleanField("Activer l'envoi SMTP réel", default=False)
    smtp_host        = models.CharField("Serveur SMTP", max_length=200, blank=True, default='',
                                        help_text="Ex: smtp.gmail.com, smtp.office365.com")
    smtp_port        = models.PositiveIntegerField("Port SMTP", default=587)
    smtp_use_tls     = models.BooleanField("Utiliser TLS", default=True)
    smtp_user        = models.CharField("Identifiant SMTP", max_length=200, blank=True, default='')
    smtp_password    = models.CharField("Mot de passe SMTP", max_length=300, blank=True, default='')
    smtp_from_email  = models.CharField("Adresse d'expédition (From)", max_length=200,
                                         blank=True, default='noreply@educnet.local')

    # ── Alertes de quota ──────────────────────────────────────────────────────
    alerte_quota_seuil = models.PositiveIntegerField(
        "Seuil d'alerte quota (%)", default=80,
        help_text="Pourcentage d'utilisation à partir duquel une alerte est envoyée (0–100)."
    )
    alerte_quota_email_actif = models.BooleanField(
        "Alertes quota par e-mail", default=True,
        help_text="Envoyer un e-mail à l'admin de l'école quand un quota atteint le seuil."
    )
    alerte_quota_app_actif = models.BooleanField(
        "Alertes quota dans l'app", default=True,
        help_text="Afficher une notification in-app à l'administrateur de l'école."
    )
    alerte_quota_message_email = models.TextField(
        "Modèle de message e-mail (alerte quota)", blank=True, default='',
        help_text=(
            "Variables disponibles : {ecole}, {ressource}, {usage}, {maximum}, {pourcentage}, {site}. "
            "Laissez vide pour utiliser le message par défaut."
        )
    )
    alerte_quota_message_app = models.TextField(
        "Modèle de message in-app (alerte quota)", blank=True, default='',
        help_text=(
            "Message court affiché dans la notification in-app. "
            "Variables : {ecole}, {ressource}, {usage}, {maximum}, {pourcentage}. "
            "Laissez vide pour le message par défaut."
        )
    )

    class Meta:
        app_label = 'super_admin'
        verbose_name = "Paramètres de la plateforme"

    def __str__(self):
        return self.site_name

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
