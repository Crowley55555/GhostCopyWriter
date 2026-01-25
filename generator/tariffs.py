"""
Конфигурация тарифных планов Ghostwriter

Определяет лимиты токенов, цены и параметры для каждого тарифа.
"""

TARIFFS = {
    'DEMO_FREE': {
        'name': 'Бесплатный старт',
        'price': 0,
        'gigachat_tokens': 30_000,
        'openai_tokens': 30_000,
        'duration_days': None,  # бессрочный
        'is_subscription': False,
        'visible_in_bot': True,
        'description': '30 000 токенов GigaChat + 30 000 токенов OpenAI. Бессрочно, одноразово.',
    },
    'BASIC': {
        'name': 'Базовый',
        'price': 590,
        'gigachat_tokens': 200_000,
        'openai_tokens': 100_000,
        'duration_days': 30,
        'is_subscription': True,
        'visible_in_bot': True,
        'description': '200 000 токенов GigaChat + 100 000 токенов OpenAI. Подписка на 30 дней.',
    },
    'PRO': {
        'name': 'Про',
        'price': 1_190,
        'gigachat_tokens': 500_000,
        'openai_tokens': 200_000,
        'duration_days': 30,
        'is_subscription': True,
        'visible_in_bot': True,
        'description': '500 000 токенов GigaChat + 200 000 токенов OpenAI. Подписка на 30 дней.',
    },
    'UNLIMITED': {
        'name': 'Безлимит',
        'price': 2_490,
        'gigachat_tokens': -1,  # безлимит
        'openai_tokens': 500_000,
        'duration_days': 30,
        'is_subscription': True,
        'visible_in_bot': True,
        'description': 'Безлимит GigaChat + 500 000 токенов OpenAI. Подписка на 30 дней.',
    },
    'HIDDEN_14D': {
        'name': 'Скрытый 14 дней',
        'price': 0,
        'gigachat_tokens': -1,  # безлимит
        'openai_tokens': 0,  # недоступен
        'duration_days': 14,
        'is_subscription': False,
        'visible_in_bot': False,
        'description': 'Безлимит GigaChat, без OpenAI. 14 дней. Только через manual_token_generator.',
    },
    'HIDDEN_30D': {
        'name': 'Скрытый 30 дней',
        'price': 0,
        'gigachat_tokens': -1,  # безлимит
        'openai_tokens': 0,  # недоступен
        'duration_days': 30,
        'is_subscription': False,
        'visible_in_bot': False,
        'description': 'Безлимит GigaChat, без OpenAI. 30 дней. Только через manual_token_generator.',
    },
    'DEVELOPER': {
        'name': 'Разработчик',
        'price': 0,
        'gigachat_tokens': -1,  # безлимит
        'openai_tokens': -1,  # безлимит
        'duration_days': None,  # бессрочный
        'is_subscription': False,
        'visible_in_bot': False,
        'description': 'Безлимит всего, бессрочно. Только для разработчиков.',
    },
}


def get_tariff_config(token_type):
    """
    Получить конфигурацию тарифа по типу
    
    Args:
        token_type: Тип токена (DEMO_FREE, BASIC, PRO, etc.)
    
    Returns:
        dict: Конфигурация тарифа или None
    """
    return TARIFFS.get(token_type)


def get_visible_tariffs():
    """
    Получить список тарифов, видимых в боте
    
    Returns:
        dict: Словарь тарифов с visible_in_bot=True
    """
    return {k: v for k, v in TARIFFS.items() if v.get('visible_in_bot', False)}


def get_subscription_tariffs():
    """
    Получить список тарифов-подписок
    
    Returns:
        dict: Словарь тарифов с is_subscription=True
    """
    return {k: v for k, v in TARIFFS.items() if v.get('is_subscription', False)}
