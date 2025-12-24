"""
Author-related models: Review, PayoutRequest, HardCopyRequest, UpfrontPaymentApplication.
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal

from .book import Book


class Review(models.Model):
    """
    Review model representing a book review.
    Per Architecture Document Section 6.
    """
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name=_('user')
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name=_('book')
    )
    rating = models.PositiveSmallIntegerField(
        _('rating'),
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text=_('Rating from 1 to 5 stars.')
    )
    review_text = models.TextField(
        _('review text'),
        blank=True,
        help_text=_('Optional written review.')
    )
    date_posted = models.DateTimeField(
        _('date posted'),
        auto_now_add=True
    )
    date_modified = models.DateTimeField(
        _('date modified'),
        auto_now=True
    )
    is_visible = models.BooleanField(
        _('is visible'),
        default=True,
        help_text=_('Whether the review is publicly visible.')
    )
    
    class Meta:
        verbose_name = _('review')
        verbose_name_plural = _('reviews')
        ordering = ['-date_posted']
        # One review per user-book combination
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'book'],
                name='unique_user_book_review'
            )
        ]
        indexes = [
            models.Index(fields=['book', 'is_visible']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.book.title} ({self.rating}★)"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update the book's average rating
        self.book.update_average_rating()
    
    def delete(self, *args, **kwargs):
        book = self.book
        super().delete(*args, **kwargs)
        # Update the book's average rating after deletion
        book.update_average_rating()


class PayoutRequest(models.Model):
    """
    PayoutRequest model for author earnings withdrawal.
    Per Architecture Document Section 6.
    """
    
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        PROCESSING = 'processing', _('Processing')
        COMPLETED = 'completed', _('Completed')
        FAILED = 'failed', _('Failed')
    
    class PayoutMethod(models.TextChoices):
        MOBILE_MONEY = 'mobile_money', _('Mobile Money')
        BANK_TRANSFER = 'bank_transfer', _('Bank Transfer')
    
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payout_requests',
        verbose_name=_('author')
    )
    amount_requested = models.DecimalField(
        _('amount requested'),
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('5000.00'))],
        help_text=_('Amount to withdraw in XAF (minimum 5,000 XAF).')
    )
    request_date = models.DateTimeField(
        _('request date'),
        auto_now_add=True
    )
    status = models.CharField(
        _('status'),
        max_length=15,
        choices=Status.choices,
        default=Status.PENDING
    )
    payout_method = models.CharField(
        _('payout method'),
        max_length=15,
        choices=PayoutMethod.choices
    )
    account_details = models.TextField(
        _('account details'),
        help_text=_('Phone number for mobile money or bank account details.')
    )
    processing_notes = models.TextField(
        _('processing notes'),
        blank=True,
        help_text=_('Internal notes for processing (admin only).')
    )
    completion_date = models.DateField(
        _('completion date'),
        null=True,
        blank=True,
        help_text=_('When the payout was completed.')
    )
    
    class Meta:
        verbose_name = _('payout request')
        verbose_name_plural = _('payout requests')
        ordering = ['-request_date']
        indexes = [
            models.Index(fields=['author']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.author.email} - {self.amount_requested:,.0f} XAF ({self.status})"


class HardCopyRequest(models.Model):
    """
    Model for users to request physical/hard copies of books they own.
    Requests are sent to admin and author for manual processing.
    """
    
    class Status(models.TextChoices):
        REQUESTED = 'REQUESTED', _('Requested')
        PROCESSING = 'PROCESSING', _('Processing')
        SHIPPED = 'SHIPPED', _('Shipped')
        DELIVERED = 'DELIVERED', _('Delivered')
        CANCELLED = 'CANCELLED', _('Cancelled')
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hardcopy_requests',
        verbose_name=_('user')
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name='hardcopy_requests',
        verbose_name=_('book')
    )
    
    # Request details
    request_date = models.DateTimeField(
        _('request date'),
        auto_now_add=True
    )
    status = models.CharField(
        _('status'),
        max_length=15,
        choices=Status.choices,
        default=Status.REQUESTED
    )
    
    # Shipping information
    full_name = models.CharField(
        _('full name'),
        max_length=200,
        help_text=_('Name for delivery')
    )
    phone_number = models.CharField(
        _('phone number'),
        max_length=20,
        help_text=_('Contact phone number')
    )
    shipping_address = models.TextField(
        _('shipping address'),
        help_text=_('Full delivery address including city, region, and any landmarks')
    )
    city = models.CharField(
        _('city'),
        max_length=100
    )
    additional_notes = models.TextField(
        _('additional notes'),
        blank=True,
        help_text=_('Any special instructions for delivery')
    )
    
    # Admin processing
    admin_notes = models.TextField(
        _('admin notes'),
        blank=True,
        help_text=_('Internal notes for processing')
    )
    tracking_number = models.CharField(
        _('tracking number'),
        max_length=100,
        blank=True,
        help_text=_('Shipping tracking number if applicable')
    )
    processed_date = models.DateTimeField(
        _('processed date'),
        null=True,
        blank=True
    )
    shipped_date = models.DateTimeField(
        _('shipped date'),
        null=True,
        blank=True
    )
    delivered_date = models.DateTimeField(
        _('delivered date'),
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = _('hard copy request')
        verbose_name_plural = _('hard copy requests')
        ordering = ['-request_date']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['book']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.book.title} ({self.status})"


class UpfrontPaymentApplication(models.Model):
    """
    Upfront payment (advance) application for authors.
    Authors can apply for an advance payment which is recouped via
    increased commission on future sales.
    """
    
    class Status(models.TextChoices):
        IN_REVIEW = 'in_review', _('In Review')
        APPROVED = 'approved', _('Approved')
        COMPLETED = 'completed', _('Completed')  # Fully recouped
        REJECTED = 'rejected', _('Rejected')
        CANCELLED = 'cancelled', _('Cancelled')
    
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='upfront_applications',
        verbose_name=_('author'),
        help_text=_('The author applying for upfront payment.')
    )
    book = models.ForeignKey(
        'Book',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='upfront_applications',
        verbose_name=_('book'),
        help_text=_('Specific book for the advance, or null for all books.')
    )
    amount_requested = models.DecimalField(
        _('amount requested'),
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('1000.00'))],
        help_text=_('Amount requested in XAF.')
    )
    reason = models.TextField(
        _('reason'),
        help_text=_('Why you need this advance payment.')
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.IN_REVIEW
    )
    rejection_reason = models.TextField(
        _('rejection reason'),
        blank=True,
        help_text=_('Reason for rejection if applicable.')
    )
    repayment_rate = models.DecimalField(
        _('repayment rate'),
        max_digits=5,
        decimal_places=2,
        default=Decimal('20.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('50.00'))],
        help_text=_('Extra percentage taken per sale to recoup advance (e.g., 20 means +20%).')
    )
    amount_recouped = models.DecimalField(
        _('amount recouped'),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_('Total amount recouped from sales so far.')
    )
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True
    )
    approved_at = models.DateTimeField(
        _('approved at'),
        null=True,
        blank=True
    )
    completed_at = models.DateTimeField(
        _('completed at'),
        null=True,
        blank=True
    )
    admin_notes = models.TextField(
        _('admin notes'),
        blank=True,
        help_text=_('Internal notes for admin review.')
    )
    terms_accepted = models.BooleanField(
        _('terms accepted'),
        default=False,
        help_text=_('Author has accepted the terms and conditions.')
    )
    
    class Meta:
        verbose_name = _('upfront payment application')
        verbose_name_plural = _('upfront payment applications')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['author']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        book_name = self.book.title if self.book else _('All Books')
        return f"{self.author.email} - {self.amount_requested} XAF ({self.status})"
    
    @property
    def remaining_amount(self):
        """Amount still to be recouped."""
        return max(Decimal('0.00'), self.amount_requested - self.amount_recouped)
    
    @property
    def recoup_progress_percent(self):
        """Percentage of advance that has been recouped."""
        if self.amount_requested <= 0:
            return 0
        return min(100, round((self.amount_recouped / self.amount_requested) * 100, 1))
    
    @property
    def is_fully_recouped(self):
        """Check if the advance has been fully recouped."""
        return self.amount_recouped >= self.amount_requested
    
    def recoup_from_sale(self, author_earning, sale_price):
        """
        Recoup from a sale. Returns the amount to deduct from author earnings.
        """
        if self.status != self.Status.APPROVED:
            return Decimal('0.00')
        
        # Calculate extra amount to deduct based on repayment_rate
        # repayment_rate is the extra % of sale price to take
        deduction = (sale_price * self.repayment_rate / 100).quantize(Decimal('0.01'))
        
        # Don't deduct more than remaining amount or more than author earning
        deduction = min(deduction, self.remaining_amount, author_earning)
        
        self.amount_recouped += deduction
        
        # Check if fully recouped
        if self.is_fully_recouped:
            from django.utils import timezone
            self.status = self.Status.COMPLETED
            self.completed_at = timezone.now()
        
        self.save()
        return deduction
