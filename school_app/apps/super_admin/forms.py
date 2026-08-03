from django import forms
from django.utils.text import slugify
from tenants.models import (
    Ecole, PlanAbonnement, AdminEcole, AnnoncePlateforme,
    MODULES_SGN, FONCTIONNALITES_SGN,
)


class LoginSuperAdminForm(forms.Form):
    email    = forms.EmailField(label="Adresse email",   widget=forms.EmailInput(attrs={'autofocus': True, 'class': 'form-control', 'placeholder': 'superadmin@exemple.com'}))
    password = forms.CharField(label="Mot de passe",    widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '••••••••'}))


class ChangePasswordSuperAdminForm(forms.Form):
    ancien_mdp   = forms.CharField(label="Mot de passe actuel",            widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    nouveau_mdp  = forms.CharField(label="Nouveau mot de passe",            widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    confirmation = forms.CharField(label="Confirmer le nouveau mot de passe", widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    def clean(self):
        data = super().clean()
        p1, p2 = data.get('nouveau_mdp', ''), data.get('confirmation', '')
        if p1 != p2:
            raise forms.ValidationError("Les deux mots de passe ne correspondent pas.")
        if len(p1) < 8:
            raise forms.ValidationError("Le mot de passe doit contenir au moins 8 caracteres.")
        return data


class Verify2FAForm(forms.Form):
    code = forms.CharField(
        label="Code d'authentification",
        max_length=8,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg text-center',
            'placeholder': '000000',
            'autocomplete': 'one-time-code',
            'inputmode': 'numeric',
            'autofocus': True,
        })
    )


class Setup2FAConfirmForm(forms.Form):
    code = forms.CharField(
        label="Code de verification",
        max_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg text-center',
            'placeholder': '000000',
            'inputmode': 'numeric',
            'autofocus': True,
        })
    )


class PlanAbonnementForm(forms.ModelForm):
    modules_inclus = forms.MultipleChoiceField(
        label="Modules inclus",
        choices=MODULES_SGN,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        help_text="Cochez les modules autorisés pour ce plan. Aucun coché = tous les modules autorisés.",
    )
    fonctionnalites_incluses = forms.MultipleChoiceField(
        label="Fonctionnalités avancées",
        choices=FONCTIONNALITES_SGN,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
    )

    class Meta:
        model = PlanAbonnement
        fields = [
            # Identification
            'nom', 'description',
            # Tarification
            'prix_mensuel', 'prix_annuel', 'essai_gratuit_jours',
            # Quotas
            'max_eleves', 'max_enseignants', 'max_classes', 'max_utilisateurs',
            'max_stockage_go', 'quota_sms_mensuel',
            # Modules / Fonctionnalités
            'modules_inclus', 'fonctionnalites_incluses',
            # Visibilité
            'is_actif', 'est_public', 'ordre_affichage',
        ]
        widgets = {
            'nom':              forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Essentiel, Pro, Entreprise…'}),
            'description':      forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Description courte affichée sur la page de tarification.'}),
            'prix_mensuel':     forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'prix_annuel':      forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': '0 = calculé automatiquement (mensuel × 12)'}),
            'essai_gratuit_jours': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'max_eleves':       forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'max_enseignants':  forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'max_classes':      forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'max_utilisateurs': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'max_stockage_go':  forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'quota_sms_mensuel': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'is_actif':   forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
            'est_public': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
            'ordre_affichage': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }
        labels = {
            'nom':                   'Nom du plan',
            'description':           'Description',
            'prix_mensuel':          'Prix mensuel (USD)',
            'prix_annuel':           'Prix annuel (USD)',
            'essai_gratuit_jours':   'Jours d\'essai gratuit',
            'max_eleves':            'Max élèves',
            'max_enseignants':       'Max enseignants',
            'max_classes':           'Max classes',
            'max_utilisateurs':      'Max utilisateurs',
            'max_stockage_go':       'Stockage max (Go)',
            'quota_sms_mensuel':     'Quota SMS / mois',
            'is_actif':              'Plan actif',
            'est_public':            'Visible publiquement',
            'ordre_affichage':       'Ordre d\'affichage',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pré-sélectionner les valeurs JSON existantes dans les checkboxes
        if self.instance and self.instance.pk:
            self.initial['modules_inclus'] = self.instance.modules_inclus or []
            self.initial['fonctionnalites_incluses'] = self.instance.fonctionnalites_incluses or []

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Convertir les choix sélectionnés en liste JSON
        instance.modules_inclus = list(self.cleaned_data.get('modules_inclus', []))
        instance.fonctionnalites_incluses = list(self.cleaned_data.get('fonctionnalites_incluses', []))
        if commit:
            instance.save()
        return instance


class CreerEcoleForm(forms.Form):
    nom               = forms.CharField(label="Nom de l'ecole", max_length=200,  widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Institut Mapendo'}))
    contact_nom       = forms.CharField(label="Nom du responsable", max_length=200, widget=forms.TextInput(attrs={'class': 'form-control'}))
    contact_email     = forms.EmailField(label="Email du responsable",           widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'directeur@ecole.cd'}))
    contact_telephone = forms.CharField(label="Telephone", max_length=50, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+243 ...'}))
    adresse           = forms.CharField(label="Adresse", required=False,         widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))
    ville             = forms.CharField(label="Ville", max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Beni'}))
    pays              = forms.CharField(label="Pays", max_length=100, initial='RDC', widget=forms.TextInput(attrs={'class': 'form-control'}))
    plan              = forms.ModelChoiceField(
        label="Plan d'abonnement",
        queryset=PlanAbonnement.objects.filter(is_actif=True),
        empty_label="Selectionner un plan",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    duree_abonnement_jours = forms.IntegerField(
        label="Durée de l'abonnement (jours)",
        required=True,
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 365'}),
    )

    def clean(self):
        data = super().clean()
        duree = data.get('duree_abonnement_jours')
        if not duree:
            raise forms.ValidationError(
                "Vous devez préciser une durée en jours pour l'abonnement."
            )
        return data

    def clean_contact_email(self):
        email = self.cleaned_data['contact_email'].lower().strip()
        if AdminEcole.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Un administrateur avec cet email existe deja.")
        return email

    def clean_nom(self):
        nom = self.cleaned_data['nom'].strip()
        slug = slugify(nom)[:50] or 'ecole'
        base = slug.replace('-', '_')
        candidate = base
        n = 1
        while Ecole.objects.filter(schema_name=candidate).exists():
            candidate = '%s_%s' % (base, n)
            n += 1
        self._schema_name = candidate
        return nom


class ModifierEcoleForm(forms.ModelForm):
    class Meta:
        model = Ecole
        fields = ['nom', 'contact_nom', 'contact_email', 'contact_telephone', 'adresse', 'ville', 'pays', 'plan', 'date_fin_abonnement', 'jours_grace']
        widgets = {
            'nom':                forms.TextInput(attrs={'class': 'form-control'}),
            'contact_nom':        forms.TextInput(attrs={'class': 'form-control'}),
            'contact_email':      forms.EmailInput(attrs={'class': 'form-control'}),
            'contact_telephone':  forms.TextInput(attrs={'class': 'form-control'}),
            'adresse':            forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'ville':              forms.TextInput(attrs={'class': 'form-control'}),
            'pays':               forms.TextInput(attrs={'class': 'form-control'}),
            'plan':               forms.Select(attrs={'class': 'form-select'}),
            'date_fin_abonnement': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'jours_grace':        forms.NumberInput(attrs={'class': 'form-control'}),
        }


class SupprimerEcoleForm(forms.Form):
    confirmation_nom = forms.CharField(
        label="Tapez le nom de l'ecole pour confirmer",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom exact de l\'ecole'}),
    )

    def __init__(self, *args, ecole=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._ecole = ecole

    def clean_confirmation_nom(self):
        val = self.cleaned_data.get('confirmation_nom', '').strip()
        if self._ecole and val != self._ecole.nom:
            raise forms.ValidationError(
                "Le nom saisi ne correspond pas. Tapez exactement : \u00ab %s \u00bb" % self._ecole.nom
            )
        return val


class PublicContactForm(forms.Form):
    nom = forms.CharField(
        label="Nom complet",
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Prénom et nom'})
    )
    email = forms.EmailField(
        label="Adresse e-mail",
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'vous@example.com'})
    )
    telephone = forms.CharField(
        label="Téléphone",
        required=False,
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+243 ...'})
    )
    sujet = forms.ChoiceField(
        label="Sujet",
        choices=[
            ('', '— Choisir un sujet —'),
            ('info', "Demande d'information"),
            ('technique', 'Problème technique'),
            ('facturation', 'Facturation / abonnement'),
            ('partenariat', 'Partenariat / collaboration'),
            ('autre', 'Autre'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    message = forms.CharField(
        label="Message",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Votre message…'})
    )

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()


class MaintenanceForm(forms.Form):
    ecole_id   = forms.IntegerField(required=False, widget=forms.HiddenInput())
    module     = forms.CharField(required=False, max_length=50, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'bulletins, notes, ... (laisser vide = tous)'}))
    message    = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}), initial="Le systeme est en maintenance. Veuillez reessayer plus tard.")
    is_urgence = forms.BooleanField(required=False, label="Urgence (maintenance hors horaires normaux)")
    debut_prevu = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}))
    fin_prevue  = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}))
    duree_estimee_minutes = forms.IntegerField(initial=60, widget=forms.NumberInput(attrs={'class': 'form-control'}))


class PlatformSettingsForm(forms.ModelForm):

    def clean_smtp_host(self):
        host = self.cleaned_data.get('smtp_host', '').strip()
        if not host:
            return host
        # Détecter si l'utilisateur a saisi une adresse e-mail au lieu d'un nom de serveur
        import re
        if '@' in host:
            raise forms.ValidationError(
                "Ce champ doit contenir le nom du serveur SMTP, pas une adresse e-mail. "
                "Exemples : smtp.gmail.com, smtp.office365.com — "
                "pas %(value)s.",
                params={'value': host},
            )
        # Vérification basique qu'il ressemble à un hostname
        if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-\.]+)$', host):
            raise forms.ValidationError(
                "Nom de serveur SMTP invalide. "
                "Exemples valides : smtp.gmail.com, mail.mondomaine.cd"
            )
        return host

    class Meta:
        from super_admin.models import PlatformSettings
        model = PlatformSettings
        fields = [
            'site_name', 'site_slogan', 'site_devise', 'site_logo',
            'adresse', 'contact_adresse', 'email_contact', 'telephone', 'contact_whatsapp',
            'site_web', 'facebook_url', 'twitter_url', 'linkedin_url', 'couleur_principale',
            # Images de fond login
            'login_bg_1', 'login_bg_2', 'login_bg_3',
            # Fonds public
            'public_bg_image', 'public_bg_image_rejoindre', 'public_bg_image_inscription', 'public_page_bg_color',
            # À propos
            'about_titre', 'about_description', 'about_mission', 'about_vision', 'about_valeurs',
            # SMTP
            'smtp_actif', 'smtp_host', 'smtp_port', 'smtp_use_tls',
            'smtp_user', 'smtp_password', 'smtp_from_email',
            # Alertes quota
            'alerte_quota_seuil', 'alerte_quota_email_actif', 'alerte_quota_app_actif',
            'alerte_quota_message_email', 'alerte_quota_message_app',
        ]
        widgets = {
            'site_name':   forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'EducNet'}),
            'site_slogan': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'School Governance Network'}),
            'site_devise': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Votre devise ou citation…'}),
            'site_logo':   forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*,.svg'}),
            'adresse':     forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Adresse postale…'}),
            'contact_adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Adresse à afficher sur la page contact…'}),
            'email_contact': forms.EmailInput(attrs={'class': 'form-control'}),
            'telephone':   forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+243 …'}),
            'contact_whatsapp': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+243 ...'}),
            'site_web':    forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://…'}),
            'facebook_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://facebook.com/…'}),
            'twitter_url':  forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://x.com/…'}),
            'linkedin_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://linkedin.com/in/…'}),
            'couleur_principale': forms.TextInput(attrs={'class': 'form-control form-control-color', 'type': 'color'}),
            # Login BG
            'login_bg_1':  forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'login_bg_2':  forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'login_bg_3':  forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'public_bg_image': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'public_bg_image_rejoindre': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'public_bg_image_inscription': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'public_page_bg_color': forms.TextInput(attrs={'class': 'form-control form-control-color', 'type': 'color'}),
            # À propos
            'about_titre':       forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'À propos de nous'}),
            'about_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Présentation générale de la plateforme…'}),
            'about_mission':     forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Notre mission…'}),
            'about_vision':      forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Notre vision…'}),
            'about_valeurs':     forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Excellence\nIntégrité\nInnovation\n(une valeur par ligne)'}),
            # SMTP
            'smtp_actif':      forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
            'smtp_host':       forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'smtp.gmail.com'}),
            'smtp_port':       forms.NumberInput(attrs={'class': 'form-control'}),
            'smtp_use_tls':    forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'smtp_user':       forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'utilisateur@domaine.com', 'autocomplete': 'off'}),
            'smtp_password':   forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
            'smtp_from_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'noreply@ecole.cd'}),
            # Alertes quota
            'alerte_quota_seuil': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 0, 'max': 100,
                'placeholder': '80',
            }),
            'alerte_quota_email_actif': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
            'alerte_quota_app_actif':   forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
            'alerte_quota_message_email': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 6,
                'placeholder': (
                    "Bonjour,\n\nL'école {ecole} a atteint {pourcentage}% de son quota "
                    "{ressource} ({usage}/{maximum}).\n\nCordialement,\n{site}"
                ),
            }),
            'alerte_quota_message_app': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': "Quota {ressource} : {usage}/{maximum} ({pourcentage}% utilisé).",
            }),
        }
        labels = {
            'site_name':         'Nom du site / plateforme',
            'site_slogan':       'Slogan',
            'site_devise':       'Devise',
            'site_logo':         'Logo de la plateforme',
            'adresse':           'Adresse postale',
            'contact_adresse':   'Adresse de contact',
            'email_contact':     'E-mail de contact',
            'telephone':         'Téléphone',
            'contact_whatsapp':  'WhatsApp',
            'site_web':          'Site web',
            'facebook_url':      'Lien Facebook',
            'twitter_url':       'Lien Twitter / X',
            'linkedin_url':      'Lien LinkedIn',
            'couleur_principale':'Couleur principale',
            'login_bg_1':        'Image de fond 1',
            'login_bg_2':        'Image de fond 2',
            'login_bg_3':        'Image de fond 3',
            'public_bg_image':   'Image publique par défaut',
            'public_bg_image_rejoindre': 'Image page Rejoindre',
            'public_bg_image_inscription': 'Image page Inscription',
            'public_page_bg_color':'Couleur de fond publique',
            'about_titre':       'Titre de la page',
            'about_description': 'Description générale',
            'about_mission':     'Notre mission',
            'about_vision':      'Notre vision',
            'about_valeurs':     'Nos valeurs (1 par ligne)',
            'smtp_actif':        'Activer l\'envoi SMTP réel',
            'smtp_host':         'Serveur SMTP (host)',
            'smtp_port':         'Port',
            'smtp_use_tls':      'Utiliser TLS/STARTTLS',
            'smtp_user':         'Identifiant SMTP',
            'smtp_password':     'Mot de passe SMTP',
            'smtp_from_email':   'Adresse d\'expédition (From)',
            'alerte_quota_seuil':           'Seuil d\'alerte (%)',
            'alerte_quota_email_actif':     'Alertes quota par e-mail',
            'alerte_quota_app_actif':       'Alertes quota dans l\'app',
            'alerte_quota_message_email':   'Message e-mail personnalisé',
            'alerte_quota_message_app':     'Message in-app personnalisé',
        }


class SuperAdminProfileForm(forms.Form):
    """Formulaire d'édition du profil super-administrateur."""
    prenom      = forms.CharField(label="Prénom",    max_length=100, required=False,
                                  widget=forms.TextInput(attrs={'class': 'form-control'}))
    nom         = forms.CharField(label="Nom",       max_length=100, required=False,
                                  widget=forms.TextInput(attrs={'class': 'form-control'}))
    email       = forms.EmailField(label="E-mail",
                                   widget=forms.EmailInput(attrs={'class': 'form-control'}))
    telephone   = forms.CharField(label="Téléphone", max_length=50, required=False,
                                  widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+243 …'}))
    photo_profil = forms.ImageField(label="Photo de profil", required=False,
                                    widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}))
    supprimer_photo = forms.BooleanField(label="Supprimer la photo actuelle", required=False,
                                         widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

    def clean_email(self):
        from super_admin.models import SuperAdmin
        email = self.cleaned_data['email'].lower().strip()
        qs = SuperAdmin.objects.filter(email__iexact=email)
        if self._sa_pk:
            qs = qs.exclude(pk=self._sa_pk)
        if qs.exists():
            raise forms.ValidationError("Cet e-mail est déjà utilisé par un autre super-administrateur.")
        return email

    def __init__(self, *args, sa_pk=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._sa_pk = sa_pk


class AnnoncePlateformeForm(forms.ModelForm):
    class Meta:
        model = AnnoncePlateforme
        fields = ['titre', 'message', 'type_annonce', 'ecole', 'publiee', 'date_expiration']
        widgets = {
            'titre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex. Mise à jour importante de la plateforme',
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 6,
                'placeholder': 'Rédigez votre message pour les administrateurs...',
            }),
            'type_annonce': forms.Select(attrs={'class': 'form-select'}),
            'ecole': forms.Select(attrs={'class': 'form-select'}),
            'publiee': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'date_expiration': forms.DateTimeInput(attrs={
                'class': 'form-control', 'type': 'datetime-local',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ecole'].required = False
        self.fields['ecole'].empty_label = "Toutes les écoles"
        self.fields['date_expiration'].required = False
