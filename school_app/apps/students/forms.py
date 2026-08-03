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
        """
        Gestion du matricule selon le contexte :

        - Nouvel élève (pas de pk) + champ vide  → génération atomique via
          MatriculeConfig.generer_matricule() (incrémente le compteur).
        - Nouvel élève + valeur soumise manuellement → conserver (saisie volontaire).
        - Élève existant + champ vide → garder le matricule d'origine.
        - Élève existant + valeur soumise → utiliser la nouvelle valeur.

        NB : le champ JS envoie une valeur VIDE pour les nouveaux élèves
        (la pré-visualisation est effacée avant soumission) afin que la
        génération atomique soit toujours utilisée en création.
        """
        value = self.cleaned_data.get('matricule', '').strip()
        is_new = not (self.instance and self.instance.pk)

        if not value:
            if is_new:
                # Générer atomiquement — garanti sans doublon
                try:
                    from school_settings.models import MatriculeConfig
                    config = MatriculeConfig.get_config()
                    return config.generer_matricule()
                except Exception:
                    import uuid
                    return f"EL{str(uuid.uuid4().int)[:8].upper()}"
            else:
                # Édition sans changement : garder l'existant
                return self.instance.matricule or value
        return value
