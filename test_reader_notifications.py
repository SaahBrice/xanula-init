"""
Test script for Reader Email Notifications.
Run with: .\venv\Scripts\python.exe test_reader_notifications.py
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
    notify_reader_async,
    notify_reader_purchase_confirmed,
    notify_reader_referral_purchase,
    notify_reader_balance_added,
    notify_reader_hard_copy_status,
)
import time

User = get_user_model()


def test_reader_notifications():
    """Test sending reader notifications."""
    
    reader_email = "saahbrice98@gmail.com"
    
    print("="*60)
    print("🧪 READER NOTIFICATION TESTER")
    print("="*60)
    
    # Find the reader user
    try:
        reader = User.objects.get(email=reader_email)
        print(f"✅ Found reader: {reader.get_display_name()} ({reader.email})")
    except User.DoesNotExist:
        print(f"❌ User {reader_email} not found. Please create this user first.")
        return
    
    # Find a book for context
    from core.models import Book
    books = Book.objects.all()[:1]
    if books.exists():
        book = books.first()
        print(f"✅ Using book: {book.title}")
    else:
        book = None
        print("⚠️  No books found. Using mock data without book context.")
    
    print("\n" + "="*60)
    print("Testing Reader Notifications...")
    print("="*60)
    
    # Test 1: Purchase Confirmed notification
    print("\n1️⃣ Testing 'Purchase Confirmed' notification...")
    notify_reader_async(
        user=reader,
        notification_type='purchase_confirmed',
        title="Purchase Confirmed!",
        message=f"Your purchase of '{book.title if book else 'Test Book'}' is complete. Enjoy reading!",
        icon="✅",
        book=book,
        details={
            "Book": book.title if book else "Test Book",
            "Author": book.author.get_display_name() if book else "Test Author",
            "Amount Paid": "5,000 XAF",
        },
        cta_url=f"{settings.SITE_URL}/library/",
        cta_text="Go to Library"
    )
    print("   ✅ Sent!")
    
    # Test 2: Referral Commission notification
    print("\n2️⃣ Testing 'Referral Commission Earned' notification...")
    notify_reader_async(
        user=reader,
        notification_type='referral_earned',
        title="Referral Commission Earned!",
        message="Someone used your referral code! You earned a commission.",
        icon="💵",
        book=book,
        details={
            "Book Purchased": book.title if book else "Test Book",
            "Commission Earned": "500 XAF",
            "New User": "New Reader",
        },
        cta_url=f"{settings.SITE_URL}/profile/",
        cta_text="View Balance"
    )
    print("   ✅ Sent!")
    
    # Test 3: Balance Added notification
    print("\n3️⃣ Testing 'Balance Added' notification...")
    notify_reader_async(
        user=reader,
        notification_type='system',
        title="Balance Added!",
        message="Your account balance has been credited.",
        icon="💰",
        details={
            "Amount Added": "2,500 XAF",
            "Reason": "Refund",
            "New Balance": "7,500 XAF",
        },
        cta_url=f"{settings.SITE_URL}/profile/",
        cta_text="View Balance"
    )
    print("   ✅ Sent!")
    
    # Test 4: Hard Copy Shipped notification
    print("\n4️⃣ Testing 'Hard Copy Shipped' notification...")
    notify_reader_async(
        user=reader,
        notification_type='hard_copy',
        title="Order Shipped!",
        message="Your hard copy has been shipped!",
        icon="🚚",
        book=book,
        details={
            "Book": book.title if book else "Test Book",
            "Status": "Shipped",
            "Tracking Number": "XANULA-HC-12345",
            "Shipping Address": "Douala, Cameroon",
        },
        cta_url=f"{settings.SITE_URL}/profile/orders/",
        cta_text="View Order"
    )
    print("   ✅ Sent!")
    
    # Test 5: Hard Copy Delivered notification
    print("\n5️⃣ Testing 'Hard Copy Delivered' notification...")
    notify_reader_async(
        user=reader,
        notification_type='hard_copy',
        title="Order Delivered!",
        message="Your hard copy has been delivered. Enjoy!",
        icon="📦",
        book=book,
        details={
            "Book": book.title if book else "Test Book",
            "Status": "Delivered",
            "Delivered To": "Douala, Cameroon",
        },
        cta_url=f"{settings.SITE_URL}/library/",
        cta_text="View Library"
    )
    print("   ✅ Sent!")
    
    print("\n⏳ Waiting 15 seconds for all emails to be sent...")
    time.sleep(15)
    
    print("\n" + "="*60)
    print("✅ All test notifications sent!")
    print(f"   Check your inbox at: {reader_email}")
    print("   You should receive 5 emails from Xanula")
    print("="*60)
    
    # Also check in-app notifications
    from core.models import Notification
    notif_count = Notification.objects.filter(user=reader).count()
    unread_count = Notification.get_unread_count(reader)
    print(f"\n📱 In-App Notifications:")
    print(f"   Total: {notif_count}")
    print(f"   Unread: {unread_count}")


if __name__ == "__main__":
    test_reader_notifications()
