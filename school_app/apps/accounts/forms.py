import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import CustomUser, generate_temp_password


# ─── Règles de force du mot de passe ─────────────────────────────────────────

def password_strength(password):
    """Retourne (passed:int, failed:list[str], is_strong:bool)."""
    rules = [
        (len(password) >= 10,                      'Au moins 10 caractères'),
        (bool(re.search(r'[A-Z]', password)),       'Au moins une majuscule'),
        (bool(re.search(r'[a-z]', password)),       'Au moins une minuscule'),
        (bool(re.search(r'\d', password)),          'Au moins un chiffre'),
        (bool(re.search(r'[!@#$%^&*()\-_=+{};:,<.>?]', password)),
         'Au moins un caractère spécial (!@#$%…)'),
    ]
    passed = [msg for ok, msg in rules if ok]
    failed = [msg for ok, msg in rules if not ok]
    return len(passed), failed, len(failed) == 0


# ─── Formulaire de connexion ─────────────────────────────────────────────────

class LoginForm(AuthenticationForm):
    """Connexion par adresse e-mail — traduit l'email en username avant authenticate()."""
    username = forms.CharField(
        label='Adresse e-mail',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Adresse e-mail',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        label='Mot de passe',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Mot de passe',
        })
    )

    def clean(self):
        email_or_username = self.data.get('username', '').strip().lower()
        try:
            user = CustomUser.objects.get(email__iexact=email_or_username)
            self.data = self.data.copy()
            self.data['username'] = user.username
        except CustomUser.DoesNotExist:
            pass
        return super().clean()


# ─── Création d'utilisateur ───────────────────────────────────────────────────

class UserCreateForm(forms.ModelForm):
    class Meta:
        model  = CustomUser
        fields = ['last_name', 'first_name', 'email', 'telephone', 'role']
        widgets = {
            'last_name':  forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom de famille'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Prénom'}),
            'email':      forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'exemple@ecole.cd'}),
            'telephone':  forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+243 …'}),
            'role':       forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'last_name':  'Nom',
            'first_name': 'Prénom',
            'email':      'Adresse e-mail (identifiant de connexion)',
            'telephone':  'Téléphone',
            'role':       'Rôle',
        }

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not email:
            raise forms.ValidationError("L'adresse e-mail est obligatoire.")
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Cette adresse e-mail est déjà utilisée.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        base = self.cleaned_data['email'].split('@')[0].lower()
        base = re.sub(r'[^a-z0-9]', '', base) or 'user'
        username = base
        suffix   = 1
        while CustomUser.objects.filter(username=username).exists():
            username = f"{base}{suffix}"
            suffix  += 1
        user.username = username
        temp_password = generate_temp_password()
        user.set_password(temp_password)
        user.must_change_password = True
        if commit:
            user.save()
        return user, temp_password


# ─── Mise à jour d'utilisateur ────────────────────────────────────────────────

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model  = CustomUser
        fields = ['last_name', 'first_name', 'email', 'telephone', 'role', 'is_active']
        widgets = {
            'last_name':  forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email':      forms.EmailInput(attrs={'class': 'form-control'}),
            'telephone':  forms.TextInput(attrs={'class': 'form-control'}),
            'role':       forms.Select(attrs={'class': 'form-select'}),
            'is_active':  forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        qs = CustomUser.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Cette adresse e-mail est déjà utilisée par un autre compte.")
        return email


# ─── Profil utilisateur (photo + infos) ──────────────────────────────────────

class ProfileForm(forms.ModelForm):
    """Permet à tout utilisateur de modifier son propre profil."""

    class Meta:
        model  = CustomUser
        fields = ['first_name', 'last_name', 'email', 'telephone', 'bio', 'photo_profil']
        widgets = {
            'first_name':   forms.TextInput(attrs={'class': 'form-control'}),
            'last_name':    forms.TextInput(attrs={'class': 'form-control'}),
            'email':        forms.EmailInput(attrs={'class': 'form-control'}),
            'telephone':    forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+243 …'}),
            'bio':          forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Quelques mots sur vous…'}),
            'photo_profil': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }
        labels = {
            'first_name':   'Prénom',
            'last_name':    'Nom',
            'email':        'Adresse e-mail',
            'telephone':    'Téléphone',
            'bio':          'Biographie / Note',
            'photo_profil': 'Photo de profil',
        }

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        qs = CustomUser.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Cette adresse e-mail est déjà utilisée.")
        return email


# ─── Changement de mot de passe forcé ────────────────────────────────────────

class ForcePasswordChangeForm(forms.Form):
    current_password = forms.CharField(
        label='Mot de passe temporaire actuel',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    new_password = forms.CharField(
        label='Nouveau mot de passe',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'id': 'id_new_password'})
    )
    confirm_password = forms.CharField(
        label='Confirmer le nouveau mot de passe',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    def __init__(self, user=None, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        pwd = self.cleaned_data.get('current_password')
        if self.user and not self.user.check_password(pwd):
            raise forms.ValidationError("Le mot de passe temporaire est incorrect.")
        return pwd

    def clean_new_password(self):
        pwd = self.cleaned_data.get('new_password', '')
        _, failed, is_strong = password_strength(pwd)
        if not is_strong:
            raise forms.ValidationError(
                "Mot de passe trop faible. Manque : " + ', '.join(failed)
            )
        return pwd

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('new_password')
        p2 = cleaned.get('confirm_password')
        if p1 and p2 and p1 != p2:
            self.add_error('confirm_password', "Les deux mots de passe ne correspondent pas.")
        return cleaned


# ─── Changement de mot de passe (depuis le profil) ───────────────────────────

class ChangePasswordForm(forms.Form):
    old_password = forms.CharField(
        label='Mot de passe actuel',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    new_password = forms.CharField(
        label='Nouveau mot de passe',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'id': 'id_new_pwd'})
    )
    confirm_password = forms.CharField(
        label='Confirmer le nouveau mot de passe',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    def __init__(self, user=None, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_old_password(self):
        pwd = self.cleaned_data.get('old_password')
        if self.user and not self.user.check_password(pwd):
            raise forms.ValidationError("Le mot de passe actuel est incorrect.")
        return pwd

    def clean_new_password(self):
        pwd = self.cleaned_data.get('new_password', '')
        _, failed, is_strong = password_strength(pwd)
        if not is_strong:
            raise forms.ValidationError(
                "Mot de passe trop faible. Manque : " + ', '.join(failed)
            )
        return pwd

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('new_password')
        p2 = cleaned.get('confirm_password')
        if p1 and p2 and p1 != p2:
            self.add_error('confirm_password', "Les deux mots de passe ne correspondent pas.")
        return cleaned
