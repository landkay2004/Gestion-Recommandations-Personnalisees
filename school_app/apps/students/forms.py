from django import forms
from .models import Student, Tuteur
from classes.models import Classe


class TuteurForm(forms.ModelForm):
    class Meta:
        model = Tuteur
        fields = ['nom', 'postnom', 'prenom', 'telephone', 'adresse', 'notes']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom de famille'}),
            'postnom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Postnom'}),
            'prenom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Prénom'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+243 …'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Adresse complète'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Notes internes…'}),
        }


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = [
            'matricule', 'nom', 'postnom', 'prenom', 'sexe',
            'date_naissance', 'lieu_naissance', 'adresse',
            'telephone', 'tuteur', 'classe', 'photo'
        ]
        widgets = {
            'matricule': forms.TextInput(attrs={'class': 'form-control'}),
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'postnom': forms.TextInput(attrs={'class': 'form-control'}),
            'prenom': forms.TextInput(attrs={'class': 'form-control'}),
            'sexe': forms.Select(attrs={'class': 'form-select'}),
            'date_naissance': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'lieu_naissance': forms.TextInput(attrs={'class': 'form-control'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'tuteur': forms.HiddenInput(),
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
        self.fields['tuteur'].required = False
        # Force le format ISO pour le champ date (obligatoire avec type="date")
        self.fields['date_naissance'].input_formats = ['%Y-%m-%d']
        # Le matricule est auto-généré si vide — rendre le champ optionnel
        self.fields['matricule'].required = False
        self.fields['matricule'].widget.attrs.update({
            'placeholder': 'Laissez vide pour générer automatiquement',
        })

    def clean_matricule(self):
        """Génère un matricule si le champ est laissé vide."""
        value = self.cleaned_data.get('matricule', '').strip()
        if not value:
            # Instance existante : conserver le matricule actuel
            if self.instance and self.instance.pk and self.instance.matricule:
                return self.instance.matricule
            # Nouvel élève : générer via MatriculeConfig
            try:
                from school_settings.models import MatriculeConfig
                config = MatriculeConfig.get_config()
                value = config.generer_matricule()
            except Exception:
                import uuid
                value = f"EL{str(uuid.uuid4().int)[:8].upper()}"
        return value
