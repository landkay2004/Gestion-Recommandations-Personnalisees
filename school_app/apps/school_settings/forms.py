from django import forms
from .models import SchoolInfo, MatriculeConfig


class SchoolInfoForm(forms.ModelForm):
    class Meta:
        model = SchoolInfo
        fields = [
            'nom', 'province', 'ville', 'commune', 'code', 'logo',
            'pwa_nom', 'pwa_nom_court', 'pwa_description',
            'portail_pwa_nom', 'portail_pwa_nom_court', 'portail_pwa_description',
            'theme_color', 'background_color',
        ]
        widgets = {
            'nom':                    forms.TextInput(attrs={'class': 'form-control'}),
            'province':               forms.TextInput(attrs={'class': 'form-control'}),
            'ville':                  forms.TextInput(attrs={'class': 'form-control'}),
            'commune':                forms.TextInput(attrs={'class': 'form-control'}),
            'code':                   forms.TextInput(attrs={'class': 'form-control'}),
            'logo':                   forms.FileInput(attrs={'class': 'form-control'}),
            'pwa_nom':                forms.TextInput(attrs={'class': 'form-control'}),
            'pwa_nom_court':          forms.TextInput(attrs={'class': 'form-control', 'maxlength': '30'}),
            'pwa_description':        forms.TextInput(attrs={'class': 'form-control'}),
            'portail_pwa_nom':        forms.TextInput(attrs={'class': 'form-control'}),
            'portail_pwa_nom_court':  forms.TextInput(attrs={'class': 'form-control', 'maxlength': '30'}),
            'portail_pwa_description': forms.TextInput(attrs={'class': 'form-control'}),
            'theme_color':            forms.TextInput(attrs={'class': 'form-control form-control-color', 'type': 'color'}),
            'background_color':       forms.TextInput(attrs={'class': 'form-control form-control-color', 'type': 'color'}),
        }


class MatriculeConfigForm(forms.ModelForm):
    class Meta:
        model = MatriculeConfig
        fields = ['format_matricule', 'prefixe', 'compteur', 'reset_annuel']
        widgets = {
            'format_matricule': forms.TextInput(attrs={
                'class': 'form-control font-monospace',
                'placeholder': '{PREFIXE}{ANNEE2}{SEQ4}',
            }),
            'prefixe': forms.TextInput(attrs={
                'class': 'form-control text-uppercase',
                'maxlength': '10',
                'placeholder': 'EL',
            }),
            'compteur': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
            }),
            'reset_annuel': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'format_matricule': 'Format du matricule',
            'prefixe': 'Préfixe ({PREFIXE})',
            'compteur': 'Compteur courant (prochain = compteur + 1)',
            'reset_annuel': 'Remettre le compteur à zéro chaque nouvelle année scolaire',
        }
