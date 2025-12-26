#!/usr/bin/env python
"""
Send announcement email to early users.

Usage:
    # Test with one email:
    python send_early_user_email.py --test saahbrice98@gmail.com
    
    # Send to all users:
    python send_early_user_email.py --send-all
    
    # Preview email content only:
    python send_early_user_email.py --preview
"""

import os
import sys
import argparse
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xanula_project.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django
django.setup()

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.auth import get_user_model

User = get_user_model()


def get_greeting():
    """Return appropriate greeting based on time of day."""
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning"
    elif hour < 17:
        return "Good afternoon"
    else:
        return "Good evening"


def send_announcement_email(user_email, user_name=None, dry_run=False):
    """
    Send announcement email to a specific user.
    
    Args:
        user_email: Email address to send to
        user_name: Display name (optional)
        dry_run: If True, just print what would be sent
    
    Returns:
        True if sent successfully, False otherwise
    """
    if not user_name:
        user_name = user_email.split('@')[0].title()
    
    context = {
        'user_name': user_name,
        'greeting': get_greeting(),
        'site_url': settings.SITE_URL,
        'year': datetime.now().year,
    }
    
    try:
        html_content = render_to_string('emails/early_user_announcement.html', context)
        text_content = strip_tags(html_content)
        
        subject = "🎉 Big Updates at Xanula - Thank You, Founding Member!"
        
        if dry_run:
            print(f"  📧 Would send to: {user_email}")
            print(f"     Subject: {subject}")
            return True
        
        # Use SMTP backend explicitly
        connection = get_connection(
            backend='django.core.mail.backends.smtp.EmailBackend',
            fail_silently=False
        )
        
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user_email],
            connection=connection,
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        
        print(f"  ✅ Sent to: {user_email}")
        return True
        
    except Exception as e:
        print(f"  ❌ Failed to send to {user_email}: {e}")
        return False


def send_to_all_users(exclude_superusers=True, dry_run=False):
    """
    Send announcement to all active users.
    
    Args:
        exclude_superusers: Skip admin accounts
        dry_run: Just preview, don't actually send
    """
    users = User.objects.filter(is_active=True)
    
    if exclude_superusers:
        users = users.filter(is_superuser=False)
    
    users = users.exclude(email='').exclude(email__isnull=True)
    
    total = users.count()
    success = 0
    failed = 0
    
    print(f"\n{'=' * 60}")
    print(f"📬 SENDING ANNOUNCEMENT TO {total} USERS")
    if dry_run:
        print("   (DRY RUN - No emails will actually be sent)")
    print(f"{'=' * 60}\n")
    
    for user in users:
        result = send_announcement_email(
            user_email=user.email,
            user_name=user.get_display_name() if hasattr(user, 'get_display_name') else user.email.split('@')[0],
            dry_run=dry_run
        )
        if result:
            success += 1
        else:
            failed += 1
    
    print(f"\n{'=' * 60}")
    print(f"📊 SUMMARY")
    print(f"{'=' * 60}")
    print(f"✅ Success: {success}")
    print(f"❌ Failed: {failed}")
    print(f"📧 Total: {total}")
    print()


def preview_email():
    """Print a preview of the email content."""
    context = {
        'user_name': 'John',
        'greeting': get_greeting(),
        'site_url': 'https://xanula.com',
        'year': datetime.now().year,
    }
    
    html_content = render_to_string('emails/early_user_announcement.html', context)
    
    print("\n" + "=" * 60)
    print("EMAIL PREVIEW")
    print("=" * 60)
    print(f"Subject: 🎉 Big Updates at Xanula - Thank You, Founding Member!")
    print("=" * 60)
    print("\n[HTML content would be rendered here - check the template file]")
    print(f"\nTemplate: templates/emails/early_user_announcement.html")
    print()


def main():
    parser = argparse.ArgumentParser(description='Send announcement email to early users')
    parser.add_argument('--test', metavar='EMAIL', help='Send test email to specified address')
    parser.add_argument('--send-all', action='store_true', help='Send to all users (requires confirmation)')
    parser.add_argument('--preview', action='store_true', help='Preview email content')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be sent without actually sending')
    
    args = parser.parse_args()
    
    if args.preview:
        preview_email()
    elif args.test:
        print(f"\n📧 Sending test email to: {args.test}")
        send_announcement_email(args.test)
        print("\n✅ Test email sent! Check your inbox.\n")
    elif args.send_all:
        if args.dry_run:
            send_to_all_users(dry_run=True)
        else:
            # Confirm before mass sending
            users_count = User.objects.filter(is_active=True, is_superuser=False).exclude(email='').count()
            print(f"\n⚠️  You are about to send emails to {users_count} users!")
            confirm = input("Type 'SEND' to confirm: ")
            if confirm == 'SEND':
                send_to_all_users(dry_run=False)
            else:
                print("Aborted.")
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
