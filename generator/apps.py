import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class GeneratorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'generator'
    
    def ready(self):
        """
        Вызывается когда Django приложение готово к работе
        
        Запускает планировщик фоновых задач для автоматической
        очистки токенов и других периодических операций.
        """
        # Импортируем здесь чтобы избежать ошибок при миграциях
        import sys
        
        # Не запускаем планировщик при выполнении команд управления
        # (migrate, makemigrations, collectstatic и т.д.)
        if 'runserver' in sys.argv or 'gunicorn' in sys.argv[0]:
            try:
                from .scheduler import start_scheduler
                start_scheduler()
            except Exception as e:
                logger.error(f"Не удалось запустить планировщик: {e}")
