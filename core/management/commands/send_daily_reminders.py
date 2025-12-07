"""
Management command for sending daily reading reminders.
Per Planning Document Section 12 (Notifications & Engagement).

Usage:
    python manage.py send_daily_reminders

This should be scheduled to run at 7 PM daily using Django-Q scheduler.
"""

from django.core.management.base import BaseCommand
from django.db.models import Q
from django_q.tasks import async_task
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send daily reading reminders to users with in-progress books'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be sent without actually sending'
        )
        parser.add_argument(
            '--sync',
            action='store_true',
            help='Send emails synchronously instead of using Django-Q'
        )
    
    def handle(self, *args, **options):
        from core.models import LibraryEntry
        from core.tasks import send_daily_reminder
        
        dry_run = options['dry_run']
        sync_mode = options['sync']
        
        # Find users with in-progress books
        # Get most recent in-progress entry per user
        in_progress_entries = LibraryEntry.objects.filter(
            completion_status=LibraryEntry.CompletionStatus.IN_PROGRESS
        ).select_related('user', 'book').order_by('user_id', '-last_accessed')
        
        # Group by user - take most recent in-progress book per user
        seen_users = set()
        entries_to_notify = []
        
        for entry in in_progress_entries:
            if entry.user_id not in seen_users:
                seen_users.add(entry.user_id)
                entries_to_notify.append(entry)
        
        if not entries_to_notify:
            self.stdout.write(self.style.WARNING('No users with in-progress books found.'))
            return
        
        self.stdout.write(f'Found {len(entries_to_notify)} users with in-progress books.')
        
        sent_count = 0
        error_count = 0
        
        for entry in entries_to_notify:
            user = entry.user
            book = entry.book
            
            if not user.email:
                self.stdout.write(self.style.WARNING(f'  Skipping {user.id}: no email'))
                continue
            
            if dry_run:
                self.stdout.write(f'  [DRY RUN] Would send to {user.email}: "{book.title}"')
                sent_count += 1
            else:
                try:
                    if sync_mode:
                        # Send synchronously
                        result = send_daily_reminder(user.id, book.id, entry.id)
                        if result:
                            sent_count += 1
                            self.stdout.write(self.style.SUCCESS(f'  Sent to {user.email}'))
                        else:
                            error_count += 1
                            self.stdout.write(self.style.ERROR(f'  Failed for {user.email}'))
                    else:
                        # Queue with Django-Q
                        async_task(
                            'core.tasks.send_daily_reminder',
                            user.id,
                            book.id,
                            entry.id,
                            task_name=f'daily_reminder_{user.id}_{book.id}',
                        )
                        sent_count += 1
                        self.stdout.write(f'  Queued for {user.email}')
                except Exception as e:
                    error_count += 1
                    logger.error(f'Error sending reminder to {user.email}: {e}')
                    self.stdout.write(self.style.ERROR(f'  Error for {user.email}: {e}'))
        
        # Summary
        mode = '[DRY RUN]' if dry_run else ('sync' if sync_mode else 'queued')
        self.stdout.write(self.style.SUCCESS(
            f'\nCompleted: {sent_count} reminders {mode}, {error_count} errors'
        ))
