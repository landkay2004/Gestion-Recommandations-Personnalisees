from django import forms
from .models import SchoolInfo


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
