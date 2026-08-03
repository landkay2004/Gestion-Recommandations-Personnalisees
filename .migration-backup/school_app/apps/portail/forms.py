from django import forms
from .models import PortailConfig


class ActivationForm(forms.Form):
    code = forms.CharField(
        label="Nouveau code d'accès",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg text-center',
            'placeholder': 'Minimum 4 caractères',
            'autocomplete': 'new-password',
        }),
        min_length=4, max_length=20
    )
    code_confirm = forms.CharField(
        label="Confirmer le code",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg text-center',
            'placeholder': 'Répétez votre code',
            'autocomplete': 'new-password',
        }),
    )

    def clean(self):
        cleaned = super().clean()
        code = cleaned.get('code')
        code_confirm = cleaned.get('code_confirm')
        if code and code_confirm and code != code_confirm:
            raise forms.ValidationError("Les codes ne correspondent pas.")
        return cleaned


class CodeAccesForm(forms.Form):
    code = forms.CharField(
        label="Code d'accès",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg text-center',
            'placeholder': 'Entrez votre code d\'accès',
            'autocomplete': 'current-password',
            'autofocus': True,
        }),
        min_length=4, max_length=20
    )


class AccesManuelForm(forms.Form):
    nom_complet = forms.CharField(
        label="Nom complet de l'élève",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex : KABONGO Jean-Pierre',
            'autocomplete': 'off',
        }),
        min_length=2, max_length=200
    )
    code = forms.CharField(
        label="Code d'accès",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Code créé lors de la première connexion',
            'autocomplete': 'current-password',
        }),
        min_length=4, max_length=20
    )


class PortailConfigForm(forms.ModelForm):
    class Meta:
        model = PortailConfig
        fields = ['nom_portail', 'logo', 'url_portail', 'texte_accueil',
                  'couleur_primaire', 'couleur_secondaire']
        widgets = {
            'nom_portail': forms.TextInput(attrs={'class': 'form-control'}),
            'url_portail': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://ecol.com',
            }),
            'texte_accueil': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'couleur_primaire': forms.TextInput(attrs={
                'type': 'color', 'class': 'form-control form-control-color',
            }),
            'couleur_secondaire': forms.TextInput(attrs={
                'type': 'color', 'class': 'form-control form-control-color',
            }),
        }
