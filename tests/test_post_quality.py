"""
Тесты фазы 2: форма и качество поста

Проверяют:
- форму: обязательные тема и площадка (VK, Telegram, Дзен), лимиты длины,
  необязательное «О бизнесе», значения по умолчанию для 12 настроек;
- сообщения к GigaChat: системный промпт со стоп-листом и правилами площадки,
  пользовательское сообщение с площадкой, темой и «О бизнесе»;
- «О бизнесе» в сессии;
- перегенерацию с теми же данными, что у первой генерации;
- постобработку ответа под новый формат;
- поиск штампов из стоп-листа;
- разметку формы генератора.

GigaChat — фейковый клиент (tests.helpers.fake_gigachat): работает настоящий
код gigachat_api, а тесты видят сообщения, которые ушли бы в GigaChat.
"""

import json
import re
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.sessions.middleware import SessionMiddleware
from gigachat.client import GIGACHAT_MODEL as GIGACHAT_LIBRARY_MODEL
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.utils.html import escape

from generator.access import check_gigachat_access
from generator.forms import (
    DEFAULT_SETTINGS,
    PLATFORM_CHOICES,
    PLATFORM_DEFAULT_SETTINGS,
    SETTING_FIELDS,
    GenerationForm,
)
from generator import gigachat_api
from generator.gigachat_api import (
    PLATFORM_RULES,
    POST_LENGTH_RANGES,
    SETTING_PROMPTS,
    STOP_PHRASES,
    SYSTEM_PROMPT_OUTPUT,
    assemble_prompt_from_criteria,
    find_stop_phrases,
    postprocess_final_result,
)
from generator.models import Generation, GigaChatTokenUsage, TemporaryAccessToken
from generator.views import MSG_NOTHING_TO_REGENERATE
from tests import runner
from tests.helpers import fake_gigachat

AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}

PLATFORMS = ('VK', 'Telegram', 'Дзен')
TOPIC = 'Осеннее меню: тыквенный латте и пирог с яблоками'
BUSINESS_INFO = 'Кофейня у метро, варим на зерне местной обжарки, пишем на «ты», без пафоса'

# Штампы из промпта фазы 2 — стоп-лист должен находить каждый
REQUIRED_STAMPS = (
    'Выведите свой бизнес на новый уровень!',
    'Выведите бизнес на новый уровень вместе с нами',
    'В современном мире без этого никуда',
    'В наше время кофе пьют все',
    'Это идеальное решение для занятых',
    'У вас есть уникальная возможность попробовать',
    'Не упустите шанс!',
    'Инновационный подход к маникюру',
    'Безграничные возможности для творчества',
    'Хотите узнать больше? Пишите!',
)

# Пробы ревью фазы 2 (замечание 1): обычный текст поста, похожий на служебные
# строки. Постобработка возвращает его целиком
REVIEW_PROBES = {
    'финальный результат в тексте': (
        'Осенний уход за волосами',
        'Сухие кончики — частая история после лета.',
        'Финальный результат зависит от домашнего ухода: маска раз в неделю.',
        'А как вы ухаживаете за волосами?',
    ),
    'этот текст — для тех': (
        'Чем хлеб на закваске отличается от обычного',
        'Этот текст — для тех, кто выбирает хлеб в магазине и читает состав.',
        'Закваска — это живая культура.',
        'А вы какой хлеб берёте?',
    ),
    'надеюсь, этот совет': (
        'Ноутбук греется и шумит?',
        'Скорее всего, пора на чистку.',
        'Надеюсь, этот совет сбережёт ваш ноутбук. Как давно вы его чистили?',
    ),
    'поступил во вступлении': (
        'Вот и поступил в меню наш осенний раф:',
        'облепиха, мёд и немного корицы.',
        'Заходи попробовать!',
    ),
    'агентство недвижимости': (
        'Ищете квартиру?',
        'Агентство недвижимости: такие вопросы решаем за день.',
        'Пишите в сообщения.',
    ),
    'пост-сравнение с вариантами': (
        'Летняя или зимняя?',
        'Вариант 1:',
        'Липучка — для города.',
        'Вариант 2:',
        'Шипы — для трассы.',
        'Какую выбираете?',
    ),
}

# Пробы повторного ревью фазы 2 (замечание 3): редкие формулировки обычного
# поста, которые постобработка срезала. Возвращаются целиком
REVIEW_2_PROBES = {
    'несколько вариантов во вступлении': (
        'Вот несколько вариантов осеннего ухода:\n'
        '— маска раз в неделю;\n'
        '— масло на кончики перед сном.\n\n'
        'А как вы ухаживаете за волосами?'
    ),
    'вариант завтрака во вступлении': (
        'Вот вариант завтрака для тех, кто спешит:\n'
        'сырник и капучино с собой.\n\n'
        'Что берёте утром?'
    ),
    'варианты на любой вкус': (
        'Хорошо, когда есть варианты на любой вкус:\n'
        'раф, флэт уайт и какао.\n\n'
        'Что выберешь?'
    ),
    'ответ без пустых строк': (
        'Хлеб на закваске\n'
        'Этот текст написан для тех, кто выбирает хлеб в магазине.\n'
        'Закваска — живая культура.\n'
        'А вы какой хлеб берёте?'
    ),
    'ответ без пустых строк и без вопроса': (
        'Хлеб на закваске\n'
        'Этот текст написан для тех, кто выбирает хлеб в магазине.\n'
        'Закваска — живая культура.\n'
        'По субботам продаём его на рынке.'
    ),
    'финальный результат отдельной строкой': (
        'Было: сухие кончики.\n'
        'Финальный результат:\n'
        'блестящие волосы и мягкие кончики.\n\n'
        'Записывайтесь на уход!'
    ),
    'заголовок Дзена «Пост:»': (
        'Пост: какой хлеб можно есть\n\n'
        'В пост многие отказываются от сдобы, но хлеб на закваске остаётся.\n\n'
        'А вы держите пост?'
    ),
    '«Пост:» и «Текст:» внутри поста': (
        'Великий пост и выпечка\n\n'
        'Пост: время, когда многие выбирают постный хлеб.\n'
        'Текст: ржаная мука, вода, соль и закваска.'
    ),
    'надеюсь, этот пост — с вопросом читателям': (
        'Облепиховый раф и тыквенный латте — оба уже в меню.\n\n'
        'Надеюсь, этот пост поможет выбрать напиток. А вы какой берёте?'
    ),
}


def try_demo():
    """Новый клиент нажимает «Попробовать» и получает демо-токен"""
    client = Client()
    client.post('/try/')
    return client


def generate(client, data):
    """POST в генератор с фейковым GigaChat; возвращает (ответ, фейк)"""
    with fake_gigachat() as fake:
        response = client.post('/generator/', data, **AJAX)
    return response, fake


def messages_of(fake, index=0):
    """(системный промпт, пользовательское сообщение) обращения index к фейку"""
    system, human = fake.invoke_messages[index]
    return system.content, human.content


def all_choice_values(field_name):
    return [value for value, _ in GenerationForm().fields[field_name].choices if value]


class GenerationFormTests(SimpleTestCase):
    """Форма: тема и площадка обязательны, ввод ограничен по длине"""

    def form(self, **data):
        return GenerationForm(data=data)

    def test_topic_and_platform_enough(self):
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                form = self.form(topic=TOPIC, platform=platform)
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.cleaned_data['platform'], platform)
                self.assertEqual(form.cleaned_data['business_info'], '')

    def test_topic_required(self):
        for topic in ('', '   '):
            with self.subTest(topic=topic):
                form = self.form(topic=topic, platform='VK')
                self.assertFalse(form.is_valid())
                self.assertIn('topic', form.errors)

    def test_platform_required(self):
        form = self.form(topic=TOPIC)
        self.assertFalse(form.is_valid())
        self.assertIn('platform', form.errors)

    def test_platform_outside_choices(self):
        for platform in ('Instagram', 'TikTok', 'Facebook', 'LinkedIn', 'Twitter', 'vk', 'Одноклассники'):
            with self.subTest(platform=platform):
                form = self.form(topic=TOPIC, platform=platform)
                self.assertFalse(form.is_valid())
                self.assertIn('platform', form.errors)

    def test_platform_choices(self):
        self.assertEqual([value for value, _ in PLATFORM_CHOICES], list(PLATFORMS))
        fields = GenerationForm().fields
        self.assertEqual([value for value, _ in fields['platform'].choices], list(PLATFORMS))
        self.assertNotIn('platform_specific', fields)

    @override_settings(GENERATION_MAX_TOPIC_LENGTH=50)
    def test_topic_length_limit(self):
        self.assertTrue(self.form(topic='т' * 50, platform='VK').is_valid())

        form = self.form(topic='т' * 51, platform='VK')
        self.assertFalse(form.is_valid())
        self.assertIn('topic', form.errors)

    @override_settings(GENERATION_MAX_BUSINESS_INFO_LENGTH=40)
    def test_business_info_length_limit(self):
        self.assertTrue(self.form(topic=TOPIC, platform='VK', business_info='б' * 40).is_valid())

        form = self.form(topic=TOPIC, platform='VK', business_info='б' * 41)
        self.assertFalse(form.is_valid())
        self.assertIn('business_info', form.errors)

    def test_settings_lengths_come_from_settings(self):
        """Лимиты длины формы — те же настройки, что в check_gigachat_access"""
        with override_settings(GENERATION_MAX_TOPIC_LENGTH=7, GENERATION_MAX_BUSINESS_INFO_LENGTH=9):
            fields = GenerationForm().fields
            self.assertEqual(fields['topic'].max_length, 7)
            self.assertEqual(fields['business_info'].max_length, 9)
            self.assertEqual(fields['topic'].widget.attrs['maxlength'], '7')
            self.assertEqual(fields['business_info'].widget.attrs['maxlength'], '9')


class DefaultSettingsTests(TestCase):
    """Пустые настройки получают значения по умолчанию на сервере"""

    def test_defaults_cover_all_settings(self):
        self.assertEqual(len(SETTING_FIELDS), 12)
        self.assertEqual(set(SETTING_PROMPTS), set(SETTING_FIELDS))
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                defaults = {**DEFAULT_SETTINGS, **PLATFORM_DEFAULT_SETTINGS[platform]}
                self.assertEqual(set(defaults), set(SETTING_FIELDS))

    def test_defaults_are_valid_choices_with_prompts(self):
        """Каждое значение по умолчанию — допустимый выбор и даёт фразу в промпте"""
        values = [(name, value) for name, value in DEFAULT_SETTINGS.items()]
        for platform_defaults in PLATFORM_DEFAULT_SETTINGS.values():
            values += list(platform_defaults.items())
        for name, value in values:
            for item in (value if isinstance(value, list) else [value]):
                with self.subTest(field=name, value=item):
                    self.assertIn(item, all_choice_values(name))
                    self.assertIn(item, SETTING_PROMPTS[name])

    def test_empty_settings_get_defaults(self):
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                form = GenerationForm(data={'topic': TOPIC, 'platform': platform})
                self.assertTrue(form.is_valid(), form.errors)
                expected = {**DEFAULT_SETTINGS, **PLATFORM_DEFAULT_SETTINGS[platform]}
                for name, value in expected.items():
                    self.assertEqual(form.cleaned_data[name], value, name)

    def test_explicit_settings_kept(self):
        form = GenerationForm(data={
            'topic': TOPIC,
            'platform': 'Telegram',
            'voice_tone': ['Юмористический'],
            'post_length': 'Длинный',
            'cta': 'Купить',
        })
        self.assertTrue(form.is_valid(), form.errors)

        self.assertEqual(form.cleaned_data['voice_tone'], ['Юмористический'])
        self.assertEqual(form.cleaned_data['post_length'], 'Длинный')
        self.assertEqual(form.cleaned_data['cta'], 'Купить')
        self.assertEqual(form.cleaned_data['audience'], DEFAULT_SETTINGS['audience'])
        self.assertEqual(form.cleaned_data['hashtag_usage'],
                         PLATFORM_DEFAULT_SETTINGS['Telegram']['hashtag_usage'])

    def test_defaults_not_shared_between_forms(self):
        """Изменение списка в одной форме не меняет значения по умолчанию"""
        form = GenerationForm(data={'topic': TOPIC, 'platform': 'VK'})
        self.assertTrue(form.is_valid())
        form.cleaned_data['voice_tone'].append('Юмористический')

        self.assertNotIn('Юмористический', DEFAULT_SETTINGS['voice_tone'])

    @override_settings(DEMO_TOKENS_PER_IP_PER_DAY=1000)
    def test_defaults_reach_system_prompt(self):
        """Генерация с одной темой и площадкой: в промпте фразы всех 12 настроек по умолчанию"""
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                response, fake = generate(try_demo(), {'topic': TOPIC, 'platform': platform})
                self.assertTrue(response.json()['success'], response.json())

                system, _ = messages_of(fake)
                defaults = {**DEFAULT_SETTINGS, **PLATFORM_DEFAULT_SETTINGS[platform]}
                for name, value in defaults.items():
                    for item in (value if isinstance(value, list) else [value]):
                        self.assertIn(SETTING_PROMPTS[name][item], system, f'{name}={item}')


@override_settings(DEMO_TOKENS_PER_IP_PER_DAY=1000)
class GigaChatMessagesTests(TestCase):
    """Сообщения к GigaChat при генерации через форму"""

    def messages(self, **data):
        response, fake = generate(try_demo(), data)
        self.assertTrue(response.json()['success'], response.json())
        self.assertEqual(fake.invoke_calls, 1)
        return messages_of(fake)

    def test_system_prompt_has_stop_list(self):
        system, _ = self.messages(topic=TOPIC, platform='VK')

        for phrase in STOP_PHRASES:
            self.assertIn(phrase, system)
        self.assertIn('штамп', system.lower())

    def test_system_prompt_has_rules_of_selected_platform_only(self):
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                system, _ = self.messages(topic=TOPIC, platform=platform)

                for rule in PLATFORM_RULES[platform]['rules']:
                    self.assertIn(rule, system)
                for other in set(PLATFORMS) - {platform}:
                    for rule in PLATFORM_RULES[other]['rules']:
                        self.assertNotIn(rule, system)

    def test_platform_rules_cover_format(self):
        """Правила площадок: абзацы, эмодзи, разметка; заголовок — только у Дзена"""
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                rules = ' '.join(PLATFORM_RULES[platform]['rules']).lower()
                self.assertIn('абзац', rules)
                self.assertIn('эмодзи', rules)
        self.assertIn('заголов', ' '.join(PLATFORM_RULES['Дзен']['rules']).lower())

    def test_user_message_has_platform_topic_business_info(self):
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                _, human = self.messages(topic=TOPIC, platform=platform, business_info=BUSINESS_INFO)

                self.assertIn(f"Площадка: {PLATFORM_RULES[platform]['label']}", human)
                self.assertIn(f'Тема: {TOPIC}', human)
                self.assertIn(f'О бизнесе: {BUSINESS_INFO}', human)

    def test_user_message_reminds_facts_only_from_input(self):
        """Напоминание не выдумывать — и в сообщении пользователя; у Дзена — ещё заголовок и без эмодзи"""
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                _, human = self.messages(topic=TOPIC, platform=platform)

                last_lines = human.splitlines()[-2:]
                reminder = next((line for line in last_lines if 'не придумывай' in line), '')
                for word in ('названия', 'бренды', 'книги', 'сайты', 'цены', 'сроки', 'обещания'):
                    self.assertIn(word, reminder)
                if platform == 'Дзен':
                    self.assertIn('заголовок', human.lower())
                    self.assertIn('эмодзи', human.lower())
                else:
                    # Нормы эмодзи теперь в сообщении у всех площадок (п. D раунда 2),
                    # заголовок — только у Дзена
                    self.assertNotIn('заголов', human.lower())

    def test_user_message_reminds_stop_phrases(self):
        """В конце сообщения пользователя — запрет штампов из STOP_PHRASES (решение владельца, п. 1)"""
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                _, human = self.messages(topic=TOPIC, platform=platform, business_info=BUSINESS_INFO)

                lines = human.splitlines()
                reminder = next((line for line in lines if 'штамп' in line.lower()), '')
                self.assertIn('перефраз', reminder.lower())
                for phrase in STOP_PHRASES:
                    self.assertIn(f'«{phrase}»', reminder)
                self.assertIn('без метафор', reminder)
                self.assertGreater(lines.index(reminder), lines.index(f'О бизнесе: {BUSINESS_INFO}'))

    def test_system_prompt_forbids_health_promises_and_metaphors(self):
        """Прогон раунда 2: модель обещала пользу для здоровья и писала метафорами («осень стучится»)"""
        system, _ = self.messages(topic=TOPIC, platform='VK')

        promises = next((line for line in system.splitlines() if line.startswith('- Не обещай')), '')
        self.assertIn('пользу для здоровья', promises)
        self.assertIn('без метафор', system)

    # Нормы площадок при значениях по умолчанию (решение владельца, п. 4:
    # нормы не меняются): длина, хэштеги, эмодзи
    NORMS = {
        'VK': ('600–1200 знаков', 'не короче 600 знаков', 'в последней строке — 1–3 хэштега',
               'эмодзи — 1–3 на весь пост'),
        'Telegram': ('300–600 знаков', 'не короче 300 знаков', 'хэштеги не ставь',
                     'эмодзи — не больше 2 на весь пост'),
        'Дзен': ('1500–2500 знаков', 'не короче 1500 знаков', 'хэштеги не ставь', 'без эмодзи, даже в списках'),
    }

    def norm_line(self, human):
        """Строка напоминания о длине, хэштегах и эмодзи"""
        lines = human.splitlines()
        reminder = next((line for line in lines if 'знаков' in line or 'предложения' in line), '')
        self.assertTrue(reminder, 'нет напоминания о длине')
        self.assertGreater(lines.index(reminder), next(i for i, line in enumerate(lines) if line.startswith('Тема:')))
        return reminder.lower()

    def test_user_message_reminds_platform_norms(self):
        """Длина, хэштеги и эмодзи площадки — в сообщении пользователя, числа те же, что в системном промпте"""
        for platform, norms in self.NORMS.items():
            with self.subTest(platform=platform):
                system, human = self.messages(topic=TOPIC, platform=platform)

                reminder = self.norm_line(human)
                for norm in norms:
                    self.assertIn(norm, reminder)
                defaults = PLATFORM_DEFAULT_SETTINGS[platform]
                low, high = POST_LENGTH_RANGES[defaults['post_length']]
                self.assertIn(f'{low}–{high} знаков', reminder)
                for name in ('post_length', 'hashtag_usage'):
                    phrase = SETTING_PROMPTS[name][defaults[name]]
                    self.assertIn(phrase, system)
                    self.assertIn(phrase.lower(), reminder)

    def test_user_message_platform_structure(self):
        """Дзен — заголовок и структура статьи, Telegram — главное в первой строке"""
        _, human = self.messages(topic=TOPIC, platform='Дзен')
        reminder = self.norm_line(human)
        self.assertIn('первая строка — заголовок', reminder)
        self.assertIn('вступление, 2–4 смысловых блока и короткий вывод', reminder)

        _, human = self.messages(topic=TOPIC, platform='Telegram')
        self.assertIn('главное — в первой строке', self.norm_line(human))

    def test_user_message_norms_follow_settings(self):
        """Выбранные длина и хэштеги меняют напоминание"""
        _, human = self.messages(topic=TOPIC, platform='VK', post_length='Длинный', hashtag_usage='Оптимально')
        reminder = self.norm_line(human)
        self.assertIn('1500–2500 знаков', reminder)
        self.assertIn('не короче 1500 знаков', reminder)
        self.assertNotIn('600–1200', reminder)
        self.assertIn('4–10 хэштегов', reminder)
        self.assertNotIn('1–3 хэштега', reminder)

        _, human = self.messages(topic=TOPIC, platform='Telegram', post_length='Очень короткий')
        reminder = self.norm_line(human)
        self.assertIn('одно-два предложения', reminder)
        self.assertNotIn('300–600', reminder)

    def test_user_message_without_business_info(self):
        _, human = self.messages(topic=TOPIC, platform='Telegram')

        self.assertNotIn('О бизнесе', human)
        self.assertIn(f'Тема: {TOPIC}', human)

    def test_no_empty_placeholders(self):
        """Нет «Напиши  пост для .»: каждая строка сообщения заполнена"""
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                system, human = self.messages(topic=TOPIC, platform=platform)

                self.assertNotRegex(human, r'для\s*[.,:]')
                self.assertNotIn('  ', human)
                for line in human.splitlines():
                    self.assertNotRegex(line, r':\s*$')
                self.assertNotIn('[', system)

    def test_system_prompt_without_old_preamble(self):
        """Ни SEO, ни запрещённых площадок, ни агентов — даже при всех выбранных настройках"""
        everything = {name: all_choice_values(name) for name in SETTING_FIELDS}
        prompts = [assemble_prompt_from_criteria(dict(everything, platform=p)) for p in PLATFORMS]
        prompts.append(self.messages(topic=TOPIC, platform='VK')[0])

        for system in prompts:
            for banned in ('seo', 'instagram', 'tiktok', 'linkedin', 'facebook', 'twitter',
                           'агент', 'круг', 'финальн', r'\[ \]'):
                self.assertIsNone(re.search(rf'(?<!\w){banned}', system, re.IGNORECASE), banned)

    def test_system_prompt_forbids_invented_facts(self):
        """Запрет выдумывать цены, скидки, адреса и акции — одной строкой правил, для каждой площадки"""
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                system, _ = self.messages(topic=TOPIC, platform=platform)

                bans = [line for line in system.splitlines()
                        if 'не выдумывай' in line.lower()
                        and all(word in line for word in ('цены', 'скидки', 'адреса', 'акции'))]
                self.assertEqual(len(bans), 1, 'нет строки с запретом выдумывать факты')

    def test_system_prompt_requires_only_post_text(self):
        """Требование отвечать только текстом поста — в конце системного промпта"""
        for keywords in ('только готовый текст поста', 'без вступления', 'без пояснений', 'вариантов'):
            self.assertIn(keywords, SYSTEM_PROMPT_OUTPUT)
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                system, _ = self.messages(topic=TOPIC, platform=platform)

                self.assertTrue(system.endswith(SYSTEM_PROMPT_OUTPUT))

    def test_bold_removed_in_generated_post_for_platform(self):
        """Генерация через форму: ** снимаются во ВКонтакте и Дзене, в Telegram остаются"""
        answer = '**Новинка недели**\n\nТыквенный латте уже в меню.'
        for platform, expected in (('VK', 'Новинка недели\n\nТыквенный латте уже в меню.'),
                                   ('Дзен', 'Новинка недели\n\nТыквенный латте уже в меню.'),
                                   ('Telegram', answer)):
            with self.subTest(platform=platform):
                client = try_demo()
                with fake_gigachat() as fake:
                    fake.TEXT = answer
                    response = client.post('/generator/', {'topic': TOPIC, 'platform': platform}, **AJAX)
                self.assertTrue(response.json()['success'], response.json())
                self.assertEqual(response.json()['result'], expected)

    def test_setting_phrases_without_stamps(self):
        """Фразы настроек сами не содержат штампов из стоп-листа"""
        for name, prompts in SETTING_PROMPTS.items():
            for value, phrase in prompts.items():
                with self.subTest(field=name, value=value):
                    self.assertEqual(find_stop_phrases(phrase), [])


@override_settings(DEMO_TOKENS_PER_IP_PER_DAY=1000)
class BusinessInfoSessionTests(TestCase):
    """«О бизнесе» сохраняется в сессии и подставляется в форму"""

    def business_info_field(self, client):
        response = client.get('/generator/')
        self.assertEqual(response.status_code, 200)
        match = re.search(r'<textarea[^>]*name="business_info"[^>]*>(.*?)</textarea>',
                          response.content.decode(), re.S)
        self.assertIsNotNone(match, 'нет поля «О бизнесе»')
        return match.group(1).strip()

    def test_new_session_has_empty_field(self):
        self.assertEqual(self.business_info_field(try_demo()), '')

    def test_saved_and_prefilled(self):
        client = try_demo()

        response, _ = generate(client, {'topic': TOPIC, 'platform': 'VK', 'business_info': BUSINESS_INFO})

        self.assertTrue(response.json()['success'])
        self.assertEqual(client.session['business_info'], BUSINESS_INFO)
        self.assertEqual(self.business_info_field(client), escape(BUSINESS_INFO))

    def test_empty_value_clears_session(self):
        client = try_demo()
        generate(client, {'topic': TOPIC, 'platform': 'VK', 'business_info': BUSINESS_INFO})

        response, _ = generate(client, {'topic': TOPIC, 'platform': 'VK', 'business_info': ''})

        self.assertTrue(response.json()['success'])
        self.assertNotIn('business_info', client.session)
        self.assertEqual(self.business_info_field(client), '')

    def test_invalid_form_keeps_session(self):
        client = try_demo()
        generate(client, {'topic': TOPIC, 'platform': 'VK', 'business_info': BUSINESS_INFO})

        response, fake = generate(client, {'topic': TOPIC, 'business_info': 'Другой бизнес'})

        self.assertFalse(response.json()['success'])
        self.assertEqual(fake.calls, 0)
        self.assertEqual(client.session['business_info'], BUSINESS_INFO)


@override_settings(DEMO_TOKENS_PER_IP_PER_DAY=1000)
class RegenerateTextTests(TestCase):
    """Перегенерация строит сообщение из last_form_data, как первая генерация"""

    FIRST = {
        'topic': TOPIC,
        'platform': 'Дзен',
        'business_info': BUSINESS_INFO,
        'voice_tone': ['Юмористический'],
    }

    def first_then_regenerate(self, regenerate_data=None):
        client = try_demo()
        with fake_gigachat() as fake:
            first = client.post('/generator/', self.FIRST, **AJAX)
            second = client.post('/regenerate-text/', regenerate_data or {}, **AJAX)
        self.assertTrue(first.json()['success'], first.json())
        self.assertTrue(second.json()['success'], second.json())
        self.assertEqual(fake.invoke_calls, 2)
        return fake

    def test_same_messages_as_first_generation(self):
        fake = self.first_then_regenerate()

        self.assertEqual(messages_of(fake, 1), messages_of(fake, 0))
        system, human = messages_of(fake, 1)
        self.assertIn(f"Площадка: {PLATFORM_RULES['Дзен']['label']}", human)
        self.assertIn(f'О бизнесе: {BUSINESS_INFO}', human)
        self.assertIn(SETTING_PROMPTS['voice_tone']['Юмористический'], system)
        for rule in PLATFORM_RULES['Дзен']['rules']:
            self.assertIn(rule, system)

    def test_post_topic_does_not_replace_last_form_data(self):
        """Перегенерация повторяет последнюю генерацию: тема из POST не подменяет её"""
        fake = self.first_then_regenerate({'topic': 'Совсем другая тема'})

        self.assertEqual(messages_of(fake, 1), messages_of(fake, 0))

    def assert_nothing_to_regenerate(self, client):
        with fake_gigachat() as fake:
            response = client.post('/regenerate-text/', {'topic': TOPIC}, **AJAX)

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], MSG_NOTHING_TO_REGENERATE)
        self.assertEqual(fake.calls, 0)
        self.assertEqual(GigaChatTokenUsage.objects.count(), 0)
        self.assertEqual(Generation.objects.count(), 0)

    def test_without_last_form_data(self):
        self.assert_nothing_to_regenerate(try_demo())

    def test_last_form_data_without_platform(self):
        """Данные старого формата (до фазы 2, без площадки) не перегенерируются"""
        client = try_demo()
        session = client.session
        session['last_form_data'] = {'topic': TOPIC, 'platform_specific': ['VK', 'Instagram']}
        session.save()

        self.assert_nothing_to_regenerate(client)

    @override_settings(GENERATION_MAX_BUSINESS_INFO_LENGTH=10)
    def test_long_business_info_in_session_denied(self):
        """Длину «О бизнесе» из сессии проверяет check_gigachat_access"""
        client = try_demo()
        session = client.session
        session['last_form_data'] = {'topic': TOPIC, 'platform': 'VK', 'business_info': 'б' * 11}
        session.save()

        with fake_gigachat() as fake:
            response = client.post('/regenerate-text/', {}, **AJAX)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
        self.assertEqual(fake.calls, 0)


class BusinessInfoAccessTests(TestCase):
    """check_gigachat_access проверяет длину «О бизнесе»"""

    def make_request(self):
        token = TemporaryAccessToken.objects.create(
            token_type='DEMO_FREE', gigachat_tokens_limit=5000, openai_tokens_limit=0,
        )
        request = RequestFactory().post('/generator/', **AJAX)
        SessionMiddleware(lambda r: None).process_request(request)
        request.session['access_token'] = str(token.token)
        return request

    @override_settings(GENERATION_MAX_BUSINESS_INFO_LENGTH=20)
    def test_business_info_too_long(self):
        request = self.make_request()

        response = check_gigachat_access(request, topic=TOPIC, business_info='б' * 21)

        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('20', data['error'])
        self.assertFalse(hasattr(request, 'token'))

    @override_settings(GENERATION_MAX_BUSINESS_INFO_LENGTH=20)
    def test_business_info_at_limit(self):
        request = self.make_request()

        self.assertIsNone(check_gigachat_access(request, topic=TOPIC, business_info='б' * 20))


class PostprocessTests(SimpleTestCase):
    """Постобработка: только текст поста, жирный текст Telegram сохраняется"""

    POST = (
        'Осень пришла — и с ней **тыквенный латте**.\n'
        '\n'
        'Варим на зерне местной обжарки, пирог с яблоками печём каждое утро.\n'
        '\n'
        'А вы уже пробовали?'
    )

    def test_plain_post_unchanged(self):
        self.assertEqual(postprocess_final_result(self.POST), self.POST)

    def test_label_line_removed(self):
        for label in ('Текст поста:', '**Текст поста:**', '**Текст поста**:', 'Пост:'):
            with self.subTest(label=label):
                self.assertEqual(postprocess_final_result(f'{label}\n\n{self.POST}'), self.POST)

    def test_inline_label_removed(self):
        self.assertEqual(postprocess_final_result(f'**Текст поста:** {self.POST}'), self.POST)

    def test_intro_and_explanation_removed(self):
        text = (
            'Вот пост для Telegram:\n\n'
            f'{self.POST}\n\n'
            'Этот пост подчёркивает атмосферу кофейни и вовлекает читателей в диалог.'
        )
        self.assertEqual(postprocess_final_result(text), self.POST)

    def test_notes_after_post_removed(self):
        for tail in ('Примечание: к посту подойдёт фото латте.',
                     '---\n\nПояснение: тон дружелюбный, без штампов.',
                     '**Рекомендации по визуалу:** фото пирога на деревянном столе.'):
            with self.subTest(tail=tail):
                self.assertEqual(postprocess_final_result(f'{self.POST}\n\n{tail}'), self.POST)

    def test_bold_lines_kept(self):
        text = '**Новинка недели**\n\nТыквенный латте уже в меню.\n\n**Только до конца октября**'
        self.assertEqual(postprocess_final_result(text), text)
        self.assertEqual(postprocess_final_result(text, 'Telegram'), text)

    def test_bold_removed_for_platforms_without_markdown(self):
        """ВКонтакте и Дзен не показывают жирный: ** снимаются, текст остаётся (решение судьи по ревью фазы 2, п. 5)"""
        text = 'Хлеб на закваске\n\n**Почему закваска важна?**\nОна даёт **кислинку** и аромат.'
        for platform in ('VK', 'Дзен'):
            with self.subTest(platform=platform):
                self.assertEqual(postprocess_final_result(text, platform),
                                 'Хлеб на закваске\n\nПочему закваска важна?\nОна даёт кислинку и аромат.')

    def test_dzen_headline_label_stripped_text_kept(self):
        text = 'Заголовок: Почему тыквенный латте — не только про тыкву\n\nРассказываем, из чего он.'
        self.assertEqual(
            postprocess_final_result(text),
            'Почему тыквенный латте — не только про тыкву\n\nРассказываем, из чего он.',
        )

    def test_markdown_headers_become_plain_lines(self):
        text = '# Тыквенный латте\n\nВступление.\n\n## Из чего он\n\nСостав.'
        self.assertEqual(postprocess_final_result(text),
                         'Тыквенный латте\n\nВступление.\n\nИз чего он\n\nСостав.')

    def test_hashtags_label_stripped_hashtags_kept(self):
        self.assertEqual(postprocess_final_result(f'{self.POST}\n\nХэштеги: #кофе #осень'),
                         f'{self.POST}\n\n#кофе #осень')

    def test_code_fence_and_quotes_removed(self):
        self.assertEqual(postprocess_final_result(f'```\n{self.POST}\n```'), self.POST)
        self.assertEqual(postprocess_final_result('«Тыквенный латте уже в меню.»'),
                         'Тыквенный латте уже в меню.')

    def test_inner_quotes_kept(self):
        text = '«Осенний» латте уже в меню. Заходите на «кофе с собой»'
        self.assertEqual(postprocess_final_result(text), text)

    def test_only_first_variant_kept(self):
        text = 'Вариант 1:\nПервый пост.\n\nВариант 2:\nВторой пост.'
        self.assertEqual(postprocess_final_result(text), 'Первый пост.')

    def test_variants_after_intro(self):
        text = 'Вот два варианта поста:\n\n**Вариант 1**\nПервый пост.\n\n**Вариант 2**\nВторой пост.'
        self.assertEqual(postprocess_final_result(text), 'Первый пост.')

    def test_review_probes_kept_whole(self):
        """Пробы ревью: строки поста через перевод строки и через пустую строку"""
        for name, lines in REVIEW_PROBES.items():
            for separator in ('\n', '\n\n'):
                with self.subTest(probe=name, separator=repr(separator)):
                    text = separator.join(lines)
                    self.assertEqual(postprocess_final_result(text), text)

    def test_review_2_probes_kept_whole(self):
        """Пробы повторного ревью: с пустыми строками между абзацами и без них"""
        for name, text in REVIEW_2_PROBES.items():
            for variant in dict.fromkeys((text, text.replace('\n\n', '\n'))):
                with self.subTest(probe=name, blank_lines='\n\n' in variant):
                    self.assertEqual(postprocess_final_result(variant), variant)

    def test_variant_intro_cut_before_variant_1_or_with_post_word(self):
        """Вступление с «вариант…» срезается перед «Вариант 1» или рядом со словом «поста», «текста», «статьи»"""
        for intro in ('Вот три варианта:', 'Конечно! Вот несколько вариантов:'):
            with self.subTest(intro=intro):
                text = f'{intro}\n\nВариант 1:\nПервый пост.\n\nВариант 2:\nВторой пост.'
                self.assertEqual(postprocess_final_result(text), 'Первый пост.')
        for intro in ('Вот вариант поста для ВКонтакте:', 'Вот вариант текста:', 'Готово, вариант статьи:'):
            with self.subTest(intro=intro):
                self.assertEqual(postprocess_final_result(f'{intro}\n\n{self.POST}'), self.POST)

    def test_explanation_last_line_without_blank_lines(self):
        """Без пустых строк последний абзац — последняя строка: пояснение там срезается"""
        post = self.POST.replace('\n\n', '\n')
        for tail in ('Этот пост подчёркивает атмосферу кофейни.', 'Примечание: к посту подойдёт фото латте.'):
            with self.subTest(tail=tail):
                self.assertEqual(postprocess_final_result(f'{post}\n{tail}'), post)

    def test_explanation_with_question_kept_label_cut(self):
        """Фраза о посте с вопросом читателям остаётся, служебная метка после неё — срезается"""
        hope = 'Надеюсь, этот пост поможет выбрать напиток. А вы какой берёте?'
        self.assertEqual(postprocess_final_result(f'{self.POST}\n\n{hope}\nПримечание: фото латте.'),
                         f'{self.POST}\n\n{hope}')
        self.assertEqual(postprocess_final_result(f'{self.POST}\n\nНадеюсь, этот пост вам поможет.'),
                         self.POST)
        self.assertEqual(postprocess_final_result(f'{self.POST}\n\nПримечание: может, спросить «А вы пробовали?»'),
                         self.POST)

    def test_final_result_marker_without_old_format_kept(self):
        """«Финальный результат» без «Агент…:» и «Критик:» в ответе — текст поста"""
        text = f'Черновик агента\n\nФинальный Результат\n{self.POST}'
        self.assertEqual(postprocess_final_result(text), text)

    def test_post_label_only_alone_in_first_line(self):
        """«Пост:» и «Текст:» снимаются, только если стоят одни в первой строке с текстом"""
        for label in ('Пост:', '**Текст:**', 'Текст:'):
            with self.subTest(label=label):
                self.assertEqual(postprocess_final_result(f'\n{label}\n{self.POST}'), self.POST)
        self.assertEqual(postprocess_final_result(f'{self.POST}\n\nТекст:\nЕщё абзац.'),
                         f'{self.POST}\n\nТекст:\nЕщё абзац.')

    def test_explanation_only_in_last_paragraph(self):
        """Фраза о самом посте срезается в последнем абзаце, в середине поста остаётся"""
        middle = 'Этот пост написан для тех, кто впервые печёт хлеб дома.'
        text = f'Хлеб на закваске\n\n{middle}\n\nЗакваска — живая культура.'
        self.assertEqual(postprocess_final_result(text), text)

        self.assertEqual(postprocess_final_result(f'{self.POST}\n\n{middle}'), self.POST)
        self.assertEqual(postprocess_final_result(f'{self.POST}\n{middle}'), self.POST)

    def test_old_agent_tail_removed(self):
        for tail in ('Агент-Критик: 8/10', 'Агент 3: финальная правка', '**Агент:** готово'):
            with self.subTest(tail=tail):
                self.assertEqual(postprocess_final_result(f'{self.POST}\n\n{tail}'), self.POST)

    def test_final_result_marker_line(self):
        """Маркер старой преамбулы — только строка целиком и только в ответе старого формата"""
        for marker in ('Финальный Результат', '**Финальный результат:**', '### Финальный результат'):
            with self.subTest(marker=marker):
                text = f'Агент-Генератор: черновик\n\n{marker}\n{self.POST}'
                self.assertEqual(postprocess_final_result(text), self.POST)

    def test_word_ocenka_in_post_kept(self):
        """Слово «оценка» в посте автосервиса — не служебная метка"""
        text = 'Бесплатная оценка ремонта за 15 минут.\n\nОценка займёт меньше, чем чашка кофе.'
        self.assertEqual(postprocess_final_result(text), text)

    def test_old_format_markers(self):
        text = (
            'Агент-Генератор: черновик про кофейню\n\n'
            'Финальный Результат\n'
            f'{self.POST}\n\n'
            'Критик: 9/10'
        )
        self.assertEqual(postprocess_final_result(text), self.POST)

    def test_empty(self):
        self.assertEqual(postprocess_final_result(''), '')
        self.assertIsNone(postprocess_final_result(None))


class StopPhrasesTests(SimpleTestCase):
    """Поиск штампов из стоп-листа в тексте"""

    def test_required_stamps_detected(self):
        for text in REQUIRED_STAMPS:
            with self.subTest(text=text):
                self.assertTrue(find_stop_phrases(text))

    def test_inflected_forms_detected(self):
        # «уникальную» — не из списка вставленных слов, поэтому «не упустите
        # … возможность» здесь не второй штамп (повторное ревью фазы 2, замечание 2)
        self.assertEqual(find_stop_phrases('Не упустите уникальную возможность!'),
                         ['уникальная возможность'])
        self.assertEqual(find_stop_phrases('Не упустите свою возможность!'),
                         ['не упустите возможность'])
        self.assertEqual(find_stop_phrases('Инновационные решения в маникюре'), ['инновационный'])

    def test_run_stamps_detected(self):
        """Штампы из постов прогона фазы 2 (посты 2, 6, 7) — по фразам из постов"""
        for text, phrase in (
                ('Облепиха — суперфуд, она укрепляет иммунитет и заряжает энергией.', 'заряжает энергией'),
                ('Утренний пилатес помогает проснуться полностью, зарядиться энергией и настроить день.',
                 'зарядиться энергией'),
                ('Мягкие упражнения подарят заряд энергии на весь день.', 'заряд энергии'),
                ('Приглашаем ваших малышей 8–11 лет присоединиться к увлекательному миру робототехники!',
                 'увлекательный мир'),
                ('Для тех, кто ценит комфорт и индивидуальный подход.', 'индивидуальный подход')):
            with self.subTest(text=text):
                self.assertIn(phrase, find_stop_phrases(text))

    def test_informal_forms_and_inserted_word_detected(self):
        """Формы на «ты» и одно слово между словами штампа (ревью фазы 2, замечание 2)"""
        for text, phrase in (('Окунись в атмосферу осени', 'окунись в атмосферу'),
                             ('Хочешь узнать больше? Пиши!', 'хочешь узнать больше?'),
                             ('Не упустите свой шанс', 'не упустите шанс'),
                             ('В нашем современном мире', 'в современном мире')):
            with self.subTest(text=text):
                self.assertIn(phrase, find_stop_phrases(text))

    def test_clean_post(self):
        self.assertEqual(find_stop_phrases(PostprocessTests.POST), [])
        self.assertEqual(find_stop_phrases('Мы работаем без выходных, в наших мастерских тепло'), [])

    def test_near_stamps_not_detected(self):
        """
        Обычные фразы со словами штампов: другой смысл, вставленное слово
        не из списка (свой, ваш, наш, этот…) или другое слово с той же основой
        (повторное ревью фазы 2, замечание 2)
        """
        for text in ('Хочешь узнать, когда привезут новое зерно? Подпишись на канал.',
                     'В наше кафе по утрам заходят студенты.',
                     'Новый уровень сложности открываем на третьем занятии.',
                     'Индивидуальные занятия и спокойный подход к ученикам.',
                     'Индивидуальные занятия подходят тем, кто стесняется группы.',
                     'Индивидуальная программа подходит даже новичкам.',
                     'В нашей студии время пролетает незаметно.',
                     'В нашей пекарне время замеса — двенадцать часов.',
                     'На новых тренажёрах уровень нагрузки меняется кнопкой.',
                     'Хотите узнать про боль в спине? Приходите на консультацию.',
                     'Утренняя зарядка даёт энергию до обеда.',
                     'Записи доступны всем ценителям кофе.',
                     'Индивидуальная подходит тем, кто стесняется группы.',
                     'Просторная раздевалка с душем и феном.'):
            with self.subTest(text=text):
                self.assertEqual(find_stop_phrases(text), [])


class GigaChatModelTests(SimpleTestCase):
    """Модель GigaChat для текста и промпта картинки — настройка GIGACHAT_MODEL (решение владельца, п. 5)"""

    def client_kwargs(self, init_name, constructor_name):
        """Аргументы конструктора клиента при настоящем _init_client / _init_direct_client"""
        init = runner.UNGUARDED.get(init_name) or getattr(gigachat_api, init_name)
        with patch(f'generator.gigachat_api.{constructor_name}') as constructor, \
                patch('generator.gigachat_api._get_credentials', return_value='test-credentials'):
            init()
        constructor.assert_called_once()
        return constructor.call_args.kwargs

    @override_settings(GIGACHAT_MODEL='GigaChat-Pro')
    def test_text_client_uses_model_from_settings(self):
        self.assertEqual(self.client_kwargs('_init_client', 'GigaChat')['model'], 'GigaChat-Pro')

    def test_default_is_library_default_model(self):
        """По умолчанию — модель, которую библиотека gigachat берёт без настройки (Lite)"""
        self.assertEqual(settings.GIGACHAT_MODEL, GIGACHAT_LIBRARY_MODEL)
        self.assertEqual(self.client_kwargs('_init_client', 'GigaChat')['model'], GIGACHAT_LIBRARY_MODEL)
        for name in ('settings.py', 'production_settings.py'):
            with self.subTest(settings=name):
                source = (Path(settings.BASE_DIR) / 'ghostwriter' / name).read_text(encoding='utf-8')
                self.assertIn(f"GIGACHAT_MODEL = os.environ.get('GIGACHAT_MODEL', '{GIGACHAT_LIBRARY_MODEL}')",
                              source)

    @override_settings(GIGACHAT_MODEL='GigaChat-Pro')
    def test_image_client_without_model_setting(self):
        """Клиент картинок (_init_direct_client) модель из настроек не получает"""
        self.assertNotIn('model', self.client_kwargs('_init_direct_client', 'GigaChatDirect'))


@override_settings(DEMO_TOKENS_PER_IP_PER_DAY=1000)
class GeneratorTemplateTests(TestCase):
    """Разметка формы: площадка, «О бизнесе», «Дополнительно» свёрнуто"""

    def setUp(self):
        response = try_demo().get('/generator/')
        self.assertEqual(response.status_code, 200)
        self.html = response.content.decode()
        match = re.search(r'<form[^>]*id="generateForm".*?</form>', self.html, re.S)
        self.assertIsNotNone(match)
        self.form = match.group(0)

    def test_platform_radios_inside_form(self):
        inputs = re.findall(r'<input[^>]*name="platform"[^>]*>', self.form)
        self.assertEqual(len(inputs), 3)
        for tag, platform in zip(inputs, PLATFORMS):
            self.assertIn('type="radio"', tag)
            self.assertIn(f'value="{platform}"', tag)

    def test_business_info_inside_form(self):
        self.assertRegex(self.form, r'<textarea[^>]*name="business_info"[^>]*maxlength="500"')
        self.assertRegex(self.form, r'<textarea[^>]*name="topic"[^>]*maxlength="500"')

    def test_advanced_settings_collapsed(self):
        match = re.search(r'<div[^>]*id="advancedSettings"[^>]*>', self.form)
        self.assertIsNotNone(match)
        self.assertRegex(match.group(0), r'class="[^"]*\bcollapse\b')
        self.assertNotRegex(match.group(0), r'class="[^"]*\bshow\b')
        self.assertIn('data-bs-target="#advancedSettings"', self.form)
        settings_part = self.form[match.start():]
        for name in SETTING_FIELDS:
            self.assertIn(f'name="{name}"', settings_part, name)

    def test_banned_platforms_removed(self):
        for text in ('platform_specific', 'Instagram', 'TikTok', 'Facebook', 'LinkedIn', 'Twitter'):
            self.assertNotIn(text, self.form)

    def test_ajax_sends_whole_form(self):
        """AJAX отправляет FormData всей формы: новые поля внутри неё уходят на сервер"""
        self.assertIn('new FormData(form)', self.html)
