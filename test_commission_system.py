"""
Test script for Dynamic Commission System.
Tests the CommissionSettings model and Book.get_effective_commission_rate() method.

Run with: python test_commission_system.py
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
from core.models import Book, CommissionSettings

User = get_user_model()


def test_commission_settings_singleton():
    """Test that CommissionSettings is a singleton."""
    print("\n=== Test 1: CommissionSettings Singleton ===")
    
    settings1 = CommissionSettings.get_settings()
    settings2 = CommissionSettings.get_settings()
    
    assert settings1.pk == settings2.pk, "Should be the same instance"
    print(f"✓ Singleton works - same instance (pk={settings1.pk})")
    
    # Try to create another instance (should fail)
    try:
        CommissionSettings.objects.create(
            ebook_commission=Decimal('15.00'),
            audiobook_commission=Decimal('35.00'),
            donation_commission=Decimal('15.00')
        )
        print("✗ Should not allow creating second instance!")
    except ValueError as e:
        print(f"✓ Correctly prevents second instance: {e}")


def test_default_commission_rates():
    """Test default commission rates are correct."""
    print("\n=== Test 2: Default Commission Rates ===")
    
    settings = CommissionSettings.get_settings()
    
    print(f"  Ebook commission: {settings.ebook_commission}%")
    print(f"  Audiobook commission: {settings.audiobook_commission}%")
    print(f"  Donation commission: {settings.donation_commission}%")
    
    # Test helper methods return decimals
    ebook_rate = CommissionSettings.get_ebook_rate()
    audiobook_rate = CommissionSettings.get_audiobook_rate()
    donation_rate = CommissionSettings.get_donation_rate()
    
    print(f"\n  As decimals:")
    print(f"  Ebook rate: {ebook_rate} (expected ~0.10)")
    print(f"  Audiobook rate: {audiobook_rate} (expected ~0.30)")
    print(f"  Donation rate: {donation_rate} (expected ~0.10)")
    
    assert ebook_rate == Decimal('0.10'), f"Expected 0.10, got {ebook_rate}"
    assert audiobook_rate == Decimal('0.30'), f"Expected 0.30, got {audiobook_rate}"
    assert donation_rate == Decimal('0.10'), f"Expected 0.10, got {donation_rate}"
    
    print("✓ All default rates correct!")


def test_book_effective_commission_rate():
    """Test Book.get_effective_commission_rate() method."""
    print("\n=== Test 3: Book Effective Commission Rate ===")
    
    # Get or create a test user
    user, _ = User.objects.get_or_create(
        email='commission_test@example.com',
        defaults={'display_name': 'Commission Test Author'}
    )
    
    # Create a test book (ebook only - no audiobook)
    ebook_only = Book(
        title='Test Ebook Only',
        author=user,
        price=Decimal('5000.00'),
        ebook_file='test.epub',
        audiobook_file='',  # No audiobook
        custom_commission_rate=None
    )
    
    rate = ebook_only.get_effective_commission_rate()
    print(f"  Ebook only (no custom rate): {rate} (expected 0.10)")
    assert rate == Decimal('0.10'), f"Expected 0.10, got {rate}"
    print("  ✓ Ebook-only uses global ebook rate")
    
    # Create a book with audiobook
    with_audiobook = Book(
        title='Test With Audiobook',
        author=user,
        price=Decimal('5000.00'),
        ebook_file='test.epub',
        audiobook_file='test.mp3',  # Has audiobook
        custom_commission_rate=None
    )
    
    rate = with_audiobook.get_effective_commission_rate()
    print(f"  With audiobook (no custom rate): {rate} (expected 0.30)")
    assert rate == Decimal('0.30'), f"Expected 0.30, got {rate}"
    print("  ✓ Book with audiobook uses global audiobook rate")
    
    # Test custom commission rate override
    custom_book = Book(
        title='Test Custom Rate',
        author=user,
        price=Decimal('5000.00'),
        ebook_file='test.epub',
        audiobook_file='test.mp3',  # Has audiobook
        custom_commission_rate=Decimal('20.00')  # Custom 20%
    )
    
    rate = custom_book.get_effective_commission_rate()
    print(f"  With audiobook + custom 20%: {rate} (expected 0.20)")
    assert rate == Decimal('0.20'), f"Expected 0.20, got {rate}"
    print("  ✓ Custom rate overrides global setting")


def test_commission_calculation():
    """Test actual commission calculations."""
    print("\n=== Test 4: Commission Calculations ===")
    
    book_price = Decimal('10000.00')  # 10,000 XAF
    
    # Scenario 1: Ebook only (10%)
    ebook_rate = CommissionSettings.get_ebook_rate()
    platform_commission = book_price * ebook_rate
    author_earning = book_price - platform_commission
    
    print(f"\n  Scenario 1: Ebook (10% commission)")
    print(f"    Book price: {book_price:,.0f} XAF")
    print(f"    Platform gets: {platform_commission:,.0f} XAF")
    print(f"    Author gets: {author_earning:,.0f} XAF")
    assert platform_commission == Decimal('1000.00'), f"Expected 1000, got {platform_commission}"
    assert author_earning == Decimal('9000.00'), f"Expected 9000, got {author_earning}"
    print("    ✓ Correct!")
    
    # Scenario 2: With audiobook (30%)
    audiobook_rate = CommissionSettings.get_audiobook_rate()
    platform_commission = book_price * audiobook_rate
    author_earning = book_price - platform_commission
    
    print(f"\n  Scenario 2: With Audiobook (30% commission)")
    print(f"    Book price: {book_price:,.0f} XAF")
    print(f"    Platform gets: {platform_commission:,.0f} XAF")
    print(f"    Author gets: {author_earning:,.0f} XAF")
    assert platform_commission == Decimal('3000.00'), f"Expected 3000, got {platform_commission}"
    assert author_earning == Decimal('7000.00'), f"Expected 7000, got {author_earning}"
    print("    ✓ Correct!")
    
    # Scenario 3: Custom 15% rate
    custom_rate = Decimal('15.00') / Decimal('100')
    platform_commission = book_price * custom_rate
    author_earning = book_price - platform_commission
    
    print(f"\n  Scenario 3: Custom 15% commission")
    print(f"    Book price: {book_price:,.0f} XAF")
    print(f"    Platform gets: {platform_commission:,.0f} XAF")
    print(f"    Author gets: {author_earning:,.0f} XAF")
    assert platform_commission == Decimal('1500.00'), f"Expected 1500, got {platform_commission}"
    assert author_earning == Decimal('8500.00'), f"Expected 8500, got {author_earning}"
    print("    ✓ Correct!")


def test_donation_commission():
    """Test donation commission uses dynamic rate."""
    print("\n=== Test 5: Donation Commission ===")
    
    from core.models import Donation
    
    donation_amount = Decimal('5000.00')  # 5,000 XAF
    rate = CommissionSettings.get_donation_rate()
    
    platform_commission = (donation_amount * rate).quantize(Decimal('0.01'))
    author_earning = donation_amount - platform_commission
    
    print(f"  Donation amount: {donation_amount:,.0f} XAF")
    print(f"  Commission rate: {rate * 100}%")
    print(f"  Platform gets: {platform_commission:,.0f} XAF")
    print(f"  Author gets: {author_earning:,.0f} XAF")
    
    assert platform_commission == Decimal('500.00'), f"Expected 500, got {platform_commission}"
    assert author_earning == Decimal('4500.00'), f"Expected 4500, got {author_earning}"
    print("  ✓ Correct!")


def test_update_commission_rates():
    """Test updating commission rates."""
    print("\n=== Test 6: Update Commission Rates ===")
    
    settings = CommissionSettings.get_settings()
    original_ebook = settings.ebook_commission
    
    # Update rate
    settings.ebook_commission = Decimal('15.00')
    settings.save()
    
    # Verify update
    new_rate = CommissionSettings.get_ebook_rate()
    print(f"  Changed ebook commission from {original_ebook}% to 15%")
    print(f"  New rate: {new_rate}")
    assert new_rate == Decimal('0.15'), f"Expected 0.15, got {new_rate}"
    print("  ✓ Rate updated successfully!")
    
    # Restore original
    settings.ebook_commission = original_ebook
    settings.save()
    print(f"  Restored to {original_ebook}%")


if __name__ == '__main__':
    print("=" * 60)
    print("DYNAMIC COMMISSION SYSTEM TESTS")
    print("=" * 60)
    
    try:
        test_commission_settings_singleton()
        test_default_commission_rates()
        test_book_effective_commission_rate()
        test_commission_calculation()
        test_donation_commission()
        test_update_commission_rates()
        
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
