from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.models import User
from django.core.validators import MaxLengthValidator
from .models import UserProfile

# Площадки поста: значение уходит в промпт (правила площадки — gigachat_api.PLATFORM_RULES)
# Фаза 2а.3: добавлен Max — четвёртая площадка (решение владельца 2026-10-07,
# idea/plan-impact.md, раздел 3). Правила форматирования Max — гипотеза
# (как Telegram), документация Max публично не найдена; уточнить после живой проверки.
PLATFORM_CHOICES = [
    ("VK", "ВКонтакте"),
    ("Telegram", "Telegram"),
    ("Max", "Max"),
    ("Дзен", "Дзен"),
]

# Меню «Модель» — закрытый список (замечание 1 ревью безопасности):
# значения из POST, которых здесь нет, отклоняются формой. Код совпадает
# с `generator.models.GigaChatTokenUsage.PROVIDER_CHOICES` — повторяется,
# чтобы форма не импортировала модели.
MODEL_GIGACHAT_LITE = 'gigachat-lite'
MODEL_GIGACHAT_PRO = 'gigachat-pro'
MODEL_YANDEXGPT = 'yandexgpt'
MODEL_CHOICES = [
    (MODEL_GIGACHAT_LITE, 'GigaChat Lite'),
    (MODEL_GIGACHAT_PRO, 'GigaChat Pro'),
    (MODEL_YANDEXGPT, 'YandexGPT'),
]
MODEL_DEFAULT = MODEL_GIGACHAT_LITE

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
    # ГИПОТЕЗА: правила Max для короткого канального поста совпадают с Telegram
    # (пабличные каналы Max, июль 2026). Документация публично не найдена;
    # уточнить после живой проверки — фаза 2а.3.
    "Max": {'post_length': "Короткий", 'hashtag_usage': "Без хэштегов", 'content_format': ["Краткий"]},
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
            'required': "Выберите площадку: ВКонтакте, Telegram, Max или Дзен.",
            'invalid_choice': "Выберите площадку: ВКонтакте, Telegram, Max или Дзен.",
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
    # Фаза 2а.3: образцы постов владельца (необязательно, до 10).
    # Форма ввода — одно поле Textarea с разделителем `---` на отдельной
    # строке (обоснование в checkpoint): 10 отдельных полей шумят на мобилке,
    # сессия хранит одной строкой, перегенерация и шаблоны настроек —
    # прозрачно. Образцы попадают в сообщение к модели в блоке с
    # маркерами (gigachat_api.build_user_message); факты из них не
    # переносятся — только тон, длина, обращение, эмодзи.
    samples = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4}),
        label="Образцы ваших постов",
        required=False,
        help_text=(
            "3–5 постов достаточно, до 10 — лучше. "
            "Разделяйте посты строкой из трёх дефисов (---)."
        ),
        error_messages={
            'max_length': "Образцы — не больше %(limit_value)d символов (сейчас %(show_value)d).",
        },
    )
    # Меню «Модель»: закрытый список, по умолчанию Lite. Пустое — Lite.
    # Форма допускает `yandexgpt`, доступность ключа проверяет view
    model = forms.ChoiceField(
        choices=MODEL_CHOICES,
        label="Модель",
        required=False,
        initial=MODEL_DEFAULT,
        error_messages={
            'invalid_choice': "Выберите модель: GigaChat Lite, GigaChat Pro или YandexGPT.",
        },
    )

    def clean_model(self):
        """Пустое — по умолчанию Lite"""
        return self.cleaned_data.get('model') or MODEL_DEFAULT

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Лимиты длины читаются при создании формы, а не при импорте:
        # те же настройки проверяет check_text_access. Фаза 2а.3: лимит
        # `samples` проверяет и форма, и `check_text_access` (защита в
        # обоих слоях: длина `samples` сверх лимита → 400 до вызова модели).
        for name, max_length in (
            ('topic', settings.GENERATION_MAX_TOPIC_LENGTH),
            ('business_info', settings.GENERATION_MAX_BUSINESS_INFO_LENGTH),
            ('samples', settings.GENERATION_MAX_SAMPLES_LENGTH),
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

# Фаза 3: регистрация по логину и паролю
class RegisterForm(UserCreationForm):
    """
    Регистрация по логину и паролю (без email)

    Поля: `username`, `password1`, `password2`, `terms_accepted`. Пароль
    проверяют встроенные валидаторы Django (`AUTH_PASSWORD_VALIDATORS`
    в `settings.py`). Галочка согласия обязательна и хранится в
    `UserProfile.terms_accepted` после регистрации.
    """

    terms_accepted = forms.BooleanField(
        required=True,
        label="Я согласен с условиями",
        help_text=(
            "Хранятся: логин, хэш пароля, «О бизнесе», образцы постов, "
            "посты и технические данные для защиты от злоупотреблений."
        ),
        error_messages={
            'required': "Нужно согласиться с условиями хранения данных.",
        },
    )

    class Meta:
        model = User
        # Email осознанно не включаем (решение владельца, фаза 3):
        # в демо адрес не нужен, уведомления не шлём
        fields = ('username',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Убираем email, даже если родитель его добавит в будущем
        self.fields.pop('email', None)


class UserProfileForm(forms.ModelForm):
    """
    Редактирование профиля зарегистрированного пользователя

    Поля `business_info` и `samples` подставляются в форму генерации
    (фаза 3). Длина проверяется в двух слоях: форма (`MaxLengthValidator`
    из поля) и `check_text_access` перед вызовом модели.
    """

    class Meta:
        model = UserProfile
        fields = ('business_info', 'samples')
        widgets = {
            'business_info': forms.Textarea(attrs={'rows': 2}),
            'samples': forms.Textarea(attrs={'rows': 4}),
        }
        labels = {
            'business_info': 'О бизнесе',
            'samples': 'Образцы ваших постов',
        }
        help_texts = {
            'business_info': 'Что продаёте, кому, как говорите. Одной-двумя строками.',
            'samples': (
                '3–5 постов достаточно, до 10 — лучше. '
                'Разделяйте посты строкой из трёх дефисов (---).'
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Лимиты длины — из настроек (как в `GenerationForm`)
        for name, max_length in (
            ('business_info', settings.GENERATION_MAX_BUSINESS_INFO_LENGTH),
            ('samples', settings.GENERATION_MAX_SAMPLES_LENGTH),
        ):
            field = self.fields[name]
            field.max_length = max_length
            field.validators.append(MaxLengthValidator(max_length))
            field.widget.attrs['maxlength'] = str(max_length)


