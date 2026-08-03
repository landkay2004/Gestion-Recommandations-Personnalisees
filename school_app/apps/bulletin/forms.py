from django import forms
from .models import ModeleBulletin
from classes.models import Classe, AnneeScolaire
from subjects.models import Matiere


class ModeleBulletinForm(forms.ModelForm):
    matieres_20 = forms.ModelMultipleChoiceField(
        queryset=Matiere.objects.filter(maxima=20),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Matières MAXIMA 20"
    )
    matieres_30 = forms.ModelMultipleChoiceField(
        queryset=Matiere.objects.filter(maxima=30),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Matières MAXIMA 30"
    )
    matieres_60 = forms.ModelMultipleChoiceField(
        queryset=Matiere.objects.filter(maxima=60),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Matières MAXIMA 60"
    )

    class Meta:
        model = ModeleBulletin
        fields = ['classe', 'annee_scolaire']
        widgets = {
            'classe': forms.Select(attrs={'class': 'form-select'}),
            'annee_scolaire': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        annee = AnneeScolaire.objects.filter(active=True).first()
        if annee:
            self.fields['classe'].queryset = Classe.objects.filter(
                annee_scolaire=annee
            ).select_related('section')
        if self.instance and self.instance.pk:
            selected = self.instance.matieres.values_list('matiere_id', flat=True)
            self.fields['matieres_20'].initial = selected
            self.fields['matieres_30'].initial = selected
            self.fields['matieres_60'].initial = selected
