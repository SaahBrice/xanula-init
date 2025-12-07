"""
Notification tasks for Django-Q background processing.
Per Architecture Document Section 14 (Background Tasks & Notifications).

These functions are designed to be called via async_task() from django_q.
"""

from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def get_email_context():
    """Get common context for all email templates."""
    return {
        'site_url': settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'http://localhost:8000',
        'current_year': datetime.now().year,
    }


def send_book_approved_notification(book_id):
    """
    Send notification email when book is approved.
    Called via Django-Q async_task.
    """
    from core.models import Book
    
    try:
        book = Book.objects.select_related('author').get(id=book_id)
        user = book.author
        
        if not user.email:
            logger.warning(f"No email for author of book {book_id}")
            return
        
        context = get_email_context()
        context['book'] = book
        
        html_content = render_to_string('emails/book_approved.html', context)
        text_content = strip_tags(html_content)
        
        msg = EmailMultiAlternatives(
            subject=f'🎉 "{book.title}" is now live on Xanula!',
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        
        logger.info(f"Sent book approval notification for book {book_id} to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send book approval notification for book {book_id}: {e}")
        return False


def send_book_denied_notification(book_id):
    """
    Send notification email when book is denied.
    Called via Django-Q async_task.
    """
    from core.models import Book
    
    try:
        book = Book.objects.select_related('author').get(id=book_id)
        user = book.author
        
        if not user.email:
            logger.warning(f"No email for author of book {book_id}")
            return
        
        context = get_email_context()
        context['book'] = book
        
        html_content = render_to_string('emails/book_denied.html', context)
        text_content = strip_tags(html_content)
        
        msg = EmailMultiAlternatives(
            subject=f'Update on "{book.title}" submission - Xanula',
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        
        logger.info(f"Sent book denial notification for book {book_id} to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send book denial notification for book {book_id}: {e}")
        return False


def send_payout_status_notification(payout_id, status):
    """
    Send notification email when payout status changes.
    Called via Django-Q async_task.
    
    Args:
        payout_id: PayoutRequest ID
        status: 'processing', 'completed', or 'failed'
    """
    from core.models import PayoutRequest
    
    try:
        payout = PayoutRequest.objects.select_related('author').get(id=payout_id)
        user = payout.author
        
        if not user.email:
            logger.warning(f"No email for author of payout {payout_id}")
            return
        
        context = get_email_context()
        context['payout'] = payout
        context['status'] = status
        
        subjects = {
            'processing': f'💳 Your payout is being processed - Xanula',
            'completed': f'✅ Payout completed: {payout.amount:,.0f} XAF - Xanula',
            'failed': f'⚠️ Payout issue - Action needed - Xanula',
        }
        
        html_content = render_to_string('emails/payout_status.html', context)
        text_content = strip_tags(html_content)
        
        msg = EmailMultiAlternatives(
            subject=subjects.get(status, 'Payout Update - Xanula'),
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        
        logger.info(f"Sent payout status ({status}) notification for payout {payout_id} to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send payout status notification for payout {payout_id}: {e}")
        return False


def send_daily_reminder(user_id, book_id, entry_id):
    """
    Send daily reading reminder to a user.
    Called via Django-Q async_task.
    """
    from django.contrib.auth import get_user_model
    from core.models import Book, LibraryEntry
    
    User = get_user_model()
    
    try:
        user = User.objects.get(id=user_id)
        book = Book.objects.get(id=book_id)
        entry = LibraryEntry.objects.get(id=entry_id)
        
        if not user.email:
            logger.warning(f"No email for user {user_id}")
            return
        
        # Calculate progress percentage
        progress_percent = 0
        if entry.reading_progress > 0:
            # Estimate based on page count (assume 300 pages average if not available)
            progress_percent = min(100, int((entry.reading_progress / 300) * 100))
        elif entry.listening_progress > 0:
            # Estimate based on audiobook duration (assume 10 hours average)
            progress_percent = min(100, int((entry.listening_progress / 36000) * 100))
        
        context = get_email_context()
        context['user'] = user
        context['book'] = book
        context['entry'] = entry
        context['progress_percent'] = progress_percent
        
        html_content = render_to_string('emails/daily_reminder.html', context)
        text_content = strip_tags(html_content)
        
        msg = EmailMultiAlternatives(
            subject=f'📖 Continue "{book.title}" on Xanula',
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        
        logger.info(f"Sent daily reminder for user {user_id} book {book_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send daily reminder for user {user_id}: {e}")
        return False


def send_purchase_receipt(purchase_id):
    """
    Send purchase receipt email.
    Called via Django-Q async_task.
    """
    from core.models import Purchase
    
    try:
        purchase = Purchase.objects.select_related('book', 'buyer').get(id=purchase_id)
        user = purchase.buyer
        book = purchase.book
        
        if not user.email:
            logger.warning(f"No email for buyer of purchase {purchase_id}")
            return
        
        context = get_email_context()
        context['purchase'] = purchase
        context['book'] = book
        context['user'] = user
        
        html_content = render_to_string('emails/purchase_receipt.html', context)
        text_content = strip_tags(html_content)
        
        msg = EmailMultiAlternatives(
            subject=f'🎉 Your Xanula Purchase: {book.title}',
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        
        logger.info(f"Sent purchase receipt for purchase {purchase_id} to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send purchase receipt for purchase {purchase_id}: {e}")
        return False
