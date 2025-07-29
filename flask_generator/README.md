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
3. Создайте файл `.env` и заполните переменные:
   - `OPENAI_API_KEY` — ваш OpenAI API ключ
   - `MIDJOURNEY_API_KEY` — ваш Midjourney API ключ
   - `GENERATOR_ENCRYPTION_KEY` — ключ Fernet (опционально, иначе сгенерируется автоматически)
   - `MIDJOURNEY_API_URL` — (опционально) endpoint Midjourney
4. Запустите сервер:
   ```bash
   python app.py
   ```

## Эндпоинты
- `POST /generate-text` — генерация текста и промпта для изображения
- `POST /generate-image` — генерация изображения по промпту

Все данные передаются и возвращаются в зашифрованном виде (Fernet).

## Деплой
Микросервис не зависит от основного Django-приложения и может быть развёрнут на любом сервере с Python 3.7+ (например, через gunicorn, uwsgi, docker).

## Пример .env
```
OPENAI_API_KEY=your_openai_key
MIDJOURNEY_API_KEY=your_midjourney_key
GENERATOR_ENCRYPTION_KEY=your_fernet_key
MIDJOURNEY_API_URL=https://api.midjourney.com/generate
``` 