from django import forms
from .models import AnneeScolaire, Section, Classe, Niveau, DecisionPromotion


class AnneeScolaireForm(forms.ModelForm):
    class Meta:
        model = AnneeScolaire
        fields = ['annee', 'active', 'date_debut', 'date_fin']
        widgets = {
            'annee': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '2024-2025'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'date_debut': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class NiveauForm(forms.ModelForm):
    class Meta:
        model = Niveau
        fields = ['nom', 'ordre', 'cycle']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex: 7ème, 8ème, 1ère Secondaire'}),
            'ordre': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'cycle': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex: Primaire, Secondaire (optionnel)'}),
        }


class SectionForm(forms.ModelForm):
    class Meta:
        model = Section
        fields = ['nom']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex: Générale, Commerciale'}),
        }


class ClasseForm(forms.ModelForm):
    class Meta:
        model = Classe
        fields = ['nom', 'niveau', 'section', 'annee_scolaire']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex: A, B, C'}),
            'niveau': forms.Select(attrs={'class': 'form-select'}),
            'section': forms.Select(attrs={'class': 'form-select'}),
            'annee_scolaire': forms.Select(attrs={'class': 'form-select'}),
        }


class DecisionPromotionForm(forms.ModelForm):
    class Meta:
        model = DecisionPromotion
        fields = ['decision', 'classe_destination', 'observations']
        widgets = {
            'decision': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'classe_destination': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'observations': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Observations…'}),
        }
