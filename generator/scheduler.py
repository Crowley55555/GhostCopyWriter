"""
Планировщик фоновых задач для Ghostwriter

Автоматически выполняет:
- Деактивацию истекших токенов
- Удаление старых деактивированных токенов
- Очистку базы данных

Использует APScheduler для встроенной автоматизации без необходимости настройки cron.
"""

import logging
from datetime import timedelta
from django.utils import timezone
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings

logger = logging.getLogger(__name__)


def cleanup_expired_tokens():
    """
    Деактивирует истекшие токены в базе данных
    
    Эта задача запускается автоматически по расписанию и деактивирует
    все токены, у которых истек срок действия, но они все еще активны.
    """
    try:
        from generator.models import TemporaryAccessToken
        
        now = timezone.now()
        
        # Находим все истекшие активные токены (исключаем бессрочные)
        from django.db.models import Q
        expired_tokens = TemporaryAccessToken.objects.filter(
            expires_at__lt=now,
            expires_at__isnull=False,  # Исключаем бессрочные
            is_active=True
        )
        
        count = expired_tokens.count()
        
        if count > 0:
            # Деактивируем их
            expired_tokens.update(is_active=False)
            logger.info(f"✅ Автоматическая очистка: деактивировано {count} истекших токенов")
        else:
            logger.debug("✅ Автоматическая очистка: истекших токенов не найдено")
        
        return count
        
    except Exception as e:
        logger.error(f"❌ Ошибка при деактивации истекших токенов: {e}")
        return 0


def delete_old_tokens():
    """
    Удаляет старые деактивированные токены из базы данных
    
    Удаляет токены которые:
    - Деактивированы (is_active=False)
    - Истекли более 90 дней назад
    
    Также удаляет генерации без пользователя (user=None) старше 90 дней,
    которые были созданы демо-токенами из manual_token_generator.
    
    Это помогает поддерживать базу данных в чистоте.
    """
    try:
        from generator.models import TemporaryAccessToken, Generation
        
        # Вычисляем дату отсечки (90 дней назад)
        cutoff_date = timezone.now() - timedelta(days=90)
        
        # Находим старые деактивированные токены (исключаем бессрочные)
        from django.db.models import Q
        old_tokens = TemporaryAccessToken.objects.filter(
            is_active=False,
            expires_at__lt=cutoff_date,
            expires_at__isnull=False  # Исключаем бессрочные
        )
        
        token_count = old_tokens.count()
        
        if token_count > 0:
            # Удаляем их
            old_tokens.delete()
            logger.info(f"🗑️ Автоматическая очистка: удалено {token_count} старых токенов (>90 дней)")
        else:
            logger.debug("🗑️ Автоматическая очистка: старых токенов не найдено")
        
        # Удаляем генерации без пользователя (демо-токены) старше 90 дней
        old_generations = Generation.objects.filter(
            user__isnull=True,  # Только генерации без пользователя (демо-токены)
            created_at__lt=cutoff_date
        )
        
        generation_count = old_generations.count()
        
        if generation_count > 0:
            old_generations.delete()
            logger.info(f"🗑️ Автоматическая очистка: удалено {generation_count} старых генераций демо-токенов (>90 дней)")
        else:
            logger.debug("🗑️ Автоматическая очистка: старых генераций демо-токенов не найдено")
        
        return token_count + generation_count
        
    except Exception as e:
        logger.error(f"❌ Ошибка при удалении старых токенов: {e}")
        return 0


def renew_subscriptions():
    """
    Автоматически пополняет лимиты токенов для подписок
    
    Эта задача проверяет все активные подписки и пополняет лимиты токенов
    когда наступает дата next_renewal.
    """
    try:
        from generator.models import TemporaryAccessToken
        
        now = timezone.now()
        
        # Находим все подписки, которые нужно пополнить
        subscriptions_to_renew = TemporaryAccessToken.objects.filter(
            is_active=True,
            next_renewal__lte=now,
            next_renewal__isnull=False
        )
        
        count = 0
        for token in subscriptions_to_renew:
            if token.renew_subscription():
                count += 1
        
        if count > 0:
            logger.info(f"🔄 Автопополнение: обновлено {count} подписок")
        else:
            logger.debug("🔄 Автопополнение: подписок для обновления не найдено")
        
        return count
        
    except Exception as e:
        logger.error(f"❌ Ошибка при автопополнении подписок: {e}")
        return 0


# Глобальный экземпляр планировщика
scheduler = None


def start_scheduler():
    """
    Запускает планировщик фоновых задач
    
    Настраивает и запускает APScheduler с задачами:
    - Деактивация истекших токенов: каждый час
    - Автопополнение подписок: каждый день в 00:01
    - Удаление старых токенов: каждое воскресенье в 03:00
    """
    global scheduler
    
    # Проверяем что планировщик еще не запущен
    if scheduler is not None:
        logger.warning("⚠️ Планировщик уже запущен")
        return
    
    try:
        # Создаем планировщик
        scheduler = BackgroundScheduler(
            timezone=settings.TIME_ZONE if hasattr(settings, 'TIME_ZONE') else 'UTC'
        )
        
        # Задача 1: Деактивация истекших токенов
        # Запускается каждый час в :00
        scheduler.add_job(
            cleanup_expired_tokens,
            trigger=CronTrigger(minute=0),  # Каждый час
            id='cleanup_expired_tokens',
            name='Деактивация истекших токенов',
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=300  # 5 минут
        )
        
        # Задача 2: Автопополнение подписок
        # Запускается каждый день в 00:01
        scheduler.add_job(
            renew_subscriptions,
            trigger=CronTrigger(hour=0, minute=1),  # Каждый день в 00:01
            id='renew_subscriptions',
            name='Автопополнение подписок',
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=3600  # 1 час
        )
        
        # Задача 3: Удаление старых токенов
        # Запускается каждое воскресенье в 03:00
        scheduler.add_job(
            delete_old_tokens,
            trigger=CronTrigger(day_of_week='sun', hour=3, minute=0),  # Воскресенье 03:00
            id='delete_old_tokens',
            name='Удаление старых токенов',
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=7200  # 2 часа
        )
        
        # Запускаем планировщик
        scheduler.start()
        
        logger.info("=" * 70)
        logger.info("🤖 Планировщик фоновых задач запущен!")
        logger.info("=" * 70)
        logger.info("📋 Активные задачи:")
        logger.info("  1️⃣ Деактивация истекших токенов - каждый час")
        logger.info("  2️⃣ Автопополнение подписок - каждый день в 00:01")
        logger.info("  3️⃣ Удаление старых токенов - воскресенье в 03:00")
        logger.info("=" * 70)
        
        # Запускаем первую очистку сразу при старте
        logger.info("🚀 Запуск начальной очистки...")
        cleanup_expired_tokens()
        
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске планировщика: {e}")
        scheduler = None


def stop_scheduler():
    """
    Останавливает планировщик фоновых задач
    
    Вызывается при завершении работы приложения.
    """
    global scheduler
    
    if scheduler is not None:
        try:
            scheduler.shutdown(wait=False)
            logger.info("🛑 Планировщик фоновых задач остановлен")
            scheduler = None
        except Exception as e:
            logger.error(f"❌ Ошибка при остановке планировщика: {e}")


def get_scheduler_status():
    """
    Возвращает статус планировщика и информацию о задачах
    
    Returns:
        dict: Словарь с информацией о статусе и задачах
    """
    global scheduler
    
    if scheduler is None:
        return {
            'running': False,
            'jobs': []
        }
    
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            'id': job.id,
            'name': job.name,
            'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
            'trigger': str(job.trigger)
        })
    
    return {
        'running': scheduler.running,
        'jobs': jobs
    }
