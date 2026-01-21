"""
URL configuration for ghostwriter project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from generator import views
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.landing_view, name='landing'),
    path('home/', views.home_view, name='home'),
    path('generator/', views.generator_view, name='index'),
    path('regenerate-text/', views.regenerate_text, name='regenerate_text'),
    path('regenerate-image/', views.regenerate_image, name='regenerate_image'),
    
    # DEPRECATED: Старая система регистрации/входа (заглушки)
    # Теперь используем систему токенов для доступа
    path('register/', views.register_disabled_view, name='register'),
    path('login/', views.login_disabled_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # User features (доступны через токены)
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.edit_profile_view, name='edit_profile'),
    path('wall/', views.user_wall_view, name='user_wall'),
    path('delete-generation/<int:gen_id>/', views.delete_generation_view, name='delete_generation'),
    path('generation/<int:gen_id>/', views.generation_detail_view, name='generation_detail'),
    
    # Token authentication routes (основной способ входа)
    path('auth/token/<uuid:token>/', views.token_auth_view, name='token_auth'),
    path('token-required/', views.token_required_page, name='token_required_page'),
    path('invalid-token/', views.invalid_token_page, name='invalid_token_page'),
    path('limit-exceeded/', views.limit_exceeded_page, name='limit_exceeded_page'),
    
    # Telegram webhook
    path('telegram/webhook/', views.telegram_webhook, name='telegram_webhook'),
    
    # API routes
    path('api/', include('generator.urls')),
]

# Quick login (только для разработки)
if settings.DEBUG:
    urlpatterns += [
        path('quick-login/<str:username>/', views.quick_login, name='quick_login'),
    ]

# В режиме DEBUG:
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)