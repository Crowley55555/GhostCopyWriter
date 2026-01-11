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
    - DEMO: 5 дней, 5 генераций в день
    - MONTHLY: 30 дней, безлимитные генерации
    - YEARLY: 365 дней, безлимитные генерации
    """
    TOKEN_TYPES = (
        ('DEMO', 'Демо (5 дней, 5 ген./день)'),
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
    
    # Лимиты для демо режима
    daily_generations_left = models.IntegerField(
        default=0,
        verbose_name="Осталось генераций сегодня",
        help_text="Для DEMO: количество генераций доступных сегодня (обнуляется каждый день)"
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

