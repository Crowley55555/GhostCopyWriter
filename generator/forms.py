from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, UserChangeForm
from django.contrib.auth.models import User
from django.core.validators import MaxLengthValidator
from .models import UserProfile

# Площадки поста: значение уходит в промпт (правила площадки — gigachat_api.PLATFORM_RULES)
PLATFORM_CHOICES = [
    ("VK", "ВКонтакте"),
    ("Telegram", "Telegram"),
    ("Дзен", "Дзен"),
]

# 12 необязательных настроек поста (блок «Дополнительно»)
SETTING_FIELDS = (
    'voice_tone', 'content_purpose', 'emotional_tone', 'content_format',
    'delivery_style', 'cta', 'formality_level', 'brand_voice',
    'post_length', 'hashtag_usage', 'mentions', 'audience',
)

# Значения по умолчанию для пустых настроек. Цель — пост, который звучит
# как владелец малого бизнеса, а не как реклама: спокойно, просто, по делу,
# без выдуманных ссылок, отзывов и партнёров
DEFAULT_SETTINGS = {
    'voice_tone': ["Дружелюбный"],
    'content_purpose': ["Информативный"],
    'emotional_tone': ["Спокойный"],
    'delivery_style': ["Прямой"],
    'cta': "Прокомментировать",
    'formality_level': ["Полуформальный"],
    'brand_voice': ["Простой"],
    'mentions': ["Без упоминаний"],
    'audience': ["Потенциальные клиенты"],
}

# Длина, хэштеги и формат зависят от площадки
PLATFORM_DEFAULT_SETTINGS = {
    "VK": {'post_length': "Средний", 'hashtag_usage': "Минимум", 'content_format': ["Краткий"]},
    "Telegram": {'post_length': "Короткий", 'hashtag_usage': "Без хэштегов", 'content_format': ["Краткий"]},
    "Дзен": {'post_length': "Длинный", 'hashtag_usage': "Без хэштегов", 'content_format': ["Подробный"]},
}


class GenerationForm(forms.Form):
    topic = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        label="Тема поста",
        error_messages={
            'required': "Напишите тему поста.",
            'max_length': "Тема — не больше %(limit_value)d символов (сейчас %(show_value)d).",
        },
    )
    platform = forms.ChoiceField(
        choices=PLATFORM_CHOICES,
        label="Площадка",
        widget=forms.RadioSelect,
        error_messages={
            'required': "Выберите площадку: ВКонтакте, Telegram или Дзен.",
            'invalid_choice': "Выберите площадку: ВКонтакте, Telegram или Дзен.",
        },
    )
    business_info = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        label="О бизнесе",
        help_text="Что продаёте, кому, как говорите. Одной-двумя строками.",
        required=False,
        error_messages={
            'max_length': "«О бизнесе» — не больше %(limit_value)d символов (сейчас %(show_value)d).",
        },
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Лимиты длины читаются при создании формы, а не при импорте:
        # те же настройки проверяет check_gigachat_access
        for name, max_length in (
            ('topic', settings.GENERATION_MAX_TOPIC_LENGTH),
            ('business_info', settings.GENERATION_MAX_BUSINESS_INFO_LENGTH),
        ):
            field = self.fields[name]
            field.max_length = max_length
            field.validators.append(MaxLengthValidator(max_length))
            field.widget.attrs['maxlength'] = str(max_length)

    def clean(self):
        """Пустые настройки получают значения по умолчанию (свои для площадки)"""
        cleaned_data = super().clean()
        defaults = {**DEFAULT_SETTINGS, **PLATFORM_DEFAULT_SETTINGS.get(cleaned_data.get('platform'), {})}
        for name, value in defaults.items():
            if not cleaned_data.get(name):
                cleaned_data[name] = list(value) if isinstance(value, list) else value
        return cleaned_data

    # --- Новые критерии ---
    # Тон голоса
    VOICE_TONE_CHOICES = [
        ("Дружелюбный", "Дружелюбный"),
        ("Профессиональный", "Профессиональный"),
        ("Неформальный", "Неформальный/Разговорный"),
        ("Юмористический", "Юмористический/Ироничный"),
        ("Вдохновляющий", "Вдохновляющий/Мотивирующий"),
        ("Серьезный", "Серьезный/Авторитетный"),
        ("Эмпатичный", "Эмпатичный/Заботливый"),
        ("Провокационный", "Провокационный/Смелый"),
        ("Официальный", "Официальный"),
    ]
    voice_tone = forms.MultipleChoiceField(
        choices=VOICE_TONE_CHOICES,
        label="Тон голоса",
        widget=forms.CheckboxSelectMultiple,
        help_text="Базовая эмоциональная и личностная окраска сообщения. Можно выбрать несколько.",
        required=False
    )

    # Цель контента
    CONTENT_PURPOSE_CHOICES = [
        ("Информативный", "Информативный/Образовательный"),
        ("Развлекательный", "Развлекательный"),
        ("Вовлекающий", "Вовлекающий (опрос/вопрос)"),
        ("Продающий", "Продающий/Презентующий"),
        ("Приводящий", "Приводящий (на сайт/мероприятие)"),
        ("Имиджевый", "Формирующий имидж/лояльность"),
        ("Новостной", "Оповещающий/Новостной"),
        ("Обучающий", "Обучающий/How-to"),
        ("Вдохновляющий", "Вдохновляющий/Истории успеха"),
    ]
    content_purpose = forms.MultipleChoiceField(
        choices=CONTENT_PURPOSE_CHOICES,
        label="Цель контента",
        widget=forms.CheckboxSelectMultiple,
        help_text="Основная задача, которую должен выполнить пост. Можно выбрать несколько.",
        required=False
    )

    # Эмоциональный окрас
    EMOTIONAL_TONE_CHOICES = [
        ("Радостный", "Радостный/Позитивный"),
        ("Спокойный", "Спокойный/Умиротворяющий"),
        ("Взволнованный", "Взволнованный/Энергичный"),
        ("Любопытный", "Любопытный/Интригующий"),
        ("Ностальгический", "Ностальгический"),
        ("Удивленный", "Удивленный/Восхищенный"),
        ("Сопереживающий", "Сопереживающий/Поддерживающий"),
        ("Срочный", "Срочный/FOMO"),
    ]
    emotional_tone = forms.MultipleChoiceField(
        choices=EMOTIONAL_TONE_CHOICES,
        label="Эмоциональный окрас",
        widget=forms.CheckboxSelectMultiple,
        help_text="Конкретная эмоция, которую должен вызвать пост. Можно выбрать несколько.",
        required=False
    )

    # Формат изложения
    CONTENT_FORMAT_CHOICES = [
        ("Краткий", "Краткий/Тезисный"),
        ("Подробный", "Подробный/Развернутый"),
        ("Списки", "Списки/Перечни"),
        ("FAQ", "Вопрос-Ответ (FAQ)"),
        ("История", "История/Кейс"),
        ("Пошаговая", "Пошаговая инструкция"),
        ("Сравнение", "Сравнение/Сопоставление"),
        ("Цитата", "Цитата/Высказывание"),
        ("Миф", "Миф vs. Реальность"),
    ]
    content_format = forms.MultipleChoiceField(
        choices=CONTENT_FORMAT_CHOICES,
        label="Формат изложения",
        widget=forms.CheckboxSelectMultiple,
        help_text="Структурный способ подачи информации. Можно выбрать несколько.",
        required=False
    )

    # Стиль подачи
    DELIVERY_STYLE_CHOICES = [
        ("Прямой", "Прямой/Без прикрас"),
        ("Повествовательный", "Повествовательный/Историйный"),
        ("Диалоговый", "Диалоговый/Интерактивный"),
        ("Визуальный", "Визуально-ориентированный"),
        ("Экспертный", "Экспертный/Аналитический"),
        ("Персонализированный", "Персонализированный (ты/вы)"),
        ("Новостной", "Новостной/Репортажный"),
    ]
    delivery_style = forms.MultipleChoiceField(
        choices=DELIVERY_STYLE_CHOICES,
        label="Стиль подачи",
        widget=forms.CheckboxSelectMultiple,
        help_text="Манера, в которой строится коммуникация. Можно выбрать несколько.",
        required=False
    )

    # Призыв к действию (CTA); пустое значение — призыв по умолчанию
    CTA_CHOICES = [
        ("", "По умолчанию"),
        ("Узнать больше", "Узнать больше (ссылка)"),
        ("Купить", "Купить/Заказать"),
        ("Записаться", "Записаться/Зарегистрироваться"),
        ("Скачать", "Скачать"),
        ("Посмотреть", "Посмотреть (видео)"),
        ("Поделиться", "Поделиться"),
        ("Прокомментировать", "Прокомментировать/Ответить"),
        ("Опрос", "Пройти опрос/Голосование"),
        ("Сохранить", "Сохранить пост"),
        ("Подписаться", "Подписаться"),
    ]
    cta = forms.ChoiceField(
        choices=CTA_CHOICES,
        label="Призыв к действию (CTA)",
        widget=forms.Select,
        help_text="Что вы хотите, чтобы пользователь сделал после прочтения.",
        required=False
    )

    # Уровень формальности
    FORMALITY_LEVEL_CHOICES = [
        ("Высокоформальный", "Высокоформальный (отчеты, B2B)"),
        ("Деловой", "Деловой/Профессиональный"),
        ("Полуформальный", "Полуформальный (большинство брендов)"),
        ("Неформальный", "Неформальный/Разговорный"),
        ("Сленговый", "Сленговый/Мемный"),
    ]
    formality_level = forms.MultipleChoiceField(
        choices=FORMALITY_LEVEL_CHOICES,
        label="Уровень формальности",
        widget=forms.CheckboxSelectMultiple,
        help_text="Степень официальности языка и обращения. Можно выбрать несколько.",
        required=False
    )

    # Брендовый голос
    BRAND_VOICE_CHOICES = [
        ("Экспертный", "Экспертный"),
        ("Инновационный", "Инновационный"),
        ("Надежный", "Надежный/Традиционный"),
        ("Любознательный", "Любознательный"),
        ("Игривый", "Игривый"),
        ("Заботливый", "Заботливый"),
        ("Бунтарский", "Бунтарский"),
        ("Люкс", "Люкс/Премиум"),
        ("Простой", "Простой/Практичный"),
    ]
    brand_voice = forms.MultipleChoiceField(
        choices=BRAND_VOICE_CHOICES,
        label="Брендовый голос",
        widget=forms.CheckboxSelectMultiple,
        help_text="Уникальные характеристики коммуникации бренда. Можно выбрать несколько.",
        required=False
    )

    # Длина поста (slider)
    POST_LENGTH_CHOICES = [
        ("Очень короткий", "Очень короткий (1 предложение)"),
        ("Короткий", "Короткий (1-2 абзаца)"),
        ("Средний", "Средний (2-4 абзаца)"),
        ("Длинный", "Длинный (более 4 абзацев)"),
    ]
    post_length = forms.ChoiceField(
        choices=POST_LENGTH_CHOICES,
        label="Длина поста",
        widget=forms.Select,
        help_text="Ориентировочный объем текста.",
        required=False
    )

    # Использование хэштегов (slider)
    HASHTAG_USAGE_CHOICES = [
        ("Без хэштегов", "Без хэштегов"),
        ("Минимум", "Минимум (1-3)"),
        ("Оптимально", "Оптимально (4-10)"),
        ("Максимум", "Максимальная видимость (10+)"),
    ]
    hashtag_usage = forms.ChoiceField(
        choices=HASHTAG_USAGE_CHOICES,
        label="Использование хэштегов",
        widget=forms.Select,
        help_text="Стратегия применения хэштегов.",
        required=False
    )

    # Использование упоминаний
    MENTIONS_CHOICES = [
        ("Без упоминаний", "Без упоминаний"),
        ("Партнеры", "Упоминать партнеров"),
        ("Клиенты", "Упоминать клиентов/отзывы"),
        ("Лидеры", "Упоминать лидеров мнений"),
    ]
    mentions = forms.MultipleChoiceField(
        choices=MENTIONS_CHOICES,
        label="Использование упоминаний",
        widget=forms.CheckboxSelectMultiple,
        help_text="Нужно ли упоминать других пользователей или бренды.",
        required=False
    )

    # Адаптация под ЦА
    AUDIENCE_CHOICES = [
        ("Новички", "Новички в теме"),
        ("Продвинутые", "Продвинутые пользователи"),
        ("Существующие клиенты", "Существующие клиенты"),
        ("Потенциальные клиенты", "Потенциальные клиенты"),
        ("Молодежь", "Молодежь"),
        ("Профессионалы", "Профессионалы"),
    ]
    audience = forms.MultipleChoiceField(
        choices=AUDIENCE_CHOICES,
        label="Адаптация под аудиторию",
        widget=forms.CheckboxSelectMultiple,
        help_text="Фокус на конкретную подгруппу аудитории. Можно выбрать несколько.",
        required=False
    )

# DEPRECATED: RegisterForm удален - регистрация отключена, используется система токенов

class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Имя пользователя или Email")
    password = forms.CharField(widget=forms.PasswordInput, label="Пароль")
    remember_me = forms.BooleanField(label="Запомнить меня", required=False, initial=False)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Настраиваем сообщения об ошибках
        self.error_messages = {
            'invalid_login': 'Неверное имя пользователя или пароль. Проверьте правильность введенных данных.',
            'inactive': 'Ваш аккаунт неактивен. Обратитесь к администратору.',
        }

# DEPRECATED: UserProfileForm и UserEditForm удалены - редактирование профиля отключено
# Регистрация и редактирование профиля не используются, система работает через токены
