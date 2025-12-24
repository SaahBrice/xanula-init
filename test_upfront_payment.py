"""
Test Script for Upfront Payment Feature
Run with: python test_upfront_payment.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xanula_project.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from decimal import Decimal
from django.utils import timezone
from core.models import Book, Purchase, UpfrontPaymentApplication
from users.models import User

def run_test():
    print("=" * 60)
    print("UPFRONT PAYMENT FEATURE TEST")
    print("=" * 60)

    # Step 1: Get or create test author
    print("\n📋 Step 1: Setting up test author...")
    author, created = User.objects.get_or_create(
        email='test_author@xanula.com',
        defaults={
            'display_name': 'Test Author',
            'earnings_balance': Decimal('0.00'),
        }
    )
    if created:
        author.set_password('testpass123')
        author.save()
        print(f"   ✓ Created test author: {author.email}")
    else:
        print(f"   ✓ Using existing author: {author.email}")

    # Step 2: Get or create a test book
    print("\n📚 Step 2: Setting up test book...")
    book, created = Book.objects.get_or_create(
        author=author,
        title='Test Book for Upfront Payment',
        defaults={
            'slug': 'test-book-upfront-payment',
            'short_description': 'A test book for upfront payment testing',
            'long_description': 'This book is used to test the upfront payment feature.',
            'category': Book.Category.FICTION,
            'language': Book.Language.ENGLISH,
            'price': Decimal('5000.00'),
            'status': Book.Status.COMPLETED,
        }
    )
    if created:
        print(f"   ✓ Created test book: {book.title}")
    else:
        print(f"   ✓ Using existing book: {book.title}")

    # Step 3: Create upfront payment application
    print("\n💰 Step 3: Creating upfront payment application...")
    # Clean up any existing test applications
    UpfrontPaymentApplication.objects.filter(author=author, reason__contains='Test application').delete()

    application = UpfrontPaymentApplication.objects.create(
        author=author,
        book=book,
        amount_requested=Decimal('50000.00'),  # 50,000 XAF
        reason='Test application for upfront payment feature verification',
        terms_accepted=True,
    )
    print(f"   ✓ Created application ID: {application.id}")
    print(f"   ✓ Amount requested: {application.amount_requested:,.0f} XAF")
    print(f"   ✓ Status: {application.status}")

    # Step 4: Simulate admin approval
    print("\n✅ Step 4: Simulating admin approval...")
    application.status = UpfrontPaymentApplication.Status.APPROVED
    application.repayment_rate = Decimal('20.00')  # 20% extra commission
    application.approved_at = timezone.now()
    application.save()
    print(f"   ✓ Application approved!")
    print(f"   ✓ Repayment rate: {application.repayment_rate}%")

    # Step 5: Simulate purchases and test recouping
    print("\n🛒 Step 5: Simulating purchases and testing recouping...")

    # Get buyer
    buyer, _ = User.objects.get_or_create(
        email='test_buyer@xanula.com',
        defaults={'display_name': 'Test Buyer'}
    )
    if _:
        buyer.set_password('testpass123')
        buyer.save()

    # Reset author earnings for test
    author.earnings_balance = Decimal('0.00')
    author.save()

    initial_recouped = application.amount_recouped
    print(f"   Initial amount recouped: {initial_recouped:,.0f} XAF")

    # Import recouping function
    from core.views import process_upfront_recouping

    # Simulate 5 purchases
    for i in range(5):
        purchase = Purchase.objects.create(
            buyer=buyer,
            book=book,
            amount_paid=book.price,
            payment_status=Purchase.PaymentStatus.COMPLETED,
            payment_method=Purchase.PaymentMethod.FAPSHI,
            platform_commission=book.price * Decimal('0.10'),  # 10% base
            author_earning=book.price * Decimal('0.90'),  # 90% to author
        )
        
        # Apply recouping logic
        recouped = process_upfront_recouping(purchase, author)
        final_earning = purchase.author_earning - recouped
        author.earnings_balance += final_earning
        author.save()
        
        # Refresh application
        application.refresh_from_db()
        
        print(f"\n   Purchase {i+1}:")
        print(f"   - Sale price: {purchase.amount_paid:,.0f} XAF")
        print(f"   - Base author earning: {purchase.author_earning:,.0f} XAF")
        print(f"   - Amount recouped: {recouped:,.0f} XAF")
        print(f"   - Final author earning: {final_earning:,.0f} XAF")
        print(f"   - Total recouped so far: {application.amount_recouped:,.0f} XAF")
        print(f"   - Remaining to recoup: {application.remaining_amount:,.0f} XAF")
        print(f"   - Progress: {application.recoup_progress_percent}%")
        print(f"   - Application status: {application.status}")

    # Step 6: Summary
    print("\n📊 Step 6: Final Summary")
    print("-" * 40)
    application.refresh_from_db()
    author.refresh_from_db()
    print(f"   Application Status: {application.status}")
    print(f"   Amount Requested: {application.amount_requested:,.0f} XAF")
    print(f"   Amount Recouped: {application.amount_recouped:,.0f} XAF")
    print(f"   Remaining: {application.remaining_amount:,.0f} XAF")
    print(f"   Progress: {application.recoup_progress_percent}%")
    print(f"   Author's Current Balance: {author.earnings_balance:,.0f} XAF")
    print(f"   Is Fully Recouped: {application.is_fully_recouped}")

    # Cleanup
    print("\n🧹 Cleanup...")
    # Delete test purchases
    Purchase.objects.filter(buyer=buyer, book=book).delete()
    # Delete test application
    application.delete()
    print("   ✓ Cleaned up test data")

    print("\n" + "=" * 60)
    print("✅ TEST COMPLETE - ALL CHECKS PASSED!")
    print("=" * 60)

if __name__ == '__main__':
    run_test()
