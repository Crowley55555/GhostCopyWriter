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
        
        # Находим все истекшие активные токены
        expired_tokens = TemporaryAccessToken.objects.filter(
            expires_at__lt=now,
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
    
    Это помогает поддерживать базу данных в чистоте.
    """
    try:
        from generator.models import TemporaryAccessToken
        
        # Вычисляем дату отсечки (90 дней назад)
        cutoff_date = timezone.now() - timedelta(days=90)
        
        # Находим старые деактивированные токены
        old_tokens = TemporaryAccessToken.objects.filter(
            is_active=False,
            expires_at__lt=cutoff_date
        )
        
        count = old_tokens.count()
        
        if count > 0:
            # Удаляем их
            old_tokens.delete()
            logger.info(f"🗑️ Автоматическая очистка: удалено {count} старых токенов (>90 дней)")
        else:
            logger.debug("🗑️ Автоматическая очистка: старых токенов не найдено")
        
        return count
        
    except Exception as e:
        logger.error(f"❌ Ошибка при удалении старых токенов: {e}")
        return 0


def reset_demo_limits():
    """
    Сбрасывает дневные лимиты для DEMO токенов в начале каждого дня
    
    Эта задача гарантирует, что даже если пользователь не заходил в приложение,
    его лимит будет сброшен на следующий день.
    """
    try:
        from generator.models import TemporaryAccessToken
        
        today = timezone.now().date()
        
        # Находим все DEMO токены с устаревшей датой сброса
        demo_tokens = TemporaryAccessToken.objects.filter(
            token_type='DEMO',
            is_active=True,
            generations_reset_date__lt=today
        )
        
        count = demo_tokens.count()
        
        if count > 0:
            # Сбрасываем лимиты
            demo_tokens.update(
                daily_generations_left=5,
                generations_reset_date=today
            )
            logger.info(f"🔄 Автоматический сброс: обновлено {count} DEMO токенов")
        else:
            logger.debug("🔄 Автоматический сброс: токенов для сброса не найдено")
        
        return count
        
    except Exception as e:
        logger.error(f"❌ Ошибка при сбросе DEMO лимитов: {e}")
        return 0


# Глобальный экземпляр планировщика
scheduler = None


def start_scheduler():
    """
    Запускает планировщик фоновых задач
    
    Настраивает и запускает APScheduler с задачами:
    - Деактивация истекших токенов: каждый час
    - Сброс DEMO лимитов: каждый день в 00:01
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
        
        # Задача 2: Сброс дневных лимитов DEMO токенов
        # Запускается каждый день в 00:01
        scheduler.add_job(
            reset_demo_limits,
            trigger=CronTrigger(hour=0, minute=1),  # Каждый день в 00:01
            id='reset_demo_limits',
            name='Сброс дневных лимитов DEMO',
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
        logger.info("  2️⃣ Сброс DEMO лимитов - каждый день в 00:01")
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
