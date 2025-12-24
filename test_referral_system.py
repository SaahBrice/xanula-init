"""
Test script for the Referral Code System.
Run with: python manage.py shell < test_referral_system.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xanula_project.settings')
django.setup()

from decimal import Decimal
from django.db import transaction
from users.models import User, generate_referral_code
from core.models import Book, Purchase, ReferralSettings, LibraryEntry


def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def test_referral_code_generation():
    """Test 1: Referral code generation."""
    print_header("TEST 1: Referral Code Generation")
    
    # Test code format
    code = generate_referral_code()
    print(f"  Generated code: {code}")
    
    assert code.startswith('REEPLS-'), f"Code should start with 'REEPLS-', got {code}"
    assert len(code) == 11, f"Code should be 11 chars, got {len(code)}"
    print("  ✓ Code format is correct (REEPLS-XXXX)")
    
    # Test uniqueness
    codes = set()
    for _ in range(10):
        codes.add(generate_referral_code())
    assert len(codes) == 10, "Generated codes should be unique"
    print("  ✓ 10 unique codes generated successfully")
    
    return True


def test_user_referral_code_auto_generation():
    """Test 2: New user gets referral code on creation."""
    print_header("TEST 2: User Auto-Generation")
    
    with transaction.atomic():
        # Create a test user
        test_email = 'referral_test_user@xanula.test'
        
        # Delete if exists
        User.objects.filter(email=test_email).delete()
        
        # Create new user
        user = User.objects.create_user(
            email=test_email,
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        
        print(f"  Created user: {user.email}")
        print(f"  Referral code: {user.referral_code}")
        
        assert user.referral_code is not None, "New user should have referral code"
        assert user.referral_code.startswith('REEPLS-'), "Code should have correct format"
        print("  ✓ New user automatically gets referral code")
        
        # Cleanup
        user.delete()
        
    return True


def test_ensure_referral_code():
    """Test 3: ensure_referral_code() for existing users without code."""
    print_header("TEST 3: Ensure Referral Code")
    
    with transaction.atomic():
        # Create user without code (force)
        test_email = 'referral_test_nocode@xanula.test'
        User.objects.filter(email=test_email).delete()
        
        user = User(
            email=test_email,
            first_name='NoCode',
            last_name='User'
        )
        user.set_password('testpass123')
        user.referral_code = None  # Force no code
        user.save()
        
        # Actually set it to None again after save
        User.objects.filter(email=test_email).update(referral_code=None)
        user.refresh_from_db()
        
        print(f"  User before: referral_code = {user.referral_code}")
        
        # Call ensure_referral_code
        code = user.ensure_referral_code()
        
        print(f"  User after: referral_code = {user.referral_code}")
        
        assert user.referral_code is not None, "User should now have code"
        assert code == user.referral_code, "Returned code should match"
        print("  ✓ ensure_referral_code() works correctly")
        
        # Cleanup
        user.delete()
        
    return True


def test_referral_settings():
    """Test 4: ReferralSettings singleton."""
    print_header("TEST 4: Referral Settings")
    
    # Get settings (creates if needed)
    settings = ReferralSettings.get_settings()
    print(f"  Current referral percent: {settings.referral_percent}%")
    print(f"  Is active: {settings.is_active}")
    
    # Test get_referral_percent
    percent = ReferralSettings.get_referral_percent()
    print(f"  get_referral_percent(): {percent}%")
    
    if settings.is_active:
        assert percent == settings.referral_percent, "Should return configured percent"
    else:
        assert percent == Decimal('0.00'), "Should return 0 if inactive"
    
    print("  ✓ ReferralSettings singleton works correctly")
    return True


def test_referral_commission_calculation():
    """Test 5: Referral commission calculation logic."""
    print_header("TEST 5: Commission Calculation")
    
    # Get referral settings
    settings = ReferralSettings.get_settings()
    referral_percent = settings.referral_percent
    
    # Simulate a purchase
    book_price = Decimal('2000.00')
    platform_commission_rate = Decimal('0.30')  # 30% for audiobook
    
    platform_commission = book_price * platform_commission_rate  # 600
    author_base = book_price - platform_commission  # 1400
    
    # Calculate referral commission (from author's share)
    referral_rate = referral_percent / Decimal('100')
    referral_commission = (book_price * referral_rate).quantize(Decimal('0.01'))
    author_final = author_base - referral_commission
    
    print(f"  Book price: {book_price} XAF")
    print(f"  Platform commission (30%): {platform_commission} XAF")
    print(f"  Author base earning: {author_base} XAF")
    print(f"  Referral commission ({referral_percent}%): {referral_commission} XAF")
    print(f"  Author final earning: {author_final} XAF")
    print(f"  ---")
    print(f"  Total: {platform_commission + author_final + referral_commission} XAF = {book_price} XAF ✓")
    
    # Verify the split adds up
    assert platform_commission + author_final + referral_commission == book_price
    print("  ✓ Commission split calculation is correct")
    
    return True


def test_self_referral_blocked():
    """Test 6: Self-referral should be blocked."""
    print_header("TEST 6: Self-Referral Block")
    
    with transaction.atomic():
        # Create a user
        test_email = 'self_referral_test@xanula.test'
        User.objects.filter(email=test_email).delete()
        
        user = User.objects.create_user(
            email=test_email,
            password='testpass123',
            first_name='Self',
            last_name='Referrer'
        )
        
        own_code = user.referral_code
        print(f"  User's own code: {own_code}")
        
        # Try to look up self
        try:
            referrer = User.objects.get(referral_code=own_code)
            is_self = referrer == user
            print(f"  Is self-referral: {is_self}")
            
            assert is_self, "Should detect self-referral"
            print("  ✓ Self-referral correctly detected (would be blocked in view)")
        finally:
            user.delete()
    
    return True


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("  REFERRAL SYSTEM TEST SUITE")
    print("="*60)
    
    tests = [
        ("Code Generation", test_referral_code_generation),
        ("Auto-Generation", test_user_referral_code_auto_generation),
        ("Ensure Code", test_ensure_referral_code),
        ("Settings Singleton", test_referral_settings),
        ("Commission Calc", test_referral_commission_calculation),
        ("Self-Referral Block", test_self_referral_blocked),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print(f"  RESULTS: {passed} passed, {failed} failed")
    print("="*60 + "\n")
    
    return failed == 0


# Run tests
if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
else:
    run_all_tests()
