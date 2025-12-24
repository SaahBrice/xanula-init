"""
Test script for Admin Email Notifications.
Run with: python test_admin_notifications.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xanula_project.settings')
django.setup()

from django.contrib.auth import get_user_model
from core.tasks import send_admin_email_async
import time

User = get_user_model()

def test_admin_email():
    """Test sending an admin notification email."""
    
    # Check if saahbrice98@gmail.com is a superuser
    admin_email = "saahbrice98@gmail.com"
    
    try:
        admin_user = User.objects.get(email=admin_email)
        if not admin_user.is_superuser:
            print(f"⚠️  {admin_email} is not a superuser. Making them one...")
            admin_user.is_superuser = True
            admin_user.is_staff = True
            admin_user.save()
            print(f"✅ {admin_email} is now a superuser!")
        else:
            print(f"✅ {admin_email} is already a superuser")
    except User.DoesNotExist:
        print(f"❌ User {admin_email} not found. Please create this user first.")
        return
    
    # Get all admin emails for verification
    admin_emails = list(User.objects.filter(
        is_superuser=True, 
        is_active=True
    ).values_list('email', flat=True))
    print(f"\n📧 Admin emails that will receive notifications: {admin_emails}")
    
    # Send test notification
    print("\n🚀 Sending test admin notification...")
    
    send_admin_email_async(
        title="Test Admin Notification",
        message="This is a test notification to verify the admin email system is working correctly.",
        icon="🧪",
        priority="high",
        details={
            "Test Field 1": "This is a test value",
            "Test Field 2": "Another test value",
            "Timestamp": str(django.utils.timezone.now()),
        }
    )
    
    print("✅ Notification sent (in background thread)")
    print("\n⏳ Waiting 5 seconds for email to be sent...")
    time.sleep(5)
    
    print("\n📬 Check your inbox at:", admin_email)
    print("   Subject should be: '🔥 [URGENT] Test Admin Notification - Xanula Admin'")


def test_specific_notifications():
    """Test each type of admin notification."""
    
    print("\n" + "="*60)
    print("Testing specific notification types...")
    print("="*60)
    
    # Test 1: Simulate new user notification
    print("\n1️⃣ Testing 'New User Registered' notification...")
    send_admin_email_async(
        title="New User Registered",
        message="A new user has joined Xanula.",
        icon="👤",
        priority="low",
        details={
            "Email": "testuser@example.com",
            "Display Name": "Test User",
            "Joined": str(django.utils.timezone.now()),
        }
    )
    print("   ✅ Sent!")
    
    # Test 2: Simulate new manuscript notification
    print("\n2️⃣ Testing 'New Book Submitted' notification...")
    send_admin_email_async(
        title="New Book Submitted",
        message="An author has submitted a new manuscript for review.",
        icon="📚",
        priority="high",
        details={
            "Book Title": "Test Book Title",
            "Author": "Test Author",
            "Author Email": "author@example.com",
            "Category": "Fiction",
            "Language": "English",
            "Price": "5,000 XAF",
        }
    )
    print("   ✅ Sent!")
    
    # Test 3: Simulate payout request notification
    print("\n3️⃣ Testing 'New Payout Request' notification...")
    send_admin_email_async(
        title="New Payout Request",
        message="An author has requested a payout.",
        icon="🏦",
        priority="high",
        details={
            "Author": "Test Author",
            "Author Email": "author@example.com",
            "Amount": "50,000 XAF",
            "Method": "Mobile Money (MTN)",
            "Account Details": "+237 6XX XXX XXX",
        }
    )
    print("   ✅ Sent!")
    
    print("\n⏳ Waiting 10 seconds for all emails to be sent...")
    time.sleep(10)
    
    print("\n" + "="*60)
    print("✅ All test notifications sent!")
    print("   Check your inbox for 4 emails from Xanula Admin")
    print("="*60)


if __name__ == "__main__":
    print("="*60)
    print("🧪 ADMIN EMAIL NOTIFICATION TESTER")
    print("="*60)
    
    # Run basic test
    test_admin_email()
    
    # Ask if user wants to run all notification tests
    response = input("\n\nDo you want to test all notification types? (y/n): ").strip().lower()
    if response == 'y':
        test_specific_notifications()
    else:
        print("\nDone! Check your email.")
