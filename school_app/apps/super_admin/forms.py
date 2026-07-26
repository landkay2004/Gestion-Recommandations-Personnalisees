from django import forms
from django.utils.text import slugify
from tenants.models import Ecole, PlanAbonnement, AdminEcole


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
    class Meta:
        model = PlanAbonnement
        fields = ['nom', 'description', 'max_eleves', 'max_enseignants', 'max_classes', 'max_utilisateurs', 'prix_mensuel', 'is_actif']
        widgets = {
            'nom':              forms.TextInput(attrs={'class': 'form-control'}),
            'description':      forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'max_eleves':       forms.NumberInput(attrs={'class': 'form-control'}),
            'max_enseignants':  forms.NumberInput(attrs={'class': 'form-control'}),
            'max_classes':      forms.NumberInput(attrs={'class': 'form-control'}),
            'max_utilisateurs': forms.NumberInput(attrs={'class': 'form-control'}),
            'prix_mensuel':     forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


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
    date_fin_abonnement = forms.DateField(
        label="Date de fin d'abonnement",
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )

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


class MaintenanceForm(forms.Form):
    ecole_id   = forms.IntegerField(required=False, widget=forms.HiddenInput())
    module     = forms.CharField(required=False, max_length=50, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'bulletins, notes, ... (laisser vide = tous)'}))
    message    = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}), initial="Le systeme est en maintenance. Veuillez reessayer plus tard.")
    is_urgence = forms.BooleanField(required=False, label="Urgence (maintenance hors horaires normaux)")
    debut_prevu = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}))
    fin_prevue  = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}))
    duree_estimee_minutes = forms.IntegerField(initial=60, widget=forms.NumberInput(attrs={'class': 'form-control'}))
