from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, UserChangeForm
from django.contrib.auth.models import User
from .models import UserProfile

PLATFORM_CHOICES = [
    ('Instagram', 'Instagram'),
    ('VK', 'VK'),
    ('Telegram', 'Telegram'),
]

TONE_CHOICES = [
    ('Дружелюбный', 'Дружелюбный'),
    ('Экспертный', 'Экспертный'),
    ('Дерзкий', 'Дерзкий'),
]

TEMPLATE_CHOICES = [
    ('Акция', 'Акция'),
    ('Новинка', 'Новинка'),
    ('Развлекательный', 'Развлекательный'),
]

class GenerationForm(forms.Form):
    platform = forms.ChoiceField(choices=PLATFORM_CHOICES, label="Платформа")
    template_type = forms.ChoiceField(choices=TEMPLATE_CHOICES, label="Тип контента")
    tone = forms.ChoiceField(choices=TONE_CHOICES, label="Тональность")
    topic = forms.CharField(widget=forms.Textarea, label="Тема поста")

class RegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label='Пароль')
    password2 = forms.CharField(widget=forms.PasswordInput, label='Повторите пароль')
    first_name = forms.CharField(max_length=50, required=True, label='Имя')
    last_name = forms.CharField(max_length=50, required=True, label='Фамилия')
    city = forms.CharField(max_length=100, required=False, label='Город')
    phone = forms.CharField(max_length=30, required=True, label='Телефон')
    date_of_birth = forms.DateField(required=False, label='Дата рождения', widget=forms.DateInput(attrs={'type': 'date'}))

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'city', 'phone', 'date_of_birth')
        labels = {
            'username': 'Никнейм',
            'email': 'Email',
        }

    def clean_password2(self):
        cd = self.cleaned_data
        if cd.get('password') != cd.get('password2'):
            raise forms.ValidationError('Пароли не совпадают')
        return cd.get('password2')

class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Имя пользователя или Email")
    password = forms.CharField(widget=forms.PasswordInput, label="Пароль")
    remember_me = forms.BooleanField(label="Запомнить меня", required=False, initial=False)

class UserProfileForm(forms.ModelForm):
    date_of_birth = forms.DateField(
        required=False,
        label='Дата рождения',
        input_formats=['%d.%m.%Y'],
        widget=forms.DateInput(attrs={
            'class': 'form-control datepicker',
            'placeholder': 'дд.мм.гггг',
            'autocomplete': 'off',
        })
    )
    class Meta:
        model = UserProfile
        fields = ['avatar', 'first_name', 'last_name', 'city', 'phone', 'date_of_birth', 'bio']
        labels = {
            'avatar': 'Аватар',
            'first_name': 'Имя',
            'last_name': 'Фамилия',
            'city': 'Город',
            'phone': 'Телефон',
            'date_of_birth': 'Дата рождения',
            'bio': 'О себе',
        }
        help_texts = {
            'bio': 'Кратко расскажите о себе',
        }

class UserEditForm(forms.ModelForm):
    date_of_birth = forms.DateField(
        required=False,
        label='Дата рождения',
        input_formats=['%d.%m.%Y'],
        widget=forms.DateInput(attrs={
            'class': 'form-control datepicker',
            'placeholder': 'дд.мм.гггг',
            'autocomplete': 'off',
        })
    )
    class Meta:
        model = UserProfile
        fields = ['avatar', 'first_name', 'last_name', 'city', 'phone', 'date_of_birth', 'bio']
        labels = {
            'avatar': 'Аватар',
            'first_name': 'Имя',
            'last_name': 'Фамилия',
            'city': 'Город',
            'phone': 'Телефон',
            'date_of_birth': 'Дата рождения',
            'bio': 'О себе',
        }
        help_texts = {
            'bio': 'Кратко расскажите о себе',
        }
