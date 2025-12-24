"""
Notification model for in-app notifications.
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Notification(models.Model):
    """
    In-app notification model for users.
    Stores notifications for authors, readers, and admins.
    """
    
    class NotificationType(models.TextChoices):
        # Author notifications
        BOOK_STATUS = 'book_status', _('Book Status Change')
        NEW_SALE = 'new_sale', _('New Sale')
        NEW_REVIEW = 'new_review', _('New Review')
        NEW_DONATION = 'new_donation', _('Donation Received')
        PAYOUT_STATUS = 'payout_status', _('Payout Status')
        UPFRONT_STATUS = 'upfront_status', _('Upfront Payment Status')
        EBOOK_READY = 'ebook_ready', _('Ebook Ready')
        AUDIOBOOK_READY = 'audiobook_ready', _('Audiobook Ready')
        
        # Reader notifications
        PURCHASE_CONFIRMED = 'purchase_confirmed', _('Purchase Confirmed')
        BOOK_ADDED = 'book_added', _('Book Added to Library')
        WISHLIST_PRICE_DROP = 'wishlist_price', _('Wishlist Price Drop')
        HARD_COPY_UPDATE = 'hard_copy', _('Hard Copy Update')
        REFERRAL_EARNED = 'referral_earned', _('Referral Commission')
        
        # General
        SYSTEM = 'system', _('System Notification')
        WELCOME = 'welcome', _('Welcome')
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name=_('user')
    )
    notification_type = models.CharField(
        _('type'),
        max_length=30,
        choices=NotificationType.choices,
        default=NotificationType.SYSTEM
    )
    title = models.CharField(
        _('title'),
        max_length=200,
        help_text=_('Short notification title.')
    )
    message = models.TextField(
        _('message'),
        help_text=_('Full notification message.')
    )
    icon = models.CharField(
        _('icon'),
        max_length=10,
        default='🔔',
        help_text=_('Emoji icon for the notification.')
    )
    is_read = models.BooleanField(
        _('is read'),
        default=False
    )
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True
    )
    
    # Optional related objects (for future clickable notifications)
    related_book_id = models.IntegerField(
        _('related book ID'),
        null=True,
        blank=True,
        help_text=_('ID of related book, if any.')
    )
    related_url = models.CharField(
        _('related URL'),
        max_length=500,
        blank=True,
        help_text=_('URL to navigate to when clicked.')
    )
    
    class Meta:
        verbose_name = _('notification')
        verbose_name_plural = _('notifications')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email}: {self.title}"
    
    @classmethod
    def create_notification(cls, user, notification_type, title, message, icon='🔔', related_book_id=None, related_url=''):
        """
        Helper method to create a notification.
        """
        return cls.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            icon=icon,
            related_book_id=related_book_id,
            related_url=related_url
        )
    
    @classmethod
    def get_unread_count(cls, user):
        """Get count of unread notifications for a user."""
        return cls.objects.filter(user=user, is_read=False).count()
    
    @classmethod
    def mark_all_read(cls, user):
        """Mark all notifications as read for a user."""
        return cls.objects.filter(user=user, is_read=False).update(is_read=True)
