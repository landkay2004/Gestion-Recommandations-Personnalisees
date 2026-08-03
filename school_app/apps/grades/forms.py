from django import forms
from .models import Note
from django.core.validators import MinValueValidator


class NoteForm(forms.Form):
    """Formulaire dynamique pour saisir les notes d'une classe."""
    def __init__(self, *args, eleves=None, matiere_classe=None, periode=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.eleves = eleves or []
        self.matiere_classe = matiere_classe
        self.periode = periode
        if eleves and matiere_classe:
            max_val = matiere_classe.matiere.maxima
            if periode in ('EXAM1', 'EXAM2'):
                max_val = matiere_classe.matiere.maxima * 2
            for eleve in eleves:
                field_name = f'note_{eleve.pk}'
                try:
                    existing = Note.objects.get(eleve=eleve, matiere_classe=matiere_classe, periode=periode)
                    initial = existing.valeur
                except Note.DoesNotExist:
                    initial = None
                self.fields[field_name] = forms.DecimalField(
                    label=eleve.nom_complet,
                    required=False,
                    initial=initial,
                    min_value=0,
                    max_value=max_val,
                    decimal_places=2,
                    widget=forms.NumberInput(attrs={
                        'class': 'form-control form-control-sm text-center',
                        'step': '0.5',
                        'placeholder': f'/{max_val}',
                    })
                )

    def save(self):
        for eleve in self.eleves:
            field_name = f'note_{eleve.pk}'
            valeur = self.cleaned_data.get(field_name)
            Note.objects.update_or_create(
                eleve=eleve,
                matiere_classe=self.matiere_classe,
                periode=self.periode,
                defaults={'valeur': valeur}
            )
