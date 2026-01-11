from .models import UserProfile, Generation, TemporaryAccessToken, GenerationTemplate
from django.contrib import admin
from django.utils.html import format_html


@admin.register(TemporaryAccessToken)
class TemporaryAccessTokenAdmin(admin.ModelAdmin):
    """
    Административная панель для управления временными токенами доступа
    """
    list_display = [
        'token_display',
        'token_type',
        'created_at',
        'expires_at',
        'is_active_display',
        'daily_generations_left',
        'total_used',
        'last_used'
    ]
    
    list_filter = [
        'token_type',
        'is_active',
        'created_at',
        'expires_at'
    ]
    
    search_fields = [
        'token',
        'current_ip'
    ]
    
    readonly_fields = [
        'token',
        'created_at',
        'last_used',
        'current_ip',
        'total_used'
    ]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('token', 'token_type', 'is_active')
        }),
        ('Временные рамки', {
            'fields': ('created_at', 'expires_at')
        }),
        ('Лимиты использования', {
            'fields': ('daily_generations_left', 'generations_reset_date', 'total_used'),
            'description': 'Для DEMO токенов применяется дневной лимит генераций'
        }),
        ('Технические данные', {
            'fields': ('last_used', 'current_ip'),
            'classes': ('collapse',)
        }),
    )
    
    def token_display(self, obj):
        """Отображение токена с копированием"""
        return format_html(
            '<code style="background: #f0f0f0; padding: 2px 5px; border-radius: 3px;">{}</code>',
            str(obj.token)
        )
    token_display.short_description = 'Токен'
    
    def is_active_display(self, obj):
        """Красивое отображение статуса активности"""
        if obj.is_active and not obj.is_expired():
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Активен</span>'
            )
        elif obj.is_expired():
            return format_html(
                '<span style="color: orange;">⏰ Истек</span>'
            )
        else:
            return format_html(
                '<span style="color: red;">✗ Деактивирован</span>'
            )
    is_active_display.short_description = 'Статус'
    
    actions = ['deactivate_tokens', 'activate_tokens', 'reset_daily_limits']
    
    def deactivate_tokens(self, request, queryset):
        """Действие для деактивации выбранных токенов"""
        count = queryset.update(is_active=False)
        self.message_user(request, f'Деактивировано токенов: {count}')
    deactivate_tokens.short_description = 'Деактивировать выбранные токены'
    
    def activate_tokens(self, request, queryset):
        """Действие для активации выбранных токенов"""
        count = queryset.update(is_active=True)
        self.message_user(request, f'Активировано токенов: {count}')
    activate_tokens.short_description = 'Активировать выбранные токены'
    
    def reset_daily_limits(self, request, queryset):
        """Действие для сброса дневных лимитов для DEMO токенов"""
        demo_tokens = queryset.filter(token_type='DEMO')
        count = demo_tokens.update(daily_generations_left=5)
        self.message_user(request, f'Сброшено лимитов для {count} DEMO токенов')
    reset_daily_limits.short_description = 'Сбросить дневные лимиты (DEMO)'


@admin.register(GenerationTemplate)
class GenerationTemplateAdmin(admin.ModelAdmin):
    """
    Административная панель для шаблонов генерации
    """
    list_display = ['name', 'user', 'is_default', 'created_at', 'updated_at']
    list_filter = ['is_default', 'created_at', 'updated_at']
    search_fields = ['name', 'user__username']
    readonly_fields = ['created_at', 'updated_at']


admin.site.register(UserProfile)
admin.site.register(Generation) 