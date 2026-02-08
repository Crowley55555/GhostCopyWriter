from .models import UserProfile, Generation, TemporaryAccessToken, GenerationTemplate, GigaChatTokenUsage, SubscriptionButtonClick, Payment, SupportTicket, Review, SupportChat
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from datetime import timedelta


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
        'gigachat_tokens_display',
        'openai_tokens_display',
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
        'total_used',
        'gigachat_tokens_used',
        'openai_tokens_used'
    ]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('token', 'token_type', 'is_active')
        }),
        ('Временные рамки', {
            'fields': ('created_at', 'expires_at')
        }),
        ('Лимиты токенов GigaChat', {
            'fields': ('gigachat_tokens_limit', 'gigachat_tokens_used'),
            'description': 'Лимит токенов GigaChat (-1 = безлимит)'
        }),
        ('Лимиты токенов OpenAI', {
            'fields': ('openai_tokens_limit', 'openai_tokens_used'),
            'description': 'Лимит токенов OpenAI (-1 = безлимит, 0 = недоступен)'
        }),
        ('Подписки', {
            'fields': ('subscription_start', 'next_renewal'),
            'description': 'Информация о подписке (для платных тарифов)',
            'classes': ('collapse',)
        }),
        ('Статистика использования', {
            'fields': ('total_used', 'last_used', 'current_ip'),
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
    
    def gigachat_tokens_display(self, obj):
        """Отображение использования токенов GigaChat"""
        if obj.gigachat_tokens_limit == -1:
            return format_html(
                '<span style="color: green;">∞ (использовано: {:,})</span>',
                obj.gigachat_tokens_used
            )
        percentage = (obj.gigachat_tokens_used / obj.gigachat_tokens_limit * 100) if obj.gigachat_tokens_limit > 0 else 0
        color = 'red' if percentage >= 100 else ('orange' if percentage >= 80 else 'green')
        return format_html(
            '<span style="color: {};">{:,} / {:,} ({:.0f}%)</span>',
            color,
            obj.gigachat_tokens_used,
            obj.gigachat_tokens_limit,
            percentage
        )
    gigachat_tokens_display.short_description = 'GigaChat'
    
    def openai_tokens_display(self, obj):
        """Отображение использования токенов OpenAI"""
        if obj.openai_tokens_limit == -1:
            return format_html(
                '<span style="color: green;">∞ (использовано: {:,})</span>',
                obj.openai_tokens_used
            )
        elif obj.openai_tokens_limit == 0:
            return format_html('<span style="color: gray;">Недоступен</span>')
        percentage = (obj.openai_tokens_used / obj.openai_tokens_limit * 100) if obj.openai_tokens_limit > 0 else 0
        color = 'red' if percentage >= 100 else ('orange' if percentage >= 80 else 'green')
        return format_html(
            '<span style="color: {};">{:,} / {:,} ({:.0f}%)</span>',
            color,
            obj.openai_tokens_used,
            obj.openai_tokens_limit,
            percentage
        )
    openai_tokens_display.short_description = 'OpenAI'
    
    actions = ['deactivate_tokens', 'activate_tokens', 'renew_subscriptions', 'reset_token_usage']
    
    def renew_subscriptions(self, request, queryset):
        """Действие для пополнения лимитов подписок"""
        count = 0
        for token in queryset:
            if token.renew_subscription():
                count += 1
        self.message_user(request, f'Пополнено лимитов для {count} подписок')
    renew_subscriptions.short_description = 'Пополнить лимиты (подписки)'
    
    def reset_token_usage(self, request, queryset):
        """Действие для сброса использованных токенов (для тестирования)"""
        count = queryset.update(
            gigachat_tokens_used=0,
            openai_tokens_used=0
        )
        self.message_user(request, f'Сброшено использование токенов для {count} записей')
    reset_token_usage.short_description = 'Сбросить использование токенов'
    
    def changelist_view(self, request, extra_context=None):
        """Добавляем статистику на страницу списка"""
        response = super().changelist_view(request, extra_context)
        
        try:
            from django.db.models import Sum, Q
            from django.utils import timezone
            
            # Общая статистика
            total_tokens = TemporaryAccessToken.objects.count()
            active_tokens = TemporaryAccessToken.objects.filter(
                is_active=True
            ).filter(
                Q(expires_at__gte=timezone.now()) | Q(expires_at__isnull=True)
            ).count()
            
            # Статистика по типам
            by_type = {}
            for token_type, _ in TemporaryAccessToken.TOKEN_TYPES:
                count = TemporaryAccessToken.objects.filter(
                    token_type=token_type,
                    is_active=True
                ).filter(
                    Q(expires_at__gte=timezone.now()) | Q(expires_at__isnull=True)
                ).count()
                by_type[token_type] = count
            
            # Общее использование токенов
            total_gigachat_used = TemporaryAccessToken.objects.aggregate(
                total=Sum('gigachat_tokens_used')
            )['total'] or 0
            total_openai_used = TemporaryAccessToken.objects.aggregate(
                total=Sum('openai_tokens_used')
            )['total'] or 0
            
            extra_context = extra_context or {}
            extra_context['token_stats'] = {
                'total_tokens': total_tokens,
                'active_tokens': active_tokens,
                'by_type': by_type,
                'total_gigachat_used': total_gigachat_used,
                'total_openai_used': total_openai_used
            }
            
            if hasattr(response, 'context_data'):
                response.context_data.update(extra_context)
        except Exception as e:
            print(f"Ошибка при расчете статистики токенов: {e}")
        
        return response


@admin.register(GenerationTemplate)
class GenerationTemplateAdmin(admin.ModelAdmin):
    """
    Административная панель для шаблонов генерации
    """
    list_display = ['name', 'user', 'is_default', 'created_at', 'updated_at']
    list_filter = ['is_default', 'created_at', 'updated_at']
    search_fields = ['name', 'user__username']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(GigaChatTokenUsage)
class GigaChatTokenUsageAdmin(admin.ModelAdmin):
    """
    Административная панель для мониторинга использования токенов GigaChat
    """
    list_display = [
        'operation_type_display',
        'user_or_token_display',
        'estimated_total_tokens',
        'topic_short',
        'platform',
        'created_at'
    ]
    
    list_filter = [
        'operation_type',
        'created_at',
        'platform'
    ]
    
    search_fields = [
        'topic',
        'user__username',
        'token__token',
        'generation__topic'
    ]
    
    readonly_fields = [
        'generation',
        'user',
        'token',
        'operation_type',
        'estimated_prompt_tokens',
        'estimated_completion_tokens',
        'estimated_total_tokens',
        'prompt_length',
        'response_length',
        'created_at',
        'topic',
        'platform'
    ]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('operation_type', 'created_at', 'topic', 'platform')
        }),
        ('Связи', {
            'fields': ('generation', 'user', 'token')
        }),
        ('Использование токенов', {
            'fields': (
                'estimated_prompt_tokens',
                'estimated_completion_tokens',
                'estimated_total_tokens',
                'prompt_length',
                'response_length'
            ),
            'description': 'Оценочные значения на основе длины промпта и ответа'
        }),
    )
    
    def operation_type_display(self, obj):
        """Отображение типа операции с цветом"""
        colors = {
            'TEXT_GENERATION': '#2196F3',
            'IMAGE_PROMPT': '#FF9800',
            'IMAGE_GENERATION': '#4CAF50'
        }
        color = colors.get(obj.operation_type, '#757575')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_operation_type_display()
        )
    operation_type_display.short_description = 'Тип операции'
    
    def user_or_token_display(self, obj):
        """Отображение пользователя или токена"""
        if obj.user:
            return format_html(
                '<span style="color: #2196F3;">👤 {}</span>',
                obj.user.username
            )
        elif obj.token:
            return format_html(
                '<span style="color: #FF9800;">🔑 {}</span>',
                str(obj.token.token)[:8]
            )
        return format_html('<span style="color: #757575;">Аноним</span>')
    user_or_token_display.short_description = 'Пользователь/Токен'
    
    def topic_short(self, obj):
        """Короткая версия темы"""
        if obj.topic:
            return obj.topic[:50] + '...' if len(obj.topic) > 50 else obj.topic
        return '-'
    topic_short.short_description = 'Тема'
    
    def get_queryset(self, request):
        """Оптимизация запросов"""
        qs = super().get_queryset(request)
        return qs.select_related('user', 'token', 'generation')
    
    def changelist_view(self, request, extra_context=None):
        """Добавляем статистику на страницу списка"""
        response = super().changelist_view(request, extra_context)
        
        try:
            # Статистика за последние 7 дней
            stats_7d = GigaChatTokenUsage.get_statistics(days=7)
            
            # Статистика за последние 30 дней
            stats_30d = GigaChatTokenUsage.get_statistics(days=30)
            
            # Общая статистика
            total_tokens = GigaChatTokenUsage.get_total_tokens()
            
            # Статистика по типам операций за все время
            by_operation = {}
            for op_type, op_name in GigaChatTokenUsage.OPERATION_TYPES:
                count = GigaChatTokenUsage.objects.filter(operation_type=op_type).count()
                tokens = GigaChatTokenUsage.objects.filter(operation_type=op_type).aggregate(
                    total=Sum('estimated_total_tokens')
                )['total'] or 0
                by_operation[op_type] = {
                    'name': op_name,
                    'count': count,
                    'tokens': tokens
                }
            
            # Стоимость (если известна цена токенов)
            # 5 млн токенов = 1000₽, значит 1 токен = 0.0002₽
            TOKEN_PRICE = 0.0002
            total_cost = total_tokens * TOKEN_PRICE
            cost_7d = stats_7d['total_tokens'] * TOKEN_PRICE
            cost_30d = stats_30d['total_tokens'] * TOKEN_PRICE
            
            extra_context = extra_context or {}
            extra_context['token_stats'] = {
                'total_tokens': total_tokens,
                'total_cost': total_cost,
                'stats_7d': stats_7d,
                'stats_30d': stats_30d,
                'cost_7d': cost_7d,
                'cost_30d': cost_30d,
                'by_operation': by_operation,
                'token_price': TOKEN_PRICE
            }
            
            if hasattr(response, 'context_data'):
                response.context_data.update(extra_context)
        except Exception as e:
            print(f"Ошибка при расчете статистики: {e}")
        
        return response


@admin.register(SubscriptionButtonClick)
class SubscriptionButtonClickAdmin(admin.ModelAdmin):
    """
    Административная панель для мониторинга кликов по кнопке "Купить доступ"
    """
    list_display = [
        'page_name_display',
        'user_or_token_display',
        'ip_address',
        'created_at'
    ]
    
    list_filter = [
        'page_name',
        'created_at',
    ]
    
    search_fields = [
        'page_url',
        'page_name',
        'user__username',
        'token__token',
        'ip_address',
        'user_agent'
    ]
    
    readonly_fields = [
        'user',
        'token',
        'page_url',
        'page_name',
        'ip_address',
        'user_agent',
        'referer',
        'created_at'
    ]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('page_name', 'page_url', 'created_at')
        }),
        ('Связи', {
            'fields': ('user', 'token')
        }),
        ('Техническая информация', {
            'fields': ('ip_address', 'user_agent', 'referer'),
            'classes': ('collapse',)
        }),
    )
    
    def page_name_display(self, obj):
        """Отображение названия страницы с цветом"""
        colors = {
            'profile': '#2196F3',
            'landing': '#4CAF50',
            'generator': '#FF9800',
            'wall': '#9C27B0',
            'token_required': '#F44336',
            'limit_exceeded': '#FF5722',
            'invalid_token': '#E91E63',
        }
        color = colors.get(obj.page_name, '#757575')
        page_display = obj.page_name or 'unknown'
        return format_html(
            '<span style="color: {}; font-weight: bold;">📄 {}</span>',
            color,
            page_display
        )
    page_name_display.short_description = 'Страница'
    
    def user_or_token_display(self, obj):
        """Отображение пользователя или токена"""
        if obj.user:
            return format_html(
                '<span style="color: #2196F3;">👤 {}</span>',
                obj.user.username
            )
        elif obj.token:
            return format_html(
                '<span style="color: #FF9800;">🔑 {}</span>',
                str(obj.token.token)[:8]
            )
        return format_html('<span style="color: #757575;">Аноним</span>')
    user_or_token_display.short_description = 'Пользователь/Токен'
    
    def get_queryset(self, request):
        """Оптимизация запросов"""
        qs = super().get_queryset(request)
        return qs.select_related('user', 'token')
    
    def changelist_view(self, request, extra_context=None):
        """Добавляем статистику на страницу списка"""
        response = super().changelist_view(request, extra_context)
        
        try:
            # Статистика за последние 7 дней
            stats_7d = SubscriptionButtonClick.get_statistics(days=7)
            
            # Статистика за последние 30 дней
            stats_30d = SubscriptionButtonClick.get_statistics(days=30)
            
            # Общая статистика
            total_clicks = SubscriptionButtonClick.get_total_clicks()
            
            # Статистика по страницам за все время
            by_page = {}
            for page_name in SubscriptionButtonClick.objects.values_list('page_name', flat=True).distinct():
                if page_name:
                    count = SubscriptionButtonClick.objects.filter(page_name=page_name).count()
                    by_page[page_name] = count
            
            extra_context = extra_context or {}
            extra_context['click_stats'] = {
                'total_clicks': total_clicks,
                'stats_7d': stats_7d,
                'stats_30d': stats_30d,
                'by_page': by_page
            }
            
            if hasattr(response, 'context_data'):
                response.context_data.update(extra_context)
        except Exception as e:
            print(f"Ошибка при расчете статистики кликов: {e}")
        
        return response


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """
    Административная панель для мониторинга платежей
    """
    list_display = [
        'telegram_user_display',
        'amount_display',
        'status_display',
        'payment_system',
        'created_at',
        'paid_at',
        'token_display'
    ]
    
    list_filter = [
        'status',
        'payment_system',
        'created_at',
        'paid_at'
    ]
    
    search_fields = [
        'external_id',
        'telegram_user_id',
        'telegram_username',
        'token__token'
    ]
    
    readonly_fields = [
        'id',
        'external_id',
        'telegram_user_id',
        'telegram_username',
        'amount',
        'currency',
        'status',
        'payment_system',
        'token',
        'created_at',
        'paid_at',
        'payment_url',
        'metadata',
        'description'
    ]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('id', 'external_id', 'status', 'payment_system')
        }),
        ('Telegram пользователь', {
            'fields': ('telegram_user_id', 'telegram_username')
        }),
        ('Платёж', {
            'fields': ('amount', 'currency', 'description')
        }),
        ('Связи', {
            'fields': ('token',)
        }),
        ('Временные метки', {
            'fields': ('created_at', 'paid_at')
        }),
        ('Техническая информация', {
            'fields': ('payment_url', 'metadata'),
            'classes': ('collapse',)
        }),
    )
    
    def telegram_user_display(self, obj):
        """Отображение Telegram пользователя"""
        if obj.telegram_username:
            return format_html(
                '<span style="color: #2196F3;">@{}</span> <small>({})</small>',
                obj.telegram_username,
                obj.telegram_user_id
            )
        return format_html(
            '<span style="color: #757575;">ID: {}</span>',
            obj.telegram_user_id
        )
    telegram_user_display.short_description = 'Telegram'
    
    def amount_display(self, obj):
        """Отображение суммы"""
        return format_html(
            '<span style="font-weight: bold;">{} {}</span>',
            obj.amount,
            obj.currency
        )
    amount_display.short_description = 'Сумма'
    
    def status_display(self, obj):
        """Отображение статуса с цветом"""
        colors = {
            'pending': '#FF9800',
            'succeeded': '#4CAF50',
            'canceled': '#F44336',
            'refunded': '#9C27B0'
        }
        icons = {
            'pending': '⏳',
            'succeeded': '✅',
            'canceled': '❌',
            'refunded': '💸'
        }
        color = colors.get(obj.status, '#757575')
        icon = icons.get(obj.status, '•')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color,
            icon,
            obj.get_status_display()
        )
    status_display.short_description = 'Статус'
    
    def token_display(self, obj):
        """Отображение связанного токена"""
        if obj.token:
            return format_html(
                '<span style="color: #4CAF50;">🔑 {}</span>',
                str(obj.token.token)[:8]
            )
        return format_html('<span style="color: #F44336;">-</span>')
    token_display.short_description = 'Токен'
    
    def get_queryset(self, request):
        """Оптимизация запросов"""
        qs = super().get_queryset(request)
        return qs.select_related('token')
    
    def changelist_view(self, request, extra_context=None):
        """Добавляем статистику на страницу списка"""
        response = super().changelist_view(request, extra_context)
        
        try:
            # Статистика платежей
            stats = Payment.get_statistics(days=30)
            
            # Общая выручка за всё время
            from django.db.models import Sum
            total_revenue_all = Payment.objects.filter(status='succeeded').aggregate(
                total=Sum('amount')
            )['total'] or 0
            
            extra_context = extra_context or {}
            extra_context['payment_stats'] = {
                'total_revenue_all': float(total_revenue_all),
                'stats_30d': stats
            }
            
            if hasattr(response, 'context_data'):
                response.context_data.update(extra_context)
        except Exception as e:
            print(f"Ошибка при расчете статистики платежей: {e}")
        
        return response


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ['id', 'telegram_user_id', 'telegram_username', 'subject_short', 'status', 'source', 'created_at']
    list_filter = ['status', 'source', 'created_at']
    search_fields = ['telegram_user_id', 'telegram_username', 'subject', 'message']
    readonly_fields = ['created_at', 'updated_at']

    def subject_short(self, obj):
        return (obj.subject or obj.message[:50] or '-')[:50]
    subject_short.short_description = 'Тема'


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['id', 'telegram_user_id', 'telegram_username', 'text_short', 'rating', 'moderation_status', 'created_at']
    list_filter = ['moderation_status', 'rating', 'created_at']
    search_fields = ['telegram_user_id', 'telegram_username', 'text']
    readonly_fields = ['created_at']
    actions = ['approve_reviews', 'reject_reviews']

    def text_short(self, obj):
        return (obj.text or '-')[:60] + ('...' if len(obj.text or '') > 60 else '')
    text_short.short_description = 'Текст'

    def approve_reviews(self, request, queryset):
        count = queryset.update(moderation_status='approved')
        self.message_user(request, f'Одобрено отзывов: {count}')
    approve_reviews.short_description = 'Одобрить'

    def reject_reviews(self, request, queryset):
        count = queryset.update(moderation_status='rejected')
        self.message_user(request, f'Отклонено отзывов: {count}')
    reject_reviews.short_description = 'Отклонить'


@admin.register(SupportChat)
class SupportChatAdmin(admin.ModelAdmin):
    list_display = ['id', 'telegram_user_id', 'telegram_username', 'status', 'created_at', 'closed_at']
    list_filter = ['status', 'created_at']
    search_fields = ['telegram_user_id', 'telegram_username']
    readonly_fields = ['created_at']


admin.site.register(UserProfile)
admin.site.register(Generation) 