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
    # Sélecteur de classe (non persisté — sert uniquement à filtrer matiere_classe)
    classe = forms.ModelChoiceField(
        queryset=Classe.objects.none(),
        required=False,
        label='Classe',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_classe_filter',
        }),
        help_text='Sélectionnez une classe pour filtrer les cours disponibles.',
    )

    class Meta:
        model = SeanceHoraire
        fields = ['annee_scolaire', 'creneau', 'matiere_classe', 'salle']
        widgets = {
            'annee_scolaire': forms.Select(attrs={'class': 'form-select'}),
            'creneau': forms.Select(attrs={'class': 'form-select'}),
            'matiere_classe': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_matiere_classe',
            }),
            'salle': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, annee_scolaire=None, classe_id=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['annee_scolaire'].queryset = AnneeScolaire.objects.order_by('-annee')
        self.fields['creneau'].queryset = CreneauHoraire.objects.filter(
            type_creneau='cours'
        ).order_by('jour', 'heure_debut')
        self.fields['salle'].required = False
        self.fields['salle'].queryset = Salle.objects.all()

        # Peupler le sélecteur de classe
        if annee_scolaire:
            classes_qs = Classe.objects.filter(
                annee_scolaire=annee_scolaire
            ).select_related('section').order_by('section__nom', 'nom')
        else:
            classes_qs = Classe.objects.select_related('section').order_by('section__nom', 'nom')
        self.fields['classe'].queryset = classes_qs

        # Pré-sélectionner la classe si on modifie une séance existante
        if self.instance.pk and self.instance.matiere_classe_id:
            try:
                self.fields['classe'].initial = self.instance.matiere_classe.classe_id
                classe_id = self.instance.matiere_classe.classe_id
            except Exception:
                pass

        # Filtrer matiere_classe selon la classe choisie
        mc_qs = MatiereClasse.objects.select_related(
            'matiere', 'classe', 'classe__section', 'enseignant__user'
        )
        if annee_scolaire:
            mc_qs = mc_qs.filter(classe__annee_scolaire=annee_scolaire)
        if classe_id:
            mc_qs = mc_qs.filter(classe_id=classe_id)

        mc_qs = mc_qs.order_by('classe__nom', 'matiere__nom')
        self.fields['matiere_classe'].queryset = mc_qs
        self.fields['matiere_classe'].label_from_instance = lambda obj: (
            f"{obj.matiere}"
            + (f" — {obj.enseignant}" if obj.enseignant else "")
        )

    def clean(self):
        cleaned = super().clean()
        # La détection de conflits est déléguée au modèle via full_clean()
        return cleaned
