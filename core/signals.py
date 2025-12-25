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


# =============================================================================
# ADMIN EMAIL NOTIFICATIONS (Triggered by signals)
# =============================================================================

# Thresholds for large transaction notifications (in XAF)
LARGE_PURCHASE_THRESHOLD = 10000  # 10,000 XAF
LARGE_DONATION_THRESHOLD = 5000   # 5,000 XAF


@receiver(post_save, sender='core.Book')
def notify_admin_on_book_submission(sender, instance, created, **kwargs):
    """
    Notify admin when a new book is submitted for review.
    """
    if not created:
        return  # Only for new books
    
    from core.models import Book
    
    # Only notify if book is submitted for review
    if instance.status == Book.Status.IN_REVIEW:
        logger.info(f"New book {instance.id} submitted for review, notifying admin")
        try:
            from core.tasks import notify_admin_new_manuscript
            notify_admin_new_manuscript(instance.id)
        except Exception as e:
            logger.error(f"Failed to notify admin of new manuscript: {e}")


@receiver(post_save, sender='core.UpfrontPaymentApplication')
def notify_admin_on_upfront_application(sender, instance, created, **kwargs):
    """
    Notify admin when a new upfront payment application is submitted.
    """
    if not created:
        return
    
    logger.info(f"New upfront payment application {instance.id}, notifying admin")
    try:
        from core.tasks import notify_admin_upfront_application
        notify_admin_upfront_application(instance.id)
    except Exception as e:
        logger.error(f"Failed to notify admin of upfront application: {e}")


@receiver(post_save, sender='core.PayoutRequest')
def notify_admin_on_payout_request(sender, instance, created, **kwargs):
    """
    Notify admin when a new payout request is created.
    """
    if not created:
        return
    
    logger.info(f"New payout request {instance.id}, notifying admin")
    try:
        from core.tasks import notify_admin_payout_request
        notify_admin_payout_request(instance.id)
    except Exception as e:
        logger.error(f"Failed to notify admin of payout request: {e}")


@receiver(post_save, sender='core.HardCopyRequest')
def notify_admin_on_hard_copy_request(sender, instance, created, **kwargs):
    """
    Notify admin when a new hard copy request is created.
    """
    if not created:
        return
    
    logger.info(f"New hard copy request {instance.id}, notifying admin")
    try:
        from core.tasks import notify_admin_hard_copy_request
        notify_admin_hard_copy_request(instance.id)
    except Exception as e:
        logger.error(f"Failed to notify admin of hard copy request: {e}")


# User registration signal - use string reference to avoid circular import
@receiver(post_save, sender='users.User')
def notify_admin_on_new_user(sender, instance, created, **kwargs):
    """
    Notify admin when a new user registers.
    """
    if not created:
        return
    
    logger.info(f"New user {instance.id} registered, notifying admin")
    try:
        from core.tasks import notify_admin_new_user
        notify_admin_new_user(instance.id)
    except Exception as e:
        logger.error(f"Failed to notify admin of new user: {e}")


@receiver(post_save, sender='core.Purchase')
def notify_admin_on_large_purchase(sender, instance, created, **kwargs):
    """
    Notify admin when a high-value purchase is completed.
    """
    from core.models import Purchase
    
    # Only for completed purchases above threshold
    if instance.payment_status != Purchase.PaymentStatus.COMPLETED:
        return
    
    if instance.amount_paid and instance.amount_paid >= LARGE_PURCHASE_THRESHOLD:
        logger.info(f"Large purchase {instance.id} ({instance.amount_paid} XAF), notifying admin")
        try:
            from core.tasks import notify_admin_large_purchase
            notify_admin_large_purchase(instance.id)
        except Exception as e:
            logger.error(f"Failed to notify admin of large purchase: {e}")


# Store previous donation status
_donation_previous_status = {}


@receiver(pre_save, sender='core.Donation')
def donation_pre_save(sender, instance, **kwargs):
    """Store previous status before save for comparison."""
    if instance.pk:
        try:
            old_donation = sender.objects.get(pk=instance.pk)
            _donation_previous_status[instance.pk] = old_donation.payment_status
        except sender.DoesNotExist:
            pass


@receiver(post_save, sender='core.Donation')
def notify_admin_on_large_donation(sender, instance, created, **kwargs):
    """
    Notify admin when a large donation is completed.
    """
    from core.models import Donation
    
    previous_status = _donation_previous_status.pop(instance.pk, None)
    
    # Only notify when donation status changes to COMPLETED
    if instance.payment_status != Donation.PaymentStatus.COMPLETED:
        return
    
    # Skip if it was already completed
    if previous_status == Donation.PaymentStatus.COMPLETED:
        return
    
    if instance.amount and instance.amount >= LARGE_DONATION_THRESHOLD:
        logger.info(f"Large donation {instance.id} ({instance.amount} XAF), notifying admin")
        try:
            from core.tasks import notify_admin_large_donation
            notify_admin_large_donation(instance.id)
        except Exception as e:
            logger.error(f"Failed to notify admin of large donation: {e}")


# =============================================================================
# AUTHOR NOTIFICATIONS (Triggered by signals)
# =============================================================================

# Store previous values for comparison
_book_previous_ebook = {}
_book_previous_audiobook = {}
_book_previous_sales = {}
_upfront_previous_status = {}


@receiver(pre_save, sender='core.Book')
def book_pre_save_extended(sender, instance, **kwargs):
    """
    Store previous file values and sales for comparison.
    (Extends the existing book_pre_save without replacing it)
    """
    if instance.pk:
        try:
            old_book = sender.objects.get(pk=instance.pk)
            _book_previous_ebook[instance.pk] = bool(old_book.ebook_file)
            _book_previous_audiobook[instance.pk] = bool(old_book.audiobook_file)
            _book_previous_sales[instance.pk] = old_book.total_sales
        except sender.DoesNotExist:
            pass


@receiver(post_save, sender='core.Book')
def author_book_notifications(sender, instance, created, **kwargs):
    """
    Handle all book-related author notifications:
    - Ebook ready
    - Audiobook ready
    - Sales milestones
    - Status changes (extends existing book_status_changed)
    """
    if created:
        return
    
    from core.models import Book
    
    # Get previous values
    had_ebook = _book_previous_ebook.pop(instance.pk, False)
    had_audiobook = _book_previous_audiobook.pop(instance.pk, False)
    previous_sales = _book_previous_sales.pop(instance.pk, 0)
    previous_status = _book_previous_status.get(instance.pk)  # From existing signal
    
    # 1. Ebook ready notification
    if not had_ebook and instance.ebook_file:
        logger.info(f"Book {instance.id} ebook ready, notifying author")
        try:
            from core.tasks import notify_author_ebook_ready
            notify_author_ebook_ready(instance.id)
        except Exception as e:
            logger.error(f"Failed to notify author of ebook ready: {e}")
    
    # 2. Audiobook ready notification
    if not had_audiobook and instance.audiobook_file:
        logger.info(f"Book {instance.id} audiobook ready, notifying author")
        try:
            from core.tasks import notify_author_audiobook_ready
            notify_author_audiobook_ready(instance.id)
        except Exception as e:
            logger.error(f"Failed to notify author of audiobook ready: {e}")
    
    # 3. Sales milestone notification
    milestones = [10, 50, 100, 500, 1000, 5000, 10000]
    for milestone in milestones:
        if previous_sales < milestone <= instance.total_sales:
            logger.info(f"Book {instance.id} reached {milestone} sales milestone")
            try:
                from core.tasks import notify_author_milestone
                notify_author_milestone(instance.id, milestone)
            except Exception as e:
                logger.error(f"Failed to notify author of milestone: {e}")
            break  # Only notify for one milestone at a time
    
    # 4. Extended book status change notifications (for statuses not handled by existing signal)
    if previous_status and previous_status != instance.status:
        from core.tasks import notify_author_book_status_change
        # These statuses are not handled by the existing book_status_changed signal
        extended_statuses = [
            Book.Status.EBOOK_READY,
            Book.Status.AUDIOBOOK_GENERATED,
            Book.Status.COMPLETED,
        ]
        if instance.status in extended_statuses:
            try:
                notify_author_book_status_change(instance.id, instance.status, previous_status)
            except Exception as e:
                logger.error(f"Failed to notify author of status change: {e}")


@receiver(post_save, sender='core.Purchase')
def notify_author_of_sale(sender, instance, created, **kwargs):
    """
    Notify author when their book is purchased.
    (Extends existing purchase_created which sends receipt to buyer)
    """
    from core.models import Purchase
    
    if not created:
        return
    
    if instance.payment_status != Purchase.PaymentStatus.COMPLETED:
        return
    
    logger.info(f"Purchase {instance.id} completed, notifying author")
    try:
        from core.tasks import notify_author_new_sale
        notify_author_new_sale(instance.id)
    except Exception as e:
        logger.error(f"Failed to notify author of sale: {e}")
    
    # Also check for referral commission
    if hasattr(instance, 'referral_commission') and instance.referral_commission and instance.referral_commission > 0:
        if hasattr(instance, 'referrer') and instance.referrer:
            try:
                from core.tasks import notify_author_referral_commission
                notify_author_referral_commission(instance.id, instance.referrer.id)
            except Exception as e:
                logger.error(f"Failed to notify referrer of commission: {e}")


@receiver(post_save, sender='core.Review')
def notify_author_of_review(sender, instance, created, **kwargs):
    """
    Notify author when they receive a new review.
    """
    if not created:
        return
    
    logger.info(f"Review {instance.id} created, notifying author")
    try:
        from core.tasks import notify_author_new_review
        notify_author_new_review(instance.id)
    except Exception as e:
        logger.error(f"Failed to notify author of review: {e}")


@receiver(post_save, sender='core.Donation')
def notify_author_of_donation(sender, instance, created, **kwargs):
    """
    Notify author when they receive a completed donation.
    (Extends existing donation signal which notifies admin)
    """
    from core.models import Donation
    
    previous_status = _donation_previous_status.get(instance.pk)
    
    # Only notify when donation status changes to COMPLETED
    if instance.payment_status != Donation.PaymentStatus.COMPLETED:
        return
    
    # Skip if it was already completed
    if previous_status == Donation.PaymentStatus.COMPLETED:
        return
    
    logger.info(f"Donation {instance.id} completed, notifying author")
    try:
        from core.tasks import notify_author_donation
        notify_author_donation(instance.id)
    except Exception as e:
        logger.error(f"Failed to notify author of donation: {e}")


@receiver(post_save, sender='core.HardCopyRequest')
def notify_author_of_hard_copy(sender, instance, created, **kwargs):
    """
    Notify author when someone orders a hard copy of their book.
    (Extends existing signal which notifies admin)
    """
    if not created:
        return
    
    logger.info(f"Hard copy request {instance.id} created, notifying author")
    try:
        from core.tasks import notify_author_hard_copy_order
        notify_author_hard_copy_order(instance.id)
    except Exception as e:
        logger.error(f"Failed to notify author of hard copy order: {e}")


@receiver(pre_save, sender='core.UpfrontPaymentApplication')
def upfront_pre_save(sender, instance, **kwargs):
    """Store previous status before save for comparison."""
    if instance.pk:
        try:
            old_app = sender.objects.get(pk=instance.pk)
            _upfront_previous_status[instance.pk] = old_app.status
        except sender.DoesNotExist:
            pass


@receiver(post_save, sender='core.UpfrontPaymentApplication')
def notify_author_of_upfront_status(sender, instance, created, **kwargs):
    """
    Notify author when their upfront payment application status changes.
    """
    if created:
        return  # Don't notify on creation
    
    previous_status = _upfront_previous_status.pop(instance.pk, None)
    if not previous_status or previous_status == instance.status:
        return  # No status change
    
    from core.models import UpfrontPaymentApplication
    
    status_map = {
        UpfrontPaymentApplication.Status.APPROVED: 'approved',
        UpfrontPaymentApplication.Status.REJECTED: 'rejected',
        UpfrontPaymentApplication.Status.DISBURSED: 'disbursed',
    }
    
    new_status = status_map.get(instance.status)
    if new_status:
        logger.info(f"Upfront application {instance.id} status changed to {new_status}")
        try:
            from core.tasks import notify_author_upfront_status
            notify_author_upfront_status(instance.id, new_status)
        except Exception as e:
            logger.error(f"Failed to notify author of upfront status: {e}")


@receiver(post_save, sender='core.PayoutRequest')
def notify_author_of_payout_status(sender, instance, created, **kwargs):
    """
    Notify author when payout status changes (in-app notification).
    (Extends existing signal which sends email)
    """
    if created:
        return  # Don't notify on creation
    
    previous_status = _payout_previous_status.get(instance.pk)
    if not previous_status or previous_status == instance.status:
        return  # No status change
    
    from core.models import PayoutRequest
    
    status_map = {
        PayoutRequest.Status.PROCESSING: 'processing',
        PayoutRequest.Status.COMPLETED: 'completed',
        PayoutRequest.Status.FAILED: 'failed',
    }
    
    new_status = status_map.get(instance.status)
    if new_status:
        try:
            from core.tasks import notify_author_payout_status
            notify_author_payout_status(instance.id, new_status)
        except Exception as e:
            logger.error(f"Failed to notify author of payout status change: {e}")


# =============================================================================
# READER NOTIFICATIONS (Triggered by signals)
# =============================================================================

# Store previous HardCopyRequest status
_hardcopy_previous_status = {}


@receiver(post_save, sender='core.Purchase')
def notify_reader_of_purchase(sender, instance, created, **kwargs):
    """
    Notify reader when their purchase is confirmed.
    (Extends existing purchase_created which sends receipt to buyer)
    """
    from core.models import Purchase
    
    if not created:
        return
    
    if instance.payment_status != Purchase.PaymentStatus.COMPLETED:
        return
    
    logger.info(f"Purchase {instance.id} completed, notifying reader")
    try:
        from core.tasks import notify_reader_purchase_confirmed
        notify_reader_purchase_confirmed(instance.id)
    except Exception as e:
        logger.error(f"Failed to notify reader of purchase: {e}")
    
    # Also notify referrer if this was a referred purchase
    if instance.referred_by and instance.referral_commission and instance.referral_commission > 0:
        logger.info(f"Purchase {instance.id} was a referral, notifying referrer")
        try:
            from core.tasks import notify_reader_referral_purchase
            notify_reader_referral_purchase(instance.referred_by.id, instance.id)
        except Exception as e:
            logger.error(f"Failed to notify referrer of purchase: {e}")


@receiver(pre_save, sender='core.HardCopyRequest')
def hardcopy_pre_save(sender, instance, **kwargs):
    """Store previous status before save for comparison."""
    if instance.pk:
        try:
            old_req = sender.objects.get(pk=instance.pk)
            _hardcopy_previous_status[instance.pk] = old_req.status
        except sender.DoesNotExist:
            pass


@receiver(post_save, sender='core.HardCopyRequest')
def notify_reader_of_hardcopy_status(sender, instance, created, **kwargs):
    """
    Notify reader when their hard copy request status changes.
    """
    if created:
        return  # Don't notify on creation (handled elsewhere for admin/author)
    
    previous_status = _hardcopy_previous_status.pop(instance.pk, None)
    if not previous_status or previous_status == instance.status:
        return  # No status change
    
    from core.models import HardCopyRequest
    
    # Only notify on these status transitions
    notify_statuses = [
        HardCopyRequest.Status.PROCESSING,
        HardCopyRequest.Status.SHIPPED,
        HardCopyRequest.Status.DELIVERED,
    ]
    
    if instance.status in notify_statuses:
        logger.info(f"Hard copy request {instance.id} status changed to {instance.status}")
        try:
            from core.tasks import notify_reader_hard_copy_status
            notify_reader_hard_copy_status(instance.id, instance.status)
        except Exception as e:
            logger.error(f"Failed to notify reader of hard copy status: {e}")
