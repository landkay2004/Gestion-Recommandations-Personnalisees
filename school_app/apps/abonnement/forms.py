"""
Formulaires pour la gestion des frais scolaires.
"""
from decimal import Decimal

from django import forms
from django.contrib.auth.validators import UnicodeUsernameValidator

from .models import TypeFrais, Paiement
from accounts.models import CustomUser, generate_temp_password


# ── TypeFrais ─────────────────────────────────────────────────────────────────

class TypeFraisForm(forms.ModelForm):
    class Meta:
        model = TypeFrais
        fields = ['nom', 'montant', 'classe', 'actif']
        widgets = {
            'nom':     forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Minerval, Tenue scolaire…'}),
            'montant': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'classe':  forms.Select(attrs={'class': 'form-select'}),
            'actif':   forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'classe': 'Classe (optionnel — vide = tous les élèves)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['classe'].empty_label = "— Tous les élèves —"
        self.fields['classe'].required = False


# ── Paiement ──────────────────────────────────────────────────────────────────

class PaiementForm(forms.ModelForm):
    class Meta:
        model = Paiement
        fields = ['type_frais', 'montant_paye', 'mode_paiement']
        widgets = {
            'type_frais':    forms.Select(attrs={'class': 'form-select'}),
            'montant_paye':  forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'mode_paiement': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, eleve=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.eleve = eleve
        if eleve:
            # N'afficher que les frais non soldés applicables à cet élève
            from .utils import get_frais_a_payer
            frais_ids = [f['type_frais'].pk for f in get_frais_a_payer(eleve)]
            self.fields['type_frais'].queryset = TypeFrais.objects.filter(pk__in=frais_ids, actif=True)

    def clean_montant_paye(self):
        montant = self.cleaned_data.get('montant_paye')
        type_frais = self.cleaned_data.get('type_frais')
        if montant and montant <= Decimal('0'):
            raise forms.ValidationError("Le montant doit être supérieur à zéro.")
        if montant and type_frais and self.eleve:
            from .utils import get_frais_a_payer
            frais_list = get_frais_a_payer(self.eleve)
            reste = next(
                (f['reste_du'] for f in frais_list if f['type_frais'].pk == type_frais.pk),
                None
            )
            if reste is not None and montant > reste:
                raise forms.ValidationError(
                    f"Montant supérieur au reste dû ({reste} USD). "
                    "Les paiements en excédent ne sont pas autorisés."
                )
        return montant

    def clean_type_frais(self):
        tf = self.cleaned_data.get('type_frais')
        if tf and self.eleve:
            # Vérification côté serveur : frais déjà soldé ?
            from .utils import get_frais_a_payer
            frais_ids = [f['type_frais'].pk for f in get_frais_a_payer(self.eleve)]
            if tf.pk not in frais_ids:
                raise forms.ValidationError("Ce frais est déjà soldé ou inapplicable à cet élève.")
        return tf


# ── Création d'un compte comptable ───────────────────────────────────────────

class ComptableCreateForm(forms.Form):
    first_name = forms.CharField(
        label="Prénom", max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    last_name = forms.CharField(
        label="Nom", max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    email = forms.EmailField(
        label="Adresse e-mail",
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
    )
    telephone = forms.CharField(
        label="Téléphone", max_length=20, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Un utilisateur avec cet e-mail existe déjà.")
        return email

    def save(self, schema_name):
        """Crée le CustomUser comptable et l'enregistre dans l'AnnuaireUtilisateur."""
        from tenants.models import AnnuaireUtilisateur
        email = self.cleaned_data['email']
        base_username = email.split('@')[0]
        username = base_username
        n = 1
        while CustomUser.objects.filter(username=username).exists():
            username = f"{base_username}{n}"
            n += 1

        temp_pwd = generate_temp_password()
        user = CustomUser(
            username=username,
            email=email,
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            telephone=self.cleaned_data.get('telephone', ''),
            role='comptable',
            must_change_password=True,
        )
        user.set_password(temp_pwd)
        user.save()

        AnnuaireUtilisateur.objects.get_or_create(
            email=email.lower(),
            defaults={'schema_name': schema_name, 'type_compte': 'comptable'},
        )
        return user, temp_pwd


class ComptableUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'telephone', 'is_active']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name':  forms.TextInput(attrs={'class': 'form-control'}),
            'email':      forms.EmailInput(attrs={'class': 'form-control'}),
            'telephone':  forms.TextInput(attrs={'class': 'form-control'}),
            'is_active':  forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'is_active': 'Compte actif',
        }
