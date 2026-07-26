from django import forms
from .models import Student
from classes.models import Classe


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = [
            'matricule', 'nom', 'postnom', 'prenom', 'sexe',
            'date_naissance', 'lieu_naissance', 'adresse',
            'telephone', 'nom_parent', 'classe', 'photo'
        ]
        widgets = {
            'matricule': forms.TextInput(attrs={'class': 'form-control'}),
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'postnom': forms.TextInput(attrs={'class': 'form-control'}),
            'prenom': forms.TextInput(attrs={'class': 'form-control'}),
            'sexe': forms.Select(attrs={'class': 'form-select'}),
            'date_naissance': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'lieu_naissance': forms.TextInput(attrs={'class': 'form-control'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'nom_parent': forms.TextInput(attrs={'class': 'form-control'}),
            'classe': forms.Select(attrs={'class': 'form-select'}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from classes.models import AnneeScolaire
        annee = AnneeScolaire.objects.filter(active=True).first()
        if annee:
            self.fields['classe'].queryset = Classe.objects.filter(
                annee_scolaire=annee
            ).select_related('section').order_by('nom', 'section__nom')
