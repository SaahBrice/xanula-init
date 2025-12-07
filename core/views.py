from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.conf import settings

from .models import Book, Review, LibraryEntry


def get_available_books():
    """Get books that are available for purchase/viewing."""
    return Book.objects.filter(
        status__in=[
            Book.Status.EBOOK_READY,
            Book.Status.AUDIOBOOK_GENERATED,
            Book.Status.COMPLETED
        ]
    ).select_related('author')


def homepage(request):
    """
    Homepage view with hero, featured books, and category browse.
    Per Planning Document Section 4.
    """
    # Featured books - latest 6 available books
    featured_books = get_available_books().order_by('-submission_date')[:6]
    
    # All categories for browse section
    categories = [
        {'slug': choice[0], 'name': choice[1]}
        for choice in Book.Category.choices
    ]
    
    context = {
        'featured_books': featured_books,
        'categories': categories,
    }
    return render(request, 'core/homepage.html', context)


def book_list(request):
    """
    Book list page with filtering, sorting, and pagination.
    Per Planning Document Section 4 and Architecture Document Section 8.
    """
    books = get_available_books()
    
    # Get filter parameters
    category = request.GET.get('category', '')
    language = request.GET.getlist('language')
    has_ebook = request.GET.get('has_ebook', '')
    has_audiobook = request.GET.get('has_audiobook', '')
    price_range = request.GET.get('price_range', '')
    sort_by = request.GET.get('sort', 'recent')
    
    # Apply category filter
    if category:
        books = books.filter(category=category)
    
    # Apply language filter
    if language:
        books = books.filter(language__in=language)
    
    # Apply format filters
    if has_ebook == 'true':
        books = books.exclude(ebook_file='')
    if has_audiobook == 'true':
        books = books.exclude(audiobook_file='')
    
    # Apply price range filter
    if price_range == 'free':
        books = books.filter(price=0)
    elif price_range == 'under1000':
        books = books.filter(price__gt=0, price__lt=1000)
    elif price_range == '1000to5000':
        books = books.filter(price__gte=1000, price__lte=5000)
    elif price_range == 'above5000':
        books = books.filter(price__gt=5000)
    
    # Apply sorting
    if sort_by == 'bestselling':
        books = books.order_by('-total_sales')
    elif sort_by == 'alphabetical':
        books = books.order_by('title')
    else:  # recent (default)
        books = books.order_by('-submission_date')
    
    # Pagination - 20 books per page
    paginator = Paginator(books, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Categories for filter sidebar
    categories = [
        {'slug': choice[0], 'name': choice[1]}
        for choice in Book.Category.choices
    ]
    
    context = {
        'page_obj': page_obj,
        'categories': categories,
        'selected_category': category,
        'selected_languages': language,
        'has_ebook': has_ebook,
        'has_audiobook': has_audiobook,
        'price_range': price_range,
        'sort_by': sort_by,
    }
    return render(request, 'core/book_list.html', context)


def search_books(request):
    """
    Search functionality with prioritized results.
    Per Planning Document Section 4 - exact title matches first, then descriptions, then author names.
    """
    query = request.GET.get('q', '').strip()
    
    if not query:
        return render(request, 'core/search_results.html', {'query': '', 'results': []})
    
    # Get available books
    available_books = get_available_books()
    
    # Priority 1: Exact title matches
    exact_matches = available_books.filter(title__iexact=query)
    
    # Priority 2: Title contains query
    title_contains = available_books.filter(
        title__icontains=query
    ).exclude(id__in=exact_matches)
    
    # Priority 3: Description matches
    description_matches = available_books.filter(
        Q(short_description__icontains=query) | Q(long_description__icontains=query)
    ).exclude(id__in=exact_matches).exclude(id__in=title_contains)
    
    # Priority 4: Author name matches
    author_matches = available_books.filter(
        Q(author__display_name__icontains=query) | Q(author__email__icontains=query)
    ).exclude(id__in=exact_matches).exclude(id__in=title_contains).exclude(id__in=description_matches)
    
    # Combine results in priority order
    from itertools import chain
    results = list(chain(exact_matches, title_contains, description_matches, author_matches))
    
    # Pagination
    paginator = Paginator(results, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'query': query,
        'page_obj': page_obj,
        'result_count': len(results),
    }
    return render(request, 'core/search_results.html', context)


def category_books(request, category_slug):
    """
    Category page - books in a specific category.
    Per Planning Document Section 4.
    """
    # Validate category exists
    category_name = None
    for choice in Book.Category.choices:
        if choice[0] == category_slug:
            category_name = choice[1]
            break
    
    if not category_name:
        messages.error(request, 'Category not found.')
        return redirect('core:book_list')
    
    # Get books in this category
    books = get_available_books().filter(category=category_slug)
    
    # Apply sorting
    sort_by = request.GET.get('sort', 'recent')
    if sort_by == 'bestselling':
        books = books.order_by('-total_sales')
    elif sort_by == 'alphabetical':
        books = books.order_by('title')
    else:
        books = books.order_by('-submission_date')
    
    # Pagination
    paginator = Paginator(books, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'category_slug': category_slug,
        'category_name': category_name,
        'page_obj': page_obj,
        'sort_by': sort_by,
    }
    return render(request, 'core/category_books.html', context)


def book_detail(request, slug):
    """
    Book detail page with all information.
    Per Planning Document Section 4.
    """
    book = get_object_or_404(
        Book.objects.select_related('author'),
        slug=slug,
        status__in=[
            Book.Status.EBOOK_READY,
            Book.Status.AUDIOBOOK_GENERATED,
            Book.Status.COMPLETED
        ]
    )
    
    # Check if user owns this book
    user_owns_book = False
    in_wishlist = False
    if request.user.is_authenticated:
        user_owns_book = LibraryEntry.objects.filter(
            user=request.user, book=book
        ).exists()
        in_wishlist = request.user.wishlist.filter(id=book.id).exists()
    
    # Get reviews
    reviews = book.reviews.filter(is_visible=True).select_related('user').order_by('-date_posted')[:10]
    review_count = book.reviews.filter(is_visible=True).count()
    
    # Check if user has already reviewed
    user_has_reviewed = False
    user_review = None
    if request.user.is_authenticated:
        user_review = book.reviews.filter(user=request.user).first()
        user_has_reviewed = user_review is not None
    
    # Get more books by author
    more_by_author = get_available_books().filter(
        author=book.author
    ).exclude(id=book.id)[:4]
    
    context = {
        'book': book,
        'user_owns_book': user_owns_book,
        'in_wishlist': in_wishlist,
        'reviews': reviews,
        'review_count': review_count,
        'user_has_reviewed': user_has_reviewed,
        'user_review': user_review,
        'more_by_author': more_by_author,
    }
    return render(request, 'core/book_detail.html', context)


def author_profile(request, user_id):
    """
    Author profile page - public profile with published books.
    Per Planning Document Section 2.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    author = get_object_or_404(User, id=user_id)
    
    # Get author's published books
    books = get_available_books().filter(author=author).order_by('-submission_date')
    
    context = {
        'author': author,
        'books': books,
        'book_count': books.count(),
    }
    return render(request, 'core/author_profile.html', context)


@login_required
@require_POST
def toggle_wishlist(request, book_id):
    """
    Add or remove book from user's wishlist.
    Per Planning Document Section 4.
    """
    book = get_object_or_404(Book, id=book_id)
    
    if request.user.wishlist.filter(id=book_id).exists():
        request.user.wishlist.remove(book)
        added = False
        message = f'"{book.title}" removed from your wishlist.'
    else:
        request.user.wishlist.add(book)
        added = True
        message = f'"{book.title}" added to your wishlist!'
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'added': added, 'message': message})
    
    messages.success(request, message)
    return redirect('core:book_detail', slug=book.slug)


@login_required
def my_wishlist(request):
    """
    View user's wishlist.
    """
    books = request.user.wishlist.filter(
        status__in=[
            Book.Status.EBOOK_READY,
            Book.Status.AUDIOBOOK_GENERATED,
            Book.Status.COMPLETED
        ]
    ).select_related('author')
    
    context = {
        'books': books,
    }
    return render(request, 'core/wishlist.html', context)
