"""
Book model and related upload path helpers.
"""
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
    
    # Hard copy availability options
    class HardCopyOption(models.TextChoices):
        NONE = 'none', _('No hard copies - Ebook/Audiobook only')
        AUTHOR_PROVIDED = 'author', _('I have hard copies to ship')
        XANULA_PRINT = 'xanula', _('Xanula should produce hard copies')
    
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
        help_text=_('Platform commission rate percentage (for legacy compatibility).')
    )
    custom_commission_rate = models.DecimalField(
        _('custom commission rate'),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text=_('Optional custom commission rate. If set, overrides global settings.')
    )
    
    # Publishing Services Options
    hard_copy_option = models.CharField(
        _('hard copy option'),
        max_length=10,
        choices=HardCopyOption.choices,
        default=HardCopyOption.NONE,
        help_text=_('Hard copy availability option.')
    )
    wants_editor_services = models.BooleanField(
        _('wants editor services'),
        default=False,
        help_text=_('Author wants Xanula editing/proofreading services.')
    )
    wants_cover_design = models.BooleanField(
        _('wants cover design'),
        default=False,
        help_text=_('Author wants Xanula to design/redesign the book cover.')
    )
    wants_formatting = models.BooleanField(
        _('wants formatting'),
        default=False,
        help_text=_('Author wants Xanula to format the book layout.')
    )
    wants_marketing_kit = models.BooleanField(
        _('wants marketing kit'),
        default=False,
        help_text=_('Author wants social media marketing materials.')
    )
    wants_third_party_distribution = models.BooleanField(
        _('wants third-party distribution'),
        default=False,
        help_text=_('Author wants distribution to Amazon KDP, REEPLS, Smashwords, etc.')
    )
    wants_isbn = models.BooleanField(
        _('wants ISBN'),
        default=False,
        help_text=_('Author wants ISBN for printed book (increases commission).')
    )
    
    # QR Code - auto-generated when book status is COMPLETED
    qr_code = models.ImageField(
        _('QR code'),
        upload_to='qr_codes/',
        null=True,
        blank=True,
        help_text=_('Auto-generated QR code linking to book page.')
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
        from .purchase import LibraryEntry
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
    
    def get_effective_commission_rate(self):
        """
        Get the effective commission rate as a decimal (e.g., 0.30 for 30%).
        Priority:
        1. If custom_commission_rate is set, use it
        2. Otherwise, use global CommissionSettings based on book format
        """
        # Check for custom per-book rate first
        if self.custom_commission_rate is not None:
            return self.custom_commission_rate / Decimal('100')
        
        # Use global settings based on book format
        from .social import CommissionSettings
        if self.has_audiobook:
            return CommissionSettings.get_audiobook_rate()
        else:
            return CommissionSettings.get_ebook_rate()
    
    def generate_qr_code(self):
        """
        Generate a QR code linking to the book page.
        Called when book status changes to COMPLETED.
        """
        import qrcode
        from io import BytesIO
        from django.core.files.base import ContentFile
        
        # Generate URL
        book_url = f"https://xanula.reepls.com/books/{self.slug}/"
        
        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(book_url)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to BytesIO
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Save to model field
        filename = f"qr_{self.slug}.png"
        self.qr_code.save(filename, ContentFile(buffer.read()), save=False)
        
        return True
