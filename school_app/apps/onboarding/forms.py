import re
from django import forms


class ChangePasswordOnboardingForm(forms.Form):
    nouveau_mdp  = forms.CharField(
        label="Nouveau mot de passe",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'id': 'id_nouveau_mdp', 'autocomplete': 'new-password'}),
    )
    confirmation = forms.CharField(
        label="Confirmer le mot de passe",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )

    def clean(self):
        d  = super().clean()
        p1 = d.get('nouveau_mdp', '')
        p2 = d.get('confirmation', '')
        if p1 != p2:
            raise forms.ValidationError("Les deux mots de passe ne correspondent pas.")
        if len(p1) < 8:
            raise forms.ValidationError("Le mot de passe doit contenir au moins 8 caracteres.")
        if not re.search(r'[A-Z]', p1):
            raise forms.ValidationError("Le mot de passe doit contenir au moins une majuscule.")
        if not re.search(r'\d', p1):
            raise forms.ValidationError("Le mot de passe doit contenir au moins un chiffre.")
        return d


TYPE_ETABLISSEMENT_CHOICES = [
    ('',            '— Sélectionner —'),
    ('ep',          'École Primaire'),
    ('college',     'Collège'),
    ('institut',    'Institut (Humanités générales)'),
    ('lyceé',       'Lycée technique'),
    ('complexe',    'Complexe scolaire'),
    ('autre',       'Autre'),
]


class ConfigurationEcoleForm(forms.Form):
    nom_ecole  = forms.CharField(label="Nom de l'établissement", max_length=200,
                                  widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Institut Bungulu', 'required': True}))
    type_etablissement = forms.ChoiceField(
        label="Type d'établissement", choices=TYPE_ETABLISSEMENT_CHOICES, required=True,
        widget=forms.Select(attrs={'class': 'form-select', 'required': True}),
    )
    annee_scolaire_actuelle = forms.CharField(
        label="Année scolaire en cours", max_length=20, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : 2025-2026', 'required': True}),
    )
    province   = forms.CharField(label="Province",  max_length=100, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'required': True}))
    ville      = forms.CharField(label="Ville",     max_length=100, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'required': True}))
    commune    = forms.CharField(label="Commune",   max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    code_ecole = forms.CharField(label="Code MEPSP", max_length=50, required=True,
                                  widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : 62024/101/03/1', 'required': True}))
    telephone  = forms.CharField(label="Téléphone", max_length=50, required=True,
                                  widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : +243 99 000 0000', 'required': True}))
    email_contact = forms.EmailField(label="E-mail de contact", required=True,
                                      widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'contact@ecole.cd', 'required': True}))
    logo       = forms.ImageField(label="Logo de l'école", required=False,
                                   widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}))


class ConditionsForm(forms.Form):
    accepter = forms.BooleanField(
        label="J'ai lu et j'accepte les conditions generales d'utilisation de la plateforme EducNet.",
        error_messages={'required': "Vous devez accepter les conditions pour continuer."},
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
