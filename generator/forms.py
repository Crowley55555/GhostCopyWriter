from django import forms

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
    platform = forms.ChoiceField(choices=PLATFORM_CHOICES)
    template_type = forms.ChoiceField(choices=TEMPLATE_CHOICES)
    tone = forms.ChoiceField(choices=TONE_CHOICES)
    topic = forms.CharField(widget=forms.Textarea)
