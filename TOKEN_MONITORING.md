# Мониторинг расхода токенов GigaChat

## Описание

Система автоматически отслеживает использование токенов GigaChat API для всех операций генерации:
- Генерация текста
- Генерация промпта для изображения
- Генерация изображения

## Как это работает

1. **Оценка токенов**: Система оценивает количество токенов на основе длины промпта и ответа (1 токен ≈ 2.5 символа для смешанного русско-английского текста)

2. **Автоматическое логирование**: Каждый запрос к GigaChat API автоматически логируется в модель `GigaChatTokenUsage`

3. **Связь с пользователями**: Записи связаны с пользователями Django или токенами доступа для анализа использования

## Просмотр статистики

### В админ-панели Django

1. Войдите в админ-панель: `/admin/`
2. Перейдите в раздел **"Использование токенов GigaChat"**
3. На странице списка отображается статистика:
   - Общее количество токенов
   - Стоимость использования (расчет: 5 млн токенов = 1000₽)
   - Статистика за 7 и 30 дней
   - Статистика по типам операций

### Фильтры и поиск

- **Фильтры**: По типу операции, дате создания, платформе
- **Поиск**: По теме, имени пользователя, токену, теме генерации

## Программный доступ к статистике

### Получить общее количество токенов

```python
from generator.models import GigaChatTokenUsage

# За все время
total = GigaChatTokenUsage.get_total_tokens()

# За период
from datetime import datetime, timedelta
start = datetime.now() - timedelta(days=7)
total_7d = GigaChatTokenUsage.get_total_tokens(start_date=start)

# По типу операции
total_text = GigaChatTokenUsage.get_total_tokens(operation_type='TEXT_GENERATION')
```

### Получить детальную статистику

```python
from generator.models import GigaChatTokenUsage

# Статистика за последние 7 дней
stats = GigaChatTokenUsage.get_statistics(days=7)

# Результат:
# {
#     'total_tokens': 1500000,
#     'total_requests': 200,
#     'by_operation': {
#         'TEXT_GENERATION': {'name': 'Генерация текста', 'count': 100, 'tokens': 800000},
#         'IMAGE_PROMPT': {'name': 'Промпт для изображения', 'count': 50, 'tokens': 300000},
#         'IMAGE_GENERATION': {'name': 'Генерация изображения', 'count': 50, 'tokens': 400000}
#     },
#     'period_days': 7
# }
```

## Расчет стоимости

Текущая цена токенов GigaChat Lite: **1000₽ за 5 млн токенов**

Формула расчета стоимости:
```
Стоимость = (Количество токенов × 1000) / 5,000,000
```

Или проще:
```
Стоимость = Количество токенов × 0.0002₽
```

## Миграция базы данных

После добавления системы мониторинга необходимо выполнить миграцию:

```bash
python manage.py migrate generator
```

## Примечания

- Оценка токенов является приблизительной (на основе длины текста)
- Точное количество токенов может отличаться от оценки GigaChat API
- Система не влияет на производительность генерации (логирование асинхронное)
- Ошибки логирования не прерывают процесс генерации

## Примеры использования

### Анализ расхода токенов по пользователям

```python
from generator.models import GigaChatTokenUsage
from django.db.models import Sum

# Топ-10 пользователей по расходу токенов
top_users = GigaChatTokenUsage.objects.values('user__username').annotate(
    total_tokens=Sum('estimated_total_tokens')
).order_by('-total_tokens')[:10]
```

### Анализ расхода по токенам доступа

```python
from generator.models import GigaChatTokenUsage
from django.db.models import Sum

# Расход по типам токенов
by_token_type = GigaChatTokenUsage.objects.filter(
    token__isnull=False
).values('token__token_type').annotate(
    total_tokens=Sum('estimated_total_tokens'),
    count=Count('id')
).order_by('-total_tokens')
```

### Прогноз расхода на следующий месяц

```python
from generator.models import GigaChatTokenUsage
from datetime import timedelta
from django.utils import timezone

# Средний расход за последние 7 дней
stats_7d = GigaChatTokenUsage.get_statistics(days=7)
avg_daily = stats_7d['total_tokens'] / 7

# Прогноз на месяц
monthly_forecast = avg_daily * 30
monthly_cost = monthly_forecast * 0.0002  # в рублях

print(f"Прогноз на месяц: {monthly_forecast:,.0f} токенов ({monthly_cost:.2f}₽)")
```
