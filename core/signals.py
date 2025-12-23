"""
Django signals for triggering notifications.
Per Architecture Document Section 14 (Background Tasks & Notifications).

These signals send notification emails directly when model status changes occur.
(Modified to work without Django-Q worker on PythonAnywhere)
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)


# Store previous status for comparison
_book_previous_status = {}
_payout_previous_status = {}


@receiver(pre_save, sender='core.Book')
def book_pre_save(sender, instance, **kwargs):
    """Store previous status before save for comparison."""
    if instance.pk:
        try:
            old_book = sender.objects.get(pk=instance.pk)
            _book_previous_status[instance.pk] = old_book.status
        except sender.DoesNotExist:
            pass


@receiver(post_save, sender='core.Book')
def book_status_changed(sender, instance, created, **kwargs):
    """
    Send notification when book status changes.
    Per Planning Document Section 12.
    """
    if created:
        return  # Don't notify on creation
    
    previous_status = _book_previous_status.pop(instance.pk, None)
    if not previous_status or previous_status == instance.status:
        return  # No status change
    
    from core.models import Book
    from core.tasks import send_book_approved_notification, send_book_denied_notification
    
    # In Review → Approved
    if previous_status == Book.Status.IN_REVIEW and instance.status == Book.Status.APPROVED:
        logger.info(f"Book {instance.id} approved, sending notification")
        try:
            send_book_approved_notification(instance.id)
        except Exception as e:
            logger.error(f"Failed to send book approved notification: {e}")
    
    # In Review → Denied
    elif previous_status == Book.Status.IN_REVIEW and instance.status == Book.Status.DENIED:
        logger.info(f"Book {instance.id} denied, sending notification")
        try:
            send_book_denied_notification(instance.id)
        except Exception as e:
            logger.error(f"Failed to send book denied notification: {e}")


@receiver(pre_save, sender='core.PayoutRequest')
def payout_pre_save(sender, instance, **kwargs):
    """Store previous status before save for comparison."""
    if instance.pk:
        try:
            old_payout = sender.objects.get(pk=instance.pk)
            _payout_previous_status[instance.pk] = old_payout.status
        except sender.DoesNotExist:
            pass


@receiver(post_save, sender='core.PayoutRequest')
def payout_status_changed(sender, instance, created, **kwargs):
    """
    Send notification when payout status changes.
    Per Planning Document Section 12.
    """
    if created:
        return  # Don't notify on creation
    
    previous_status = _payout_previous_status.pop(instance.pk, None)
    if not previous_status or previous_status == instance.status:
        return  # No status change
    
    from core.models import PayoutRequest
    from core.tasks import send_payout_status_notification
    
    status_map = {
        PayoutRequest.Status.PROCESSING: 'processing',
        PayoutRequest.Status.COMPLETED: 'completed',
        PayoutRequest.Status.FAILED: 'failed',
    }
    
    new_status = status_map.get(instance.status)
    if new_status and previous_status in [PayoutRequest.Status.PENDING, PayoutRequest.Status.PROCESSING]:
        logger.info(f"Payout {instance.id} status changed to {new_status}, sending notification")
        try:
            send_payout_status_notification(instance.id, new_status)
        except Exception as e:
            logger.error(f"Failed to send payout notification: {e}")


@receiver(post_save, sender='core.Purchase')
def purchase_created(sender, instance, created, **kwargs):
    """
    Send purchase receipt when new purchase is completed.
    """
    from core.models import Purchase
    from core.tasks import send_purchase_receipt
    
    if created and instance.payment_status == Purchase.PaymentStatus.COMPLETED:
        logger.info(f"Purchase {instance.id} completed, sending receipt")
        try:
            send_purchase_receipt(instance.id)
        except Exception as e:
            logger.error(f"Failed to send purchase receipt: {e}")
