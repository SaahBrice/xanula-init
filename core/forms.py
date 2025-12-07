"""
Forms for Xanula core application.
Handles book submission, editing, and payout requests.
"""
from django import forms
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from decimal import Decimal

from .models import Book, PayoutRequest


# File upload constraints per Planning Document
ALLOWED_MANUSCRIPT_EXTENSIONS = ['pdf', 'docx', 'epub', 'txt']
MAX_MANUSCRIPT_SIZE = 25 * 1024 * 1024  # 25MB
ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png']
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
MIN_PRICE = Decimal('0')
MAX_PRICE = Decimal('50000')


def validate_file_size(file, max_size, file_type="file"):
    """Validate file size doesn't exceed maximum."""
    if file.size > max_size:
        max_mb = max_size / (1024 * 1024)
        raise ValidationError(
            _(f'The {file_type} is too large. Maximum size is {max_mb:.0f}MB.')
        )


class BookSubmissionForm(forms.ModelForm):
    """
    Form for submitting a new book.
    Per Planning Document Section 3 and Architecture Document Section 6.
    """
    
    # Custom field for "make this free" checkbox
    make_free = forms.BooleanField(
        required=False,
        label=_('Make this book free'),
        help_text=_('Check this to offer the book for free.')
    )
    
    class Meta:
        model = Book
        fields = [
            'title',
            'short_description',
            'long_description',
            'cover_image',
            'category',
            'language',
            'price',
            'manuscript_file',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 bg-dark-100 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent',
                'placeholder': 'Enter your book title',
            }),
            'short_description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 bg-dark-100 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none',
                'placeholder': 'Brief description for book listings (max 200 characters)',
                'rows': 3,
                'maxlength': 200,
                'x-data': '',
                'x-on:input': 'charCount = $el.value.length',
            }),
            'long_description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 bg-dark-100 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent',
                'placeholder': 'Full description that appears on the book detail page',
                'rows': 6,
            }),
            'category': forms.Select(attrs={
                'class': 'w-full px-4 py-3 bg-dark-100 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent',
            }),
            'language': forms.RadioSelect(attrs={
                'class': 'text-primary-500 focus:ring-primary-500',
            }),
            'price': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 bg-dark-100 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent',
                'placeholder': '0',
                'min': '0',
                'max': '50000',
                'step': '100',
                'x-bind:disabled': 'makeFree',
            }),
            'cover_image': forms.FileInput(attrs={
                'class': 'hidden',
                'accept': 'image/jpeg,image/png',
                'x-ref': 'coverInput',
                'x-on:change': 'previewCover($event)',
            }),
            'manuscript_file': forms.FileInput(attrs={
                'class': 'hidden',
                'accept': '.pdf,.docx,.epub,.txt',
                'x-ref': 'manuscriptInput',
                'x-on:change': 'checkManuscript($event)',
            }),
        }
        labels = {
            'title': _('Book Title'),
            'short_description': _('Short Description'),
            'long_description': _('Full Description'),
            'cover_image': _('Cover Image'),
            'category': _('Category'),
            'language': _('Language'),
            'price': _('Price (XAF)'),
            'manuscript_file': _('Manuscript File'),
        }
        help_texts = {
            'short_description': _('Maximum 200 characters. This appears in book listings.'),
            'long_description': _('Detailed description that appears on the book page.'),
            'cover_image': _('JPEG or PNG, max 5MB. Recommended size: 800x1200 pixels.'),
            'manuscript_file': _('PDF, DOCX, EPUB, or TXT. Maximum 25MB.'),
            'price': _('Set price in XAF (0-50,000). Use checkbox below for free books.'),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add file extension validators
        self.fields['manuscript_file'].validators.append(
            FileExtensionValidator(allowed_extensions=ALLOWED_MANUSCRIPT_EXTENSIONS)
        )
        self.fields['cover_image'].validators.append(
            FileExtensionValidator(allowed_extensions=ALLOWED_IMAGE_EXTENSIONS)
        )
    
    def clean_manuscript_file(self):
        """Validate manuscript file size."""
        file = self.cleaned_data.get('manuscript_file')
        if file:
            validate_file_size(file, MAX_MANUSCRIPT_SIZE, "manuscript")
        return file
    
    def clean_cover_image(self):
        """Validate cover image size."""
        file = self.cleaned_data.get('cover_image')
        if file:
            validate_file_size(file, MAX_IMAGE_SIZE, "cover image")
        return file
    
    def clean_price(self):
        """Validate price is within allowed range."""
        price = self.cleaned_data.get('price')
        if price is None:
            price = Decimal('0')
        if price < MIN_PRICE:
            raise ValidationError(_('Price cannot be negative.'))
        if price > MAX_PRICE:
            raise ValidationError(_(f'Price cannot exceed {MAX_PRICE:,.0f} XAF.'))
        return price
    
    def clean(self):
        """Handle make_free checkbox."""
        cleaned_data = super().clean()
        make_free = cleaned_data.get('make_free')
        if make_free:
            cleaned_data['price'] = Decimal('0')
        return cleaned_data


class BookEditForm(BookSubmissionForm):
    """
    Form for editing a denied book.
    Inherits from BookSubmissionForm with slight modifications.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make files optional for editing (keep existing if not changed)
        self.fields['manuscript_file'].required = False
        self.fields['cover_image'].required = False
    
    def clean_manuscript_file(self):
        """Allow empty file (keeps existing) or validate new upload."""
        file = self.cleaned_data.get('manuscript_file')
        if file:
            validate_file_size(file, MAX_MANUSCRIPT_SIZE, "manuscript")
        return file
    
    def clean_cover_image(self):
        """Allow empty file (keeps existing) or validate new upload."""
        file = self.cleaned_data.get('cover_image')
        if file:
            validate_file_size(file, MAX_IMAGE_SIZE, "cover image")
        return file


class PayoutRequestForm(forms.ModelForm):
    """
    Form for requesting a payout.
    Per Planning Document Section 6.
    """
    
    class Meta:
        model = PayoutRequest
        fields = ['amount_requested', 'payout_method', 'account_details']
        widgets = {
            'amount_requested': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 bg-dark-100 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent',
                'placeholder': 'Enter amount',
                'min': '5000',
                'step': '100',
            }),
            'payout_method': forms.RadioSelect(attrs={
                'class': 'text-primary-500 focus:ring-primary-500',
            }),
            'account_details': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 bg-dark-100 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent',
                'placeholder': 'Enter your phone number for Mobile Money or bank account details',
                'rows': 3,
            }),
        }
        labels = {
            'amount_requested': _('Amount to Withdraw (XAF)'),
            'payout_method': _('Payout Method'),
            'account_details': _('Account Details'),
        }
        help_texts = {
            'amount_requested': _('Minimum 5,000 XAF. Maximum is your current balance.'),
            'account_details': _('For Mobile Money: enter phone number. For Bank Transfer: enter bank name, account number, and account holder name.'),
        }
    
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user:
            self.fields['amount_requested'].widget.attrs['max'] = str(user.earnings_balance)
    
    def clean_amount_requested(self):
        """Validate amount against user's balance."""
        amount = self.cleaned_data.get('amount_requested')
        if amount is None:
            raise ValidationError(_('Amount is required.'))
        
        # Minimum validation
        if amount < Decimal('5000'):
            raise ValidationError(_('Minimum payout amount is 5,000 XAF.'))
        
        # Maximum validation (user's balance)
        if self.user and amount > self.user.earnings_balance:
            raise ValidationError(
                _(f'Amount cannot exceed your balance of {self.user.earnings_balance:,.0f} XAF.')
            )
        
        return amount
    
    def clean_account_details(self):
        """Ensure account details are provided."""
        details = self.cleaned_data.get('account_details', '').strip()
        if not details:
            raise ValidationError(_('Please provide your account details.'))
        if len(details) < 10:
            raise ValidationError(_('Please provide complete account details.'))
        return details
