import json
import secrets

import pyotp
from django.contrib.auth.hashers import make_password, check_password
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone


class SuperAdmin(models.Model):
    email = models.EmailField("Email", unique=True)
    password = models.CharField("Mot de passe (hache)", max_length=255)
    nom = models.CharField("Nom", max_length=100, blank=True)
    prenom = models.CharField("Prenom", max_length=100, blank=True)
    telephone = models.CharField("Téléphone", max_length=50, blank=True, default='')
    photo_profil = models.ImageField("Photo de profil", upload_to='platform/admins/', null=True, blank=True)
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
    site_logo    = models.FileField(
        "Logo plateforme",
        upload_to='platform/',
        null=True,
        blank=True,
        validators=[FileExtensionValidator(['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'])],
        help_text="PNG, JPG, GIF, SVG ou WEBP recommandé. Le logo s'affiche dans la barre latérale, la page de connexion et les en-têtes d'e-mails.",
    )
    adresse      = models.TextField("Adresse",        blank=True)
    contact_adresse = models.TextField("Adresse de contact", blank=True,
                                       help_text="Adresse physique affichée sur la page Contact.")
    email_contact = models.EmailField("E-mail contact", blank=True)
    telephone    = models.CharField("Téléphone",      max_length=50, blank=True)
    contact_whatsapp = models.CharField("WhatsApp",   max_length=32, blank=True,
                                         help_text="Numéro WhatsApp au format international, ex. +243123456789.")
    site_web     = models.URLField("Site web",        blank=True)
    facebook_url = models.URLField("Lien Facebook", blank=True, default='')
    twitter_url  = models.URLField("Lien Twitter / X", blank=True, default='')
    linkedin_url = models.URLField("Lien LinkedIn", blank=True, default='')
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

    # ── Images de fond — page de connexion ────────────────────────────────────
    login_bg_1 = models.ImageField(
        "Image fond login 1", upload_to='platform/login/', null=True, blank=True,
        help_text="Première image de fond du diaporama sur la page de connexion."
    )
    login_bg_2 = models.ImageField(
        "Image fond login 2", upload_to='platform/login/', null=True, blank=True,
        help_text="Deuxième image de fond (optionnel)."
    )
    login_bg_3 = models.ImageField(
        "Image fond login 3", upload_to='platform/login/', null=True, blank=True,
        help_text="Troisième image de fond (optionnel)."
    )

    public_bg_image = models.ImageField(
        "Image de fond publique", upload_to='platform/public/', null=True, blank=True,
        help_text="Image de fond par défaut utilisée quand aucune image spécifique à une page publique n'est configurée."
    )
    public_bg_image_rejoindre = models.ImageField(
        "Image de fond page Rejoindre", upload_to='platform/public/', null=True, blank=True,
        help_text="Image de fond utilisée sur la page Rejoindre. Remplace l'image publique par défaut si elle est définie."
    )
    public_bg_image_inscription = models.ImageField(
        "Image de fond page Inscription", upload_to='platform/public/', null=True, blank=True,
        help_text="Image de fond utilisée sur le formulaire d'inscription. Remplace l'image publique par défaut si elle est définie."
    )
    public_page_bg_color = models.CharField(
        "Couleur de fond publique", max_length=7, default="#0d0b2e",
        help_text="Couleur unie affichée sur les pages publiques lorsque aucune image de fond n'est configurée."
    )

    # ── Page À propos ─────────────────────────────────────────────────────────
    about_titre       = models.CharField("Titre — À propos", max_length=200, blank=True, default='À propos de nous')
    about_description = models.TextField("Description générale", blank=True, default='')
    about_mission     = models.TextField("Notre mission", blank=True, default='')
    about_vision      = models.TextField("Notre vision", blank=True, default='')
    about_valeurs     = models.TextField("Nos valeurs (1 par ligne)", blank=True, default='')

    class Meta:
        app_label = 'super_admin'
        verbose_name = "Paramètres de la plateforme"

    def __str__(self):
        return self.site_name

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
