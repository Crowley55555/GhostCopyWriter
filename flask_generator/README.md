# 🤖 Flask AI Generator Microservice

Независимый микросервис для генерации контента через внешние AI API с поддержкой шифрования данных. Разработан для соблюдения требований 152-ФЗ о персональных данных.

## 🎯 Назначение

Этот микросервис обеспечивает изоляцию AI обработки от основного Django приложения:
- **Безопасность**: Обработка только обезличенных данных без доступа к персональной информации
- **Масштабируемость**: Независимое развертывание и горизонтальное масштабирование
- **Отказоустойчивость**: Fallback механизмы при недоступности AI API
- **Соответствие 152-ФЗ**: Четкое разделение персональных данных и AI обработки

## 🏗️ Архитектура

```
Django App  ←→  [Encrypted Data]  ←→  Flask Microservice  ←→  AI APIs
    ↓                                        ↓                    ↓
User Data                            Content Processing     OpenAI/GigaChat
Profiles                             Text Generation        DALL-E
History                              Image Prompts          External APIs
Templates                            Crypto Utils
```

## 📁 Структура проекта

```
flask_generator/
├── 🚀 app.py                 # Основное Flask приложение
├── 📝 text_gen.py            # Генерация текста через OpenAI GPT
├── 🎨 image_gen.py           # Генерация изображений через DALL-E
├── 🔧 prompt_utils.py        # Сборка промптов по критериям
├── 🔐 crypto_utils.py        # Шифрование/дешифрование данных
├── 📋 requirements.txt       # Python зависимости
├── 📄 README.md              # Этот файл
└── 🔧 .env.example           # Пример конфигурации
```

## ⚡ Быстрый старт

### 1. Установка зависимостей
   ```bash
   cd flask_generator
   pip install -r requirements.txt
   ```

### 2. Настройка окружения
Создайте файл `.env` в папке `flask_generator`:
```env
# OpenAI API для генерации текста и изображений
   OPENAI_API_KEY=your_openai_api_key_here

# Ключ шифрования (должен совпадать с Django)
   GENERATOR_ENCRYPTION_KEY=k6W1hS1TpK-fOe-1pEGSSXmSDHkQNrpsI-TfuL-7EHI=

# Опциональные настройки
FLASK_ENV=development
FLASK_DEBUG=True
   ```
   
### 3. Запуск сервера

**Рекомендуемый способ (Flask CLI):**
   ```bash
   python -m flask --app app run --host=0.0.0.0 --port=5000 --debug
   ```

**Альтернативные способы:**
```bash
# Прямой запуск
python app.py

# Через gunicorn (продакшн)
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### 4. Проверка работоспособности
   ```bash
curl http://localhost:5000/
# Ответ: {"status": "ok", "message": "Flask Generator API is running"}
```

## 🔌 API Endpoints

### Health Check
```http
GET /
```
**Ответ:**
```json
{
  "status": "ok",
  "message": "Flask Generator API is running",
  "endpoints": ["/generate-text", "/generate-image"]
}
```

### Тестовый endpoint
```http
POST /test
Content-Type: application/json

{
  "test": "data"
}
```

### Генерация текста
```http
POST /generate-text
Content-Type: application/json

{
  "data": "encrypted_form_parameters"
}
```

**Параметры (после расшифровки):**
- `topic` - тема поста
- `voice_tone` - тон голоса
- `platform_specific` - платформы
- `post_length` - длина поста
- `cta` - призыв к действию
- другие параметры формы

**Ответ:**
```json
{
  "data": "encrypted_result_with_text_and_image_prompt"
}
```

### Генерация изображения
```http
POST /generate-image
Content-Type: application/json

{
  "data": "encrypted_image_prompt"
}
```

**Ответ:**
```json
{
  "data": "encrypted_image_url"
}
```

## 🔐 Безопасность и шифрование

### Принципы безопасности
1. **Шифрование всех данных**: Используется Fernet (симметричное шифрование)
2. **Отсутствие персональных данных**: Обрабатываются только обезличенные промпты
3. **Изоляция от основной БД**: Нет прямого доступа к пользовательским данным
4. **Безопасная передача**: HTTPS для всех запросов в продакшне

### Связь с Django (production)

Django на российском сервере доступен снаружи как `https://<IP>/` (порт **443**, самоподписанный SSL — см. `deploy/generate-ssl-ip.sh` и [ssl/README.md](../ssl/README.md) в корне репозитория).

В `.env` Django укажите URL этого Flask-сервиса:

```env
FLASK_EXTERNAL_URL=https://your-flask-server.com
```

Django шифрует промпты и обращается к Flask по HTTPS. Инструкция по деплою Flask: `deploy/deploy-flask.sh`, обзор — [DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md).

### Пример шифрования
```python
from crypto_utils import encrypt_data, decrypt_data

# Шифрование данных перед отправкой
data = {"topic": "AI в маркетинге"}
encrypted = encrypt_data(json.dumps(data).encode())

# Расшифровка полученных данных
decrypted = decrypt_data(encrypted)
original_data = json.loads(decrypted.decode())
```

## 🤖 AI Интеграции

### OpenAI GPT (Генерация текста)
- **Модели**: GPT-4o-mini (по умолчанию), настраивается через OPENAI_MODEL
- **Функции**: Создание постов, адаптация под платформы, SEO-оптимизация
- **Fallback**: Mock ответы при отсутствии API ключа

### OpenAI DALL-E (Генерация изображений)
- **Модели**: DALL-E 2, DALL-E 3
- **Функции**: Создание изображений по промптам, стилизация
- **Форматы**: PNG, JPEG (настраивается)

### Система промптов
```python
# Пример сборки промпта
prompt = assemble_prompt_from_criteria({
    'topic': 'AI в маркетинге',
    'voice_tone': ['Профессиональный'],
    'platform_specific': ['LinkedIn'],
    'post_length': 'Средний'
})
```

## 🔧 Конфигурация

### Переменные окружения
```env
# Обязательные
OPENAI_API_KEY=sk-...                    # OpenAI API ключ
GENERATOR_ENCRYPTION_KEY=base64_key      # Ключ шифрования

# Опциональные
FLASK_ENV=development                    # Режим Flask
FLASK_DEBUG=True                         # Отладка
OPENAI_MODEL=gpt-4o-mini               # Модель GPT (по умолчанию)
DALLE_MODEL=dall-e-3                     # Модель DALL-E
REQUEST_TIMEOUT=30                       # Таймаут запросов
```

### Настройки модели
```python
# В text_gen.py можно настроить параметры GPT
response = openai_client.chat.completions.create(
    model="gpt-4o-mini",  # или через OPENAI_MODEL
    messages=[...],
    max_tokens=1000,
    temperature=0.7,
    top_p=1.0
)
```

## 🚀 Деплой

### Docker
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

### Docker Compose
```yaml
version: '3.8'
services:
  flask-generator:
    build: ./flask_generator
    ports:
      - "5000:5000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - GENERATOR_ENCRYPTION_KEY=${GENERATOR_ENCRYPTION_KEY}
    restart: unless-stopped
```

### Systemd Service
```ini
[Unit]
Description=Flask AI Generator
After=network.target

[Service]
Type=exec
User=www-data
WorkingDirectory=/path/to/flask_generator
ExecStart=/path/to/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

## 📊 Мониторинг

### Логирование
```python
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Метрики
- Время ответа AI API
- Количество успешных/неудачных запросов
- Использование токенов OpenAI
- Ошибки шифрования/расшифровки

### Health Checks
   ```bash
# Простая проверка
curl -f http://localhost:5000/ || exit 1

# Проверка с тестовыми данными
curl -X POST http://localhost:5000/test \
  -H "Content-Type: application/json" \
  -d '{"test": "health_check"}'
```

## 🧪 Тестирование

### Запуск тестов
   ```bash
# Установка тестовых зависимостей
pip install pytest pytest-flask

# Запуск тестов
python -m pytest tests/test_flask_app.py -v

# С покрытием кода
python -m pytest tests/test_flask_app.py --cov=flask_generator
```

### Тестирование API
```python
def test_health_endpoint():
    response = client.get('/')
    assert response.status_code == 200
    assert response.json['status'] == 'ok'

def test_generate_text():
    encrypted_data = encrypt_test_data({'topic': 'test'})
    response = client.post('/generate-text', 
                          json={'data': encrypted_data})
    assert response.status_code == 200
```

## 🔍 Отладка

### Логи разработки
```bash
# Запуск с подробными логами
FLASK_DEBUG=True python app.py

# Просмотр логов в реальном времени
tail -f flask_generator.log
```

### Частые проблемы
1. **Ошибки шифрования**: Проверьте совпадение ключей в Django и Flask
2. **OpenAI API лимиты**: Мониторьте использование токенов
3. **Таймауты**: Увеличьте `REQUEST_TIMEOUT` для медленных запросов
4. **Кодировка**: Убедитесь в UTF-8 для всех текстовых данных

## 🤝 Интеграция с Django

### Настройка Django
```python
# В settings.py
FLASK_GEN_URL = 'http://localhost:5000'
GENERATOR_ENCRYPTION_KEY = 'your_encryption_key'
```

### Пример вызова из Django
```python
from .fastapi_client import generate_text_and_prompt

# Генерация контента
result = generate_text_and_prompt({
    'topic': 'AI в маркетинге',
    'voice_tone': ['Профессиональный']
})
```

## 📚 Дополнительные ресурсы

### Документация
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Fernet Encryption](https://cryptography.io/en/latest/fernet/)

### Полезные ссылки
- [OpenAI Python Library](https://github.com/openai/openai-python)
- [Flask Best Practices](https://flask.palletsprojects.com/en/2.3.x/patterns/)
- [Microservices Architecture](https://microservices.io/)

---

<p align="center">
  <i>Микросервис разработан с учетом требований 152-ФЗ РФ о персональных данных</i>
</p>