from django.contrib import admin
from .models import Manuscript

@admin.register(Manuscript)
class ManuscriptAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'created_at', 'updated_at')
    list_filter = ('user',)
    search_fields = ('title', 'user__email')
