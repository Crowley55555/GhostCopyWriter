from django.urls import path
from . import views

urlpatterns = [
    path('save-template/', views.save_template_view, name='save_template'),
    path('get-templates/', views.get_templates_view, name='get_templates'),
    path('load-template/', views.load_template_view, name='load_template'),
    path('delete-template/', views.delete_template_view, name='delete_template'),
    path('rename-template/', views.rename_template_view, name='rename_template'),
    path('set-default-template/', views.set_default_template_view, name='set_default_template'),
] 