from django.urls import path
from . import views

app_name = 'write'

urlpatterns = [
    path('', views.write_landing, name='landing'),
    path('create/', views.create_manuscript, name='create'),
    path('<int:manuscript_id>/', views.editor, name='editor'),
    path('<int:manuscript_id>/save/', views.save_manuscript, name='save'),
]
