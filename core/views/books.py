"""
Book browsing views: homepage, book list, search, category, detail.
"""
from ._views import (
    get_available_books,
    homepage,
    book_list,
    search_books,
    category_books,
    book_detail,
    author_profile,
    toggle_wishlist,
    my_wishlist,
    book_preview,
)

__all__ = [
    'get_available_books',
    'homepage',
    'book_list',
    'search_books',
    'category_books',
    'book_detail',
    'author_profile',
    'toggle_wishlist',
    'my_wishlist',
    'book_preview',
]
