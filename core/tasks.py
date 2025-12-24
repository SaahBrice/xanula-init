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


def send_hard_copy_request_notification(request_id):
    """
    Send notification emails to admin and author when a hard copy is requested.
    Called via Django-Q async_task.
    """
    from core.models import HardCopyRequest
    
    try:
        hc_request = HardCopyRequest.objects.select_related(
            'user', 'book', 'book__author'
        ).get(id=request_id)
        
        user = hc_request.user
        book = hc_request.book
        author = book.author
        
        context = get_email_context()
        context['request'] = hc_request
        context['user'] = user
        context['book'] = book
        context['author'] = author
        
        html_content = render_to_string('emails/hardcopy_request.html', context)
        text_content = strip_tags(html_content)
        
        # Send to admin
        admin_email = settings.DEFAULT_FROM_EMAIL
        msg = EmailMultiAlternatives(
            subject=f'📦 Hard Copy Request: {book.title} - Xanula',
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[admin_email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        logger.info(f"Sent hard copy notification to admin for request {request_id}")
        
        # Send to author if they have email
        if author.email and author.email != admin_email:
            msg_author = EmailMultiAlternatives(
                subject=f'📦 Hard Copy Request for "{book.title}" - Xanula',
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[author.email],
            )
            msg_author.attach_alternative(html_content, "text/html")
            msg_author.send()
            logger.info(f"Sent hard copy notification to author {author.email} for request {request_id}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to send hard copy notification for request {request_id}: {e}")
        return False


# =============================================================================
# ADMIN EMAIL NOTIFICATIONS (Non-blocking with threading)
# =============================================================================

import threading


def send_admin_email_async(title, message, icon="🔔", priority="medium", details=None):
    """
    Send an email notification to all admin users in a non-blocking thread.
    
    Args:
        title: Email subject/title
        message: Main notification message
        icon: Emoji icon for the email
        priority: 'high', 'medium', or 'low'
        details: Optional dict of key-value pairs to display
    """
    def _send():
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            # Get all superuser emails
            admin_emails = list(User.objects.filter(
                is_superuser=True, 
                is_active=True
            ).values_list('email', flat=True))
            
            if not admin_emails:
                logger.warning("No admin emails found for notification")
                return False
            
            context = get_email_context()
            context.update({
                'title': title,
                'message': message,
                'icon': icon,
                'priority': priority,
                'details': details or {},
            })
            
            html_content = render_to_string('emails/admin_notification.html', context)
            text_content = strip_tags(html_content)
            
            # Priority prefix for subject
            priority_prefix = {
                'high': '🔥 [URGENT]',
                'medium': '📋',
                'low': 'ℹ️',
            }
            
            subject = f"{priority_prefix.get(priority, '')} {title} - Xanula Admin"
            
            # Force SMTP backend for admin notifications (even in DEBUG mode)
            from django.core.mail import get_connection
            connection = get_connection(
                backend='django.core.mail.backends.smtp.EmailBackend',
                fail_silently=False
            )
            
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=admin_emails,
                connection=connection,
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            logger.info(f"Sent admin notification '{title}' to {len(admin_emails)} admins")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send admin email notification: {e}")
            return False
    
    # Run in background thread (non-blocking)
    thread = threading.Thread(target=_send, daemon=True)
    thread.start()


# Convenience functions for specific admin notifications

def notify_admin_new_manuscript(book_id):
    """Notify admin of new manuscript submission."""
    from core.models import Book
    try:
        book = Book.objects.select_related('author').get(id=book_id)
        send_admin_email_async(
            title="New Book Submitted",
            message=f"{book.author.get_display_name()} has submitted a new manuscript for review.",
            icon="📚",
            priority="high",
            details={
                "Book Title": book.title,
                "Author": book.author.get_display_name(),
                "Author Email": book.author.email,
                "Category": book.get_category_display(),
                "Language": book.get_language_display(),
                "Price": f"{book.price:,.0f} XAF" if book.price > 0 else "Free",
            }
        )
    except Exception as e:
        logger.error(f"Failed to notify admin of new manuscript {book_id}: {e}")


def notify_admin_upfront_application(application_id):
    """Notify admin of new upfront payment application."""
    from core.models import UpfrontPaymentApplication
    try:
        app = UpfrontPaymentApplication.objects.select_related('author', 'book').get(id=application_id)
        send_admin_email_async(
            title="New Upfront Payment Application",
            message=f"{app.author.get_display_name()} is requesting an advance payment.",
            icon="💰",
            priority="high",
            details={
                "Author": app.author.get_display_name(),
                "Author Email": app.author.email,
                "Book": app.book.title if app.book else "Not specified",
                "Requested Amount": f"{app.requested_amount:,.0f} XAF",
                "Reason": app.reason[:100] + "..." if len(app.reason) > 100 else app.reason,
            }
        )
    except Exception as e:
        logger.error(f"Failed to notify admin of upfront application {application_id}: {e}")


def notify_admin_payout_request(payout_id):
    """Notify admin of new payout request."""
    from core.models import PayoutRequest
    try:
        payout = PayoutRequest.objects.select_related('author').get(id=payout_id)
        send_admin_email_async(
            title="New Payout Request",
            message=f"{payout.author.get_display_name()} has requested a payout.",
            icon="🏦",
            priority="high",
            details={
                "Author": payout.author.get_display_name(),
                "Author Email": payout.author.email,
                "Amount": f"{payout.amount:,.0f} XAF",
                "Method": payout.get_payout_method_display(),
                "Account Details": payout.payment_details[:50] + "..." if len(payout.payment_details) > 50 else payout.payment_details,
            }
        )
    except Exception as e:
        logger.error(f"Failed to notify admin of payout request {payout_id}: {e}")


def notify_admin_hard_copy_request(request_id):
    """Notify admin of new hard copy request."""
    from core.models import HardCopyRequest
    try:
        req = HardCopyRequest.objects.select_related('user', 'book').get(id=request_id)
        send_admin_email_async(
            title="New Hard Copy Order",
            message=f"{req.user.get_display_name()} has ordered a hard copy.",
            icon="📦",
            priority="medium",
            details={
                "Customer": req.user.get_display_name(),
                "Customer Email": req.user.email,
                "Book": req.book.title,
                "Quantity": str(req.quantity),
                "Shipping Address": req.address[:80] + "..." if len(req.address) > 80 else req.address,
            }
        )
    except Exception as e:
        logger.error(f"Failed to notify admin of hard copy request {request_id}: {e}")


def notify_admin_new_user(user_id):
    """Notify admin of new user registration."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
        send_admin_email_async(
            title="New User Registered",
            message=f"A new user has joined Xanula.",
            icon="👤",
            priority="low",
            details={
                "Email": user.email,
                "Display Name": user.get_display_name(),
                "Joined": user.date_joined.strftime("%Y-%m-%d %H:%M"),
            }
        )
    except Exception as e:
        logger.error(f"Failed to notify admin of new user {user_id}: {e}")


def notify_admin_large_purchase(purchase_id):
    """Notify admin of high-value purchase."""
    from core.models import Purchase
    try:
        purchase = Purchase.objects.select_related('buyer', 'book', 'book__author').get(id=purchase_id)
        send_admin_email_async(
            title="Large Purchase Made!",
            message=f"A high-value purchase was completed.",
            icon="🛒",
            priority="medium",
            details={
                "Buyer": purchase.buyer.get_display_name(),
                "Book": purchase.book.title,
                "Author": purchase.book.author.get_display_name(),
                "Amount": f"{purchase.amount_paid:,.0f} XAF",
                "Commission": f"{purchase.platform_commission:,.0f} XAF",
            }
        )
    except Exception as e:
        logger.error(f"Failed to notify admin of large purchase {purchase_id}: {e}")


def notify_admin_large_donation(donation_id):
    """Notify admin of large donation."""
    from core.models import Donation
    try:
        donation = Donation.objects.select_related('donor', 'recipient').get(id=donation_id)
        send_admin_email_async(
            title="Large Donation Received!",
            message=f"A significant donation was made.",
            icon="❤️",
            priority="medium",
            details={
                "Donor": donation.donor.get_display_name() if donation.donor else "Anonymous",
                "Recipient": donation.recipient.get_display_name(),
                "Amount": f"{donation.amount:,.0f} XAF",
                "Platform Fee": f"{donation.platform_fee:,.0f} XAF",
            }
        )
    except Exception as e:
        logger.error(f"Failed to notify admin of large donation {donation_id}: {e}")


# =============================================================================
# AUTHOR NOTIFICATIONS (Email + In-App, Non-blocking with threading)
# =============================================================================

def notify_author_async(user, notification_type, title, message, icon="📚", 
                        book=None, details=None, cta_url=None, cta_text=None):
    """
    Send notification to author via Email + In-App notification.
    Uses threading for non-blocking execution.
    
    Args:
        user: Author user object
        notification_type: Notification.NotificationType value
        title: Notification title
        message: Notification message
        icon: Emoji icon
        book: Optional Book object for email template
        details: Optional dict of details to show
        cta_url: Optional call-to-action URL
        cta_text: Optional call-to-action button text
    """
    def _send():
        try:
            # 1. Create In-App Notification
            from core.models import Notification
            Notification.create_notification(
                user=user,
                notification_type=notification_type,
                title=title,
                message=message,
                icon=icon,
                related_book_id=book.id if book else None,
                related_url=cta_url or ''
            )
            logger.info(f"Created in-app notification for {user.email}: {title}")
            
            # 2. Send Email (if user has email notifications enabled)
            if not user.email:
                logger.warning(f"No email for user {user.id}")
                return
            
            # Check if user has email notifications enabled
            if hasattr(user, 'email_notifications') and not user.email_notifications:
                logger.info(f"Email notifications disabled for {user.email}")
                return
            
            context = get_email_context()
            context.update({
                'title': title,
                'message': message,
                'icon': icon,
                'book': book,
                'details': details or {},
                'cta_url': cta_url,
                'cta_text': cta_text,
            })
            
            html_content = render_to_string('emails/author_notification.html', context)
            text_content = strip_tags(html_content)
            
            # Force SMTP backend (even in DEBUG mode)
            from django.core.mail import get_connection
            connection = get_connection(
                backend='django.core.mail.backends.smtp.EmailBackend',
                fail_silently=False
            )
            
            msg = EmailMultiAlternatives(
                subject=f"{icon} {title} - Xanula",
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
                connection=connection,
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            logger.info(f"Sent author email notification to {user.email}: {title}")
            
        except Exception as e:
            logger.error(f"Failed to notify author {user.email}: {e}")
    
    # Run in background thread
    thread = threading.Thread(target=_send, daemon=True)
    thread.start()


# Specific Author Notification Functions

def notify_author_new_sale(purchase_id):
    """Notify author when their book is purchased."""
    from core.models import Purchase
    try:
        purchase = Purchase.objects.select_related('book', 'book__author', 'buyer').get(id=purchase_id)
        book = purchase.book
        author = book.author
        
        # Calculate author earnings
        author_earnings = purchase.amount_paid - purchase.platform_commission
        
        notify_author_async(
            user=author,
            notification_type='new_sale',
            title=f"New Sale: {book.title}",
            message=f"Congratulations! Someone just purchased your book.",
            icon="🎉",
            book=book,
            details={
                "Buyer": purchase.buyer.get_display_name(),
                "Sale Amount": f"{purchase.amount_paid:,.0f} XAF",
                "Your Earnings": f"{author_earnings:,.0f} XAF",
                "Total Sales": f"{book.total_sales} copies",
            },
            cta_url=f"{settings.SITE_URL}/my-books/analytics/",
            cta_text="View Analytics"
        )
    except Exception as e:
        logger.error(f"Failed to notify author of new sale {purchase_id}: {e}")


def notify_author_new_review(review_id):
    """Notify author when they receive a new review."""
    from core.models import Review
    try:
        review = Review.objects.select_related('book', 'book__author', 'reviewer').get(id=review_id)
        book = review.book
        author = book.author
        
        # Don't notify if author reviews their own book
        if review.reviewer == author:
            return
        
        stars = "⭐" * review.rating
        
        notify_author_async(
            user=author,
            notification_type='new_review',
            title=f"New {review.rating}-Star Review",
            message=f"Your book '{book.title}' received a new review!",
            icon="⭐",
            book=book,
            details={
                "Reviewer": review.reviewer.get_display_name(),
                "Rating": stars,
                "Comment": (review.content[:100] + "...") if len(review.content) > 100 else review.content,
            },
            cta_url=f"{settings.SITE_URL}/books/{book.slug}/",
            cta_text="View Review"
        )
    except Exception as e:
        logger.error(f"Failed to notify author of new review {review_id}: {e}")


def notify_author_donation(donation_id):
    """Notify author when they receive a donation/tip."""
    from core.models import Donation
    try:
        donation = Donation.objects.select_related('recipient', 'donor', 'book').get(id=donation_id)
        author = donation.recipient
        
        # Calculate net amount after platform fee
        net_amount = donation.amount - donation.platform_fee
        
        notify_author_async(
            user=author,
            notification_type='new_donation',
            title="You Received a Tip!",
            message=f"Someone just showed their appreciation for your work.",
            icon="❤️",
            book=donation.book,
            details={
                "From": donation.donor.get_display_name() if donation.donor else "Anonymous",
                "Amount": f"{donation.amount:,.0f} XAF",
                "Your Earnings": f"{net_amount:,.0f} XAF",
                "Message": donation.message[:80] if donation.message else "No message",
            },
            cta_url=f"{settings.SITE_URL}/my-books/donations/",
            cta_text="View Donations"
        )
    except Exception as e:
        logger.error(f"Failed to notify author of donation {donation_id}: {e}")


def notify_author_hard_copy_order(request_id):
    """Notify author when someone orders a hard copy of their book."""
    from core.models import HardCopyRequest
    try:
        req = HardCopyRequest.objects.select_related('book', 'book__author', 'user').get(id=request_id)
        book = req.book
        author = book.author
        
        notify_author_async(
            user=author,
            notification_type='hard_copy',
            title="Hard Copy Ordered",
            message=f"Someone ordered a printed copy of '{book.title}'!",
            icon="📦",
            book=book,
            details={
                "Customer": req.user.get_display_name(),
                "Quantity": str(req.quantity),
                "Status": "Pending",
            },
            cta_url=f"{settings.SITE_URL}/my-books/",
            cta_text="View My Books"
        )
    except Exception as e:
        logger.error(f"Failed to notify author of hard copy order {request_id}: {e}")


def notify_author_ebook_ready(book_id):
    """Notify author when their ebook conversion is complete."""
    from core.models import Book
    try:
        book = Book.objects.select_related('author').get(id=book_id)
        author = book.author
        
        notify_author_async(
            user=author,
            notification_type='ebook_ready',
            title="Ebook Ready!",
            message=f"Your book '{book.title}' has been converted to ebook format.",
            icon="📖",
            book=book,
            details={
                "Book": book.title,
                "Status": "Ebook Available",
            },
            cta_url=f"{settings.SITE_URL}/books/{book.slug}/",
            cta_text="View Book"
        )
    except Exception as e:
        logger.error(f"Failed to notify author of ebook ready {book_id}: {e}")


def notify_author_audiobook_ready(book_id):
    """Notify author when their audiobook generation is complete."""
    from core.models import Book
    try:
        book = Book.objects.select_related('author').get(id=book_id)
        author = book.author
        
        notify_author_async(
            user=author,
            notification_type='audiobook_ready',
            title="Audiobook Ready!",
            message=f"Your audiobook for '{book.title}' has been generated.",
            icon="🎧",
            book=book,
            details={
                "Book": book.title,
                "Status": "Audiobook Available",
            },
            cta_url=f"{settings.SITE_URL}/books/{book.slug}/",
            cta_text="Listen Now"
        )
    except Exception as e:
        logger.error(f"Failed to notify author of audiobook ready {book_id}: {e}")


def notify_author_book_status_change(book_id, new_status, old_status=None):
    """Notify author when their book status changes."""
    from core.models import Book
    try:
        book = Book.objects.select_related('author').get(id=book_id)
        author = book.author
        
        status_info = {
            Book.Status.APPROVED: ("Book Approved!", "Your book is now being processed.", "✅"),
            Book.Status.EBOOK_READY: ("Ebook Ready!", "Your ebook has been generated and is live.", "📖"),
            Book.Status.AUDIOBOOK_GENERATED: ("Audiobook Generated!", "Your audiobook is now available.", "🎧"),
            Book.Status.COMPLETED: ("Book Complete!", "All formats of your book are now live.", "🎉"),
            Book.Status.DENIED: ("Submission Update", "Your book submission needs attention.", "⚠️"),
        }
        
        info = status_info.get(new_status)
        if not info:
            return  # Unknown status
        
        title, message, icon = info
        
        notify_author_async(
            user=author,
            notification_type='book_status',
            title=title,
            message=message,
            icon=icon,
            book=book,
            details={
                "Book": book.title,
                "New Status": book.get_status_display(),
            },
            cta_url=f"{settings.SITE_URL}/my-books/",
            cta_text="View My Books"
        )
    except Exception as e:
        logger.error(f"Failed to notify author of book status change {book_id}: {e}")


def notify_author_payout_status(payout_id, new_status):
    """Notify author when their payout request status changes."""
    from core.models import PayoutRequest
    try:
        payout = PayoutRequest.objects.select_related('author').get(id=payout_id)
        author = payout.author
        
        status_info = {
            'processing': ("Payout Processing", "Your payout request is being processed.", "💳"),
            'completed': ("Payout Completed!", f"Your payout of {payout.amount:,.0f} XAF has been sent.", "✅"),
            'failed': ("Payout Issue", "There was an issue with your payout. Please check your details.", "⚠️"),
        }
        
        info = status_info.get(new_status)
        if not info:
            return
        
        title, message, icon = info
        
        notify_author_async(
            user=author,
            notification_type='payout_status',
            title=title,
            message=message,
            icon=icon,
            details={
                "Amount": f"{payout.amount:,.0f} XAF",
                "Method": payout.get_payout_method_display(),
                "Status": new_status.title(),
            },
            cta_url=f"{settings.SITE_URL}/my-books/payout/",
            cta_text="View Payout"
        )
    except Exception as e:
        logger.error(f"Failed to notify author of payout status {payout_id}: {e}")


def notify_author_upfront_status(application_id, new_status):
    """Notify author when their upfront payment application status changes."""
    from core.models import UpfrontPaymentApplication
    try:
        app = UpfrontPaymentApplication.objects.select_related('author', 'book').get(id=application_id)
        author = app.author
        
        status_info = {
            'approved': ("Upfront Payment Approved!", "Congratulations! Your application has been approved.", "✅"),
            'rejected': ("Application Update", "Your upfront payment application has been reviewed.", "ℹ️"),
            'disbursed': ("Payment Sent!", f"Your advance of {app.approved_amount:,.0f} XAF has been sent.", "💰"),
        }
        
        info = status_info.get(new_status)
        if not info:
            return
        
        title, message, icon = info
        
        details = {
            "Requested Amount": f"{app.requested_amount:,.0f} XAF",
            "Status": new_status.title(),
        }
        if app.approved_amount:
            details["Approved Amount"] = f"{app.approved_amount:,.0f} XAF"
        
        notify_author_async(
            user=author,
            notification_type='upfront_status',
            title=title,
            message=message,
            icon=icon,
            book=app.book,
            details=details,
            cta_url=f"{settings.SITE_URL}/my-books/upfront/",
            cta_text="View Application"
        )
    except Exception as e:
        logger.error(f"Failed to notify author of upfront status {application_id}: {e}")


def notify_author_milestone(book_id, milestone):
    """Notify author when their book reaches a sales milestone."""
    from core.models import Book
    try:
        book = Book.objects.select_related('author').get(id=book_id)
        author = book.author
        
        milestone_icons = {
            10: "🌟",
            50: "⭐",
            100: "🏆",
            500: "💎",
            1000: "👑",
        }
        
        icon = milestone_icons.get(milestone, "🎉")
        
        notify_author_async(
            user=author,
            notification_type='system',
            title=f"Milestone: {milestone} Sales!",
            message=f"Congratulations! '{book.title}' has reached {milestone} sales!",
            icon=icon,
            book=book,
            details={
                "Book": book.title,
                "Total Sales": f"{book.total_sales} copies",
                "Milestone": f"{milestone} sales",
            },
            cta_url=f"{settings.SITE_URL}/my-books/analytics/",
            cta_text="View Analytics"
        )
    except Exception as e:
        logger.error(f"Failed to notify author of milestone {book_id}: {e}")


def notify_author_referral_commission(purchase_id, referrer_id):
    """Notify author when they earn a referral commission."""
    from core.models import Purchase
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    try:
        purchase = Purchase.objects.select_related('book', 'buyer').get(id=purchase_id)
        referrer = User.objects.get(id=referrer_id)
        
        notify_author_async(
            user=referrer,
            notification_type='referral_earned',
            title="Referral Commission Earned!",
            message=f"You earned a commission from a referral purchase.",
            icon="💵",
            book=purchase.book,
            details={
                "Book": purchase.book.title,
                "Commission": f"{purchase.referral_commission:,.0f} XAF",
                "Referred User": purchase.buyer.get_display_name(),
            },
            cta_url=f"{settings.SITE_URL}/my-books/analytics/",
            cta_text="View Earnings"
        )
    except Exception as e:
        logger.error(f"Failed to notify of referral commission {purchase_id}: {e}")


# =============================================================================
# READER NOTIFICATIONS (Email + In-App, Non-blocking with threading)
# =============================================================================

def notify_reader_async(user, notification_type, title, message, icon="📚", 
                        book=None, details=None, cta_url=None, cta_text=None):
    """
    Send notification to reader via Email + In-App notification.
    Uses threading for non-blocking execution.
    
    Args:
        user: Reader user object
        notification_type: Notification.NotificationType value
        title: Notification title
        message: Notification message
        icon: Emoji icon
        book: Optional Book object for email template
        details: Optional dict of details to show
        cta_url: Optional call-to-action URL
        cta_text: Optional call-to-action button text
    """
    def _send():
        try:
            # 1. Create In-App Notification
            from core.models import Notification
            Notification.create_notification(
                user=user,
                notification_type=notification_type,
                title=title,
                message=message,
                icon=icon,
                related_book_id=book.id if book else None,
                related_url=cta_url or ''
            )
            logger.info(f"Created in-app notification for reader {user.email}: {title}")
            
            # 2. Send Email
            if not user.email:
                logger.warning(f"No email for user {user.id}")
                return
            
            # Check if user has email notifications enabled
            if hasattr(user, 'email_notifications') and not user.email_notifications:
                logger.info(f"Email notifications disabled for {user.email}")
                return
            
            context = get_email_context()
            context.update({
                'title': title,
                'message': message,
                'icon': icon,
                'book': book,
                'details': details or {},
                'cta_url': cta_url,
                'cta_text': cta_text,
            })
            
            # Reuse author_notification template (works for readers too)
            html_content = render_to_string('emails/author_notification.html', context)
            text_content = strip_tags(html_content)
            
            # Force SMTP backend (even in DEBUG mode)
            from django.core.mail import get_connection
            connection = get_connection(
                backend='django.core.mail.backends.smtp.EmailBackend',
                fail_silently=False
            )
            
            msg = EmailMultiAlternatives(
                subject=f"{icon} {title} - Xanula",
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
                connection=connection,
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            logger.info(f"Sent reader email notification to {user.email}: {title}")
            
        except Exception as e:
            logger.error(f"Failed to notify reader {user.email}: {e}")
    
    # Run in background thread
    thread = threading.Thread(target=_send, daemon=True)
    thread.start()


# Specific Reader Notification Functions

def notify_reader_purchase_confirmed(purchase_id):
    """Notify reader when their purchase is confirmed."""
    from core.models import Purchase
    try:
        purchase = Purchase.objects.select_related('book', 'book__author', 'buyer').get(id=purchase_id)
        book = purchase.book
        buyer = purchase.buyer
        
        notify_reader_async(
            user=buyer,
            notification_type='purchase_confirmed',
            title="Purchase Confirmed!",
            message=f"Your purchase of '{book.title}' is complete. Enjoy reading!",
            icon="✅",
            book=book,
            details={
                "Book": book.title,
                "Author": book.author.get_display_name(),
                "Amount Paid": f"{purchase.amount_paid:,.0f} XAF",
            },
            cta_url=f"{settings.SITE_URL}/library/",
            cta_text="Go to Library"
        )
    except Exception as e:
        logger.error(f"Failed to notify reader of purchase {purchase_id}: {e}")


def notify_reader_referral_purchase(referrer_id, purchase_id):
    """Notify reader when someone uses their referral code to make a purchase."""
    from core.models import Purchase
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    try:
        purchase = Purchase.objects.select_related('book', 'buyer').get(id=purchase_id)
        referrer = User.objects.get(id=referrer_id)
        
        notify_reader_async(
            user=referrer,
            notification_type='referral_earned',
            title="Referral Commission Earned!",
            message=f"Someone used your referral code! You earned a commission.",
            icon="💵",
            book=purchase.book,
            details={
                "Book Purchased": purchase.book.title,
                "Commission Earned": f"{purchase.referral_commission:,.0f} XAF",
                "New User": purchase.buyer.get_display_name(),
            },
            cta_url=f"{settings.SITE_URL}/profile/",
            cta_text="View Balance"
        )
    except Exception as e:
        logger.error(f"Failed to notify referrer of purchase {purchase_id}: {e}")


def notify_reader_balance_added(user_id, amount, reason="Refund"):
    """Notify reader when their balance is increased."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    try:
        user = User.objects.get(id=user_id)
        
        notify_reader_async(
            user=user,
            notification_type='system',
            title="Balance Added!",
            message=f"Your account balance has been credited.",
            icon="💰",
            details={
                "Amount Added": f"{amount:,.0f} XAF",
                "Reason": reason,
                "New Balance": f"{user.earnings_balance:,.0f} XAF" if hasattr(user, 'earnings_balance') else "Check profile",
            },
            cta_url=f"{settings.SITE_URL}/profile/",
            cta_text="View Balance"
        )
    except Exception as e:
        logger.error(f"Failed to notify user of balance added {user_id}: {e}")


def notify_reader_hard_copy_status(request_id, new_status):
    """Notify reader when their hard copy request status changes."""
    from core.models import HardCopyRequest
    try:
        req = HardCopyRequest.objects.select_related('user', 'book').get(id=request_id)
        user = req.user
        book = req.book
        
        status_info = {
            'PROCESSING': ("Order Processing", "Your hard copy order is being prepared.", "📋"),
            'SHIPPED': ("Order Shipped!", "Your hard copy has been shipped!", "🚚"),
            'DELIVERED': ("Order Delivered!", "Your hard copy has been delivered. Enjoy!", "📦"),
        }
        
        info = status_info.get(new_status)
        if not info:
            return
        
        title, message, icon = info
        
        details = {
            "Book": book.title,
            "Status": new_status.title(),
        }
        
        if req.tracking_number:
            details["Tracking Number"] = req.tracking_number
        
        if new_status == 'SHIPPED':
            details["Shipping Address"] = req.city
        
        notify_reader_async(
            user=user,
            notification_type='hard_copy',
            title=title,
            message=message,
            icon=icon,
            book=book,
            details=details,
            cta_url=f"{settings.SITE_URL}/profile/orders/",
            cta_text="View Order"
        )
    except Exception as e:
        logger.error(f"Failed to notify reader of hard copy status {request_id}: {e}")
