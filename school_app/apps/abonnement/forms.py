"""
Formulaires pour la gestion des frais scolaires et paiements plateforme.
Les formulaires comptable sont dans l'app comptable/forms.py.
"""
from decimal import Decimal
from django import forms
from .models import TypeFrais


# ── TypeFrais ─────────────────────────────────────────────────────────────────

class TypeFraisForm(forms.ModelForm):
    class Meta:
        model = TypeFrais
        fields = ['nom', 'montant', 'classe', 'actif']
        widgets = {
            'nom':     forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Minerval, Tenue scolaire…'}),
            'montant': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'classe':  forms.Select(attrs={'class': 'form-select'}),
            'actif':   forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'classe': 'Classe (optionnel — vide = tous les élèves)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['classe'].empty_label = "— Tous les élèves —"
        self.fields['classe'].required = False


# ── Paiement plateforme (mobile money / virement d'abonnement) ───────────────

class PaiementPlateformeForm(forms.Form):
    MODE_CHOICES = [
        ('mobile_money', 'Mobile Money (M-Pesa, Airtel Money, Orange Money…)'),
        ('virement',     'Virement bancaire'),
        ('especes',      'Espèces (remise en main propre)'),
    ]

    montant = forms.DecimalField(
        label="Montant payé (USD)",
        min_value=Decimal('1.00'),
        max_digits=10, decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control', 'step': '0.01', 'min': '1',
            'placeholder': 'Ex : 50.00',
        }),
    )
    mode = forms.ChoiceField(
        label="Mode de paiement",
        choices=MODE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    numero_transaction = forms.CharField(
        label="Numéro de transaction / référence",
        max_length=100, required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex : MP2026XXXXXX (optionnel)',
        }),
    )
    preuve = forms.FileField(
        label="Preuve de paiement",
        required=False,
        help_text="Capture d'écran, reçu photo ou PDF. Formats : JPG, PNG, PDF, WebP. Max 5 Mo.",
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.jpg,.jpeg,.png,.pdf,.webp'}),
    )
    notes = forms.CharField(
        label="Commentaire (optionnel)",
        max_length=500, required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control', 'rows': 3,
            'placeholder': 'Informations supplémentaires…',
        }),
    )

    def clean_montant(self):
        m = self.cleaned_data.get('montant')
        if m and m <= Decimal('0'):
            raise forms.ValidationError("Le montant doit être supérieur à zéro.")
        return m
