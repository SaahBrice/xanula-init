"""
Purchase and LibraryEntry models.
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from decimal import Decimal

from .book import Book


class Purchase(models.Model):
    """
    Purchase model representing a book purchase transaction.
    Per Architecture Document Section 6.
    """
    
    class PaymentMethod(models.TextChoices):
        STRIPE = 'stripe', _('Stripe (Card)')
        FAPSHI = 'fapshi', _('Fapshi (Mobile Money)')
    
    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        COMPLETED = 'completed', _('Completed')
        FAILED = 'failed', _('Failed')
        REFUNDED = 'refunded', _('Refunded')
    
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='purchases',
        verbose_name=_('buyer')
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name='purchases',
        verbose_name=_('book')
    )
    purchase_date = models.DateTimeField(
        _('purchase date'),
        auto_now_add=True
    )
    amount_paid = models.DecimalField(
        _('amount paid'),
        max_digits=10,
        decimal_places=2,
        help_text=_('Amount paid in XAF.')
    )
    payment_method = models.CharField(
        _('payment method'),
        max_length=10,
        choices=PaymentMethod.choices
    )
    payment_transaction_id = models.CharField(
        _('transaction ID'),
        max_length=255,
        blank=True,
        help_text=_('Payment gateway transaction reference.')
    )
    payment_status = models.CharField(
        _('payment status'),
        max_length=15,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING
    )
    platform_commission = models.DecimalField(
        _('platform commission'),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_('Commission amount for the platform.')
    )
    author_earning = models.DecimalField(
        _('author earning'),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_('Earning amount for the author.')
    )
    
    # Referral tracking
    referred_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referral_purchases',
        verbose_name=_('referred by'),
        help_text=_('User who referred this purchase.')
    )
    referral_commission = models.DecimalField(
        _('referral commission'),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_('Commission paid to referrer.')
    )
    
    class Meta:
        verbose_name = _('purchase')
        verbose_name_plural = _('purchases')
        ordering = ['-purchase_date']
        indexes = [
            models.Index(fields=['buyer']),
            models.Index(fields=['book']),
            models.Index(fields=['payment_status']),
        ]
    
    def __str__(self):
        return f"{self.buyer.email} - {self.book.title}"
    
    def save(self, *args, **kwargs):
        # Calculate commission and author earning
        if self.amount_paid and self.book:
            commission_rate = Decimal(str(self.book.commission_rate)) / Decimal('100')
            self.platform_commission = self.amount_paid * commission_rate
            self.author_earning = self.amount_paid - self.platform_commission
        super().save(*args, **kwargs)


class LibraryEntry(models.Model):
    """
    LibraryEntry model representing a book in a user's library.
    Per Architecture Document Section 6.
    """
    
    class DownloadStatus(models.TextChoices):
        NOT_DOWNLOADED = 'not_downloaded', _('Not Downloaded')
        DOWNLOADED = 'downloaded', _('Downloaded')
        OUTDATED = 'outdated', _('Outdated')
    
    class CompletionStatus(models.TextChoices):
        NOT_STARTED = 'not_started', _('Not Started')
        IN_PROGRESS = 'in_progress', _('In Progress')
        COMPLETED = 'completed', _('Completed')
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='library',
        verbose_name=_('user')
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name='library_entries',
        verbose_name=_('book')
    )
    date_added = models.DateTimeField(
        _('date added'),
        auto_now_add=True
    )
    last_accessed = models.DateTimeField(
        _('last accessed'),
        null=True,
        blank=True
    )
    reading_progress = models.PositiveIntegerField(
        _('reading progress'),
        default=0,
        help_text=_('Current page number for ebook reading.')
    )
    listening_progress = models.PositiveIntegerField(
        _('listening progress'),
        default=0,
        help_text=_('Current position in seconds for audiobook.')
    )
    download_status = models.CharField(
        _('download status'),
        max_length=20,
        choices=DownloadStatus.choices,
        default=DownloadStatus.NOT_DOWNLOADED
    )
    completion_status = models.CharField(
        _('completion status'),
        max_length=15,
        choices=CompletionStatus.choices,
        default=CompletionStatus.NOT_STARTED
    )
    
    class Meta:
        verbose_name = _('library entry')
        verbose_name_plural = _('library entries')
        ordering = ['-date_added']
        # One entry per user-book combination
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'book'],
                name='unique_user_book_library'
            )
        ]
        indexes = [
            models.Index(fields=['user', 'book']),
            models.Index(fields=['completion_status']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.book.title}"
