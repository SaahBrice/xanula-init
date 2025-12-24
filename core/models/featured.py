"""
Featured Book model for curating homepage featured books.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from .book import Book


class FeaturedBook(models.Model):
    """
    Model to curate featured books for the homepage.
    Allows selecting 6 books per language (French and English).
    """
    
    class Language(models.TextChoices):
        ENGLISH = 'en', _('English')
        FRENCH = 'fr', _('French')
    
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name='featured_entries',
        verbose_name=_('book'),
        limit_choices_to={'status__in': ['approved', 'ebook_ready', 'audiobook_generated', 'completed']},
        help_text=_('Select a published book to feature.')
    )
    language = models.CharField(
        _('language'),
        max_length=2,
        choices=Language.choices,
        help_text=_('The language section this book appears in.')
    )
    position = models.PositiveIntegerField(
        _('position'),
        default=1,
        help_text=_('Display order (1-6). Lower numbers appear first.')
    )
    is_active = models.BooleanField(
        _('active'),
        default=True,
        help_text=_('Whether this featured book is currently shown.')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('featured book')
        verbose_name_plural = _('featured books')
        ordering = ['language', 'position']
        unique_together = ['language', 'position']
    
    def __str__(self):
        return f"{self.book.title} ({self.get_language_display()}) - Position {self.position}"
    
    def clean(self):
        from django.core.exceptions import ValidationError
        if self.position < 1 or self.position > 6:
            raise ValidationError({'position': _('Position must be between 1 and 6.')})
