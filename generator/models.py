"""
Django модели для системы генерации контента

Модели:
- UserProfile: Расширенный профиль пользователя
- Generation: Сгенерированный контент (текст + изображения)
- GenerationTemplate: Сохраненные шаблоны настроек генерации
- TemporaryAccessToken: Временные токены доступа для анонимных пользователей
- GigaChatTokenUsage: Отслеживание расхода токенов GigaChat
- SubscriptionButtonClick: Отслеживание кликов по кнопке подписки
- Payment: Платежи пользователей (ЮКасса, Тинькофф)
"""

import uuid
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    """
    Расширенный профиль пользователя (legacy, используется только для совместимости)
    
    ВАЖНО: Регистрация пользователей отключена, используется система токенов.
    Эта модель оставлена только для обратной совместимости с существующими данными.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
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
    через временные токены с различными ограничениями по типу и лимитам токенов.
    
    Типы токенов:
    - DEMO_FREE: Бесплатный старт (бессрочный, одноразовый)
    - BASIC: Базовый (500₽/мес, подписка)
    - PRO: Про (1500₽/мес, подписка)
    - UNLIMITED: Безлимит (3500₽/мес, подписка)
    - HIDDEN_14D: Скрытый 14 дней (только manual)
    - HIDDEN_30D: Скрытый 30 дней (только manual)
    - DEVELOPER: Разработчик (бессрочный, безлимит)
    """
    TOKEN_TYPES = (
        ('DEMO_FREE', 'Бесплатный старт'),
        ('BASIC', 'Базовый (500₽/мес)'),
        ('PRO', 'Про (1500₽/мес)'),
        ('UNLIMITED', 'Безлимит (3500₽/мес)'),
        ('HIDDEN_14D', 'Скрытый 14 дней'),
        ('HIDDEN_30D', 'Скрытый 30 дней'),
        ('DEVELOPER', 'Разработчик'),
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
        max_length=20, 
        choices=TOKEN_TYPES,
        verbose_name="Тип токена"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата истечения",
        help_text="Токен становится недействительным после этой даты (None = бессрочный)"
    )
    
    # Лимиты токенов GigaChat
    gigachat_tokens_limit = models.IntegerField(
        default=-1,
        verbose_name="Лимит токенов GigaChat",
        help_text="-1 = безлимит, 0+ = количество токенов"
    )
    gigachat_tokens_used = models.IntegerField(
        default=0,
        verbose_name="Использовано токенов GigaChat",
        help_text="Текущее использование токенов GigaChat"
    )
    
    # Лимиты токенов OpenAI
    openai_tokens_limit = models.IntegerField(
        default=0,
        verbose_name="Лимит токенов OpenAI",
        help_text="-1 = безлимит, 0 = недоступен, 0+ = количество токенов"
    )
    openai_tokens_used = models.IntegerField(
        default=0,
        verbose_name="Использовано токенов OpenAI",
        help_text="Текущее использование токенов OpenAI"
    )
    
    # Подписки (для платных тарифов)
    subscription_start = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата начала подписки",
        help_text="Дата начала подписки (для автопополнения)"
    )
    next_renewal = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Следующее пополнение",
        help_text="Дата следующего автоматического пополнения лимитов"
    )
    
    # Статистика использования (legacy, оставляем для совместимости)
    total_used = models.IntegerField(
        default=0,
        verbose_name="Всего использований",
        help_text="Общее количество генераций через этот токен (legacy)"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен",
        help_text="Неактивные токены не могут быть использованы"
    )
    
    # Telegram пользователь (для защиты от мультиаккаунтов)
    telegram_user_id = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name="Telegram User ID",
        help_text="ID пользователя в Telegram (для защиты от мультиаккаунтов)"
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
            models.Index(fields=['telegram_user_id', 'token_type', 'is_active']),
            models.Index(fields=['telegram_user_id', 'is_active']),
        ]
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['is_active', 'expires_at']),
        ]
    
    def __str__(self):
        return f"{self.get_token_type_display()} - {self.token} (истекает {self.expires_at.strftime('%d.%m.%Y')})"
    
    def is_expired(self):
        """Проверяет, истек ли срок действия токена"""
        # DEVELOPER и бессрочные токены никогда не истекают
        if self.token_type == 'DEVELOPER' or self.expires_at is None:
            return False
        return timezone.now() > self.expires_at
    
    def can_use_gigachat(self):
        """
        Проверяет, может ли токен использовать GigaChat
        
        Returns:
            tuple: (bool, str) - (может использовать, причина если нет)
        """
        if not self.is_active or self.is_expired():
            return False, "Токен неактивен или истёк"
        
        # Безлимит
        if self.gigachat_tokens_limit == -1:
            return True, None
        
        # Проверяем лимит
        if self.gigachat_tokens_used >= self.gigachat_tokens_limit:
            return False, "Лимит токенов GigaChat исчерпан"
        
        return True, None
    
    def can_use_openai(self):
        """
        Проверяет, может ли токен использовать OpenAI
        
        Returns:
            tuple: (bool, str) - (может использовать, причина если нет)
        """
        if not self.is_active or self.is_expired():
            return False, "Токен неактивен или истёк"
        
        # OpenAI недоступен
        if self.openai_tokens_limit == 0:
            return False, "OpenAI недоступен для этого тарифа"
        
        # Безлимит
        if self.openai_tokens_limit == -1:
            return True, None
        
        # Проверяем лимит
        if self.openai_tokens_used >= self.openai_tokens_limit:
            return False, "Лимит токенов OpenAI исчерпан"
        
        return True, None
    
    def consume_gigachat_tokens(self, tokens_count):
        """
        Увеличивает счётчик использованных токенов GigaChat
        
        Args:
            tokens_count (int): Количество использованных токенов
        
        Returns:
            bool: True если успешно, False если превышен лимит
        """
        if self.gigachat_tokens_limit == -1:
            # Безлимит - просто увеличиваем счётчик
            self.gigachat_tokens_used += tokens_count
            self.save()
            return True
        
        if self.gigachat_tokens_used + tokens_count > self.gigachat_tokens_limit:
            return False
        
        self.gigachat_tokens_used += tokens_count
        self.save()
        return True
    
    def consume_openai_tokens(self, tokens_count):
        """
        Увеличивает счётчик использованных токенов OpenAI
        
        Args:
            tokens_count (int): Количество использованных токенов
        
        Returns:
            bool: True если успешно, False если превышен лимит
        """
        if self.openai_tokens_limit == -1:
            # Безлимит - просто увеличиваем счётчик
            self.openai_tokens_used += tokens_count
            self.save()
            return True
        
        if self.openai_tokens_limit == 0:
            return False
        
        if self.openai_tokens_used + tokens_count > self.openai_tokens_limit:
            return False
        
        self.openai_tokens_used += tokens_count
        self.save()
        return True
    
    def can_generate(self):
        """
        Проверяет, может ли токен использоваться для генерации
        (legacy метод для обратной совместимости)
        """
        if not self.is_active or self.is_expired():
            return False
        
        # DEVELOPER токены имеют неограниченные генерации
        if self.token_type == 'DEVELOPER':
            return True
        
        # Проверяем хотя бы один из лимитов (GigaChat или OpenAI)
        can_gc, _ = self.can_use_gigachat()
        can_oa, _ = self.can_use_openai()
        
        # Если хотя бы один доступен - можно генерировать
        return can_gc or can_oa
    
    def consume_generation(self, ip_address=None):
        """
        Обновляет статистику использования (legacy метод)
        
        Args:
            ip_address (str): IP адрес пользователя для логирования
        """
        self.total_used += 1
        self.last_used = timezone.now()
        if ip_address:
            self.current_ip = ip_address
        self.save()
    
    def renew_subscription(self):
        """
        Пополняет лимиты токенов для подписки
        
        Вызывается автоматически при наступлении next_renewal
        """
        from .tariffs import get_tariff_config
        
        tariff = get_tariff_config(self.token_type)
        if not tariff or not tariff.get('is_subscription'):
            return False
        
        # Сбрасываем использованные токены
        self.gigachat_tokens_used = 0
        self.openai_tokens_used = 0
        
        # Обновляем дату следующего пополнения
        if self.next_renewal:
            from datetime import timedelta
            self.next_renewal = self.next_renewal + timedelta(days=tariff['duration_days'])
        else:
            from datetime import timedelta
            self.next_renewal = timezone.now() + timedelta(days=tariff['duration_days'])
        
        self.save()
        return True


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


class Payment(models.Model):
    """
    Платежи пользователей
    
    Хранит информацию о платежах через ЮКасса и другие системы.
    Связывает платёж с токеном доступа после успешной оплаты.
    """
    PAYMENT_STATUS = (
        ('pending', 'Ожидает оплаты'),
        ('succeeded', 'Оплачен'),
        ('canceled', 'Отменён'),
        ('refunded', 'Возврат'),
    )
    
    PAYMENT_SYSTEMS = (
        ('yookassa', 'ЮКасса'),
        ('tinkoff', 'Тинькофф Касса'),
    )
    
    # Идентификаторы
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="ID платежа"
    )
    external_id = models.CharField(
        max_length=255,
        unique=True,
        verbose_name="Внешний ID",
        help_text="ID платежа в платёжной системе (ЮКасса/Тинькофф)"
    )
    
    # Telegram пользователь
    telegram_user_id = models.BigIntegerField(
        verbose_name="Telegram User ID",
        help_text="ID пользователя в Telegram"
    )
    telegram_username = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Telegram Username",
        help_text="Username пользователя в Telegram (если есть)"
    )
    
    # Данные о платеже
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Сумма",
        help_text="Сумма платежа в рублях"
    )
    currency = models.CharField(
        max_length=3,
        default='RUB',
        verbose_name="Валюта"
    )
    
    # Статус и система
    status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS,
        default='pending',
        verbose_name="Статус"
    )
    payment_system = models.CharField(
        max_length=20,
        choices=PAYMENT_SYSTEMS,
        default='yookassa',
        verbose_name="Платёжная система"
    )
    
    # Связь с токеном (создаётся после успешной оплаты)
    token = models.OneToOneField(
        TemporaryAccessToken,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment',
        verbose_name="Выданный токен"
    )
    
    # Описание (тариф)
    description = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Описание",
        help_text="Описание платежа (например, '30 дней подписки')"
    )
    
    # Временные метки
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Создан"
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Оплачен"
    )
    
    # URL для оплаты (сохраняем для возможности повторного использования)
    payment_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="Ссылка на оплату"
    )
    
    # Метаданные (raw response от платёжной системы)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Метаданные",
        help_text="Дополнительные данные от платёжной системы"
    )
    
    class Meta:
        verbose_name = "Платёж"
        verbose_name_plural = "Платежи"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['telegram_user_id']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['external_id']),
        ]
    
    def __str__(self):
        user_info = self.telegram_username or f"ID:{self.telegram_user_id}"
        return f"{user_info} - {self.amount} {self.currency} - {self.get_status_display()}"
    
    @classmethod
    def get_statistics(cls, days=30):
        """
        Получить статистику платежей за последние N дней
        
        Args:
            days: Количество дней для анализа
        
        Returns:
            dict: Статистика платежей
        """
        from datetime import timedelta
        from django.db.models import Sum, Count
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        queryset = cls.objects.filter(created_at__gte=cutoff_date)
        
        total_payments = queryset.count()
        successful_payments = queryset.filter(status='succeeded').count()
        total_revenue = queryset.filter(status='succeeded').aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        # По статусам
        by_status = {}
        for status_code, status_name in cls.PAYMENT_STATUS:
            count = queryset.filter(status=status_code).count()
            by_status[status_code] = {
                'name': status_name,
                'count': count
            }
        
        # По дням
        by_day = {}
        for i in range(min(days, 30)):  # Максимум 30 дней в детализации
            day = timezone.now().date() - timedelta(days=i)
            count = queryset.filter(status='succeeded', paid_at__date=day).count()
            revenue = queryset.filter(status='succeeded', paid_at__date=day).aggregate(
                total=Sum('amount')
            )['total'] or 0
            by_day[day.isoformat()] = {
                'count': count,
                'revenue': float(revenue)
            }
        
        return {
            'total_payments': total_payments,
            'successful_payments': successful_payments,
            'total_revenue': float(total_revenue),
            'conversion_rate': (successful_payments / total_payments * 100) if total_payments > 0 else 0,
            'by_status': by_status,
            'by_day': by_day,
            'period_days': days
        }

