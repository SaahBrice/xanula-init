"""
Test script for Admin Email Notifications (Forces SMTP).
Run with: .\venv\Scripts\python.exe test_admin_email_smtp.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xanula_project.settings')
django.setup()

# Force SMTP backend (override console backend)
from django.conf import settings
settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone

User = get_user_model()

def test_simple_email():
    """Test sending a simple email directly."""
    
    admin_email = "saahbrice98@gmail.com"
    
    print("="*60)
    print("🧪 SMTP EMAIL TEST")
    print("="*60)
    
    # Print current email settings
    print(f"\n📧 Email Settings:")
    print(f"   EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
    print(f"   EMAIL_HOST: {settings.EMAIL_HOST}")
    print(f"   EMAIL_PORT: {settings.EMAIL_PORT}")
    print(f"   EMAIL_HOST_USER: {settings.EMAIL_HOST_USER[:5]}..." if settings.EMAIL_HOST_USER else "   EMAIL_HOST_USER: NOT SET ❌")
    print(f"   EMAIL_HOST_PASSWORD: {'*' * 8}..." if settings.EMAIL_HOST_PASSWORD else "   EMAIL_HOST_PASSWORD: NOT SET ❌")
    print(f"   EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
    print(f"   DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
    
    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        print("\n❌ ERROR: Email credentials not configured in .env file!")
        print("   Please add EMAIL_HOST_USER and EMAIL_HOST_PASSWORD to your .env")
        return
    
    print(f"\n🚀 Sending test email to {admin_email}...")
    
    try:
        send_mail(
            subject="🧪 Xanula Test Email - Admin Notifications",
            message="This is a test email to verify your admin notification system is working.\n\nIf you received this, the email configuration is correct!",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[admin_email],
            fail_silently=False,
        )
        print("✅ Email sent successfully!")
        print(f"\n📬 Check your inbox at: {admin_email}")
        
    except Exception as e:
        print(f"\n❌ Failed to send email: {e}")
        print("\nPossible issues:")
        print("  1. Gmail 'Less secure apps' is not enabled")
        print("  2. You need to use an App Password (if 2FA is enabled)")
        print("  3. Check your EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in .env")


if __name__ == "__main__":
    test_simple_email()
