"""
Core models package.
All models are re-exported here for backward compatibility.
"""

from .book import (
    Book,
    manuscript_upload_path,
    ebook_upload_path,
    audiobook_upload_path,
    cover_upload_path,
)

from .purchase import (
    Purchase,
    LibraryEntry,
)

from .author import (
    Review,
    PayoutRequest,
    HardCopyRequest,
    UpfrontPaymentApplication,
)

from .social import (
    Donation,
    ReferralSettings,
    CommissionSettings,
)

from .featured import FeaturedBook

from .notification import Notification

from .article import Article

__all__ = [
    # Book
    'Book',
    'manuscript_upload_path',
    'ebook_upload_path',
    'audiobook_upload_path',
    'cover_upload_path',
    # Purchase
    'Purchase',
    'LibraryEntry',
    # Author
    'Review',
    'PayoutRequest',
    'HardCopyRequest',
    'UpfrontPaymentApplication',
    # Social
    'Donation',
    'ReferralSettings',
    'CommissionSettings',
    # Featured
    'FeaturedBook',
    # Notification
    'Notification',
    # Blog
    'Article',
]

