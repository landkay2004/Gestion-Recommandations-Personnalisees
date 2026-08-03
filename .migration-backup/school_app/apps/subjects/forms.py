from django import forms
from .models import Matiere, MatiereClasse, Maxima


class MaximaForm(forms.ModelForm):
    class Meta:
        model = Maxima
        fields = ['valeur']
        widgets = {
            'valeur': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 1000}),
        }
        labels = {'valeur': 'Valeur du maxima'}


class MatiereForm(forms.ModelForm):
    class Meta:
        model = Matiere
        fields = ['nom', 'maxima']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'maxima': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [(m.valeur, f"MAXIMA {m.valeur}") for m in Maxima.objects.all()]
        if not choices:
            choices = [(20, 'MAXIMA 20')]  # fallback si aucun maxima configuré
        self.fields['maxima'] = forms.ChoiceField(
            choices=choices,
            widget=forms.Select(attrs={'class': 'form-select'}),
            label='Bloc MAXIMA',
        )

    def clean_maxima(self):
        return int(self.cleaned_data['maxima'])


class MatiereClasseForm(forms.ModelForm):
    class Meta:
        model = MatiereClasse
        fields = ['matiere', 'classe', 'enseignant']
        widgets = {
            'matiere': forms.Select(attrs={'class': 'form-select'}),
            'classe': forms.Select(attrs={'class': 'form-select'}),
            'enseignant': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from classes.models import Classe, AnneeScolaire
        annee = AnneeScolaire.objects.filter(active=True).first()
        if annee:
            self.fields['classe'].queryset = Classe.objects.filter(
                annee_scolaire=annee
            ).select_related('section')
        self.fields['enseignant'].required = False
