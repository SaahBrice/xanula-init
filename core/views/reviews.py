"""
Review management views: submit, edit, delete reviews.
"""
from ._views import (
    submit_review,
    edit_review,
    delete_review,
)

__all__ = [
    'submit_review',
    'edit_review',
    'delete_review',
]
