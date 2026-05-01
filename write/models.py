from django.db import models
from django.conf import settings


class Manuscript(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='manuscripts',
    )
    title = models.CharField(max_length=500)
    content = models.JSONField(default=dict, blank=True)
    ai_profile = models.JSONField(default=dict, blank=True)
    ai_memory = models.JSONField(default=dict, blank=True)
    ai_voice = models.JSONField(default=dict, blank=True)
    ai_chapter_map = models.JSONField(default=dict, blank=True)
    ai_entities = models.JSONField(default=dict, blank=True)
    ai_consistency = models.JSONField(default=dict, blank=True)
    ai_usage = models.JSONField(default=dict, blank=True)
    ai_memory_stale = models.JSONField(default=dict, blank=True)
    ai_profile_confirmed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title
