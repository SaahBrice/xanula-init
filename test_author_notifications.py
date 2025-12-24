"""
Test script for Author Email Notifications.
Run with: .\venv\Scripts\python.exe test_author_notifications.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xanula_project.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.conf import settings
from core.tasks import (
    notify_author_async,
    notify_author_new_sale,
    notify_author_new_review,
    notify_author_donation,
    notify_author_hard_copy_order,
    notify_author_ebook_ready,
    notify_author_audiobook_ready,
    notify_author_book_status_change,
    notify_author_payout_status,
    notify_author_milestone,
)
import time

User = get_user_model()


def test_author_notifications():
    """Test sending author notifications."""
    
    author_email = "saahbrice98@gmail.com"
    
    print("="*60)
    print("🧪 AUTHOR NOTIFICATION TESTER")
    print("="*60)
    
    # Find the author user
    try:
        author = User.objects.get(email=author_email)
        print(f"✅ Found author: {author.get_display_name()} ({author.email})")
    except User.DoesNotExist:
        print(f"❌ User {author_email} not found. Please create this user first.")
        return
    
    # Find a book by this author
    from core.models import Book
    books = Book.objects.filter(author=author)
    if books.exists():
        book = books.first()
        print(f"✅ Found book: {book.title}")
    else:
        book = None
        print("⚠️  No books found for this author. Using mock data.")
    
    print("\n" + "="*60)
    print("Testing Author Notifications...")
    print("="*60)
    
    # Test 1: Generic author notification
    print("\n1️⃣ Testing 'Generic Author Notification'...")
    notify_author_async(
        user=author,
        notification_type='system',
        title="Test Author Notification",
        message="This is a test notification to verify the author notification system is working!",
        icon="🧪",
        book=book,
        details={
            "Test Field 1": "Value 1",
            "Test Field 2": "Value 2",
            "Timestamp": str(django.utils.timezone.now()),
        },
        cta_url=f"{settings.SITE_URL}/my-books/",
        cta_text="View My Books"
    )
    print("   ✅ Sent!")
    
    # Test 2: New Sale notification
    print("\n2️⃣ Testing 'New Sale' notification...")
    notify_author_async(
        user=author,
        notification_type='new_sale',
        title=f"New Sale: {book.title if book else 'Test Book'}",
        message="Congratulations! Someone just purchased your book.",
        icon="🎉",
        book=book,
        details={
            "Buyer": "Test Buyer",
            "Sale Amount": "5,000 XAF",
            "Your Earnings": "4,250 XAF",
            "Total Sales": "25 copies",
        },
        cta_url=f"{settings.SITE_URL}/my-books/analytics/",
        cta_text="View Analytics"
    )
    print("   ✅ Sent!")
    
    # Test 3: New Review notification
    print("\n3️⃣ Testing 'New Review' notification...")
    notify_author_async(
        user=author,
        notification_type='new_review',
        title="New 5-Star Review",
        message=f"Your book received a new review!",
        icon="⭐",
        book=book,
        details={
            "Reviewer": "Happy Reader",
            "Rating": "⭐⭐⭐⭐⭐",
            "Comment": "Amazing book! Highly recommended for everyone...",
        },
        cta_url=f"{settings.SITE_URL}/books/test/",
        cta_text="View Review"
    )
    print("   ✅ Sent!")
    
    # Test 4: Donation received notification
    print("\n4️⃣ Testing 'Donation Received' notification...")
    notify_author_async(
        user=author,
        notification_type='new_donation',
        title="You Received a Tip!",
        message="Someone just showed their appreciation for your work.",
        icon="❤️",
        book=book,
        details={
            "From": "Generous Fan",
            "Amount": "2,000 XAF",
            "Your Earnings": "1,700 XAF",
            "Message": "Keep writing amazing stories!",
        },
        cta_url=f"{settings.SITE_URL}/my-books/donations/",
        cta_text="View Donations"
    )
    print("   ✅ Sent!")
    
    # Test 5: Ebook Ready notification
    print("\n5️⃣ Testing 'Ebook Ready' notification...")
    notify_author_async(
        user=author,
        notification_type='ebook_ready',
        title="Ebook Ready!",
        message=f"Your book has been converted to ebook format.",
        icon="📖",
        book=book,
        details={
            "Book": book.title if book else "Test Book",
            "Status": "Ebook Available",
        },
        cta_url=f"{settings.SITE_URL}/books/test/",
        cta_text="View Book"
    )
    print("   ✅ Sent!")
    
    # Test 6: Sales Milestone notification
    print("\n6️⃣ Testing 'Sales Milestone' notification...")
    notify_author_async(
        user=author,
        notification_type='system',
        title="Milestone: 100 Sales!",
        message=f"Congratulations! Your book has reached 100 sales!",
        icon="🏆",
        book=book,
        details={
            "Book": book.title if book else "Test Book",
            "Total Sales": "100 copies",
            "Milestone": "100 sales",
        },
        cta_url=f"{settings.SITE_URL}/my-books/analytics/",
        cta_text="View Analytics"
    )
    print("   ✅ Sent!")
    
    print("\n⏳ Waiting 15 seconds for all emails to be sent...")
    time.sleep(15)
    
    print("\n" + "="*60)
    print("✅ All test notifications sent!")
    print(f"   Check your inbox at: {author_email}")
    print("   You should receive 6 emails from Xanula")
    print("="*60)
    
    # Also check in-app notifications
    from core.models import Notification
    notif_count = Notification.objects.filter(user=author).count()
    unread_count = Notification.get_unread_count(author)
    print(f"\n📱 In-App Notifications:")
    print(f"   Total: {notif_count}")
    print(f"   Unread: {unread_count}")


if __name__ == "__main__":
    test_author_notifications()
