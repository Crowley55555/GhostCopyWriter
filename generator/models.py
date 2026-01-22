"""
Django модели для системы генерации контента

Модели:
- UserProfile: Расширенный профиль пользователя
- Generation: Сгенерированный контент (текст + изображения)
- GenerationTemplate: Сохраненные шаблоны настроек генерации
- TemporaryAccessToken: Временные токены доступа для анонимных пользователей
"""

import uuid
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    """
    Расширенный профиль пользователя
    
    Хранит дополнительную информацию о пользователе:
    личные данные, контакты, биографию, аватар
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=50, blank=True, verbose_name="Имя")
    last_name = models.CharField(max_length=50, blank=True, verbose_name="Фамилия")
    city = models.CharField(max_length=100, blank=True, verbose_name="Город")
    phone = models.CharField(max_length=30, blank=True, verbose_name="Телефон")
    date_of_birth = models.DateField(blank=True, null=True, verbose_name="Дата рождения")
    bio = models.TextField(blank=True, verbose_name="О себе")
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name="Аватар")
    terms_accepted = models.BooleanField(default=False, verbose_name="Принял условия")

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"

    def __str__(self):
        return f"Профиль: {self.user.username}"


class Generation(models.Model):
    """
    Сгенерированный контент пользователя
    
    Хранит результаты генерации текста и изображений.
    Поддерживает множественные версии через разделители:
    - Текст: разделен "--- Перегенерация N ---"
    - Изображения: разделены символом "|"
    """
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='generations', 
        null=True, 
        blank=True,
        verbose_name="Пользователь"
    )
    topic = models.TextField(verbose_name="Тема")
    result = models.TextField(verbose_name="Сгенерированный текст")
    image_url = models.CharField(
        max_length=512, 
        blank=True, 
        null=True,
        verbose_name="URL изображения(й)",
        help_text="Множественные URL разделены символом |"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Генерация"
        verbose_name_plural = "Генерации"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username if self.user else 'Аноним'}: {self.topic[:30]}..."


class GenerationTemplate(models.Model):
    """
    Шаблоны настроек генерации
    
    Позволяет пользователям сохранять и переиспользовать
    наборы параметров для генерации контента
    """
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='generation_templates',
        verbose_name="Пользователь"
    )
    name = models.CharField(max_length=100, verbose_name="Название шаблона")
    settings = models.JSONField(verbose_name="Настройки", help_text="JSON с параметрами генерации")
    is_default = models.BooleanField(default=False, verbose_name="По умолчанию")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        unique_together = ('user', 'name')
        ordering = ['-updated_at']
        verbose_name = "Шаблон генерации"
        verbose_name_plural = "Шаблоны генерации"

    def __str__(self):
        return f"{self.user.username}: {self.name}"


class TemporaryAccessToken(models.Model):
    """
    Временные токены доступа для анонимных пользователей
    
    Позволяет пользователям получать доступ к приложению без регистрации
    через временные токены с различными ограничениями по типу.
    
    Типы токенов:
    - DEMO: 7 дней, безлимитные генерации
    - MONTHLY: 30 дней, безлимитные генерации
    - YEARLY: 365 дней, безлимитные генерации
    """
    TOKEN_TYPES = (
        ('DEMO', 'Демо (7 дней, безлимит)'),
        ('MONTHLY', '30 дней'),
        ('YEARLY', '365 дней'),
        ('DEVELOPER', 'Разработчик (бессрочный, безлимит)'),
    )
    
    # Уникальный токен (UUID) - без связи с User для анонимного доступа
    token = models.UUIDField(
        default=uuid.uuid4, 
        unique=True, 
        editable=False,
        verbose_name="Токен",
        help_text="Уникальный идентификатор токена доступа"
    )
    
    # Тип токена и время жизни
    token_type = models.CharField(
        max_length=10, 
        choices=TOKEN_TYPES,
        verbose_name="Тип токена"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )
    expires_at = models.DateTimeField(
        verbose_name="Дата истечения",
        help_text="Токен становится недействительным после этой даты"
    )
    
    # Лимиты генераций (не используется для DEMO, -1 = безлимит)
    daily_generations_left = models.IntegerField(
        default=-1,
        verbose_name="Осталось генераций сегодня",
        help_text="-1 = безлимит, 0+ = количество генераций (устаревшее поле)"
    )
    generations_reset_date = models.DateField(
        null=True, 
        blank=True,
        verbose_name="Дата сброса счетчика",
        help_text="Дата последнего сброса счетчика генераций"
    )
    
    # Статистика использования
    total_used = models.IntegerField(
        default=0,
        verbose_name="Всего использований",
        help_text="Общее количество генераций через этот токен"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен",
        help_text="Неактивные токены не могут быть использованы"
    )
    
    # Сессионные данные (технические, не ПДн)
    last_used = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name="Последнее использование",
        help_text="Время последней генерации с этим токеном"
    )
    current_ip = models.GenericIPAddressField(
        null=True, 
        blank=True,
        verbose_name="Текущий IP",
        help_text="IP адрес последнего использования (для технической диагностики)"
    )
    
    class Meta:
        verbose_name = "Временный токен доступа"
        verbose_name_plural = "Временные токены доступа"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['is_active', 'expires_at']),
        ]
    
    def __str__(self):
        return f"{self.get_token_type_display()} - {self.token} (истекает {self.expires_at.strftime('%d.%m.%Y')})"
    
    def is_expired(self):
        """Проверяет, истек ли срок действия токена"""
        # DEVELOPER токены никогда не истекают
        if self.token_type == 'DEVELOPER':
            return False
        return timezone.now() > self.expires_at
    
    def reset_daily_limit(self):
        """Сбрасывает дневной лимит генераций для DEMO токенов"""
        if self.token_type == 'DEMO':
            today = timezone.now().date()
            if self.generations_reset_date != today:
                self.daily_generations_left = 5
                self.generations_reset_date = today
                self.save()
    
    def can_generate(self):
        """Проверяет, может ли токен использоваться для генерации"""
        if not self.is_active or self.is_expired():
            return False
        
        # DEVELOPER токены имеют неограниченные генерации
        if self.token_type == 'DEVELOPER':
            return True
        
        if self.token_type == 'DEMO':
            self.reset_daily_limit()
            return self.daily_generations_left > 0
        
        return True
    
    def consume_generation(self, ip_address=None):
        """
        Уменьшает счетчик генераций и обновляет статистику
        
        Args:
            ip_address (str): IP адрес пользователя для логирования
        """
        # DEVELOPER токены не имеют лимитов
        if self.token_type == 'DEMO':
            if self.daily_generations_left > 0:
                self.daily_generations_left -= 1
        
        self.total_used += 1
        self.last_used = timezone.now()
        if ip_address:
            self.current_ip = ip_address
        self.save()


class GigaChatTokenUsage(models.Model):
    """
    Отслеживание расхода токенов GigaChat API
    
    Хранит информацию о каждом запросе к GigaChat API:
    - Тип операции (текст, промпт изображения, генерация изображения)
    - Количество использованных токенов (оценка)
    - Связь с генерацией и пользователем
    """
    OPERATION_TYPES = (
        ('TEXT_GENERATION', 'Генерация текста'),
        ('IMAGE_PROMPT', 'Промпт для изображения'),
        ('IMAGE_GENERATION', 'Генерация изображения'),
    )
    
    # Связь с генерацией (опционально)
    generation = models.ForeignKey(
        Generation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='token_usages',
        verbose_name="Генерация"
    )
    
    # Связь с пользователем или токеном
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='gigachat_token_usages',
        verbose_name="Пользователь"
    )
    token = models.ForeignKey(
        TemporaryAccessToken,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='gigachat_token_usages',
        verbose_name="Токен доступа"
    )
    
    # Тип операции и метаданные
    operation_type = models.CharField(
        max_length=20,
        choices=OPERATION_TYPES,
        verbose_name="Тип операции"
    )
    
    # Оценка токенов (на основе длины промпта и ответа)
    estimated_prompt_tokens = models.IntegerField(
        default=0,
        verbose_name="Токенов в промпте (оценка)"
    )
    estimated_completion_tokens = models.IntegerField(
        default=0,
        verbose_name="Токенов в ответе (оценка)"
    )
    estimated_total_tokens = models.IntegerField(
        default=0,
        verbose_name="Всего токенов (оценка)"
    )
    
    # Метаданные запроса
    prompt_length = models.IntegerField(
        default=0,
        verbose_name="Длина промпта (символов)",
        help_text="Общая длина промпта в символах"
    )
    response_length = models.IntegerField(
        default=0,
        verbose_name="Длина ответа (символов)",
        help_text="Длина ответа от API в символах"
    )
    
    # Временные метки
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )
    
    # Дополнительная информация
    topic = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Тема генерации"
    )
    platform = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Платформа"
    )
    
    class Meta:
        verbose_name = "Использование токенов GigaChat"
        verbose_name_plural = "Использование токенов GigaChat"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['operation_type', 'created_at']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['token', 'created_at']),
            models.Index(fields=['generation']),
        ]
    
    def __str__(self):
        user_info = self.user.username if self.user else (str(self.token.token)[:8] if self.token else 'Аноним')
        return f"{self.get_operation_type_display()} - {user_info} - {self.estimated_total_tokens} токенов"
    
    @classmethod
    def get_total_tokens(cls, start_date=None, end_date=None, operation_type=None):
        """
        Получить общее количество использованных токенов за период
        
        Args:
            start_date: Начальная дата (опционально)
            end_date: Конечная дата (опционально)
            operation_type: Тип операции (опционально)
        
        Returns:
            int: Общее количество токенов
        """
        queryset = cls.objects.all()
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        if operation_type:
            queryset = queryset.filter(operation_type=operation_type)
        
        return queryset.aggregate(
            total=models.Sum('estimated_total_tokens')
        )['total'] or 0
    
    @classmethod
    def get_statistics(cls, days=7):
        """
        Получить статистику использования токенов за последние N дней
        
        Args:
            days: Количество дней для анализа
        
        Returns:
            dict: Статистика использования
        """
        from datetime import timedelta
        cutoff_date = timezone.now() - timedelta(days=days)
        
        queryset = cls.objects.filter(created_at__gte=cutoff_date)
        
        total_tokens = queryset.aggregate(
            total=models.Sum('estimated_total_tokens')
        )['total'] or 0
        
        by_operation = {}
        for op_type, op_name in cls.OPERATION_TYPES:
            count = queryset.filter(operation_type=op_type).count()
            tokens = queryset.filter(operation_type=op_type).aggregate(
                total=models.Sum('estimated_total_tokens')
            )['total'] or 0
            by_operation[op_type] = {
                'name': op_name,
                'count': count,
                'tokens': tokens
            }
        
        return {
            'total_tokens': total_tokens,
            'total_requests': queryset.count(),
            'by_operation': by_operation,
            'period_days': days
        }


class SubscriptionButtonClick(models.Model):
    """
    Отслеживание кликов по кнопке "Купить доступ"
    
    Хранит информацию о каждом клике по кнопке подписки:
    - Страница, с которой был клик
    - Пользователь или токен (если есть)
    - IP адрес
    - User-Agent
    - Референр
    """
    # Связь с пользователем или токеном
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subscription_clicks',
        verbose_name="Пользователь"
    )
    token = models.ForeignKey(
        TemporaryAccessToken,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subscription_clicks',
        verbose_name="Токен доступа"
    )
    
    # Информация о клике
    page_url = models.CharField(
        max_length=500,
        verbose_name="URL страницы",
        help_text="Страница, с которой был сделан клик"
    )
    page_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Название страницы",
        help_text="Название страницы (например, 'profile', 'landing')"
    )
    
    # Техническая информация
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP адрес"
    )
    user_agent = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="User-Agent"
    )
    referer = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="Referer"
    )
    
    # Временная метка
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата и время клика"
    )
    
    class Meta:
        verbose_name = "Клик по кнопке подписки"
        verbose_name_plural = "Клики по кнопке подписки"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['page_name', 'created_at']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['token', 'created_at']),
        ]
    
    def __str__(self):
        user_info = self.user.username if self.user else (str(self.token.token)[:8] if self.token else 'Аноним')
        page = self.page_name or self.page_url[:50]
        return f"{page} - {user_info} - {self.created_at.strftime('%d.%m.%Y %H:%M')}"
    
    @classmethod
    def get_statistics(cls, days=7):
        """
        Получить статистику кликов за последние N дней
        
        Args:
            days: Количество дней для анализа
        
        Returns:
            dict: Статистика кликов
        """
        from datetime import timedelta
        cutoff_date = timezone.now() - timedelta(days=days)
        
        queryset = cls.objects.filter(created_at__gte=cutoff_date)
        
        total_clicks = queryset.count()
        
        # Статистика по страницам
        by_page = {}
        for page_name in queryset.values_list('page_name', flat=True).distinct():
            if page_name:
                count = queryset.filter(page_name=page_name).count()
                by_page[page_name] = count
        
        # Статистика по дням
        by_day = {}
        for i in range(days):
            day = timezone.now().date() - timedelta(days=i)
            count = queryset.filter(created_at__date=day).count()
            by_day[day.isoformat()] = count
        
        # Статистика по пользователям/токенам
        user_clicks = queryset.filter(user__isnull=False).count()
        token_clicks = queryset.filter(token__isnull=False, user__isnull=True).count()
        anonymous_clicks = queryset.filter(user__isnull=True, token__isnull=True).count()
        
        return {
            'total_clicks': total_clicks,
            'by_page': by_page,
            'by_day': by_day,
            'user_clicks': user_clicks,
            'token_clicks': token_clicks,
            'anonymous_clicks': anonymous_clicks,
            'period_days': days
        }
    
    @classmethod
    def get_total_clicks(cls, start_date=None, end_date=None, page_name=None):
        """
        Получить общее количество кликов за период
        
        Args:
            start_date: Начальная дата (опционально)
            end_date: Конечная дата (опционально)
            page_name: Название страницы (опционально)
        
        Returns:
            int: Общее количество кликов
        """
        queryset = cls.objects.all()
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        if page_name:
            queryset = queryset.filter(page_name=page_name)
        
        return queryset.count()

