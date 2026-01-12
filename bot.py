"""
Telegram бот для Ghostwriter

Простой бот для генерации временных токенов доступа без сбора персональных данных.

Особенности:
- Полная анонимность - не запрашивает телефон, email, имя
- Каждый пользователь = анонимная сессия
- Генерация токенов без привязки к личности
- Простой интерфейс с 3 кнопками выбора тарифа

Настройка:
1. Создайте бота у @BotFather и получите токен
2. Установите webhook: python bot.py --set-webhook
3. Или запустите в polling режиме: python bot.py

Требования:
pip install python-telegram-bot requests python-dotenv
"""

import os
import sys
import logging
import argparse
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Настройки
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
WEBHOOK_URL = os.getenv('TELEGRAM_WEBHOOK_URL')  # Например: https://yourdomain.com/telegram/webhook/
WEBHOOK_SECRET = os.getenv('TELEGRAM_WEBHOOK_SECRET')
DJANGO_API_URL = os.getenv('DJANGO_API_URL', 'http://localhost:8000')  # URL Django сервера
DJANGO_API_KEY = os.getenv('DJANGO_API_KEY', '')  # API ключ для аутентификации

if not BOT_TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN не установлен в .env файле!")
    sys.exit(1)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды /start
    
    Отправляет приветственное сообщение с кнопками выбора тарифа.
    """
    user = update.effective_user
    
    # Создаем inline клавиатуру с кнопками
    keyboard = [
        [InlineKeyboardButton("🆓 Демо 5 дней", callback_data='demo')],
        [InlineKeyboardButton("📅 30 дней", callback_data='buy_monthly')],
        [InlineKeyboardButton("📆 1 год", callback_data='buy_yearly')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        f"👋 Привет!\n\n"
        f"Добро пожаловать в <b>Ghostwriter</b> - генератор контента для соцсетей!\n\n"
        f"Выберите тариф для получения доступа:\n\n"
        f"🆓 <b>DEMO</b> - 5 дней, 5 генераций в день (бесплатно)\n"
        f"📅 <b>30 дней</b> - безлимитные генерации\n"
        f"📆 <b>1 год</b> - безлимитные генерации\n\n"
        f"🔒 <i>Мы не собираем персональные данные. Полная анонимность.</i>"
    )
    
    await update.message.reply_html(
        welcome_text,
        reply_markup=reply_markup
    )
    
    logger.info(f"Пользователь {user.id} запустил команду /start")


def create_token_via_api(token_type, telegram_user_id=None):
    """
    Создает токен через Django API
    
    Args:
        token_type: Тип токена ('DEMO', 'MONTHLY', 'YEARLY')
        telegram_user_id: ID пользователя Telegram (для предотвращения повторной выдачи DEMO)
    
    Returns:
        dict: Данные токена или None при ошибке
    """
    try:
        # Определяем параметры токена
        if token_type == 'DEMO':
            expires_days = 5
            daily_limit = 5
        elif token_type == 'MONTHLY':
            expires_days = 30
            daily_limit = -1  # Безлимит
        elif token_type == 'YEARLY':
            expires_days = 365
            daily_limit = -1  # Безлимит
        else:
            logger.error(f"Неизвестный тип токена: {token_type}")
            return None
        
        # Отправляем запрос к Django API
        url = f"{DJANGO_API_URL}/api/tokens/create/"
        
        headers = {}
        if DJANGO_API_KEY:
            headers['X-API-Key'] = DJANGO_API_KEY
        
        data = {
            'token_type': token_type,
            'expires_days': expires_days,
            'daily_limit': daily_limit
        }
        
        # Передаем telegram_user_id для DEMO токенов (для предотвращения повторной выдачи)
        if token_type == 'DEMO' and telegram_user_id:
            data['telegram_user_id'] = telegram_user_id
        
        logger.info(f"Отправка запроса к Django API: {url}")
        response = requests.post(url, json=data, headers=headers, timeout=10)
        
        if response.status_code == 201:
            result = response.json()
            logger.info(f"✅ Токен создан успешно: {result.get('token')}")
            return result
        elif response.status_code == 200:
            # Токен уже существует (для DEMO)
            result = response.json()
            logger.info(f"ℹ️ Использован существующий токен: {result.get('token')}")
            return result
        else:
            logger.error(f"❌ Ошибка создания токена: {response.status_code} - {response.text}")
            return None
            
    except requests.RequestException as e:
        logger.error(f"❌ Ошибка подключения к Django API: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка при создании токена: {e}")
        return None


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик нажатий на inline кнопки
    
    Обрабатывает выбор тарифа и создает реальные токены через Django API.
    """
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    action = query.data
    
    logger.info(f"Пользователь {user.id} нажал кнопку: {action}")
    
    if action == 'demo':
        # Показываем промежуточное сообщение
        await query.edit_message_text(
            text="⏳ <b>Генерирую DEMO токен...</b>\n\n"
                 "Пожалуйста, подождите несколько секунд.",
            parse_mode='HTML'
        )
        
        # Создаем токен через Django API (передаем user_id для предотвращения повторной выдачи)
        token_data = create_token_via_api('DEMO', telegram_user_id=user.id)
        
        if token_data:
            # Успешно создали или получили существующий токен
            token = token_data.get('token')
            expires_at = token_data.get('expires_at')
            token_url = token_data.get('url')
            is_existing = token_data.get('is_existing', False)
            
            # Парсим дату истечения
            try:
                expires_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                expires_str = expires_dt.strftime('%d.%m.%Y %H:%M')
            except:
                expires_str = expires_at
            
            # Формируем сообщение в зависимости от того, новый это токен или существующий
            if is_existing:
                demo_text = (
                    "ℹ️ <b>У вас уже есть активный DEMO токен!</b>\n\n"
                    "📝 <b>Условия:</b>\n"
                    "• Срок действия: 5 дней\n"
                    "• Генераций в день: 5\n\n"
                    "🔗 <b>Ваша ссылка:</b>\n"
                    f"{token_url}\n\n"
                    f"📅 <b>Активна до:</b> {expires_str}\n"
                    f"⚡ <b>Генераций доступно сегодня:</b> {token_data.get('daily_limit', 5)}\n\n"
                    "📌 <i>Используйте эту ссылку для доступа</i>\n\n"
                    "💡 <b>Примечание:</b> Один пользователь может получить только один активный DEMO токен."
                )
            else:
                demo_text = (
                    "✅ <b>DEMO токен готов!</b>\n\n"
                    "📝 <b>Условия:</b>\n"
                    "• Срок действия: 5 дней\n"
                    "• Генераций в день: 5\n\n"
                    "🔗 <b>Ваша ссылка:</b>\n"
                    f"{token_url}\n\n"
                    f"📅 <b>Активна до:</b> {expires_str}\n"
                    f"⚡ <b>Генераций доступно сегодня:</b> 5\n\n"
                    "📌 <i>Скопируйте ссылку и откройте в браузере</i>\n\n"
                    "💡 <b>Совет:</b> Сохраните эту ссылку - она работает как логин!"
                )
            
            await query.edit_message_text(
                text=demo_text,
                parse_mode='HTML'
            )
        else:
            # Ошибка создания токена
            error_text = (
                "❌ <b>Ошибка создания токена</b>\n\n"
                "Не удалось создать DEMO токен. Возможные причины:\n"
                "• Django сервер недоступен\n"
                "• Проблемы с подключением\n\n"
                "Пожалуйста, попробуйте позже или обратитесь в поддержку."
            )
            
            await query.edit_message_text(
                text=error_text,
                parse_mode='HTML'
            )
    
    elif action == 'buy_monthly':
        await query.edit_message_text(
            text="⚠️ <b>Платёжная система в разработке</b>\n\n"
                 "Тариф <b>30 дней</b> будет доступен после запуска.\n\n"
                 "Мы учли ваш интерес к этому тарифу! 📊",
            parse_mode='HTML'
        )
    
    elif action == 'buy_yearly':
        await query.edit_message_text(
            text="⚠️ <b>Платёжная система в разработке</b>\n\n"
                 "Тариф <b>1 год</b> будет доступен после запуска.\n\n"
                 "Мы учли ваш интерес к этому тарифу! 📊",
            parse_mode='HTML'
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help"""
    help_text = (
        "🤖 <b>Ghostwriter Bot - Справка</b>\n\n"
        "<b>Доступные команды:</b>\n"
        "/start - Начать работу и получить токен\n"
        "/help - Показать эту справку\n"
        "/plans - Показать доступные тарифы\n\n"
        "<b>Как это работает:</b>\n"
        "1. Нажмите /start\n"
        "2. Выберите тариф\n"
        "3. Получите ссылку с токеном\n"
        "4. Откройте ссылку в браузере\n"
        "5. Начните генерировать контент!\n\n"
        "💡 <i>Никакой регистрации не требуется</i>"
    )
    
    await update.message.reply_html(help_text)


async def plans_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /plans - показывает доступные тарифы"""
    plans_text = (
        "📋 <b>Доступные тарифы Ghostwriter</b>\n\n"
        "🆓 <b>DEMO</b>\n"
        "• Срок: 5 дней\n"
        "• Генераций: 5 в день\n"
        "• Цена: Бесплатно\n\n"
        "📅 <b>30 дней</b>\n"
        "• Срок: 30 дней\n"
        "• Генераций: Безлимит\n"
        "• Цена: В разработке\n\n"
        "📆 <b>1 год</b>\n"
        "• Срок: 365 дней\n"
        "• Генераций: Безлимит\n"
        "• Цена: В разработке\n\n"
        "💡 <i>Для получения токена используйте /start</i>"
    )
    
    await update.message.reply_html(plans_text)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик ошибок"""
    logger.error(f"Ошибка при обработке обновления: {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Произошла ошибка при обработке вашего запроса.\n"
            "Пожалуйста, попробуйте позже или обратитесь в поддержку."
        )


def main_polling():
    """
    Запуск бота в polling режиме (для разработки)
    
    В этом режиме бот постоянно опрашивает Telegram API на наличие новых сообщений.
    Подходит для локальной разработки и тестирования.
    """
    logger.info("🚀 Запуск бота в polling режиме...")
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("plans", plans_command))
    
    # Регистрируем обработчик callback'ов от inline кнопок
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Регистрируем обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запускаем бота
    logger.info("✅ Бот успешно запущен! Нажмите Ctrl+C для остановки.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


def set_webhook():
    """
    Установка webhook для production режима
    
    В этом режиме Telegram отправляет обновления на указанный URL,
    а Django webhook обрабатывает их через views.telegram_webhook
    """
    import requests
    
    if not WEBHOOK_URL:
        logger.error("❌ TELEGRAM_WEBHOOK_URL не установлен в .env файле!")
        return
    
    logger.info(f"🔧 Установка webhook: {WEBHOOK_URL}")
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    
    data = {
        'url': WEBHOOK_URL,
    }
    
    # Добавляем секретный токен для верификации запросов
    if WEBHOOK_SECRET:
        data['secret_token'] = WEBHOOK_SECRET
    
    try:
        response = requests.post(url, json=data)
        result = response.json()
        
        if result.get('ok'):
            logger.info("✅ Webhook успешно установлен!")
            logger.info(f"📍 URL: {WEBHOOK_URL}")
            if WEBHOOK_SECRET:
                logger.info(f"🔐 Secret token: установлен")
        else:
            logger.error(f"❌ Ошибка установки webhook: {result}")
    
    except Exception as e:
        logger.error(f"❌ Исключение при установке webhook: {e}")


def delete_webhook():
    """Удаление webhook"""
    import requests
    
    logger.info("🗑️ Удаление webhook...")
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
    
    try:
        response = requests.post(url)
        result = response.json()
        
        if result.get('ok'):
            logger.info("✅ Webhook успешно удалён!")
        else:
            logger.error(f"❌ Ошибка удаления webhook: {result}")
    
    except Exception as e:
        logger.error(f"❌ Исключение при удалении webhook: {e}")


def get_webhook_info():
    """Получение информации о текущем webhook"""
    import requests
    
    logger.info("ℹ️ Получение информации о webhook...")
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
    
    try:
        response = requests.get(url)
        result = response.json()
        
        if result.get('ok'):
            webhook_info = result['result']
            logger.info("✅ Информация о webhook:")
            logger.info(f"   URL: {webhook_info.get('url', 'не установлен')}")
            logger.info(f"   Pending updates: {webhook_info.get('pending_update_count', 0)}")
            logger.info(f"   Последняя ошибка: {webhook_info.get('last_error_message', 'нет')}")
        else:
            logger.error(f"❌ Ошибка получения информации: {result}")
    
    except Exception as e:
        logger.error(f"❌ Исключение при получении информации: {e}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Telegram бот для Ghostwriter')
    parser.add_argument('--set-webhook', action='store_true', help='Установить webhook для production')
    parser.add_argument('--delete-webhook', action='store_true', help='Удалить webhook')
    parser.add_argument('--webhook-info', action='store_true', help='Показать информацию о webhook')
    
    args = parser.parse_args()
    
    if args.set_webhook:
        set_webhook()
    elif args.delete_webhook:
        delete_webhook()
    elif args.webhook_info:
        get_webhook_info()
    else:
        # Запуск в polling режиме (по умолчанию)
        main_polling()
