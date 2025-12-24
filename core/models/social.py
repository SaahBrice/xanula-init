"""
Social/donation-related models: Donation, ReferralSettings.
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class Donation(models.Model):
    """
    Donation/Tip model for supporting authors.
    Users can send tips to authors with optional messages.
    Platform takes 10% commission, author receives 90%.
    """
    
    class PaymentMethod(models.TextChoices):
        STRIPE = 'stripe', _('Stripe (Card)')
        FAPSHI = 'fapshi', _('Fapshi (Mobile Money)')
    
    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        COMPLETED = 'completed', _('Completed')
        FAILED = 'failed', _('Failed')
        REFUNDED = 'refunded', _('Refunded')
    
    # Who donated
    donor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='donations_made',
        verbose_name=_('donor'),
        help_text=_('User who made the donation.')
    )
    
    # Who receives
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='donations_received',
        verbose_name=_('recipient'),
        help_text=_('Author receiving the donation.')
    )
    
    # Optional: Which book inspired this
    book = models.ForeignKey(
        'Book',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='donations',
        verbose_name=_('book'),
        help_text=_('Book that inspired this donation (optional).')
    )
    
    # Amount in XAF
    amount = models.DecimalField(
        _('amount'),
        max_digits=12,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('500.00')),
            MaxValueValidator(Decimal('327500.00'))  # ~500 EUR at 655 rate
        ],
        help_text=_('Donation amount in XAF (min 500, max 327,500).')
    )
    
    # Personal message
    message = models.TextField(
        _('message'),
        max_length=500,
        blank=True,
        help_text=_('Personal message to the author.')
    )
    
    # Terms accepted
    terms_accepted = models.BooleanField(
        _('terms accepted'),
        default=False,
        help_text=_('User accepted donation terms.')
    )
    
    # Payment details
    payment_method = models.CharField(
        _('payment method'),
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.FAPSHI
    )
    
    payment_status = models.CharField(
        _('payment status'),
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING
    )
    
    payment_transaction_id = models.CharField(
        _('transaction ID'),
        max_length=255,
        blank=True,
        help_text=_('Payment gateway transaction ID.')
    )
    
    # Commission split (10% platform, 90% author)
    platform_commission = models.DecimalField(
        _('platform commission'),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_('Platform commission (10%).')
    )
    
    author_earning = models.DecimalField(
        _('author earning'),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_('Amount received by author (90%).')
    )
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    completed_at = models.DateTimeField(_('completed at'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('donation')
        verbose_name_plural = _('donations')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.donor} → {self.recipient}: {self.amount:,.0f} XAF"
    
    def calculate_split(self):
        """Calculate the platform/author split based on global commission settings."""
        rate = CommissionSettings.get_donation_rate()
        self.platform_commission = (self.amount * rate).quantize(Decimal('0.01'))
        self.author_earning = self.amount - self.platform_commission
    
    def save(self, *args, **kwargs):
        # Auto-calculate split if not set
        if self.author_earning == Decimal('0.00') and self.amount > 0:
            self.calculate_split()
        super().save(*args, **kwargs)


class ReferralSettings(models.Model):
    """
    Singleton model for global referral settings.
    Only one instance should exist in the database.
    """
    referral_percent = models.DecimalField(
        _('referral commission percent'),
        max_digits=5,
        decimal_places=2,
        default=Decimal('5.00'),
        help_text=_('Percentage of sale that goes to referrer (deducted from author share).')
    )
    is_active = models.BooleanField(
        _('referral system active'),
        default=True,
        help_text=_('Enable or disable the referral system.')
    )
    
    class Meta:
        verbose_name = _('referral settings')
        verbose_name_plural = _('referral settings')
    
    def __str__(self):
        return f"Referral Settings ({self.referral_percent}%)"
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists (singleton)
        if not self.pk and ReferralSettings.objects.exists():
            raise ValueError("Only one ReferralSettings instance allowed.")
        super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Get the singleton settings instance, creating it if needed."""
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings
    
    @classmethod
    def get_referral_percent(cls):
        """Get current referral percentage."""
        settings = cls.get_settings()
        if settings.is_active:
            return settings.referral_percent
        return Decimal('0.00')


class CommissionSettings(models.Model):
    """
    Singleton model for global platform commission settings.
    Only one instance should exist in the database.
    """
    ebook_commission = models.DecimalField(
        _('ebook commission percent'),
        max_digits=5,
        decimal_places=2,
        default=Decimal('10.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text=_('Platform commission for ebook-only purchases (default 10%).')
    )
    audiobook_commission = models.DecimalField(
        _('audiobook commission percent'),
        max_digits=5,
        decimal_places=2,
        default=Decimal('30.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text=_('Platform commission for purchases with audiobook (default 30%).')
    )
    donation_commission = models.DecimalField(
        _('donation commission percent'),
        max_digits=5,
        decimal_places=2,
        default=Decimal('10.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text=_('Platform commission for donations (default 10%).')
    )
    
    class Meta:
        verbose_name = _('commission settings')
        verbose_name_plural = _('commission settings')
    
    def __str__(self):
        return f"Commission Settings (Ebook: {self.ebook_commission}%, Audiobook: {self.audiobook_commission}%, Donation: {self.donation_commission}%)"
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists (singleton)
        if not self.pk and CommissionSettings.objects.exists():
            raise ValueError("Only one CommissionSettings instance allowed.")
        super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Get the singleton settings instance, creating it if needed."""
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings
    
    @classmethod
    def get_ebook_rate(cls):
        """Get current ebook commission rate as decimal (e.g., 0.10 for 10%)."""
        settings = cls.get_settings()
        return settings.ebook_commission / Decimal('100')
    
    @classmethod
    def get_audiobook_rate(cls):
        """Get current audiobook commission rate as decimal (e.g., 0.30 for 30%)."""
        settings = cls.get_settings()
        return settings.audiobook_commission / Decimal('100')
    
    @classmethod
    def get_donation_rate(cls):
        """Get current donation commission rate as decimal (e.g., 0.10 for 10%)."""
        settings = cls.get_settings()
        return settings.donation_commission / Decimal('100')
