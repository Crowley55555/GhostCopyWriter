# Flask OpenAI+Midjourney Generator

Этот микросервис реализует API для генерации текста (OpenAI) и изображений (Midjourney) с шифрованием данных. Полностью независим, готов к деплою отдельно от основного приложения.

## Структура
- `app.py` — основной Flask-приложение (эндпоинты)
- `text_gen.py` — генерация текста через OpenAI
- `image_gen.py` — генерация промпта и изображений через OpenAI/Midjourney
- `prompt_utils.py` — сборка промпта по критериям
- `crypto_utils.py` — шифрование/дешифрование данных
- `requirements.txt` — зависимости

## Запуск

1. Перейдите в папку `flask_generator`:
   ```bash
   cd flask_generator
   ```
2. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
3. Создайте файл `.env` в папке `flask_generator` и заполните переменные:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   COMETAPI_KEY=your_cometapi_key_here
   GENERATOR_ENCRYPTION_KEY=k6W1hS1TpK-fOe-1pEGSSXmSDHkQNrpsI-TfuL-7EHI=
   COMETAPI_URL=https://api.cometapi.com/v1
   ```
   
   **⚠️ Важно:** 
   - `OPENAI_API_KEY` для генерации текста и промптов
   - `COMETAPI_KEY` для генерации изображений
   - `GENERATOR_ENCRYPTION_KEY` должен совпадать с Django (уже настроен)
4. Запустите сервер:

   **Вариант 1 (рекомендуемый):**
   ```bash
   python -m flask --app app run --host=0.0.0.0 --port=5000 --debug
   ```

   **Вариант 2:**
   ```bash
   python run.py
   ```

   **Вариант 3 (Windows):**
   ```bash
   start.bat
   ```

   **Вариант 4 (Linux/Mac):**
   ```bash
   chmod +x start.sh
   ./start.sh
   ```

## Эндпоинты
- `GET /` — health check
- `POST /generate-text` — генерация текста через OpenAI и промпта для изображения
- `POST /generate-image` — генерация изображения через CometAPI

Все данные передаются и возвращаются в зашифрованном виде (Fernet).

## Деплой
Микросервис не зависит от основного Django-приложения и может быть развёрнут на любом сервере с Python 3.7+ (например, через gunicorn, uwsgi, docker).

## Пример .env
```
OPENAI_API_KEY=your_openai_key
COMETAPI_KEY=your_cometapi_key
GENERATOR_ENCRYPTION_KEY=k6W1hS1TpK-fOe-1pEGSSXmSDHkQNrpsI-TfuL-7EHI=
COMETAPI_URL=https://api.cometapi.com/v1
``` 