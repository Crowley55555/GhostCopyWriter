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
    path('', views.home_view, name='home'),
    path('generator/', views.generator_view, name='index'),
    path('regenerate-text/', views.regenerate_text, name='regenerate_text'),
    path('regenerate-image/', views.regenerate_image, name='regenerate_image'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.edit_profile_view, name='edit_profile'),
    path('wall/', views.user_wall_view, name='user_wall'),
    path('delete-generation/<int:gen_id>/', views.delete_generation_view, name='delete_generation'),
    path('generation/<int:gen_id>/', views.generation_detail_view, name='generation_detail'),
    path('agreement/', views.agreement_view, name='user_agreement'),
    path('api/', include('generator.urls')),
]

# В режиме DEBUG:
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)