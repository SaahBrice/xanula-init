"""
Management command to generate referral codes for existing users without one.
Run with: python manage.py generate_referral_codes
"""
from django.core.management.base import BaseCommand
from users.models import User, generate_referral_code


class Command(BaseCommand):
    help = 'Generate referral codes for all users who do not have one'
    
    def handle(self, *args, **options):
        users_without_code = User.objects.filter(referral_code__isnull=True)
        count = users_without_code.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('All users already have referral codes.'))
            return
        
        self.stdout.write(f'Generating referral codes for {count} users...')
        
        for user in users_without_code:
            user.referral_code = generate_referral_code()
            user.save(update_fields=['referral_code'])
            self.stdout.write(f'  {user.email} → {user.referral_code}')
        
        self.stdout.write(self.style.SUCCESS(f'Successfully generated {count} referral codes.'))
