"""
Blog Article model for the Xanula blog section.
"""

from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.utils import timezone
from django.urls import reverse
from django_ckeditor_5.fields import CKEditor5Field


def article_thumbnail_path(instance, filename):
    """Upload path for article thumbnails."""
    return f'blog/thumbnails/{filename}'


def article_audio_path(instance, filename):
    """Upload path for article audio files."""
    return f'blog/audio/{filename}'


class Article(models.Model):
    """Blog article model with English and French content support."""
    
    # English (default)
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=300, blank=True, default='')
    content = CKEditor5Field(config_name='default')
    
    # French translations
    title_fr = models.CharField(max_length=200, blank=True, default='', verbose_name='Title (French)')
    subtitle_fr = models.CharField(max_length=300, blank=True, default='', verbose_name='Subtitle (French)')
    content_fr = CKEditor5Field(config_name='default', blank=True, default='', verbose_name='Content (French)')
    
    slug = models.SlugField(max_length=250, unique=True, blank=True)
    thumbnail = models.ImageField(upload_to=article_thumbnail_path, blank=True, null=True)
    
    # Audio files
    french_audio = models.FileField(
        upload_to=article_audio_path,
        blank=True, null=True,
        help_text="French audio version of the article"
    )
    english_audio = models.FileField(
        upload_to=article_audio_path,
        blank=True, null=True,
        help_text="English audio version of the article"
    )
    
    # Stats
    likes_count = models.PositiveIntegerField(default=0)
    
    # Author & status
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='articles'
    )
    is_published = models.BooleanField(default=False)
    send_notifications = models.BooleanField(
        default=False,
        help_text="Check this to send email & in-app notifications when publishing. Uncheck to publish silently."
    )
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Article'
        verbose_name_plural = 'Articles'
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            if not base_slug:
                base_slug = 'article'
            slug = base_slug
            counter = 1
            while Article.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('core:article_detail', kwargs={'slug': self.slug})
    
    def get_title(self, language_code='en'):
        """Get title based on language, falls back to English."""
        if language_code == 'fr' and self.title_fr:
            return self.title_fr
        return self.title
    
    def get_subtitle(self, language_code='en'):
        """Get subtitle based on language, falls back to English."""
        if language_code == 'fr' and self.subtitle_fr:
            return self.subtitle_fr
        return self.subtitle
    
    def get_content(self, language_code='en'):
        """Get content based on language, falls back to English."""
        if language_code == 'fr' and self.content_fr:
            return self.content_fr
        return self.content
    
    @property
    def reading_time(self):
        """Estimate reading time in minutes."""
        from django.utils.html import strip_tags
        word_count = len(strip_tags(self.content).split())
        minutes = max(1, word_count // 200)
        return minutes
