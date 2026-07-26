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
            issuer_name='SGN RDC Platform'
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
