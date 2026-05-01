from django.contrib import admin
from .models import Manuscript

@admin.register(Manuscript)
class ManuscriptAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'ai_profile_confirmed', 'ai_memory_needs_refresh', 'created_at', 'updated_at')
    list_filter = ('user', 'ai_profile_confirmed')
    search_fields = ('title', 'user__email')

    @admin.display(boolean=True, description='Memory stale')
    def ai_memory_needs_refresh(self, obj):
        return bool((obj.ai_memory_stale or {}).get('is_stale'))
