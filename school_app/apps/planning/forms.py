from django import forms
from django.core.exceptions import ValidationError
from .models import Salle, CreneauHoraire, SeanceHoraire
from subjects.models import MatiereClasse
from classes.models import AnneeScolaire, Classe


class SalleForm(forms.ModelForm):
    class Meta:
        model = Salle
        fields = ['nom', 'capacite', 'description']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Salle A1'}),
            'capacite': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Optionnel'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optionnel'}),
        }


class CreneauHoraireForm(forms.ModelForm):
    class Meta:
        model = CreneauHoraire
        fields = ['jour', 'type_creneau', 'heure_debut', 'heure_fin', 'libelle']
        widgets = {
            'jour': forms.Select(attrs={'class': 'form-select'}),
            'type_creneau': forms.Select(attrs={'class': 'form-select'}),
            'heure_debut': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'heure_fin': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'libelle': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Généré automatiquement'}),
        }


class SeanceHoraireForm(forms.ModelForm):
    class Meta:
        model = SeanceHoraire
        fields = ['annee_scolaire', 'creneau', 'matiere_classe', 'salle']
        widgets = {
            'annee_scolaire': forms.Select(attrs={'class': 'form-select'}),
            'creneau': forms.Select(attrs={'class': 'form-select'}),
            'matiere_classe': forms.Select(attrs={'class': 'form-select'}),
            'salle': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, annee_scolaire=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['annee_scolaire'].queryset = AnneeScolaire.objects.order_by('-annee')
        self.fields['creneau'].queryset = CreneauHoraire.objects.order_by('jour', 'heure_debut')
        self.fields['salle'].required = False
        self.fields['salle'].queryset = Salle.objects.all()
        mc_qs = MatiereClasse.objects.select_related(
            'matiere', 'classe', 'classe__section', 'enseignant__user'
        )
        if annee_scolaire:
            mc_qs = mc_qs.filter(classe__annee_scolaire=annee_scolaire)
        self.fields['matiere_classe'].queryset = mc_qs
        self.fields['matiere_classe'].label_from_instance = lambda obj: (
            f"{obj.matiere} — {obj.classe}"
            + (f" ({obj.enseignant})" if obj.enseignant else "")
        )

    def clean(self):
        cleaned = super().clean()
        # Delegate conflict detection to model.clean()
        return cleaned
