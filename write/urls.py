from django.urls import path
from . import views

app_name = 'write'

urlpatterns = [
    path('', views.write_landing, name='landing'),
    path('create/', views.create_manuscript, name='create'),
    path('<int:manuscript_id>/', views.editor, name='editor'),
    path('<int:manuscript_id>/save/', views.save_manuscript, name='save'),
    path('<int:manuscript_id>/ai/analyze/', views.ai_analyze, name='ai_analyze'),
    path('<int:manuscript_id>/ai/profile/', views.ai_profile, name='ai_profile'),
    path('<int:manuscript_id>/ai/inspect/', views.ai_inspect, name='ai_inspect'),
    path('<int:manuscript_id>/ai/generate/', views.ai_generate, name='ai_generate'),
]
