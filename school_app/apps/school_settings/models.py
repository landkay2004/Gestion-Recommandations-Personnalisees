import io
import os

from django.db import models
from django.conf import settings


class SchoolInfo(models.Model):
    # ── Informations de base ────────────────────────────────────────────────
    nom      = models.CharField(max_length=200, default="Institut Bungulu")
    province = models.CharField(max_length=100, default="Nord-Kivu")
    ville    = models.CharField(max_length=100, default="Beni")
    commune  = models.CharField(max_length=100, default="Bungulu")
    code     = models.CharField(max_length=50,  default="62024 / 101 / 03 / 1")
    logo     = models.ImageField(upload_to='school/', null=True, blank=True)

    # ── PWA Système (back-office : préfets, enseignants) ───────────────────
    pwa_nom         = models.CharField("Nom complet (PWA système)",   max_length=200, default="Système de Gestion Scolaire")
    pwa_nom_court   = models.CharField("Nom court (PWA système)",     max_length=30,  default="SGS")
    pwa_description = models.CharField("Description (PWA système)",   max_length=300, default="Plateforme de gestion scolaire.")

    # ── PWA Portail Parent ──────────────────────────────────────────────────
    portail_pwa_nom         = models.CharField("Nom complet (PWA portail parent)",  max_length=200, default="Portail Parent")
    portail_pwa_nom_court   = models.CharField("Nom court (PWA portail parent)",    max_length=30,  default="Parent")
    portail_pwa_description = models.CharField("Description (PWA portail parent)",  max_length=300,
        default="Consultation des résultats scolaires, bulletins et informations des élèves.")

    # ── Identité visuelle ───────────────────────────────────────────────────
    theme_color      = models.CharField("Couleur principale (theme_color)",      max_length=7, default="#1E293B")
    background_color = models.CharField("Couleur d'arrière-plan (background_color)", max_length=7, default="#0f172a")

    class Meta:
        verbose_name = "Informations de l'école"

    def __str__(self):
        return self.nom

    @classmethod
    def get_info(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    # ── Génération d'icônes PWA ─────────────────────────────────────────────

    def generate_pwa_icons(self):
        """Génère toutes les tailles d'icônes PWA + favicon à partir du logo.

        Les fichiers sont écrits dans MEDIA_ROOT/school/icons/.
        """
        if not self.logo:
            return False
        try:
            from PIL import Image as PILImage
        except ImportError:
            return False

        try:
            self.logo.seek(0)
            img = PILImage.open(self.logo).convert('RGBA')
        except Exception:
            return False

        icons_dir = os.path.join(settings.MEDIA_ROOT, 'school', 'icons')
        os.makedirs(icons_dir, exist_ok=True)

        sizes = [72, 96, 128, 144, 152, 192, 384, 512]
        for size in sizes:
            resized = img.resize((size, size), PILImage.LANCZOS)
            # Fond blanc pour les formats non-transparents
            bg = PILImage.new('RGB', (size, size), (255, 255, 255))
            bg.paste(resized, mask=resized.split()[3] if resized.mode == 'RGBA' else None)
            bg.save(os.path.join(icons_dir, f'icon-{size}.png'), 'PNG', optimize=True)

        # Favicon 32×32
        fav = img.resize((32, 32), PILImage.LANCZOS)
        fav_path = os.path.join(icons_dir, 'favicon.png')
        fav.save(fav_path, 'PNG', optimize=True)

        return True

    def pwa_icons_exist(self):
        """Retourne True si les icônes générées existent dans le répertoire media."""
        path = os.path.join(settings.MEDIA_ROOT, 'school', 'icons', 'icon-192.png')
        return os.path.exists(path)

    def pwa_icons_base_url(self):
        """URL de base pour les icônes générées (sans slash final)."""
        return settings.MEDIA_URL.rstrip('/') + '/school/icons'


# ── Signal post_save : génère les icônes automatiquement lors de l'upload ─────

from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=SchoolInfo)
def auto_generate_icons(sender, instance, **kwargs):
    """Régénère les icônes PWA chaque fois que SchoolInfo est sauvegardé avec un logo."""
    if instance.logo:
        try:
            instance.generate_pwa_icons()
        except Exception:
            pass
