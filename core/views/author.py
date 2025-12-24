"""
Author publishing and dashboard views.
"""
from ._views import (
    publish_book,
    my_books,
    edit_book,
    request_payout,
    author_analytics,
    analytics_data_api,
    upfront_applications_list,
    apply_upfront_payment,
    cancel_upfront_application,
    upfront_terms_content,
    process_upfront_recouping,
)

__all__ = [
    'publish_book',
    'my_books',
    'edit_book',
    'request_payout',
    'author_analytics',
    'analytics_data_api',
    'upfront_applications_list',
    'apply_upfront_payment',
    'cancel_upfront_application',
    'upfront_terms_content',
    'process_upfront_recouping',
]
