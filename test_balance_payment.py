"""
Test script for Balance Payment System.
Tests full balance payment and commission calculations.

Run with: python test_balance_payment.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xanula_project.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from decimal import Decimal
from django.contrib.auth import get_user_model
from core.models import Book, Purchase, LibraryEntry, CommissionSettings

User = get_user_model()


def test_purchase_model_payment_methods():
    """Test that new payment methods exist."""
    print("\n=== Test 1: Payment Method Choices ===")
    
    methods = [choice[0] for choice in Purchase.PaymentMethod.choices]
    print(f"  Available methods: {methods}")
    
    assert 'stripe' in methods, "Missing stripe"
    assert 'fapshi' in methods, "Missing fapshi"
    assert 'balance' in methods, "Missing balance"
    assert 'partial' in methods, "Missing partial"
    
    print("  ✓ All 4 payment methods available!")


def test_full_balance_purchase_simulation():
    """Test full balance purchase flow."""
    print("\n=== Test 2: Full Balance Purchase Simulation ===")
    
    # Get or create test users
    buyer, _ = User.objects.get_or_create(
        email='balance_buyer@test.com',
        defaults={'display_name': 'Balance Buyer', 'earnings_balance': Decimal('5000.00')}
    )
    # Ensure buyer has enough balance
    buyer.earnings_balance = Decimal('5000.00')
    buyer.save()
    
    author, _ = User.objects.get_or_create(
        email='balance_author@test.com',
        defaults={'display_name': 'Balance Author', 'earnings_balance': Decimal('0.00')}
    )
    author.earnings_balance = Decimal('1000.00')  # Starting balance
    author.save()
    
    print(f"  Buyer initial balance: {buyer.earnings_balance:,.0f} XAF")
    print(f"  Author initial balance: {author.earnings_balance:,.0f} XAF")
    
    # Create or get a test book
    book, _ = Book.objects.get_or_create(
        slug='test-balance-book',
        defaults={
            'title': 'Test Balance Book',
            'author': author,
            'price': Decimal('3000.00'),
            'short_description': 'Test book for balance payment',
            'long_description': 'Full description',
            'category': Book.Category.FICTION,
            'status': Book.Status.COMPLETED,
            'manuscript_file': 'test.pdf',
            'ebook_file': 'test.epub',
            'cover_image': 'test.jpg',
        }
    )
    
    # Clear any existing purchases/library entries for this test
    Purchase.objects.filter(buyer=buyer, book=book).delete()
    LibraryEntry.objects.filter(user=buyer, book=book).delete()
    
    book_price = book.price
    print(f"\n  Book price: {book_price:,.0f} XAF")
    
    # Simulate balance purchase
    print("\n  Simulating balance purchase...")
    
    # 1. Check balance is sufficient
    assert buyer.earnings_balance >= book_price, "Balance check failed"
    print("  ✓ Balance check passed")
    
    # 2. Deduct from buyer
    buyer.earnings_balance -= book_price
    buyer.save(update_fields=['earnings_balance'])
    print(f"  ✓ Deducted {book_price:,.0f} XAF from buyer")
    
    # 3. Calculate commission
    commission_rate = book.get_effective_commission_rate()
    platform_commission = book_price * commission_rate
    author_earning = book_price - platform_commission
    
    print(f"  Commission rate: {commission_rate * 100}%")
    print(f"  Platform gets: {platform_commission:,.0f} XAF")
    print(f"  Author gets: {author_earning:,.0f} XAF")
    
    # 4. Create purchase record
    purchase = Purchase.objects.create(
        buyer=buyer,
        book=book,
        amount_paid=book_price,
        payment_method=Purchase.PaymentMethod.BALANCE,
        payment_status=Purchase.PaymentStatus.COMPLETED,
        payment_transaction_id=f'BAL-{buyer.id}-{book.id}',
        platform_commission=platform_commission,
        author_earning=author_earning,
        balance_used=book_price
    )
    print(f"  ✓ Purchase created (ID: {purchase.id})")
    
    # 5. Credit author
    author.earnings_balance += author_earning
    author.save(update_fields=['earnings_balance'])
    print(f"  ✓ Credited author {author_earning:,.0f} XAF")
    
    # 6. Create library entry
    entry, _ = LibraryEntry.objects.get_or_create(user=buyer, book=book)
    print(f"  ✓ Library entry created")
    
    # Verify final balances
    buyer.refresh_from_db()
    author.refresh_from_db()
    
    print(f"\n  FINAL RESULTS:")
    print(f"    Buyer balance: {buyer.earnings_balance:,.0f} XAF (started: 5,000, paid: {book_price:,.0f})")
    print(f"    Author balance: {author.earnings_balance:,.0f} XAF (started: 1,000, earned: {author_earning:,.0f})")
    
    assert buyer.earnings_balance == Decimal('2000.00'), f"Expected 2000, got {buyer.earnings_balance}"
    assert purchase.payment_method == Purchase.PaymentMethod.BALANCE, "Wrong payment method"
    assert purchase.balance_used == book_price, "balance_used not recorded"
    
    print("  ✓ Full balance purchase test PASSED!")


def test_partial_payment_scenario():
    """Test partial payment calculation scenario."""
    print("\n=== Test 3: Partial Payment Scenario ===")
    
    user_balance = Decimal('1500.00')
    book_price = Decimal('4000.00')
    
    print(f"  User balance: {user_balance:,.0f} XAF")
    print(f"  Book price: {book_price:,.0f} XAF")
    
    # Can't pay full balance
    can_pay_full = user_balance >= book_price
    assert not can_pay_full, "Should not be able to pay full"
    print(f"  Can pay full balance: {can_pay_full}")
    
    # Can pay partial
    can_pay_partial = user_balance > 0 and user_balance < book_price
    assert can_pay_partial, "Should be able to pay partial"
    print(f"  Can pay partial: {can_pay_partial}")
    
    # Calculate remaining
    balance_to_use = min(user_balance, book_price)
    remaining_amount = max(book_price - user_balance, Decimal('0.00'))
    
    print(f"\n  Balance to use: {balance_to_use:,.0f} XAF")
    print(f"  Remaining (pay via gateway): {remaining_amount:,.0f} XAF")
    
    assert balance_to_use == Decimal('1500.00'), f"Expected 1500, got {balance_to_use}"
    assert remaining_amount == Decimal('2500.00'), f"Expected 2500, got {remaining_amount}"
    
    print("  ✓ Partial payment calculation test PASSED!")


def test_no_balance_scenario():
    """Test scenario with no balance."""
    print("\n=== Test 4: No Balance Scenario ===")
    
    user_balance = Decimal('0.00')
    book_price = Decimal('2000.00')
    
    can_pay_full = user_balance >= book_price
    can_pay_partial = user_balance > 0 and user_balance < book_price
    
    print(f"  User balance: {user_balance:,.0f} XAF")
    print(f"  Can pay full: {can_pay_full}")
    print(f"  Can pay partial: {can_pay_partial}")
    
    assert not can_pay_full, "Should not pay full"
    assert not can_pay_partial, "Should not pay partial"
    
    print("  ✓ No balance scenario test PASSED!")


def test_exact_balance_scenario():
    """Test when balance equals exactly book price."""
    print("\n=== Test 5: Exact Balance Scenario ===")
    
    user_balance = Decimal('3000.00')
    book_price = Decimal('3000.00')
    
    can_pay_full = user_balance >= book_price
    can_pay_partial = user_balance > 0 and user_balance < book_price
    
    print(f"  User balance: {user_balance:,.0f} XAF")
    print(f"  Book price: {book_price:,.0f} XAF")
    print(f"  Can pay full: {can_pay_full}")
    print(f"  Can pay partial: {can_pay_partial}")
    
    assert can_pay_full, "Should be able to pay full"
    assert not can_pay_partial, "Should not show partial"
    
    print("  ✓ Exact balance scenario test PASSED!")


def cleanup_test_data():
    """Clean up test data."""
    print("\n=== Cleanup ===")
    
    # Remove test purchases and library entries
    Purchase.objects.filter(buyer__email='balance_buyer@test.com').delete()
    LibraryEntry.objects.filter(user__email='balance_buyer@test.com').delete()
    
    print("  ✓ Test data cleaned up")


if __name__ == '__main__':
    print("=" * 60)
    print("BALANCE PAYMENT SYSTEM TESTS")
    print("=" * 60)
    
    try:
        test_purchase_model_payment_methods()
        test_full_balance_purchase_simulation()
        test_partial_payment_scenario()
        test_no_balance_scenario()
        test_exact_balance_scenario()
        cleanup_test_data()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED! ✓")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
