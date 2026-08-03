import io
import os

from django.db import models
from django.conf import settings

from config.tenant_media import get_tenant_schema, _ext


def school_info_logo_path(instance, filename):
    """Logo de l'école, organisé par tenant."""
    schema = get_tenant_schema()
    return f'tenants/{schema}/school/logo{_ext(filename)}'


class SchoolInfo(models.Model):
    TYPE_ETABLISSEMENT_CHOICES = [
        ('',            '— Sélectionner —'),
        ('ep',          'École Primaire'),
        ('college',     'Collège'),
        ('institut',    'Institut (Humanités générales)'),
        ('lyceé',       'Lycée technique'),
        ('athénée',     'Athénée'),
        ('ecole_prof',  'École professionnelle'),
        ('complexe',    'Complexe scolaire'),
        ('autre',       'Autre'),
    ]

    # ── Informations de base ────────────────────────────────────────────────
    nom                    = models.CharField(max_length=200, default="Institut Bungulu")
    type_etablissement     = models.CharField("Type d'établissement", max_length=30,
                                              choices=TYPE_ETABLISSEMENT_CHOICES, blank=True, default='institut')
    annee_scolaire_actuelle = models.CharField("Année scolaire en cours", max_length=20, blank=True, default='',
                                               help_text="Ex : 2025-2026")
    province = models.CharField(max_length=100, default="Nord-Kivu")
    ville    = models.CharField(max_length=100, default="Beni")
    commune  = models.CharField(max_length=100, default="Bungulu")
    code     = models.CharField(max_length=50,  default="62024 / 101 / 03 / 1")
    telephone       = models.CharField("Téléphone", max_length=50, blank=True, default='')
    email_contact   = models.EmailField("Email de contact", blank=True, default='')
    logo     = models.ImageField(upload_to=school_info_logo_path, null=True, blank=True)

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
            # Supporte le stockage local (seek) et les stockages distants
            # (Cloudinary) où seek() n'est pas disponible → téléchargement via URL.
            try:
                self.logo.seek(0)
                img_bytes = io.BytesIO(self.logo.read())
            except (AttributeError, TypeError, Exception):
                import urllib.request
                with urllib.request.urlopen(self.logo.url) as resp:
                    img_bytes = io.BytesIO(resp.read())
            img = PILImage.open(img_bytes).convert('RGBA')
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


# ─────────────────────────────────────────────────────────────────────────────
# Configuration de la matriculation automatique des élèves
# ─────────────────────────────────────────────────────────────────────────────

class MatriculeConfig(models.Model):
    """
    Singleton (pk=1) par école : configure le format de matriculation automatique.

    Variables disponibles dans format_matricule :
        {PREFIXE}   → valeur du champ prefixe (ex. "EL", "IB", "ETD")
        {ANNEE}     → année scolaire en cours, 4 chiffres (ex. "2025")
        {ANNEE2}    → 2 derniers chiffres de l'année (ex. "25")
        {MOIS}      → mois courant, 2 chiffres (ex. "08")
        {SEQ}       → numéro séquentiel brut (ex. "42")
        {SEQ3}      → séquentiel sur 3 chiffres (ex. "042")
        {SEQ4}      → séquentiel sur 4 chiffres (ex. "0042")
        {SEQ5}      → séquentiel sur 5 chiffres (ex. "00042")

    Exemple : "{PREFIXE}-{ANNEE2}-{SEQ4}" → "EL-25-0042"
    """

    format_matricule = models.CharField(
        "Format du matricule",
        max_length=100,
        default="{PREFIXE}{ANNEE2}{SEQ4}",
        help_text=(
            "Variables : {PREFIXE}, {ANNEE}, {ANNEE2}, {MOIS}, "
            "{SEQ}, {SEQ3}, {SEQ4}, {SEQ5}. "
            "Exemple : {PREFIXE}-{ANNEE2}-{SEQ4} → EL-25-0001"
        ),
    )
    prefixe = models.CharField(
        "Préfixe",
        max_length=10,
        default="EL",
        help_text="Remplace {PREFIXE} dans le format. Ex : EL, IB, ETD",
    )
    compteur = models.PositiveIntegerField(
        "Compteur actuel",
        default=0,
        help_text="Incrémenté automatiquement à chaque inscription. Modifiable pour reprendre une numérotation existante.",
    )
    reset_annuel = models.BooleanField(
        "Réinitialiser le compteur chaque année scolaire",
        default=False,
        help_text="Si activé, le compteur repart à 0 au début de chaque nouvelle année scolaire.",
    )
    annee_reference = models.CharField(
        "Année de référence du compteur",
        max_length=4,
        blank=True,
        default="",
        help_text="Année scolaire en cours lors du dernier incrément (gestion du reset annuel).",
    )

    class Meta:
        verbose_name = "Configuration de la matriculation"

    def __str__(self):
        return f"Matricule : {self.format_matricule} (compteur={self.compteur})"

    @classmethod
    def get_config(cls):
        """Retourne (ou crée) la configuration singleton pk=1."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    # ── Utilitaires internes ──────────────────────────────────────────────────

    def _get_annee(self) -> str:
        """Retourne l'année scolaire en cours (4 chiffres)."""
        try:
            info = SchoolInfo.get_info()
            raw = (info.annee_scolaire_actuelle or '').strip()
            year = raw.split('-')[0].strip()
            if len(year) == 4 and year.isdigit():
                return year
        except Exception:
            pass
        from django.utils import timezone
        return str(timezone.now().year)

    def _variables(self) -> dict:
        """Construit le dictionnaire des variables de remplacement."""
        from django.utils import timezone
        annee = self._get_annee()
        seq = self.compteur
        return {
            'PREFIXE': self.prefixe or 'EL',
            'ANNEE':   annee,
            'ANNEE2':  annee[-2:],
            'MOIS':    timezone.now().strftime('%m'),
            'SEQ':     str(seq),
            'SEQ3':    str(seq).zfill(3),
            'SEQ4':    str(seq).zfill(4),
            'SEQ5':    str(seq).zfill(5),
        }

    def apercu(self, numero: int | None = None) -> str:
        """
        Retourne un aperçu du format avec le numéro donné (ou compteur+1).
        N'incrémente PAS le compteur.
        """
        annee = self._get_annee()
        from django.utils import timezone
        seq = numero if numero is not None else self.compteur + 1
        variables = {
            'PREFIXE': self.prefixe or 'EL',
            'ANNEE':   annee,
            'ANNEE2':  annee[-2:],
            'MOIS':    timezone.now().strftime('%m'),
            'SEQ':     str(seq),
            'SEQ3':    str(seq).zfill(3),
            'SEQ4':    str(seq).zfill(4),
            'SEQ5':    str(seq).zfill(5),
        }
        result = self.format_matricule or '{PREFIXE}{ANNEE2}{SEQ4}'
        for key, val in variables.items():
            result = result.replace('{' + key + '}', val)
        return result

    # ── Génération thread-safe ────────────────────────────────────────────────

    def generer_matricule(self) -> str:
        """
        Génère le prochain matricule et incrémente le compteur de façon atomique.
        Utilise SELECT FOR UPDATE pour éviter les doublons en cas d'inscriptions simultanées.
        """
        from django.db import transaction
        from django.utils import timezone

        with transaction.atomic():
            config = MatriculeConfig.objects.select_for_update().get(pk=self.pk)
            annee = config._get_annee()

            # Reset annuel si activé et nouvelle année détectée
            if config.reset_annuel and config.annee_reference != annee:
                config.compteur = 0
                config.annee_reference = annee

            config.compteur += 1
            config.save(update_fields=['compteur', 'annee_reference'])

            annee2 = annee[-2:]
            seq = config.compteur

            variables = {
                'PREFIXE': config.prefixe or 'EL',
                'ANNEE':   annee,
                'ANNEE2':  annee2,
                'MOIS':    timezone.now().strftime('%m'),
                'SEQ':     str(seq),
                'SEQ3':    str(seq).zfill(3),
                'SEQ4':    str(seq).zfill(4),
                'SEQ5':    str(seq).zfill(5),
            }

            fmt = config.format_matricule or '{PREFIXE}{ANNEE2}{SEQ4}'
            matricule = fmt
            for key, val in variables.items():
                matricule = matricule.replace('{' + key + '}', val)

            return matricule


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
