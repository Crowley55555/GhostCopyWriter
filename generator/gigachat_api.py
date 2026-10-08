import os
import base64
import re
import time
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from django.conf import settings

from langchain_gigachat.chat_models import GigaChat
from langchain_core.messages import SystemMessage, HumanMessage
from gigachat import GigaChat as GigaChatDirect
from gigachat.models import Chat, Messages, MessagesRole

try:
    from gigachat.exceptions import ResponseError as GigaChatResponseError
except ImportError:
    GigaChatResponseError = Exception  # fallback if module structure differs

# Импорт для логирования токенов
try:
    from generator.models import GigaChatTokenUsage, Generation
    TOKEN_TRACKING_ENABLED = True
except ImportError:
    TOKEN_TRACKING_ENABLED = False

load_dotenv()

# Новый способ: один Authorization Key (рекомендуется)
GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS")

# Старый способ: Client ID + Client Secret (для обратной совместимости)
CLIENT_ID = os.getenv("GIGACHAT_CLIENT_ID")
CLIENT_SECRET = os.getenv("GIGACHAT_CLIENT_SECRET")

SCOPE = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")

# Отладочный вывод для диагностики проблем с переменными окружения
print("=" * 60)
print("GigaChat Configuration:")
print(f"  GIGACHAT_CREDENTIALS: {'SET (' + str(len(GIGACHAT_CREDENTIALS)) + ' chars)' if GIGACHAT_CREDENTIALS else 'NOT SET'}")
print(f"  CLIENT_ID: {'SET' if CLIENT_ID else 'NOT SET'}")
print(f"  CLIENT_SECRET: {'SET' if CLIENT_SECRET else 'NOT SET'}")
print(f"  SCOPE: {SCOPE}")
print("=" * 60)

def _get_credentials():
    """
    Получает credentials для GigaChat API.
    
    Поддерживает два способа:
    1. GIGACHAT_CREDENTIALS - готовый Authorization Key (рекомендуется)
    2. CLIENT_ID + CLIENT_SECRET - старый способ (будет закодирован в base64)
    """
    # Способ 1: Готовый Authorization Key (рекомендуется)
    if GIGACHAT_CREDENTIALS:
        print("Используем GIGACHAT_CREDENTIALS (готовый ключ)")
        return GIGACHAT_CREDENTIALS
    
    # Способ 2: Client ID + Client Secret (старый способ)
    if CLIENT_ID and CLIENT_SECRET:
        # Проверяем, не являются ли они одинаковыми (значит это готовый ключ)
        if CLIENT_ID == CLIENT_SECRET:
            print("CLIENT_ID == CLIENT_SECRET, используем как готовый ключ")
            return CLIENT_ID
        
        print("Используем CLIENT_ID:CLIENT_SECRET (base64)")
        creds = f"{CLIENT_ID}:{CLIENT_SECRET}".encode("utf-8")
        return base64.b64encode(creds).decode()
    
    # Ничего не настроено
    print("WARNING: GigaChat credentials не настроены!")
    print("Добавьте в .env файл:")
    print("  GIGACHAT_CREDENTIALS=ваш_authorization_key")
    print("или:")
    print("  GIGACHAT_CLIENT_ID=ваш_client_id")
    print("  GIGACHAT_CLIENT_SECRET=ваш_client_secret")
    return None

def _init_client():
    """Клиент для текста и промпта картинки; модель — настройка GIGACHAT_MODEL"""
    credentials = _get_credentials()
    if not credentials:
        raise ValueError("GigaChat credentials не настроены")
    return GigaChat(
        credentials=credentials,
        scope=SCOPE,
        model=settings.GIGACHAT_MODEL,
        verify_ssl_certs=False,
        timeout=120  # 2 минуты для текста
    )

def _init_direct_client():
    """Инициализация прямого клиента GigaChat для генерации изображений"""
    credentials = _get_credentials()
    if not credentials:
        raise ValueError("GigaChat credentials не настроены")
    return GigaChatDirect(
        credentials=credentials,
        scope=SCOPE,
        verify_ssl_certs=False,
        timeout=300  # 5 минут для изображений (они генерируются дольше)
    )

# --- ПРОМПТ ПОСТА ---
# Пост должен звучать как бизнес, а не как нейросеть. Системный промпт:
# роль и правила, стоп-лист штампов, формат площадки, фразы по настройкам,
# требование к ответу. Пользовательское сообщение: площадка, тема, «О бизнесе»

# Штампы, которые выдают текст нейросети. Прямо запрещены в системном промпте;
# find_stop_phrases ищет их в готовом тексте с учётом окончаний
STOP_PHRASES = [
    "на новый уровень",  # «выведите (свой) бизнес на новый уровень» и подобные
    "в современном мире",
    "в наше время",
    "идеальное решение",
    "уникальная возможность",
    "не упустите шанс",
    "не упустите возможность",
    "инновационный",
    "безграничные возможности",
    "хотите узнать больше?",
    "хочешь узнать больше?",
    "индивидуальный подход",
    "команда профессионалов",
    "широкий ассортимент",
    "высокое качество",
    "доступные цены",
    "незабываемые впечатления",
    "окунитесь в атмосферу",
    "окунись в атмосферу",
    "ни для кого не секрет",
    "с душой",
    "увлекательный мир",
    "не оставит равнодушным",
    "заряд энергии",
    # Глаголы с другой основой («заряж-», «заряд-ить»): окончания их не покрывают
    "заряжает энергией",
    "зарядиться энергией",
    "стучится в двери",
]

SYSTEM_PROMPT = """Ты — автор постов для соцсетей малого бизнеса: кофеен, салонов, мастерских, студий, магазинов у дома. Пишешь от имени бизнеса — так, как о своём деле рассказал бы сам владелец.

Как писать:
- По-русски, живым разговорным языком: короткие предложения, простые слова, без канцелярита и рекламного пафоса.
- Сразу к делу: первая фраза — о теме поста, а не общие рассуждения.
- Бери конкретику из темы и описания бизнеса: что именно продаётся или происходит, для кого, чем отличается. Одна живая деталь лучше трёх общих слов.
- Если в описании бизнеса сказано, как говорить (на «ты» или на «вы», с юмором или серьёзно, от первого лица), следуй ему: это важнее настроек ниже.
- Не выдумывай то, чего нет во вводе: цены, скидки, акции, сроки, адреса, телефоны, ссылки, часы работы, имена, отзывы и цифры. Нет детали — обойдись без неё.
- Не обещай того, чего нет во вводе: «без очередей», «за 15 минут», пользу для здоровья. Способ связи — только из ввода; если его нет, зови в комментарии или в личные сообщения.
- Без преувеличений и громких обещаний. Говори прямо, без метафор и красивостей.
- Не используй штампы: {stop_phrases}. Их перефразировки тоже не подходят."""

SYSTEM_PROMPT_OUTPUT = (
    "Ответ — только готовый текст поста, который можно сразу опубликовать: "
    "без вступления вроде «Вот пост», без меток «Текст поста:» и «Заголовок:», "
    "без пояснений, вариантов и комментариев после текста."
)

# Нормы длины, хэштегов и эмодзи. Из них собираются правила площадки, фразы
# настроек (системный промпт) и напоминание в конце сообщения пользователя:
# числа записаны один раз
POST_LENGTH_RANGES = {
    "Короткий": (300, 600),
    "Средний": (600, 1200),
    "Длинный": (1500, 2500),
}
HASHTAG_RANGES = {
    "Без хэштегов": (0, 0),
    "Минимум": (1, 3),
    "Оптимально": (4, 10),
    "Максимум": (11, None),
}
PLATFORM_EMOJI = {
    "VK": (1, 3),
    "Telegram": (0, 2),
    "Дзен": (0, 0),
}
DZEN_STRUCTURE = "вступление, 2–4 смысловых блока и короткий вывод"


# Знаков на слово в русском тексте с пробелами: подсказка длины в словах
# рядом с нормой в знаках
_CHARS_PER_WORD = 6


def _length_norm(value):
    """«600–1200 знаков (около 100–200 слов)» для настройки post_length"""
    if value not in POST_LENGTH_RANGES:
        return "одно-два предложения"
    low, high = POST_LENGTH_RANGES[value]
    words = [round(chars / _CHARS_PER_WORD, -1) for chars in (low, high)]
    return f"{low}–{high} знаков (около {words[0]:.0f}–{words[1]:.0f} слов)"


def _length_minimum(value):
    """«не короче 600 знаков»: в прогоне модель писала короче нормы"""
    if value not in POST_LENGTH_RANGES:
        return ""
    return f", не короче {POST_LENGTH_RANGES[value][0]} знаков"


def _hashtags_word(count):
    if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        return "хэштега"
    return "хэштегов"


def _hashtag_norm(value):
    """«1–3 хэштега» для настройки hashtag_usage; None — без хэштегов"""
    low, high = HASHTAG_RANGES[value]
    if high == 0:
        return None
    if high is None:
        return f"больше {low - 1} {_hashtags_word(low - 1)}"
    return f"{low}–{high} {_hashtags_word(high)}"


def _emoji_norm(platform):
    """«Эмодзи — 1–3», «Эмодзи — не больше 2», «Без эмодзи»"""
    low, high = PLATFORM_EMOJI[platform]
    if not high:
        return "Без эмодзи"
    if not low:
        return f"Эмодзи — не больше {high}"
    return f"Эмодзи — {low}–{high}"


# Формат под площадку; label — название площадки в сообщении к GigaChat,
# reminder — главное правило площадки для напоминания в сообщении пользователя.
# Длина и хэштеги — настройки post_length и hashtag_usage: их значения
# по умолчанию свои для каждой площадки (forms.PLATFORM_DEFAULT_SETTINGS)
PLATFORM_RULES = {
    "VK": {
        'label': "ВКонтакте",
        'rules': [
            "Пост для сообщества ВКонтакте. Первая строка цепляет и сразу говорит, о чём пост.",
            "Абзацы по 2–3 предложения, между абзацами пустая строка.",
            f"{_emoji_norm('VK')} на весь пост, по смыслу, не в начале каждой строки.",
            "Без Markdown: ВКонтакте не показывает жирный шрифт, звёздочки останутся в тексте.",
        ],
    },
    "Telegram": {
        'label': "Telegram",
        'reminder': "Главное — в первой строке.",
        'rules': [
            "Пост для Telegram-канала. Главное — в первой строке: её видно в уведомлении.",
            "Короткие абзацы по 1–3 предложения, между абзацами пустая строка.",
            "Одну-две ключевые фразы можно выделить жирным: **так**. Другой разметки не нужно.",
            f"{_emoji_norm('Telegram')} на весь пост.",
        ],
    },
    "Дзен": {
        'label': "Дзен",
        'reminder': f"Первая строка — заголовок статьи, дальше {DZEN_STRUCTURE}.",
        'rules': [
            "Статья для Дзена. Первая строка — всегда заголовок: конкретный, до 70 знаков, "
            "без кавычек, без слова «Заголовок» и без точки в конце.",
            f"После заголовка — пустая строка, затем {DZEN_STRUCTURE}.",
            "Абзацы по 2–4 предложения, между абзацами пустая строка. "
            "Подзаголовки — отдельной строкой, без символов #.",
            f"{_emoji_norm('Дзен')}, даже в списках: пункты начинай с дефиса или цифры. Без Markdown.",
        ],
    },
}

# --- ФРАЗЫ ПО НАСТРОЙКАМ ---
# Без выдуманных фактов и без штампов: ссылки, отзывы, партнёры и сроки —
# только если они есть во вводе
VOICE_TONE_PROMPTS = {
    "Дружелюбный": "Тон — дружелюбный, как в живом разговоре с клиентом.",
    "Профессиональный": "Тон — профессиональный и уверенный, но без канцелярита.",
    "Неформальный": "Тон — неформальный, разговорный.",
    "Юмористический": "Тон — с лёгким юмором и иронией, без натужных шуток.",
    "Вдохновляющий": "Тон — вдохновляющий, но без пафоса.",
    "Серьезный": "Тон — серьёзный, авторитетный.",
    "Эмпатичный": "Тон — заботливый: покажи, что понимаешь заботы читателя.",
    "Провокационный": "Тон — смелый: можно начать с неожиданного утверждения.",
    "Официальный": "Тон — официальный, деловой.",
}
CONTENT_PURPOSE_PROMPTS = {
    "Информативный": "Цель — рассказать о теме: что это, для кого и чем полезно.",
    "Развлекательный": "Цель — развлечь читателя, не теряя связи с бизнесом.",
    "Вовлекающий": "Цель — вовлечь: задай читателям вопрос или предложи выбрать вариант.",
    "Продающий": "Цель — показать товар или услугу так, чтобы захотелось купить, без давления.",
    "Приводящий": "Цель — позвать на сайт, в магазин или на мероприятие; адрес и ссылку указывай, только если они есть во вводе.",
    "Имиджевый": "Цель — показать, какой это бизнес: подход, люди, ценности.",
    "Новостной": "Цель — сообщить новость: что случилось и что это значит для клиентов.",
    "Обучающий": "Цель — научить: дай полезный совет или короткую инструкцию.",
    "Вдохновляющий": "Цель — вдохновить историей; не выдумывай события и людей.",
}
EMOTIONAL_TONE_PROMPTS = {
    "Радостный": "Настроение — радостное, позитивное.",
    "Спокойный": "Настроение — спокойное, без восклицаний и нагнетания.",
    "Взволнованный": "Настроение — энергичное, живое.",
    "Любопытный": "Настроение — интригующее: начни с вопроса или неожиданной детали.",
    "Ностальгический": "Настроение — тёплое, немного ностальгическое.",
    "Удивленный": "Настроение — удивление и восхищение деталью.",
    "Сопереживающий": "Настроение — поддерживающее, с сочувствием к читателю.",
    "Срочный": "Подчеркни, почему не стоит откладывать, — только если во вводе есть срок или ограничение; без давления.",
}
CONTENT_FORMAT_PROMPTS = {
    "Краткий": "Формат — коротко и по делу, без вступлений и воды.",
    "Подробный": "Формат — подробно: объясни, как это устроено и почему это важно.",
    "Списки": "Используй короткий список там, где он помогает читать.",
    "FAQ": "Формат — вопрос-ответ: 2–4 вопроса, которые на самом деле задают клиенты.",
    "История": "Формат — короткая история или случай; опирайся на ввод, не выдумывай имена и цифры.",
    "Пошаговая": "Формат — пошаговая инструкция.",
    "Сравнение": "Формат — сравнение: было и стало или один вариант против другого.",
    "Цитата": "Начни с короткой мысли по теме; не приписывай её известным людям.",
    "Миф": "Формат — миф и реальность: распространённое заблуждение и как на самом деле.",
}
DELIVERY_STYLE_PROMPTS = {
    "Прямой": "Подача — прямая, без прикрас и лишних слов.",
    "Повествовательный": "Подача — рассказ, как будто делишься случаем из жизни бизнеса.",
    "Диалоговый": "Подача — диалог с читателем: обращайся к нему и задавай вопросы.",
    "Визуальный": "Опиши, как это выглядит: цвета, детали, обстановку.",
    "Экспертный": "Подача — экспертная: объясняй со знанием дела, простыми словами.",
    "Персонализированный": "Обращайся к читателю напрямую — на «вы» или на «ты», как принято в описании бизнеса.",
    "Новостной": "Подача — новостная: факты по порядку.",
}
CTA_PROMPTS = {
    "Узнать больше": "В конце предложи узнать подробности; ссылку ставь, только если она есть во вводе, иначе позови в сообщения.",
    "Купить": "В конце предложи купить или заказать; способ заказа — только из ввода, иначе позови в сообщения.",
    "Записаться": "В конце предложи записаться; способ записи — только из ввода, иначе позови в сообщения.",
    "Скачать": "В конце предложи скачать материал, если он упомянут во вводе.",
    "Посмотреть": "В конце предложи посмотреть видео, если оно упомянуто во вводе.",
    "Поделиться": "В конце предложи поделиться постом с тем, кому он пригодится.",
    "Прокомментировать": "В конце задай читателям простой вопрос о том, о чём пост, — такой, на который хочется ответить в комментариях.",
    "Опрос": "В конце предложи читателям проголосовать или выбрать вариант.",
    "Сохранить": "В конце предложи сохранить пост, чтобы не потерять.",
    "Подписаться": "В конце предложи подписаться.",
}
FORMALITY_LEVEL_PROMPTS = {
    "Высокоформальный": "Язык — официальный, строгий.",
    "Деловой": "Язык — деловой, профессиональный.",
    "Полуформальный": "Язык — живой и вежливый: без сленга и без канцелярита.",
    "Неформальный": "Язык — разговорный.",
    "Сленговый": "Язык — молодёжный, можно сленг, но без перебора.",
}
BRAND_VOICE_PROMPTS = {
    "Экспертный": "Голос бренда — эксперт, который знает своё дело.",
    "Инновационный": "Голос бренда — про новое: что необычного в подходе, без громких слов.",
    "Надежный": "Голос бренда — надёжный, основательный.",
    "Любознательный": "Голос бренда — любознательный, увлечённый своим делом.",
    "Игривый": "Голос бренда — игривый, лёгкий.",
    "Заботливый": "Голос бренда — заботливый.",
    "Бунтарский": "Голос бренда — дерзкий, идёт против привычного.",
    "Люкс": "Голос бренда — премиальный и сдержанный, без кричащих слов.",
    "Простой": "Голос бренда — простой и практичный: говори о пользе, а не о величии.",
}
POST_LENGTH_PROMPTS = {
    "Очень короткий": f"Длина — {_length_norm('Очень короткий')}.",
    "Короткий": f"Длина — {_length_norm('Короткий')}, 1–2 абзаца{_length_minimum('Короткий')}.",
    "Средний": f"Длина — {_length_norm('Средний')}, 3–4 абзаца{_length_minimum('Средний')}.",
    "Длинный": f"Длина — {_length_norm('Длинный')}, больше 4 абзацев{_length_minimum('Длинный')}.",
}
HASHTAG_USAGE_PROMPTS = {
    value: f"В последней строке — {_hashtag_norm(value)} по теме." if _hashtag_norm(value) else "Хэштеги не ставь."
    for value in HASHTAG_RANGES
}
MENTIONS_PROMPTS = {
    "Без упоминаний": "Не упоминай другие аккаунты и бренды.",
    "Партнеры": "Упомяни партнёров, только если они названы во вводе.",
    "Клиенты": "Сошлись на клиентов или отзывы, только если они есть во вводе; не придумывай отзывы.",
    "Лидеры": "Упомяни лидеров мнений, только если они названы во вводе.",
}
AUDIENCE_PROMPTS = {
    "Новички": "Пиши для новичков: без терминов или с объяснением.",
    "Продвинутые": "Пиши для тех, кто разбирается в теме.",
    "Существующие клиенты": "Пиши для постоянных клиентов.",
    "Потенциальные клиенты": "Пиши для тех, кто ещё не знаком с бизнесом.",
    "Молодежь": "Пиши для молодёжи.",
    "Профессионалы": "Пиши для профессионалов.",
}

# Фразы по 12 настройкам формы (forms.SETTING_FIELDS). Длина и хэштеги
# идут в раздел формата, остальные — в «Настройки поста»
SETTING_PROMPTS = {
    'voice_tone': VOICE_TONE_PROMPTS,
    'content_purpose': CONTENT_PURPOSE_PROMPTS,
    'emotional_tone': EMOTIONAL_TONE_PROMPTS,
    'content_format': CONTENT_FORMAT_PROMPTS,
    'delivery_style': DELIVERY_STYLE_PROMPTS,
    'cta': CTA_PROMPTS,
    'formality_level': FORMALITY_LEVEL_PROMPTS,
    'brand_voice': BRAND_VOICE_PROMPTS,
    'post_length': POST_LENGTH_PROMPTS,
    'hashtag_usage': HASHTAG_USAGE_PROMPTS,
    'mentions': MENTIONS_PROMPTS,
    'audience': AUDIENCE_PROMPTS,
}
FORMAT_SETTINGS = ('post_length', 'hashtag_usage')


def _setting_phrases(data, names):
    """Фразы по выбранным значениям настроек (значение — строка или список)"""
    phrases = []
    for name in names:
        values = data.get(name) or []
        if isinstance(values, str):
            values = [values]
        for value in values:
            phrase = SETTING_PROMPTS[name].get(value)
            if phrase:
                phrases.append(phrase)
    return phrases


# --- PROMPT ASSEMBLY FUNCTIONS ---
def assemble_prompt_from_criteria(data):
    """
    Собирает системный промпт: роль и правила со стоп-листом, формат площадки
    (с длиной и хэштегами), фразы по остальным настройкам, требование к ответу

    Значения по умолчанию для пустых настроек подставляет форма
    (GenerationForm.clean); здесь в промпт идут только заполненные.
    """
    stop_phrases = ', '.join(f'«{phrase}»' for phrase in STOP_PHRASES)
    parts = [SYSTEM_PROMPT.format(stop_phrases=stop_phrases)]

    platform = PLATFORM_RULES.get(data.get('platform'))
    format_lines = (platform['rules'] if platform else []) + _setting_phrases(data, FORMAT_SETTINGS)
    if format_lines:
        title = f"Формат — {platform['label']}:" if platform else "Формат:"
        parts.append('\n'.join([title] + [f'- {line}' for line in format_lines]))

    other_settings = [name for name in SETTING_PROMPTS if name not in FORMAT_SETTINGS]
    setting_lines = _setting_phrases(data, other_settings)
    if setting_lines:
        parts.append('\n'.join(['Настройки поста:'] + [f'- {line}' for line in setting_lines]))

    parts.append(SYSTEM_PROMPT_OUTPUT)
    return '\n\n'.join(parts)


# Повторы правил в конце сообщения пользователя. В прогоне фазы 2 модель,
# видя запреты только в системном промпте, придумывала название салона и бренд,
# писала штампы из стоп-листа и посты короче нормы площадки
USER_MESSAGE_FACTS_REMINDER = (
    "Бери факты только из этого сообщения: не придумывай названия, бренды, книги, сайты, цены, сроки и обещания."
)
USER_MESSAGE_STOP_PHRASES_REMINDER = (
    "Не используй штампы и их перефразировки: {stop_phrases}. Говори прямо, без метафор."
)


def _format_reminder(data):
    """
    Норма площадки и выбранных настроек: длина, хэштеги, эмодзи и главное
    правило площадки. Те же фразы и числа, что в системном промпте
    """
    platform = data.get('platform')
    lines = _setting_phrases(data, FORMAT_SETTINGS)
    if platform in PLATFORM_EMOJI:
        emoji_allowed = PLATFORM_EMOJI[platform][1]
        lines.append(f"{_emoji_norm(platform)}{' на весь пост' if emoji_allowed else ', даже в списках'}.")
    reminder = PLATFORM_RULES.get(platform, {}).get('reminder')
    if reminder:
        lines.append(reminder)
    return ' '.join(lines)


def build_user_message(data):
    """
    Сообщение пользователя: площадка, тема, «О бизнесе» (если заполнено),
    затем напоминания: норма площадки, штампы, выдуманные факты
    """
    lines = ["Напиши пост."]
    platform = PLATFORM_RULES.get(data.get('platform'))
    if platform:
        lines.append(f"Площадка: {platform['label']}")
    lines.append(f"Тема: {(data.get('topic') or '').strip()}")
    business_info = (data.get('business_info') or '').strip()
    if business_info:
        lines.append(f"О бизнесе: {business_info}")
    format_reminder = _format_reminder(data)
    if format_reminder:
        lines.append(format_reminder)
    lines.append(USER_MESSAGE_STOP_PHRASES_REMINDER.format(
        stop_phrases=', '.join(f'«{phrase}»' for phrase in STOP_PHRASES)))
    lines.append(USER_MESSAGE_FACTS_REMINDER)
    return '\n'.join(lines)


# Окончания для поиска штампов (после замены «ё» на «е»). Основа слова штампа —
# слово без самого длинного окончания своей части речи; в тексте после основы
# допускается любое окончание той же части речи: «подход» находит «подхода»,
# но не «подходит», «душой» — «душою», но не «душем»
_VERB_ENDINGS = (
    'иться', 'аться', 'яться', 'уться', 'еться', 'итесь', 'айтесь', 'ится', 'ятся', 'атся', 'ется',
    'ются', 'утся', 'ешься', 'ишься', 'емся', 'имся', 'ись', 'ить', 'ать', 'ять', 'еть', 'уть',
    'ите', 'айте', 'ешь', 'ишь', 'ает', 'яет', 'ует', 'ают', 'яют', 'уют', 'аем', 'ит', 'ят', 'ут',
    'ют', 'ет', 'ем', 'им', 'ай', 'и',
)
_ADJECTIVE_ENDINGS = (
    'ого', 'его', 'ому', 'ему', 'ыми', 'ими', 'ый', 'ий', 'ой', 'ая', 'яя', 'ое', 'ее', 'ые', 'ие',
    'ую', 'юю', 'ым', 'им', 'ом', 'ем', 'ей', 'ых', 'их',
)
# Без «ем»: «душой» не находит «душем»
_NOUN_ENDINGS = (
    'иями', 'ями', 'ами', 'ией', 'ием', 'иям', 'иях', 'ия', 'ие', 'ии', 'ию', 'ий', 'ой', 'ей', 'ою',
    'ею', 'ом', 'ам', 'ям', 'ах', 'ях', 'ов', 'ев', 'ью', 'а', 'я', 'о', 'е', 'и', 'ы', 'у', 'ю', 'ь',
)
# Какое окончание слова штампа отбрасывается и к какой части речи оно относится.
# Неоднозначные окончания отнесены к одной части речи по словам стоп-листа:
# «ом» — прилагательное («в современном»), «ой» — существительное («с душой»)
_STRIP_ENDINGS = (
    (('иться', 'аться', 'ится', 'итесь', 'ись', 'ить', 'ать', 'ите', 'ешь', 'ает', 'ит'), _VERB_ENDINGS),
    (('ого', 'ому', 'ыми', 'ый', 'ий', 'ая', 'ое', 'ые', 'ую', 'ым', 'ом', 'ых'), _ADJECTIVE_ENDINGS),
    (_NOUN_ENDINGS, _NOUN_ENDINGS),
)
# Основа короче — слово ищется целиком: «новый», «хотите», «узнать»
_MIN_STEM_LENGTH = 3
# Слова, которые допускаются между словами штампа: «не упустите свой шанс»,
# «в нашем современном мире». Другие слова — уже другая фраза:
# «в нашей студии время», «индивидуальные занятия подходят»
_STOP_PHRASE_INSERTED_WORD = r'(?:сво[йюие]|(?:ваш|наш)(?:а|е|и|у|его|ей|ему|им|ими|ем|их)?|этот|эту|эти|это)'


def _stop_word_pattern(word):
    """Шаблон слова штампа: основа и окончание той же части речи"""
    if len(word) <= 2:
        return re.escape(word)
    for strip_endings, match_endings in _STRIP_ENDINGS:
        for ending in sorted(strip_endings, key=len, reverse=True):
            if word.endswith(ending):
                stem = word[:-len(ending)]
                if len(stem) < _MIN_STEM_LENGTH:
                    return re.escape(word)
                return re.escape(stem) + '(?:' + '|'.join(match_endings) + ')'
    # Окончания нет («подход», «шанс», «мир»): основа — само слово, дальше — как у существительного
    return re.escape(word) + '(?:' + '|'.join(_NOUN_ENDINGS) + ')?'


def _stop_phrase_pattern(phrase):
    """
    Шаблон штампа с учётом окончаний

    От слова остаётся основа без типичного окончания: «уникальная возможность»
    находит и «уникальную возможность», «окунитесь» — и «окунись». Слова из
    одной-двух букв («в», «не») и слова с короткой основой ищутся целиком.
    Между словами штампа допускается одно слово из короткого списка:
    «не упустите свой шанс», «в нашем современном мире».
    """
    words = [_stop_word_pattern(word) for word in re.findall(r'\w+', phrase.lower().replace('ё', 'е'))]
    separator = rf'\b(?:\s+{_STOP_PHRASE_INSERTED_WORD}\b)?\s+'
    return re.compile(r'\b' + separator.join(words) + r'\b')


_STOP_PATTERNS = [(phrase, _stop_phrase_pattern(phrase)) for phrase in STOP_PHRASES]


def find_stop_phrases(text):
    """Штампы из STOP_PHRASES, найденные в тексте (с учётом окончаний)"""
    if not text:
        return []
    normalized = text.lower().replace('ё', 'е')
    return [phrase for phrase, pattern in _STOP_PATTERNS if pattern.search(normalized)]


def estimate_tokens(text):
    """
    Оценивает количество токенов в тексте
    
    Для русского языка: ~1 токен = 2-3 символа
    Для английского: ~1 токен = 4 символа
    Используем среднее значение: ~1 токен = 2.5 символа для смешанного текста
    
    Args:
        text: Текст для оценки
    
    Returns:
        int: Оценочное количество токенов
    """
    if not text:
        return 0
    # Оценка: 1 токен ≈ 2.5 символа для смешанного русско-английского текста
    return int(len(str(text)) / 2.5)


def log_token_usage(operation_type, prompt_text, response_text, generation_id=None, 
                    user=None, token=None, topic=None, platform=None):
    """
    Логирует использование токенов GigaChat
    
    Args:
        operation_type: Тип операции ('TEXT_GENERATION', 'IMAGE_PROMPT', 'IMAGE_GENERATION')
        prompt_text: Текст промпта
        response_text: Текст ответа от API
        generation_id: ID генерации (опционально)
        user: Пользователь Django (опционально)
        token: TemporaryAccessToken (опционально)
        topic: Тема генерации (опционально)
        platform: Платформа (опционально)
    """
    if not TOKEN_TRACKING_ENABLED:
        return
    
    try:
        prompt_tokens = estimate_tokens(prompt_text)
        completion_tokens = estimate_tokens(response_text)
        total_tokens = prompt_tokens + completion_tokens
        
        generation = None
        if generation_id:
            try:
                generation = Generation.objects.get(id=generation_id)
            except Generation.DoesNotExist:
                pass

        # Тема и платформа приходят от пользователя и бывают длиннее полей.
        # PostgreSQL отверг бы такую строку, и вызов остался бы без учёта
        topic_max = GigaChatTokenUsage._meta.get_field('topic').max_length
        platform_max = GigaChatTokenUsage._meta.get_field('platform').max_length
        if topic:
            topic = str(topic)[:topic_max]
        if platform:
            platform = str(platform)[:platform_max]

        GigaChatTokenUsage.objects.create(
            generation=generation,
            user=user,
            token=token,
            operation_type=operation_type,
            estimated_prompt_tokens=prompt_tokens,
            estimated_completion_tokens=completion_tokens,
            estimated_total_tokens=total_tokens,
            prompt_length=len(str(prompt_text)),
            response_length=len(str(response_text)),
            topic=topic,
            platform=platform
        )
    except Exception as e:
        # Не прерываем выполнение при ошибке логирования
        print(f"Ошибка при логировании токенов: {e}")


GIGACHAT_LIMIT_WARNING = "WARNING: Лимит токенов GigaChat исчерпан. Пожалуйста, обновите подписку или выберите другой тариф."


def _gigachat_limit_reached(token):
    """
    Лимит GigaChat у переданного токена исчерпан (или токен неактивен, истёк)

    Проверяется перед каждым обращением к клиенту: view проверяет доступ
    один раз, а цепочка «текст → промпт → картинка» делает до трёх вызовов.
    """
    return token is not None and not token.can_use_gigachat()[0]


def _account_gigachat_call(token, tokens_used, **log_kwargs):
    """
    Учёт состоявшегося вызова GigaChat: списание с токена и строка GigaChatTokenUsage

    Квота к этому моменту уже потрачена, поэтому учитывается и вызов,
    пересёкший лимит токена: его результат отдаётся как обычно, а следующий
    вызов остановит _gigachat_limit_reached (токен в памяти видит списание).
    """
    if token:
        try:
            token.consume_gigachat_tokens(tokens_used)
        except Exception as e:
            print(f"Ошибка при учёте токенов GigaChat: {e}")
    log_token_usage(token=token, **log_kwargs)


# --- ПОСТОБРАБОТКА ОТВЕТА ---
# Метки перед текстом: «Текст поста:», «**Заголовок:**», «Хэштеги:».
# Метка снимается, текст после неё остаётся (заголовок Дзена, хэштеги)
_LABEL_RE = re.compile(
    r'^\s*[*_]{0,2}\s*(?:текст поста|готовый пост|заголовок|хэштеги|хештеги|'
    r'призыв к действию|cta)\s*[*_]{0,2}\s*:\s*[*_]{0,2}\s*',
    re.IGNORECASE,
)
# Метки «Пост:» и «Текст:» — только одни в первой строке с текстом:
# «Пост: какой хлеб можно есть» — заголовок Дзена
_POST_WORD_LABEL_RE = re.compile(r'^\s*[*_]{0,2}\s*(?:пост|текст)\s*[*_]{0,2}\s*:\s*[*_]{0,2}\s*$', re.IGNORECASE)
# Метка «Текст поста:» — всё до неё служебное
_POST_LABEL_RE = re.compile(r'^\s*[*_]{0,2}\s*текст поста\s*[*_]{0,2}\s*:', re.IGNORECASE)
# Маркер старой преамбулы: пост — после него. Только строка целиком
# («Финальный результат зависит от ухода» — текст поста) и только в ответе
# старого формата, с «Агент…:» или «Критик:» («Было: … / Финальный результат: /
# блестящие волосы» — тоже текст поста)
_OLD_FINAL_RE = re.compile(r'^\W*финальный результат\W*$', re.IGNORECASE)
_OLD_FORMAT_RE = re.compile(r'^\s*[*_]{0,2}\s*(?:агент(?:-\w+)?\s*\d*|критик)\s*[*_]{0,2}\s*:', re.IGNORECASE)
# Вступление модели перед постом: «Вот пост для Telegram:». Слова целиком:
# «Вот и поступил в меню…» — начало поста
_INTRO_RE = re.compile(r'^\s*(?:конечно|вот|хорошо|отлично|ниже|держите|готово)\b.*:\s*$', re.IGNORECASE)
_INTRO_POST_RE = re.compile(r'\b(?:пост|поста|текст|текста|стать[яюи])\b', re.IGNORECASE)
# Вступление с «вариант…» — только про варианты поста («Вот два варианта поста:»)
# или перед меткой «Вариант 1»: «Вот несколько вариантов осеннего ухода:» — начало поста
_INTRO_VARIANT_RE = re.compile(r'\bвариант\w*', re.IGNORECASE)
_INTRO_VARIANT_OF_POST_RE = re.compile(r'\bвариант\w*\s+(?:поста|постов|текста|текстов|статьи|статей)\b',
                                       re.IGNORECASE)
# Пояснения и служебные блоки после поста. Ищутся только в последнем абзаце:
# с такой строки он отрезается до конца.
# Служебные метки (и старые «Критик», «Агент-…:») — всегда
_TAIL_LABEL_RE = re.compile(
    r'^\s*[*_]{0,2}\s*(?:примечание|пояснение|комментарий|рекомендации по визуалу|ключевые слова|'
    r'оценка критика|резюме улучшений|финальная оценка|критик|агент(?:-\w+)?\s*\d*)\s*[*_]{0,2}\s*:',
    re.IGNORECASE,
)
# Фраза о самом посте («подчёркивает», «написан», «надеюсь, пост…»): «Этот текст —
# для тех, кто…» и «Надеюсь, этот совет…» — текст поста. С вопросом читателям
# после неё не срезается: вопрос ценнее, чем снятая обёртка
_TAIL_PHRASE_RE = re.compile(
    r'^\s*[*_]{0,2}\s*(?:'
    r'(?:(?:этот|данный) )?(?:пост|текст)(?: \w+)? (?:'
    r'подч[её]ркива|написан|составлен|создан|получил|подходит|соответствует|сочета|'
    r'ориентирован|рассчитан|выдержан|направлен|нацелен|призван|акцентир|отража|передаёт|передает|'
    r'содержит|включает|использует|демонстрир|вовлека|привлека|мотивир|побужда)'
    r'|надеюсь,? (?:этот |данный )?(?:пост|текст)\b'
    r')',
    re.IGNORECASE,
)
_VARIANT_RE = re.compile(r'^\s*[*_]{0,2}\s*вариант\s*(\d+)\s*[*_]{0,2}\s*[:.]?\s*[*_]{0,2}\s*$', re.IGNORECASE)
# Площадки без Markdown: ** остались бы в тексте звёздочками. Жирный снимается,
# текст остаётся (решение судьи по ревью фазы 2, п. 5: в прогоне раунда 2
# Lite выделяла подзаголовки Дзена жирным)
PLATFORMS_WITHOUT_MARKDOWN = ('VK', 'Дзен')
_BOLD_RE = re.compile(r'\*\*(.+?)\*\*')
_FENCE_RE = re.compile(r'^\s*```')
_SEPARATOR_RE = re.compile(r'^\s*(?:-{3,}|\*{3,}|_{3,})\s*$')
_MARKDOWN_HEADER_RE = re.compile(r'^\s*#{1,6}\s+')
_WRAPPING_QUOTES = (('«', '»'), ('"', '"'), ('“', '”'))


def _is_variant_1(line):
    match = _VARIANT_RE.match(line) if line is not None else None
    return bool(match) and match.group(1) == '1'


def _is_intro(line, next_line):
    """
    Вступление модели перед постом. «Вариант…» — только про варианты поста
    или перед «Вариант 1»; иначе нужно слово «пост», «текст», «статья»
    """
    if not _INTRO_RE.match(line):
        return False
    if _INTRO_VARIANT_RE.search(line):
        return bool(_INTRO_VARIANT_OF_POST_RE.search(line)) or _is_variant_1(next_line)
    return bool(_INTRO_POST_RE.search(line))


def _tail_start(lines, start):
    """
    Первая строка пояснения после поста среди lines[start:] или None

    Служебная метка срезается всегда, фраза о самом посте — если после неё
    нет вопроса читателям
    """
    for i in range(start, len(lines)):
        if _TAIL_LABEL_RE.match(lines[i]):
            return i
        if _TAIL_PHRASE_RE.match(lines[i]) and not any('?' in line for line in lines[i:]):
            return i
    return None


def postprocess_final_result(text, platform=None):
    """
    Оставляет только текст поста

    Снимает то, что модель иногда добавляет вокруг поста: обёртку ```,
    вступление («Вот пост:»), метки («Текст поста:», «Заголовок:»), варианты
    кроме первого, пояснения после текста, кавычки вокруг всего ответа,
    символы # у заголовков. **Жирный** остаётся в Telegram и снимается
    во ВКонтакте и Дзене (platform). Маркеры старой преамбулы («Финальный
    Результат», «Критик», «Агент…») тоже срезаются.
    """
    if not text:
        return text

    lines = [line.rstrip() for line in text.strip().splitlines() if not _FENCE_RE.match(line)]

    # Всё до «Финальный Результат» (в ответе старого формата) или до метки
    # «Текст поста:» — служебное
    old_format = any(_OLD_FORMAT_RE.match(line) for line in lines)
    for i, line in enumerate(lines):
        if old_format and _OLD_FINAL_RE.search(line):
            lines = lines[i + 1:]
            break
        if _POST_LABEL_RE.match(line):
            lines = lines[i:]
            break

    content = [i for i, line in enumerate(lines) if line.strip()]
    if content:
        next_line = lines[content[1]] if len(content) > 1 else None
        if _is_intro(lines[content[0]], next_line):
            del lines[content[0]]

    # Несколько вариантов — остаётся первый. Только если ответ начинается
    # с «Вариант 1»: в посте-сравнении варианты — часть текста
    first = next((i for i, line in enumerate(lines) if line.strip()), len(lines))
    if first < len(lines) and _is_variant_1(lines[first]):
        variants = [i for i, line in enumerate(lines) if _VARIANT_RE.match(line)]
        end = variants[1] if len(variants) > 1 else len(lines)
        lines = lines[first + 1:end]

    # Метка «Пост:» или «Текст:» одна в первой строке с текстом
    first = next((i for i, line in enumerate(lines) if line.strip()), len(lines))
    if first < len(lines) and _POST_WORD_LABEL_RE.match(lines[first]):
        lines[first] = ''

    # Пояснения после поста — только в последнем абзаце, пока они там есть.
    # Без пустых строк последний абзац — последняя строка. Первая строка
    # с текстом не отрезается никогда
    first = next((i for i, line in enumerate(lines) if line.strip()), len(lines))
    while True:
        while lines and not lines[-1].strip():
            lines.pop()
        blank_lines = [i + 1 for i, line in enumerate(lines) if not line.strip() and i > first]
        paragraph_start = max(blank_lines[-1] if blank_lines else len(lines) - 1, first + 1)
        tail = _tail_start(lines, paragraph_start)
        if tail is None:
            break
        lines = lines[:tail]

    cleaned = []
    for line in lines:
        if _SEPARATOR_RE.match(line):
            continue
        line = _MARKDOWN_HEADER_RE.sub('', line)
        line = _LABEL_RE.sub('', line)
        if platform in PLATFORMS_WITHOUT_MARKDOWN:
            line = _BOLD_RE.sub(r'\1', line)
        cleaned.append(line)
    result = re.sub(r'\n{3,}', '\n\n', '\n'.join(cleaned)).strip()

    for open_quote, close_quote in _WRAPPING_QUOTES:
        if len(result) > 1 and result[0] == open_quote and result[-1] == close_quote:
            inner = result[1:-1]
            if open_quote not in inner and close_quote not in inner:
                result = inner.strip()
            break
    return result

def generate_text(data, user=None, token=None, generation_id=None):
    """
    Генерирует текст через GigaChat API
    
    Args:
        data: Параметры генерации
        user: Пользователь Django (опционально, для логирования)
        token: TemporaryAccessToken (опционально, для логирования)
        generation_id: ID генерации (опционально, для логирования)
    
    Returns:
        str: Сгенерированный текст
    """
    if _gigachat_limit_reached(token):
        return GIGACHAT_LIMIT_WARNING
    try:
        print("Инициализация клиента GigaChat для генерации текста...")
        giga = _init_client()
        print("Клиент успешно инициализирован")
        system_prompt = assemble_prompt_from_criteria(data)
        user_message = build_user_message(data)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]
        
        # Подготовка промпта для логирования
        full_prompt = f"{system_prompt}\n\n{user_message}"
        
        print("Отправка запроса на генерацию текста...")
        resp = giga.invoke(messages)
        print("Текст успешно сгенерирован")
        
        # --- Постобработка: убираем подписи и промежуточные этапы ---
        clean_result = postprocess_final_result(resp.content, data.get('platform'))

        # Учёт вызова (и пересёкшего лимит: текст уже оплачен квотой и отдаётся)
        _account_gigachat_call(
            token,
            estimate_tokens(full_prompt) + estimate_tokens(resp.content),
            operation_type='TEXT_GENERATION',
            prompt_text=full_prompt,
            response_text=resp.content,
            generation_id=generation_id,
            user=user,
            topic=data.get('topic'),
            platform=data.get('platform')
        )

        return clean_result
    except Exception as e:
        print(f"Ошибка при генерации текста: {e}")
        print(f"Тип ошибки: {type(e)}")
        if "429" in str(e) or "Too Many Requests" in str(e):
            return "WARNING: Превышен лимит запросов к GigaChat. Попробуйте позже."
        elif "401" in str(e) or "Unauthorized" in str(e):
            return "WARNING: Ошибка аутентификации. Проверьте настройки GigaChat."
        elif "403" in str(e) or "Forbidden" in str(e):
            return "WARNING: Доступ запрещен. Проверьте права доступа к GigaChat."
        else:
            return f"WARNING: Ошибка при генерации текста: {str(e)[:100]}"

def generate_image_prompt_from_text(text, form_data, user=None, token=None, generation_id=None):
    """
    Генерирует промпт для генератора изображения на основе сгенерированного текста поста и параметров формы.
    Возвращает строку-промпт для генерации иллюстрации.
    
    Args:
        text: Сгенерированный текст поста
        form_data: Параметры формы
        user: Пользователь Django (опционально, для логирования)
        token: TemporaryAccessToken (опционально, для логирования)
        generation_id: ID генерации (опционально, для логирования)
    
    Returns:
        str: Промпт для генерации изображения
    """
    if _gigachat_limit_reached(token):
        return None
    try:
        giga = _init_client()
        # Системный промпт для визуального генератора
        sys_prompt = (
            "Ты — креативный визуализатор. "
            "Проанализируй следующий текст поста для соцсетей и выдели ключевые визуальные образы, которые должны быть отражены на иллюстрации. "
            "Сформулируй короткий, ёмкий промпт для генерации изображения в стиле соцсетей. "
            "Учитывай платформу, аудиторию, стиль и цель поста."
        )
        # Собираем параметры для контекста
        platform = form_data.get('platform', '')
        audience = ', '.join(form_data.get('audience', [])) if form_data.get('audience') else ''
        style = ', '.join(form_data.get('delivery_style', [])) if form_data.get('delivery_style') else ''
        purpose = ', '.join(form_data.get('content_purpose', [])) if form_data.get('content_purpose') else ''
        # Формируем полный промпт
        user_prompt = (
            f"Текст поста: {text}\n"
            f"Платформа: {platform}\n"
            f"Аудитория: {audience}\n"
            f"Стиль: {style}\n"
            f"Цель: {purpose}"
        )
        full_prompt = f"{sys_prompt}\n\n{user_prompt}"
        
        messages = [
            SystemMessage(content=sys_prompt),
            HumanMessage(content=user_prompt)
        ]
        resp = giga.invoke(messages)
        result = resp.content.strip()

        # Учёт вызова (и пересёкшего лимит: промпт уже оплачен квотой и отдаётся)
        _account_gigachat_call(
            token,
            estimate_tokens(full_prompt) + estimate_tokens(resp.content),
            operation_type='IMAGE_PROMPT',
            prompt_text=full_prompt,
            response_text=resp.content,
            generation_id=generation_id,
            user=user,
            topic=form_data.get('topic'),
            platform=platform
        )

        return result
    except Exception as e:
        print(f"Ошибка при генерации промпта для изображения: {e}")
        return None

# Модифицированная функция генерации изображения

def generate_image_gigachat(image_prompt, user=None, token=None, generation_id=None):
    """
    Генерация изображения через GigaChat API по готовому промпту.
    
    Args:
        image_prompt: Промпт для генерации изображения
        user: Пользователь Django (опционально, для логирования)
        token: TemporaryAccessToken (опционально, для логирования)
        generation_id: ID генерации (опционально, для логирования)
    
    Returns:
        str: Base64 изображение или None
    """
    if _gigachat_limit_reached(token):
        return None
    try:
        print("Инициализация клиента GigaChat для генерации изображения...")
        giga = _init_direct_client()
        print("Клиент для изображений успешно инициализирован")
        time.sleep(1)
        
        system_message = "Ты — талантливый художник, специализирующийся на создании иллюстраций для социальных сетей"
        full_prompt = f"{system_message}\n\n{image_prompt}"
        
        payload = Chat(
            messages=[
                Messages(role=MessagesRole.SYSTEM, content=system_message),
                Messages(role=MessagesRole.USER, content=image_prompt)
            ],
            function_call="auto",
        )
        print("Отправка запроса на генерацию изображения...")
        last_error = None
        for attempt in range(3):
            try:
                response = giga.chat(payload)
                response_content = response.choices[0].message.content
                break
            except Exception as chat_err:
                last_error = chat_err
                err_str = str(chat_err)
                if ("429" in err_str or "Too Many Requests" in err_str) and attempt < 2:
                    wait_sec = 15 * (attempt + 1)
                    print(f"GigaChat 429 Too Many Requests, повтор через {wait_sec} с (попытка {attempt + 1}/3)")
                    time.sleep(wait_sec)
                else:
                    raise
        else:
            if last_error:
                raise last_error
            raise RuntimeError("Не удалось получить ответ GigaChat")
        print("GigaChat image response:", response_content)

        # Учёт вызова сразу после ответа: квота потрачена, даже если картинку
        # не удастся извлечь или скачать. Картинка, пересёкшая лимит, отдаётся
        _account_gigachat_call(
            token,
            estimate_tokens(full_prompt) + 1000,  # Примерная оценка для изображения
            operation_type='IMAGE_GENERATION',
            prompt_text=full_prompt,
            response_text=str(response_content)[:500],  # Ограничиваем для логирования
            generation_id=generation_id,
            user=user
        )

        # Если ответ уже содержит готовое base64 изображение, возвращаем его напрямую
        if isinstance(response_content, str) and response_content.strip().startswith("data:image"):
            print("Получено готовое base64 изображение от GigaChat")
            return response_content.strip()

        file_id = extract_image_id(response_content)
        if file_id:
            return download_image(giga, file_id)
        else:
            print("Не удалось извлечь ID изображения из ответа")
            return None
    except Exception as e:
        print(f"Ошибка при генерации изображения через GigaChat: {e}")
        print(f"Тип ошибки: {type(e)}")
        if "429" in str(e) or "Too Many Requests" in str(e):
            print("Превышен лимит запросов к GigaChat")
        elif "401" in str(e) or "Unauthorized" in str(e):
            print("Ошибка аутентификации GigaChat")
        elif "403" in str(e) or "Forbidden" in str(e):
            print("Доступ запрещен к GigaChat")
        return None

def extract_image_id(response_content):
    """Извлекает ID изображения из HTML-ответа GigaChat"""
    try:
        # 0. Если ответ уже содержит data:image -> возврат целиком
        if isinstance(response_content, str) and response_content.strip().startswith("data:image"):
            print("Ответ уже содержит data:image — возвращаем как есть")
            return response_content.strip()
        
        # 0.1 Если это длинная base64 строка без префикса
        base64_candidate = response_content.strip().replace("\n", "")
        if len(base64_candidate) > 1000 and re.fullmatch(r'[A-Za-z0-9+/=]+', base64_candidate):
            print("Ответ выглядит как чистая base64 строка — возвращаем с префиксом")
            return f"data:image/jpeg;base64,{base64_candidate}"
        
        # Парсим HTML с помощью BeautifulSoup
        soup = BeautifulSoup(response_content, "html.parser")
        img_tag = soup.find('img')
        
        if img_tag and img_tag.get('src'):
            file_id = img_tag.get('src')
            print(f"Извлечен ID изображения: {file_id}")
            return file_id
        else:
            # 1. Поиск тега <img src="...">
            match = re.search(r'<img[^>]*src="([^"]+)"', response_content)
            if match:
                file_id = match.group(1)
                print(f"Извлечен ID изображения (regex img): {file_id}")
                return file_id
            
            # 2. Поиск markdown вида ![alt](file_id)
            match_md = re.search(r'!\[[^\]]*\]\(([^)]+)\)', response_content)
            if match_md:
                file_id = match_md.group(1)
                print(f"Извлечен ID изображения (markdown): {file_id}")
                return file_id
            
            # 3. Поиск UUID в тексте
            match_uuid = re.search(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', response_content)
            if match_uuid:
                file_id = match_uuid.group(0)
                print(f"Извлечен ID изображения (uuid): {file_id}")
                return file_id
        
        # 4. Поиск JSON-подобного "fileId":"..." или "file_id":"..."
        match_json = re.search(r'"(?:fileId|file_id)"\s*:\s*"([^"]+)"', response_content)
        if match_json:
            file_id = match_json.group(1)
            print(f"Извлечен ID изображения (json): {file_id}")
            return file_id
        
        # 5. Поиск первой http/https ссылки
        match_http = re.search(r'(https?://[^\s"\'<>]+)', response_content)
        if match_http:
            file_id = match_http.group(1)
            print(f"Извлечен ID изображения (http): {file_id}")
            return file_id
        
        print("Не найден тег img в ответе")
        return None
        
    except Exception as e:
        print(f"Ошибка при извлечении ID изображения: {e}")
        return None

def download_image(giga_client, file_id):
    """Скачивает изображение по ID и возвращает base64 данные"""
    try:
        # Если пришла уже готовая строка data:image — вернуть сразу
        if isinstance(file_id, str) and file_id.startswith("data:image"):
            print("file_id уже является data:image — возвращаем")
            return file_id
        
        # Если это ссылка http/https — скачать напрямую без авторизации
        if isinstance(file_id, str) and file_id.startswith("http"):
            print("file_id является полной ссылкой — скачиваем через requests")
            import requests, base64
            try:
                resp = requests.get(file_id, timeout=20, verify=False)
                if resp.status_code == 200:
                    image_base64 = base64.b64encode(resp.content).decode('utf-8')
                    return f"data:image/jpeg;base64,{image_base64}"
                else:
                    print(f"Не удалось скачать изображение по ссылке, код: {resp.status_code}")
            except Exception as ex:
                print(f"Ошибка скачивания по ссылке: {ex}")
        
        image_response = giga_client.get_image(file_id)
        print(f"get_image вернул: type={type(image_response)}, has content={getattr(image_response, 'content', 'N/A') is not None if image_response else False}")

        if image_response and hasattr(image_response, 'content'):
            content = image_response.content
            print(f"content: type={type(content)}, len={len(content) if content is not None else 0}")

            try:
                # Проверяем тип content и обрабатываем соответственно
                if isinstance(content, str):
                    if content.startswith('data:image'):
                        print("Изображение получено от GigaChat (str data:image)")
                        return content
                    if len(content) > 1000:
                        print(f"Изображение получено от GigaChat (str), размер: {len(content)}")
                        return f"data:image/jpeg;base64,{content}"
                    print(f"Строка content слишком короткая: {len(content)}")
                    return None
                if isinstance(content, bytes):
                    import base64
                    image_base64 = base64.b64encode(content).decode('utf-8')
                    print(f"Изображение получено от GigaChat (bytes), размер base64: {len(image_base64)}")
                    return f"data:image/jpeg;base64,{image_base64}"
                # Возможно content — dict/list (ответ API в другом формате)
                if hasattr(content, '__iter__') and not isinstance(content, (str, bytes)):
                    print(f"content итерируемый, не str/bytes: {type(content)}")
                else:
                    print(f"Неизвестный тип content: {type(content)}")
                return None
            except Exception as e:
                print(f"Ошибка при обработке content: {e}")
                import traceback
                traceback.print_exc()
                return None
        else:
            print("Пустой ответ при скачивании изображения или нет атрибута content")
            return None
            
    except Exception as e:
        print(f"Ошибка при скачивании изображения: {e}")
        import traceback
        traceback.print_exc()
        
        # Попробуем альтернативный способ через requests
        try:
            print("Пробуем альтернативный способ через requests...")
            import requests
            from gigachat.client import GigaChat
            
            # Получаем токен доступа
            auth_response = requests.post(
                "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
                headers={
                    "Authorization": f"Bearer {_get_base64_credentials()}",
                    "RqUID": "123456789",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={"scope": SCOPE},
                verify=False
            )
            
            if auth_response.status_code == 200:
                access_token = auth_response.json().get("access_token")
                
                # Скачиваем изображение напрямую
                image_url = f"https://gigachat.devices.sberbank.ru/api/v1/files/{file_id}/content"
                headers = {"Authorization": f"Bearer {access_token}"}
                
                img_response = requests.get(image_url, headers=headers, verify=False)
                
                if img_response.status_code == 200:
                    import base64
                    image_base64 = base64.b64encode(img_response.content).decode('utf-8')
                    result = f"data:image/jpeg;base64,{image_base64}"
                    print(f"Альтернативный способ успешен, длина: {len(image_base64)}")
                    return result
                else:
                    print(f"Ошибка при скачивании через requests: {img_response.status_code}")
                    return None
            else:
                print(f"Ошибка аутентификации: {auth_response.status_code}")
                return None
                
        except Exception as alt_e:
            print(f"Альтернативный способ также не сработал: {alt_e}")
            return None
