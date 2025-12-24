from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django.urls import reverse
from decimal import Decimal
import uuid


def manuscript_upload_path(instance, filename):
    """Upload path for manuscript files: media/manuscripts/YEAR/MONTH/"""
    from datetime import datetime
    now = datetime.now()
    ext = filename.split('.')[-1]
    new_filename = f"{instance.slug}-{uuid.uuid4().hex[:8]}.{ext}"
    return f"manuscripts/{now.year}/{now.month:02d}/{new_filename}"


def ebook_upload_path(instance, filename):
    """Upload path for ebook files: media/ebooks/YEAR/MONTH/"""
    from datetime import datetime
    now = datetime.now()
    ext = filename.split('.')[-1]
    new_filename = f"{instance.slug}-{uuid.uuid4().hex[:8]}.{ext}"
    return f"ebooks/{now.year}/{now.month:02d}/{new_filename}"


def audiobook_upload_path(instance, filename):
    """Upload path for audiobook files: media/audiobooks/YEAR/MONTH/"""
    from datetime import datetime
    now = datetime.now()
    ext = filename.split('.')[-1]
    new_filename = f"{instance.slug}-{uuid.uuid4().hex[:8]}.{ext}"
    return f"audiobooks/{now.year}/{now.month:02d}/{new_filename}"


def cover_upload_path(instance, filename):
    """Upload path for cover images: media/covers/YEAR/MONTH/"""
    from datetime import datetime
    now = datetime.now()
    ext = filename.split('.')[-1]
    new_filename = f"{instance.slug}-{uuid.uuid4().hex[:8]}.{ext}"
    return f"covers/{now.year}/{now.month:02d}/{new_filename}"


class Book(models.Model):
    """
    Book model representing a book in the Xanula platform.
    Per Architecture Document Section 6.
    """
    
    # Categories per Planning Document Section 14
    class Category(models.TextChoices):
        FICTION = 'fiction', _('Fiction')
        ROMANCE = 'romance', _('Romance')
        THRILLER_MYSTERY = 'thriller_mystery', _('Thriller & Mystery')
        DRAMA = 'drama', _('Drama')
        SCIFI_FANTASY = 'scifi_fantasy', _('Science Fiction & Fantasy')
        HORROR = 'horror', _('Horror')
        COURSE = 'course', _('Course')
        POLITICS = 'politics', _('Politics')
        NON_FICTION = 'non_fiction', _('Non-Fiction')
        BIOGRAPHY_MEMOIR = 'biography_memoir', _('Biography & Memoir')
        SELF_HELP = 'self_help', _('Self-Help & Personal Development')
        BUSINESS_MONEY = 'business_money', _('Business & Money')
        HISTORY = 'history', _('History')
        HEALTH_WELLNESS = 'health_wellness', _('Health & Wellness')
        RELIGION_SPIRITUALITY = 'religion_spirituality', _('Religion & Spirituality')
        CHILDREN_YA = 'children_ya', _('Children & Young Adult')
        POETRY = 'poetry', _('Poetry')
        ACADEMIC = 'academic', _('Academic & Educational')
        AFRICAN_LITERATURE = 'african_literature', _('African Literature & Culture')
    
    # Languages per Planning Document Section 14
    class Language(models.TextChoices):
        ENGLISH = 'en', _('English')
        FRENCH = 'fr', _('French')
    
    # Book status per Planning Document Section 4
    class Status(models.TextChoices):
        IN_REVIEW = 'in_review', _('In Review')
        APPROVED = 'approved', _('Approved')
        DENIED = 'denied', _('Denied')
        EBOOK_READY = 'ebook_ready', _('Ebook Ready')
        AUDIOBOOK_GENERATED = 'audiobook_generated', _('Audiobook Generated')
        COMPLETED = 'completed', _('Completed')
    
    # Commission rates
    class CommissionRate(models.IntegerChoices):
        LOW = 10, _('10%')
        HIGH = 30, _('30%')
    
    # Basic book information
    title = models.CharField(
        _('title'),
        max_length=255,
        help_text=_('The title of the book.')
    )
    slug = models.SlugField(
        _('slug'),
        max_length=280,
        unique=True,
        blank=True,
        help_text=_('URL-friendly version of the title.')
    )
    short_description = models.CharField(
        _('short description'),
        max_length=200,
        help_text=_('Brief description for listings (max 200 characters).')
    )
    long_description = models.TextField(
        _('long description'),
        help_text=_('Full description for the book detail page.')
    )
    
    # Author relationship
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='books',
        verbose_name=_('author'),
        help_text=_('The author/publisher of this book.')
    )
    
    # Classification
    category = models.CharField(
        _('category'),
        max_length=30,
        choices=Category.choices,
        default=Category.FICTION,
        help_text=_('Book category.')
    )
    language = models.CharField(
        _('language'),
        max_length=5,
        choices=Language.choices,
        default=Language.ENGLISH,
        help_text=_('Primary language of the book.')
    )
    
    # Pricing
    price = models.DecimalField(
        _('price'),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text=_('Price in XAF (0 for free books).')
    )
    
    # Status and workflow
    status = models.CharField(
        _('status'),
        max_length=25,
        choices=Status.choices,
        default=Status.IN_REVIEW,
        help_text=_('Current status in the publishing workflow.')
    )
    denial_reason = models.TextField(
        _('denial reason'),
        blank=True,
        help_text=_('Reason for denial (if status is Denied).')
    )
    commission_rate = models.IntegerField(
        _('commission rate'),
        choices=CommissionRate.choices,
        default=CommissionRate.LOW,
        help_text=_('Platform commission rate percentage.')
    )
    
    # Dates
    submission_date = models.DateTimeField(
        _('submission date'),
        auto_now_add=True,
        help_text=_('When the book was submitted.')
    )
    approval_date = models.DateField(
        _('approval date'),
        null=True,
        blank=True,
        help_text=_('When the book was approved.')
    )
    completion_date = models.DateField(
        _('completion date'),
        null=True,
        blank=True,
        help_text=_('When all conversions were completed.')
    )
    
    # Files
    manuscript_file = models.FileField(
        _('manuscript file'),
        upload_to=manuscript_upload_path,
        help_text=_('Original manuscript file (PDF, DOCX, EPUB, TXT).')
    )
    ebook_file = models.FileField(
        _('ebook file'),
        upload_to=ebook_upload_path,
        blank=True,
        null=True,
        help_text=_('Converted ebook file.')
    )
    audiobook_file = models.FileField(
        _('audiobook file'),
        upload_to=audiobook_upload_path,
        blank=True,
        null=True,
        help_text=_('Generated audiobook file.')
    )
    cover_image = models.ImageField(
        _('cover image'),
        upload_to=cover_upload_path,
        help_text=_('Book cover image.')
    )
    
    # Statistics
    total_sales = models.PositiveIntegerField(
        _('total sales'),
        default=0,
        help_text=_('Total number of copies sold.')
    )
    average_rating = models.DecimalField(
        _('average rating'),
        max_digits=3,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('5.00'))],
        help_text=_('Average rating (0-5 stars).')
    )
    
    class Meta:
        verbose_name = _('book')
        verbose_name_plural = _('books')
        ordering = ['-submission_date']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['category']),
            models.Index(fields=['language']),
            models.Index(fields=['author']),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            # Generate unique slug
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Book.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        """Returns the book detail page URL."""
        return reverse('core:book_detail', kwargs={'slug': self.slug})
    
    def can_be_purchased_by(self, user):
        """Check if a user can purchase this book (doesn't already own it)."""
        if not user.is_authenticated:
            return True  # They can view, but will need to login
        return not LibraryEntry.objects.filter(user=user, book=self).exists()
    
    @property
    def is_free(self):
        """Check if the book is free."""
        return self.price == Decimal('0.00')
    
    @property
    def is_available(self):
        """Check if the book is available for purchase."""
        return self.status in [
            self.Status.EBOOK_READY,
            self.Status.AUDIOBOOK_GENERATED,
            self.Status.COMPLETED
        ]
    
    @property
    def has_audiobook(self):
        """Check if audiobook is available."""
        return bool(self.audiobook_file)
    
    @property
    def has_ebook(self):
        """Check if ebook is available."""
        return bool(self.ebook_file)
    
    @property
    def formatted_price(self):
        """Returns formatted price in XAF."""
        if self.is_free:
            return _("Free")
        return f"{self.price:,.0f} XAF"
    
    def update_average_rating(self):
        """Recalculate and update the average rating."""
        from django.db.models import Avg
        avg = self.reviews.filter(is_visible=True).aggregate(Avg('rating'))['rating__avg']
        self.average_rating = Decimal(str(avg)) if avg else Decimal('0.00')
        self.save(update_fields=['average_rating'])


class Purchase(models.Model):
    """
    Purchase model representing a book purchase transaction.
    Per Architecture Document Section 6.
    """
    
    class PaymentMethod(models.TextChoices):
        STRIPE = 'stripe', _('Stripe (Card)')
        FAPSHI = 'fapshi', _('Fapshi (Mobile Money)')
    
    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        COMPLETED = 'completed', _('Completed')
        FAILED = 'failed', _('Failed')
        REFUNDED = 'refunded', _('Refunded')
    
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='purchases',
        verbose_name=_('buyer')
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name='purchases',
        verbose_name=_('book')
    )
    purchase_date = models.DateTimeField(
        _('purchase date'),
        auto_now_add=True
    )
    amount_paid = models.DecimalField(
        _('amount paid'),
        max_digits=10,
        decimal_places=2,
        help_text=_('Amount paid in XAF.')
    )
    payment_method = models.CharField(
        _('payment method'),
        max_length=10,
        choices=PaymentMethod.choices
    )
    payment_transaction_id = models.CharField(
        _('transaction ID'),
        max_length=255,
        blank=True,
        help_text=_('Payment gateway transaction reference.')
    )
    payment_status = models.CharField(
        _('payment status'),
        max_length=15,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING
    )
    platform_commission = models.DecimalField(
        _('platform commission'),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_('Commission amount for the platform.')
    )
    author_earning = models.DecimalField(
        _('author earning'),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_('Earning amount for the author.')
    )
    
    class Meta:
        verbose_name = _('purchase')
        verbose_name_plural = _('purchases')
        ordering = ['-purchase_date']
        indexes = [
            models.Index(fields=['buyer']),
            models.Index(fields=['book']),
            models.Index(fields=['payment_status']),
        ]
    
    def __str__(self):
        return f"{self.buyer.email} - {self.book.title}"
    
    def save(self, *args, **kwargs):
        # Calculate commission and author earning
        if self.amount_paid and self.book:
            commission_rate = Decimal(str(self.book.commission_rate)) / Decimal('100')
            self.platform_commission = self.amount_paid * commission_rate
            self.author_earning = self.amount_paid - self.platform_commission
        super().save(*args, **kwargs)


class LibraryEntry(models.Model):
    """
    LibraryEntry model representing a book in a user's library.
    Per Architecture Document Section 6.
    """
    
    class DownloadStatus(models.TextChoices):
        NOT_DOWNLOADED = 'not_downloaded', _('Not Downloaded')
        DOWNLOADED = 'downloaded', _('Downloaded')
        OUTDATED = 'outdated', _('Outdated')
    
    class CompletionStatus(models.TextChoices):
        NOT_STARTED = 'not_started', _('Not Started')
        IN_PROGRESS = 'in_progress', _('In Progress')
        COMPLETED = 'completed', _('Completed')
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='library',
        verbose_name=_('user')
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name='library_entries',
        verbose_name=_('book')
    )
    date_added = models.DateTimeField(
        _('date added'),
        auto_now_add=True
    )
    last_accessed = models.DateTimeField(
        _('last accessed'),
        null=True,
        blank=True
    )
    reading_progress = models.PositiveIntegerField(
        _('reading progress'),
        default=0,
        help_text=_('Current page number for ebook reading.')
    )
    listening_progress = models.PositiveIntegerField(
        _('listening progress'),
        default=0,
        help_text=_('Current position in seconds for audiobook.')
    )
    download_status = models.CharField(
        _('download status'),
        max_length=20,
        choices=DownloadStatus.choices,
        default=DownloadStatus.NOT_DOWNLOADED
    )
    completion_status = models.CharField(
        _('completion status'),
        max_length=15,
        choices=CompletionStatus.choices,
        default=CompletionStatus.NOT_STARTED
    )
    
    class Meta:
        verbose_name = _('library entry')
        verbose_name_plural = _('library entries')
        ordering = ['-date_added']
        # One entry per user-book combination
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'book'],
                name='unique_user_book_library'
            )
        ]
        indexes = [
            models.Index(fields=['user', 'book']),
            models.Index(fields=['completion_status']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.book.title}"


class Review(models.Model):
    """
    Review model representing a book review.
    Per Architecture Document Section 6.
    """
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name=_('user')
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name=_('book')
    )
    rating = models.PositiveSmallIntegerField(
        _('rating'),
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text=_('Rating from 1 to 5 stars.')
    )
    review_text = models.TextField(
        _('review text'),
        blank=True,
        help_text=_('Optional written review.')
    )
    date_posted = models.DateTimeField(
        _('date posted'),
        auto_now_add=True
    )
    date_modified = models.DateTimeField(
        _('date modified'),
        auto_now=True
    )
    is_visible = models.BooleanField(
        _('is visible'),
        default=True,
        help_text=_('Whether the review is publicly visible.')
    )
    
    class Meta:
        verbose_name = _('review')
        verbose_name_plural = _('reviews')
        ordering = ['-date_posted']
        # One review per user-book combination
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'book'],
                name='unique_user_book_review'
            )
        ]
        indexes = [
            models.Index(fields=['book', 'is_visible']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.book.title} ({self.rating}★)"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update the book's average rating
        self.book.update_average_rating()
    
    def delete(self, *args, **kwargs):
        book = self.book
        super().delete(*args, **kwargs)
        # Update the book's average rating after deletion
        book.update_average_rating()


class PayoutRequest(models.Model):
    """
    PayoutRequest model for author earnings withdrawal.
    Per Architecture Document Section 6.
    """
    
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        PROCESSING = 'processing', _('Processing')
        COMPLETED = 'completed', _('Completed')
        FAILED = 'failed', _('Failed')
    
    class PayoutMethod(models.TextChoices):
        MOBILE_MONEY = 'mobile_money', _('Mobile Money')
        BANK_TRANSFER = 'bank_transfer', _('Bank Transfer')
    
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payout_requests',
        verbose_name=_('author')
    )
    amount_requested = models.DecimalField(
        _('amount requested'),
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('5000.00'))],
        help_text=_('Amount to withdraw in XAF (minimum 5,000 XAF).')
    )
    request_date = models.DateTimeField(
        _('request date'),
        auto_now_add=True
    )
    status = models.CharField(
        _('status'),
        max_length=15,
        choices=Status.choices,
        default=Status.PENDING
    )
    payout_method = models.CharField(
        _('payout method'),
        max_length=15,
        choices=PayoutMethod.choices
    )
    account_details = models.TextField(
        _('account details'),
        help_text=_('Phone number for mobile money or bank account details.')
    )
    processing_notes = models.TextField(
        _('processing notes'),
        blank=True,
        help_text=_('Internal notes for processing (admin only).')
    )
    completion_date = models.DateField(
        _('completion date'),
        null=True,
        blank=True,
        help_text=_('When the payout was completed.')
    )
    
    class Meta:
        verbose_name = _('payout request')
        verbose_name_plural = _('payout requests')
        ordering = ['-request_date']
        indexes = [
            models.Index(fields=['author']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.author.email} - {self.amount_requested:,.0f} XAF ({self.status})"


class HardCopyRequest(models.Model):
    """
    Model for users to request physical/hard copies of books they own.
    Requests are sent to admin and author for manual processing.
    """
    
    class Status(models.TextChoices):
        REQUESTED = 'REQUESTED', _('Requested')
        PROCESSING = 'PROCESSING', _('Processing')
        SHIPPED = 'SHIPPED', _('Shipped')
        DELIVERED = 'DELIVERED', _('Delivered')
        CANCELLED = 'CANCELLED', _('Cancelled')
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hardcopy_requests',
        verbose_name=_('user')
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name='hardcopy_requests',
        verbose_name=_('book')
    )
    
    # Request details
    request_date = models.DateTimeField(
        _('request date'),
        auto_now_add=True
    )
    status = models.CharField(
        _('status'),
        max_length=15,
        choices=Status.choices,
        default=Status.REQUESTED
    )
    
    # Shipping information
    full_name = models.CharField(
        _('full name'),
        max_length=200,
        help_text=_('Name for delivery')
    )
    phone_number = models.CharField(
        _('phone number'),
        max_length=20,
        help_text=_('Contact phone number')
    )
    shipping_address = models.TextField(
        _('shipping address'),
        help_text=_('Full delivery address including city, region, and any landmarks')
    )
    city = models.CharField(
        _('city'),
        max_length=100
    )
    additional_notes = models.TextField(
        _('additional notes'),
        blank=True,
        help_text=_('Any special instructions for delivery')
    )
    
    # Admin processing
    admin_notes = models.TextField(
        _('admin notes'),
        blank=True,
        help_text=_('Internal notes for processing')
    )
    tracking_number = models.CharField(
        _('tracking number'),
        max_length=100,
        blank=True,
        help_text=_('Shipping tracking number if applicable')
    )
    processed_date = models.DateTimeField(
        _('processed date'),
        null=True,
        blank=True
    )
    shipped_date = models.DateTimeField(
        _('shipped date'),
        null=True,
        blank=True
    )
    delivered_date = models.DateTimeField(
        _('delivered date'),
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = _('hard copy request')
        verbose_name_plural = _('hard copy requests')
        ordering = ['-request_date']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['book']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.book.title} ({self.status})"


class UpfrontPaymentApplication(models.Model):
    """
    Upfront payment (advance) application for authors.
    Authors can apply for an advance payment which is recouped via
    increased commission on future sales.
    """
    
    class Status(models.TextChoices):
        IN_REVIEW = 'in_review', _('In Review')
        APPROVED = 'approved', _('Approved')
        COMPLETED = 'completed', _('Completed')  # Fully recouped
        REJECTED = 'rejected', _('Rejected')
        CANCELLED = 'cancelled', _('Cancelled')
    
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='upfront_applications',
        verbose_name=_('author'),
        help_text=_('The author applying for upfront payment.')
    )
    book = models.ForeignKey(
        'Book',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='upfront_applications',
        verbose_name=_('book'),
        help_text=_('Specific book for the advance, or null for all books.')
    )
    amount_requested = models.DecimalField(
        _('amount requested'),
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('1000.00'))],
        help_text=_('Amount requested in XAF.')
    )
    reason = models.TextField(
        _('reason'),
        help_text=_('Why you need this advance payment.')
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.IN_REVIEW
    )
    rejection_reason = models.TextField(
        _('rejection reason'),
        blank=True,
        help_text=_('Reason for rejection if applicable.')
    )
    repayment_rate = models.DecimalField(
        _('repayment rate'),
        max_digits=5,
        decimal_places=2,
        default=Decimal('20.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('50.00'))],
        help_text=_('Extra percentage taken per sale to recoup advance (e.g., 20 means +20%).')
    )
    amount_recouped = models.DecimalField(
        _('amount recouped'),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_('Total amount recouped from sales so far.')
    )
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True
    )
    approved_at = models.DateTimeField(
        _('approved at'),
        null=True,
        blank=True
    )
    completed_at = models.DateTimeField(
        _('completed at'),
        null=True,
        blank=True
    )
    admin_notes = models.TextField(
        _('admin notes'),
        blank=True,
        help_text=_('Internal notes for admin review.')
    )
    terms_accepted = models.BooleanField(
        _('terms accepted'),
        default=False,
        help_text=_('Author has accepted the terms and conditions.')
    )
    
    class Meta:
        verbose_name = _('upfront payment application')
        verbose_name_plural = _('upfront payment applications')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['author']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        book_name = self.book.title if self.book else _('All Books')
        return f"{self.author.email} - {self.amount_requested} XAF ({self.status})"
    
    @property
    def remaining_amount(self):
        """Amount still to be recouped."""
        return max(Decimal('0.00'), self.amount_requested - self.amount_recouped)
    
    @property
    def recoup_progress_percent(self):
        """Percentage of advance that has been recouped."""
        if self.amount_requested <= 0:
            return 0
        return min(100, round((self.amount_recouped / self.amount_requested) * 100, 1))
    
    @property
    def is_fully_recouped(self):
        """Check if the advance has been fully recouped."""
        return self.amount_recouped >= self.amount_requested
    
    def recoup_from_sale(self, author_earning, sale_price):
        """
        Recoup from a sale. Returns the amount to deduct from author earnings.
        """
        if self.status != self.Status.APPROVED:
            return Decimal('0.00')
        
        # Calculate extra amount to deduct based on repayment_rate
        # repayment_rate is the extra % of sale price to take
        deduction = (sale_price * self.repayment_rate / 100).quantize(Decimal('0.01'))
        
        # Don't deduct more than remaining amount or more than author earning
        deduction = min(deduction, self.remaining_amount, author_earning)
        
        self.amount_recouped += deduction
        
        # Check if fully recouped
        if self.is_fully_recouped:
            from django.utils import timezone
            self.status = self.Status.COMPLETED
            self.completed_at = timezone.now()
        
        self.save()
        return deduction

