from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.contrib import messages
from datetime import date
from django.utils import timezone

from .models import Book, Purchase, LibraryEntry, Review, PayoutRequest, HardCopyRequest, UpfrontPaymentApplication, Donation, ReferralSettings


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    """
    Admin configuration for Book model.
    Per Planning Document Section 13 and Architecture Document Section 15.
    """
    
    list_display = (
        'title',
        'author',
        'category',
        'language',
        'price_display',
        'status',
        'total_sales',
        'average_rating',
        'submission_date',
    )
    
    list_filter = (
        'status',
        'category',
        'language',
        'hard_copy_option',
        'wants_editor_services',
        'wants_cover_design',
        'wants_formatting',
        'wants_marketing_kit',
        'wants_third_party_distribution',
        'submission_date',
    )
    
    search_fields = (
        'title',
        'short_description',
        'author__email',
        'author__display_name',
    )
    
    readonly_fields = (
        'slug',
        'submission_date',
        'total_sales',
        'average_rating',
    )
    
    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'author')
        }),
        (_('Descriptions'), {
            'fields': ('short_description', 'long_description')
        }),
        (_('Classification'), {
            'fields': ('category', 'language', 'price', 'commission_rate')
        }),
        (_('Status & Workflow'), {
            'fields': ('status', 'denial_reason', 'approval_date', 'completion_date'),
            'description': 'Manage the book publishing workflow.'
        }),
        (_('Files'), {
            'fields': ('manuscript_file', 'cover_image', 'ebook_file', 'audiobook_file')
        }),
        (_('Publishing Services'), {
            'fields': (
                'hard_copy_option',
                'wants_editor_services',
                'wants_cover_design',
                'wants_formatting',
                'wants_marketing_kit',
                'wants_third_party_distribution',
                'wants_isbn',
                'qr_code',
            ),
            'description': 'Author-requested publishing services. QR code auto-generated when status = Completed.'
        }),
        (_('Statistics'), {
            'fields': ('total_sales', 'average_rating'),
            'classes': ('collapse',)
        }),
        (_('Dates'), {
            'fields': ('submission_date',),
            'classes': ('collapse',)
        }),
    )
    
    autocomplete_fields = ['author']
    date_hierarchy = 'submission_date'
    ordering = ['-submission_date']
    
    class Media:
        js = ('js/admin_upload.js',)
    
    actions = ['approve_books', 'deny_books', 'mark_as_ebook_ready', 'mark_as_completed']
    
    def price_display(self, obj):
        """Display formatted price."""
        return obj.formatted_price
    price_display.short_description = _('Price')
    
    @admin.action(description=_('Approve selected books'))
    def approve_books(self, request, queryset):
        """Approve selected books."""
        updated = queryset.filter(status=Book.Status.IN_REVIEW).update(
            status=Book.Status.APPROVED,
            approval_date=date.today()
        )
        self.message_user(
            request,
            f'{updated} book(s) have been approved.',
            messages.SUCCESS
        )
    
    @admin.action(description=_('Deny selected books'))
    def deny_books(self, request, queryset):
        """Deny selected books - requires denial reason to be set first."""
        books_without_reason = queryset.filter(
            status=Book.Status.IN_REVIEW,
            denial_reason=''
        ).count()
        if books_without_reason > 0:
            self.message_user(
                request,
                f'{books_without_reason} book(s) need a denial reason set before denying.',
                messages.WARNING
            )
            return
        
        updated = queryset.filter(status=Book.Status.IN_REVIEW).update(
            status=Book.Status.DENIED
        )
        self.message_user(
            request,
            f'{updated} book(s) have been denied.',
            messages.SUCCESS
        )
    
    @admin.action(description=_('Mark as Ebook Ready'))
    def mark_as_ebook_ready(self, request, queryset):
        """Mark approved books as ebook ready."""
        updated = queryset.filter(status=Book.Status.APPROVED).update(
            status=Book.Status.EBOOK_READY
        )
        self.message_user(
            request,
            f'{updated} book(s) marked as ebook ready.',
            messages.SUCCESS
        )
    
    @admin.action(description=_('Mark as Completed'))
    def mark_as_completed(self, request, queryset):
        """Mark books as completed."""
        for book in queryset.filter(status__in=[Book.Status.EBOOK_READY, Book.Status.AUDIOBOOK_GENERATED]):
            book.status = Book.Status.COMPLETED
            book.completion_date = date.today()
            # Generate QR code
            if not book.qr_code:
                try:
                    book.generate_qr_code()
                except Exception as e:
                    self.message_user(request, f'QR generation failed for {book.title}: {e}', messages.WARNING)
            book.save()
        self.message_user(
            request,
            f'{queryset.count()} book(s) marked as completed with QR codes.',
            messages.SUCCESS
        )
    
    def save_model(self, request, obj, form, change):
        """Override save to generate QR code when status changes to COMPLETED."""
        if change:
            # Get old status from database
            old_obj = Book.objects.get(pk=obj.pk)
            old_status = old_obj.status
            new_status = obj.status
            
            # Generate QR code if status changed to COMPLETED
            if old_status != Book.Status.COMPLETED and new_status == Book.Status.COMPLETED:
                if not obj.qr_code:
                    try:
                        obj.generate_qr_code()
                        self.message_user(request, f'QR code generated for "{obj.title}"', messages.SUCCESS)
                    except Exception as e:
                        self.message_user(request, f'QR generation failed: {e}', messages.WARNING)
        
        super().save_model(request, obj, form, change)


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    """
    Admin configuration for Purchase model.
    Read-only, searchable by user and book.
    """
    
    list_display = (
        'buyer',
        'book',
        'amount_paid_display',
        'payment_method',
        'payment_status',
        'platform_commission_display',
        'author_earning_display',
        'purchase_date',
    )
    
    list_filter = (
        'payment_status',
        'payment_method',
        'purchase_date',
    )
    
    search_fields = (
        'buyer__email',
        'buyer__display_name',
        'book__title',
        'payment_transaction_id',
    )
    
    readonly_fields = (
        'buyer',
        'book',
        'purchase_date',
        'amount_paid',
        'payment_method',
        'payment_transaction_id',
        'platform_commission',
        'author_earning',
    )
    
    fieldsets = (
        (None, {
            'fields': ('buyer', 'book', 'purchase_date')
        }),
        (_('Payment Details'), {
            'fields': ('amount_paid', 'payment_method', 'payment_transaction_id', 'payment_status')
        }),
        (_('Earnings Split'), {
            'fields': ('platform_commission', 'author_earning')
        }),
    )
    
    date_hierarchy = 'purchase_date'
    ordering = ['-purchase_date']
    
    def has_add_permission(self, request):
        """Disable manual creation of purchases."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Only allow changing payment status."""
        return True
    
    def amount_paid_display(self, obj):
        return f"{obj.amount_paid:,.0f} XAF"
    amount_paid_display.short_description = _('Amount')
    
    def platform_commission_display(self, obj):
        return f"{obj.platform_commission:,.0f} XAF"
    platform_commission_display.short_description = _('Commission')
    
    def author_earning_display(self, obj):
        return f"{obj.author_earning:,.0f} XAF"
    author_earning_display.short_description = _('Author Earning')


@admin.register(LibraryEntry)
class LibraryEntryAdmin(admin.ModelAdmin):
    """
    Admin configuration for LibraryEntry model.
    """
    
    list_display = (
        'user',
        'book',
        'date_added',
        'last_accessed',
        'completion_status',
        'download_status',
        'reading_progress',
    )
    
    list_filter = (
        'completion_status',
        'download_status',
        'date_added',
    )
    
    search_fields = (
        'user__email',
        'user__display_name',
        'book__title',
    )
    
    readonly_fields = (
        'date_added',
    )
    
    fieldsets = (
        (None, {
            'fields': ('user', 'book', 'date_added')
        }),
        (_('Progress'), {
            'fields': ('reading_progress', 'listening_progress', 'completion_status')
        }),
        (_('Access'), {
            'fields': ('last_accessed', 'download_status')
        }),
    )
    
    autocomplete_fields = ['user', 'book']
    date_hierarchy = 'date_added'
    ordering = ['-date_added']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """
    Admin configuration for Review model.
    Can toggle is_visible for moderation.
    """
    
    list_display = (
        'user',
        'book',
        'rating_stars',
        'is_visible',
        'date_posted',
        'date_modified',
    )
    
    list_filter = (
        'rating',
        'is_visible',
        'date_posted',
    )
    
    search_fields = (
        'user__email',
        'user__display_name',
        'book__title',
        'review_text',
    )
    
    readonly_fields = (
        'date_posted',
        'date_modified',
    )
    
    fieldsets = (
        (None, {
            'fields': ('user', 'book')
        }),
        (_('Review Content'), {
            'fields': ('rating', 'review_text')
        }),
        (_('Moderation'), {
            'fields': ('is_visible',)
        }),
        (_('Dates'), {
            'fields': ('date_posted', 'date_modified'),
            'classes': ('collapse',)
        }),
    )
    
    autocomplete_fields = ['user', 'book']
    date_hierarchy = 'date_posted'
    ordering = ['-date_posted']
    
    actions = ['hide_reviews', 'show_reviews']
    
    def rating_stars(self, obj):
        """Display rating as stars."""
        return '★' * obj.rating + '☆' * (5 - obj.rating)
    rating_stars.short_description = _('Rating')
    
    @admin.action(description=_('Hide selected reviews'))
    def hide_reviews(self, request, queryset):
        updated = queryset.update(is_visible=False)
        self.message_user(request, f'{updated} review(s) hidden.', messages.SUCCESS)
    
    @admin.action(description=_('Show selected reviews'))
    def show_reviews(self, request, queryset):
        updated = queryset.update(is_visible=True)
        self.message_user(request, f'{updated} review(s) shown.', messages.SUCCESS)


@admin.register(PayoutRequest)
class PayoutRequestAdmin(admin.ModelAdmin):
    """
    Admin configuration for PayoutRequest model.
    Can change status and add processing notes.
    """
    
    list_display = (
        'author',
        'amount_display',
        'payout_method',
        'status',
        'request_date',
        'completion_date',
    )
    
    list_filter = (
        'status',
        'payout_method',
        'request_date',
    )
    
    search_fields = (
        'author__email',
        'author__display_name',
        'account_details',
    )
    
    readonly_fields = (
        'author',
        'amount_requested',
        'request_date',
        'payout_method',
        'account_details',
    )
    
    fieldsets = (
        (None, {
            'fields': ('author', 'amount_requested', 'request_date')
        }),
        (_('Payout Details'), {
            'fields': ('payout_method', 'account_details')
        }),
        (_('Processing'), {
            'fields': ('status', 'processing_notes', 'completion_date')
        }),
    )
    
    date_hierarchy = 'request_date'
    ordering = ['-request_date']
    
    actions = ['mark_processing', 'mark_completed', 'mark_failed']
    
    def amount_display(self, obj):
        return f"{obj.amount_requested:,.0f} XAF"
    amount_display.short_description = _('Amount')
    
    @admin.action(description=_('Mark as Processing'))
    def mark_processing(self, request, queryset):
        updated = queryset.filter(status=PayoutRequest.Status.PENDING).update(
            status=PayoutRequest.Status.PROCESSING
        )
        self.message_user(request, f'{updated} request(s) marked as processing.', messages.SUCCESS)
    
    @admin.action(description=_('Mark as Completed'))
    def mark_completed(self, request, queryset):
        updated = queryset.filter(status=PayoutRequest.Status.PROCESSING).update(
            status=PayoutRequest.Status.COMPLETED,
            completion_date=date.today()
        )
        self.message_user(request, f'{updated} request(s) marked as completed.', messages.SUCCESS)
    
    @admin.action(description=_('Mark as Failed'))
    def mark_failed(self, request, queryset):
        updated = queryset.filter(
            status__in=[PayoutRequest.Status.PENDING, PayoutRequest.Status.PROCESSING]
        ).update(status=PayoutRequest.Status.FAILED)
        self.message_user(request, f'{updated} request(s) marked as failed.', messages.SUCCESS)


@admin.register(HardCopyRequest)
class HardCopyRequestAdmin(admin.ModelAdmin):
    """
    Admin configuration for HardCopyRequest model.
    Manage physical book requests from users.
    """
    
    list_display = (
        'user',
        'book',
        'book_author',
        'city',
        'status',
        'request_date',
        'shipped_date',
    )
    
    list_filter = (
        'status',
        'city',
        'request_date',
    )
    
    search_fields = (
        'user__email',
        'user__display_name',
        'book__title',
        'book__author__email',
        'full_name',
        'phone_number',
        'city',
        'shipping_address',
    )
    
    readonly_fields = (
        'user',
        'book',
        'request_date',
        'full_name',
        'phone_number',
        'shipping_address',
        'city',
        'additional_notes',
    )
    
    fieldsets = (
        (_('Request Info'), {
            'fields': ('user', 'book', 'request_date', 'status')
        }),
        (_('Shipping Details'), {
            'fields': ('full_name', 'phone_number', 'shipping_address', 'city', 'additional_notes')
        }),
        (_('Processing'), {
            'fields': ('admin_notes', 'tracking_number', 'processed_date', 'shipped_date', 'delivered_date')
        }),
    )
    
    date_hierarchy = 'request_date'
    ordering = ['-request_date']
    
    actions = ['mark_processing', 'mark_shipped', 'mark_delivered', 'mark_cancelled']
    
    def book_author(self, obj):
        return obj.book.author.get_display_name()
    book_author.short_description = _('Author')
    
    @admin.action(description=_('Mark as Processing'))
    def mark_processing(self, request, queryset):
        updated = queryset.filter(status=HardCopyRequest.Status.REQUESTED).update(
            status=HardCopyRequest.Status.PROCESSING,
            processed_date=timezone.now()
        )
        self.message_user(request, f'{updated} request(s) marked as processing.', messages.SUCCESS)
    
    @admin.action(description=_('Mark as Shipped'))
    def mark_shipped(self, request, queryset):
        updated = queryset.filter(status=HardCopyRequest.Status.PROCESSING).update(
            status=HardCopyRequest.Status.SHIPPED,
            shipped_date=timezone.now()
        )
        self.message_user(request, f'{updated} request(s) marked as shipped.', messages.SUCCESS)
    
    @admin.action(description=_('Mark as Delivered'))
    def mark_delivered(self, request, queryset):
        updated = queryset.filter(status=HardCopyRequest.Status.SHIPPED).update(
            status=HardCopyRequest.Status.DELIVERED,
            delivered_date=timezone.now()
        )
        self.message_user(request, f'{updated} request(s) marked as delivered.', messages.SUCCESS)
    
    @admin.action(description=_('Cancel selected requests'))
    def mark_cancelled(self, request, queryset):
        updated = queryset.exclude(
            status__in=[HardCopyRequest.Status.DELIVERED, HardCopyRequest.Status.CANCELLED]
        ).update(status=HardCopyRequest.Status.CANCELLED)
        self.message_user(request, f'{updated} request(s) cancelled.', messages.SUCCESS)


@admin.register(UpfrontPaymentApplication)
class UpfrontPaymentApplicationAdmin(admin.ModelAdmin):
    """
    Admin configuration for UpfrontPaymentApplication model.
    Allows admins to review, approve, or reject author advance requests.
    """
    
    list_display = (
        'author',
        'amount_display',
        'book_display',
        'status',
        'repayment_rate_display',
        'progress_display',
        'created_at',
    )
    
    list_filter = (
        'status',
        'created_at',
    )
    
    search_fields = (
        'author__email',
        'author__display_name',
        'book__title',
        'reason',
    )
    
    readonly_fields = (
        'author',
        'book',
        'amount_requested',
        'reason',
        'created_at',
        'updated_at',
        'amount_recouped',
        'terms_accepted',
        'approved_at',
        'completed_at',
    )
    
    fieldsets = (
        (_('Application Info'), {
            'fields': ('author', 'book', 'amount_requested', 'reason', 'terms_accepted', 'created_at')
        }),
        (_('Review Status'), {
            'fields': ('status', 'rejection_reason', 'approved_at', 'completed_at')
        }),
        (_('Repayment'), {
            'fields': ('repayment_rate', 'amount_recouped'),
            'description': 'Set repayment rate before approving. This is the extra % taken per sale.'
        }),
        (_('Admin Notes'), {
            'fields': ('admin_notes',),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    actions = ['approve_applications', 'reject_applications']
    
    def amount_display(self, obj):
        return f"{obj.amount_requested:,.0f} XAF"
    amount_display.short_description = _('Amount')
    
    def book_display(self, obj):
        return obj.book.title if obj.book else _('All Books')
    book_display.short_description = _('Book')
    
    def repayment_rate_display(self, obj):
        return f"{obj.repayment_rate}%"
    repayment_rate_display.short_description = _('Repayment Rate')
    
    def progress_display(self, obj):
        if obj.status == UpfrontPaymentApplication.Status.APPROVED:
            return f"{obj.recoup_progress_percent}% ({obj.amount_recouped:,.0f}/{obj.amount_requested:,.0f} XAF)"
        elif obj.status == UpfrontPaymentApplication.Status.COMPLETED:
            return "100% ✓"
        return "-"
    progress_display.short_description = _('Recouped')
    
    @admin.action(description=_('Approve selected applications'))
    def approve_applications(self, request, queryset):
        updated = queryset.filter(
            status=UpfrontPaymentApplication.Status.IN_REVIEW
        ).update(
            status=UpfrontPaymentApplication.Status.APPROVED,
            approved_at=timezone.now()
        )
        self.message_user(request, f'{updated} application(s) approved.', messages.SUCCESS)
    
    @admin.action(description=_('Reject selected applications'))
    def reject_applications(self, request, queryset):
        # Check that rejection reason is set
        apps_without_reason = queryset.filter(
            status=UpfrontPaymentApplication.Status.IN_REVIEW,
            rejection_reason=''
        ).count()
        if apps_without_reason > 0:
            self.message_user(
                request,
                f'{apps_without_reason} application(s) need a rejection reason set first.',
                messages.WARNING
            )
            return
        
        updated = queryset.filter(
            status=UpfrontPaymentApplication.Status.IN_REVIEW
        ).update(status=UpfrontPaymentApplication.Status.REJECTED)
        self.message_user(request, f'{updated} application(s) rejected.', messages.SUCCESS)


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    """Admin configuration for Donation model."""
    
    list_display = (
        'id',
        'donor_display',
        'recipient_display',
        'amount_display',
        'payment_status',
        'payment_method',
        'created_at',
    )
    
    list_filter = ('payment_status', 'payment_method', 'created_at')
    search_fields = ('donor__email', 'recipient__email', 'message')
    readonly_fields = ('created_at', 'completed_at', 'platform_commission', 'author_earning')
    
    fieldsets = (
        (_('Participants'), {
            'fields': ('donor', 'recipient', 'book')
        }),
        (_('Donation Details'), {
            'fields': ('amount', 'message', 'terms_accepted')
        }),
        (_('Payment'), {
            'fields': ('payment_method', 'payment_status', 'payment_transaction_id')
        }),
        (_('Commission Split'), {
            'fields': ('platform_commission', 'author_earning')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'completed_at')
        }),
    )
    
    def donor_display(self, obj):
        return obj.donor.get_display_name()
    donor_display.short_description = _('Donor')
    
    def recipient_display(self, obj):
        return obj.recipient.get_display_name()
    recipient_display.short_description = _('Recipient')
    
    def amount_display(self, obj):
        return f"{obj.amount:,.0f} XAF"
    amount_display.short_description = _('Amount')


@admin.register(ReferralSettings)
class ReferralSettingsAdmin(admin.ModelAdmin):
    """Admin for global referral settings (singleton)."""
    
    list_display = ('referral_percent', 'is_active')
    
    def has_add_permission(self, request):
        # Only allow one instance
        return not ReferralSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        return False


from .models import CommissionSettings

@admin.register(CommissionSettings)
class CommissionSettingsAdmin(admin.ModelAdmin):
    """Admin for global commission settings (singleton)."""
    
    list_display = ('ebook_commission', 'audiobook_commission', 'donation_commission')
    
    fieldsets = (
        (_('Purchase Commissions'), {
            'fields': ('ebook_commission', 'audiobook_commission'),
            'description': _('Platform commission rates for book purchases.')
        }),
        (_('Donation Commissions'), {
            'fields': ('donation_commission',),
            'description': _('Platform commission rate for author donations.')
        }),
    )
    
    def has_add_permission(self, request):
        # Only allow one instance
        return not CommissionSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        return False
