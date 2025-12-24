from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
import secrets
import string

from .managers import CustomUserManager


def generate_referral_code():
    """Generate a unique referral code in format REEPLS-XXXX."""
    chars = string.ascii_uppercase + string.digits
    while True:
        code = 'REEPLS-' + ''.join(secrets.choice(chars) for _ in range(4))
        # Check if code already exists
        from users.models import User
        if not User.objects.filter(referral_code=code).exists():
            return code


class User(AbstractUser):
    """
    Custom User model for Xanula platform.
    
    Uses email as the primary identifier instead of username.
    Includes additional fields per Architecture Document Section 6:
    - display_name: User's public display name
    - profile_picture: Optional profile image
    - earnings_balance: Accumulated author earnings
    - google_account_id: Google OAuth identifier
    - bio: Short description of user (per Planning Document Section 2)
    - wishlist: Books user wants to purchase later
    """
    
    # Remove username field, use email instead
    username = None
    email = models.EmailField(
        _('email address'),
        unique=True,
        help_text=_('Required. A valid email address.'),
        error_messages={
            'unique': _('A user with that email already exists.'),
        },
    )
    
    # Display name shown publicly
    display_name = models.CharField(
        _('display name'),
        max_length=100,
        blank=True,
        help_text=_('Public display name shown on the platform.'),
    )
    
    # Profile picture (optional)
    profile_picture = models.ImageField(
        _('profile picture'),
        upload_to='profiles/%Y/%m/',
        blank=True,
        null=True,
        help_text=_('Optional profile picture.'),
    )
    
    # Short bio/description
    bio = models.TextField(
        _('bio'),
        max_length=500,
        blank=True,
        help_text=_('Short description about the user.'),
    )
    
    # Earnings balance for authors
    earnings_balance = models.DecimalField(
        _('earnings balance'),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_('Accumulated earnings from book sales in XAF.'),
    )
    
    # Google OAuth account ID (for users who signed up via Google)
    google_account_id = models.CharField(
        _('Google account ID'),
        max_length=255,
        blank=True,
        null=True,
        unique=True,
        help_text=_('Google account identifier for OAuth users.'),
    )
    
    # Wishlist - books user wants to purchase later
    wishlist = models.ManyToManyField(
        'core.Book',
        related_name='wishlisted_by',
        blank=True,
        verbose_name=_('wishlist'),
        help_text=_('Books saved for later purchase.'),
    )
    
    # Referral code - unique per user, format: REEPLS-XXXX
    referral_code = models.CharField(
        _('referral code'),
        max_length=11,
        unique=True,
        blank=True,
        null=True,
        help_text=_('Unique referral code for this user.'),
    )
    
    # Use email as the username field
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # Email is already required by USERNAME_FIELD
    
    # Use custom manager
    objects = CustomUserManager()
    
    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['-date_joined']
    
    def __str__(self):
        return self.display_name or self.email
    
    def get_display_name(self):
        """Returns the display name or email if not set."""
        return self.display_name or self.email.split('@')[0]
    
    @property
    def is_author(self):
        """Check if user has published any books."""
        return self.books.exists()
    
    @property
    def formatted_earnings(self):
        """Returns formatted earnings balance in XAF."""
        return f"{self.earnings_balance:,.0f} XAF"
    
    def can_request_payout(self):
        """Check if user can request a payout (minimum 5,000 XAF)."""
        return self.earnings_balance >= Decimal('5000.00')
    
    @property
    def payout_eligible_amount(self):
        """Returns the amount eligible for payout."""
        if self.can_request_payout():
            return self.earnings_balance
        return Decimal('0.00')
    
    def ensure_referral_code(self):
        """Ensure user has a referral code, generate if missing."""
        if not self.referral_code:
            self.referral_code = generate_referral_code()
            self.save(update_fields=['referral_code'])
        return self.referral_code
    
    def save(self, *args, **kwargs):
        # Auto-generate referral code for new users
        if not self.pk and not self.referral_code:
            self.referral_code = generate_referral_code()
        super().save(*args, **kwargs)

