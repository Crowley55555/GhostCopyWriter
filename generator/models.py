"""
Django модели для системы генерации контента

Модели:
- UserProfile: Расширенный профиль пользователя
- Generation: Сгенерированный контент (текст + изображения)
- GenerationTemplate: Сохраненные шаблоны настроек генерации
"""

from django.contrib.auth.models import User
from django.db import models


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

