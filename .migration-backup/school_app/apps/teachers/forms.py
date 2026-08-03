from django import forms
from accounts.models import CustomUser, generate_temp_password
from .models import Teacher


class TeacherForm(forms.Form):
    GENRE_CHOICES = [('', '— Choisir —'), ('M', 'Masculin'), ('F', 'Féminin')]

    first_name = forms.CharField(label='Prénom', max_length=100,
                                  widget=forms.TextInput(attrs={'class': 'form-control'}))
    postnom = forms.CharField(label='Post-nom', max_length=100, required=False,
                               widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(label='Nom de famille', max_length=100,
                                 widget=forms.TextInput(attrs={'class': 'form-control'}))
    genre = forms.ChoiceField(label='Genre', choices=GENRE_CHOICES, required=False,
                               widget=forms.Select(attrs={'class': 'form-select'}))
    username = forms.CharField(label="Nom d'utilisateur", max_length=150,
                                widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(label='Email', required=False,
                              widget=forms.EmailInput(attrs={'class': 'form-control'}))
    telephone = forms.CharField(label='Téléphone', max_length=20, required=False,
                                 widget=forms.TextInput(attrs={'class': 'form-control'}))
    photo_profil = forms.ImageField(
        label='Photo de profil', required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        help_text="Photo affichée dans la liste des enseignants et dans son profil."
    )

    def __init__(self, *args, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        if instance:
            self.fields['first_name'].initial  = instance.user.first_name
            self.fields['postnom'].initial     = instance.postnom
            self.fields['last_name'].initial   = instance.user.last_name
            self.fields['genre'].initial       = instance.genre
            self.fields['username'].initial    = instance.user.username
            self.fields['email'].initial       = instance.user.email
            self.fields['telephone'].initial   = instance.telephone
            self.fields['photo_profil'].initial = instance.user.photo_profil

    def clean_username(self):
        username = self.cleaned_data['username']
        qs = CustomUser.objects.filter(username=username)
        if self.instance:
            qs = qs.exclude(pk=self.instance.user.pk)
        if qs.exists():
            raise forms.ValidationError("Ce nom d'utilisateur est déjà utilisé.")
        return username

    def save(self):
        """
        Retourne (teacher, temp_password) à la création,
        ou (teacher, None) lors d'une mise à jour.
        """
        data = self.cleaned_data
        if self.instance:
            user = self.instance.user
            user.first_name = data['first_name']
            user.last_name  = data['last_name']
            user.username   = data['username']
            user.email      = data['email']
            if data.get('photo_profil'):
                user.photo_profil = data['photo_profil']
            user.save()
            self.instance.postnom   = data.get('postnom', '')
            self.instance.genre     = data.get('genre', '')
            self.instance.telephone = data['telephone']
            self.instance.save()
            return self.instance, None
        else:
            temp_password = generate_temp_password()
            user = CustomUser.objects.create_user(
                username=data['username'],
                first_name=data['first_name'],
                last_name=data['last_name'],
                email=data['email'],
                password=temp_password,
                role='enseignant',
            )
            if data.get('photo_profil'):
                user.photo_profil = data['photo_profil']
            user.must_change_password = True
            user.save(update_fields=['must_change_password', 'photo_profil'])
            teacher = Teacher.objects.create(
                user=user,
                postnom=data.get('postnom', ''),
                genre=data.get('genre', ''),
                telephone=data['telephone'],
            )
            return teacher, temp_password
