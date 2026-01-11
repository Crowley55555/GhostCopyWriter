from django.urls import path
from . import views

urlpatterns = [
    path('save-template/', views.save_template_view, name='save_template'),
    path('get-templates/', views.get_templates_view, name='get_templates'),
    path('load-template/', views.load_template_view, name='load_template'),
    path('delete-template/', views.delete_template_view, name='delete_template'),
    path('rename-template/', views.rename_template_view, name='rename_template'),
    path('set-default-template/', views.set_default_template_view, name='set_default_template'),
    path('regenerate-text/', views.regenerate_text, name='regenerate_text'),
    path('regenerate-image/', views.regenerate_image, name='regenerate_image'),
    
    # API endpoints для создания токенов (используется ботом)
    path('api/tokens/create/', views.api_create_token, name='api_create_token'),
    path('api/tokens/<uuid:token>/', views.api_token_info, name='api_token_info'),
] 