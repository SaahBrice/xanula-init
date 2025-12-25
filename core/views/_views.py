from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.conf import settings

from ..models import Book, Review, LibraryEntry, PayoutRequest, UpfrontPaymentApplication, Donation, ReferralSettings


def process_upfront_recouping(purchase, author):
    """
    Process upfront payment recouping for a completed purchase.
    Deducts from author earnings if they have an active upfront payment.
    
    Returns:
        Decimal: The amount deducted from author earnings
    """
    from decimal import Decimal
    
    # Find active upfront payment application(s) for this author
    # Either for the specific book or for all books
    active_applications = UpfrontPaymentApplication.objects.filter(
        author=author,
        status=UpfrontPaymentApplication.Status.APPROVED
    ).filter(
        # Either the application is for this specific book or for all books (book=None)
        Q(book=purchase.book) | Q(book__isnull=True)
    ).order_by('created_at')  # Process oldest first
    
    total_deducted = Decimal('0.00')
    
    for application in active_applications:
        if application.remaining_amount <= 0:
            continue
            
        # Calculate deduction based on repayment rate
        deduction = application.recoup_from_sale(
            author_earning=purchase.author_earning - total_deducted,
            sale_price=purchase.amount_paid
        )
        total_deducted += deduction
        
        # If all earnings are recouped, stop processing
        if total_deducted >= purchase.author_earning:
            break
    
    return total_deducted


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
    from core.models import FeaturedBook
    
    # Get user's preferred language from Django's locale
    user_language = getattr(request, 'LANGUAGE_CODE', 'en')[:2]  # 'en' or 'fr'
    
    # Get featured books for user's language, fallback to English
    featured_entries = FeaturedBook.objects.filter(
        language=user_language, 
        is_active=True
    ).select_related('book', 'book__author').order_by('position')[:6]
    
    # If no featured books for user's language, try English
    if not featured_entries.exists() and user_language != 'en':
        featured_entries = FeaturedBook.objects.filter(
            language='en', 
            is_active=True
        ).select_related('book', 'book__author').order_by('position')[:6]
    
    # Extract books from featured entries, or fallback to latest books
    if featured_entries.exists():
        featured_books = [entry.book for entry in featured_entries]
    else:
        featured_books = list(get_available_books().order_by('-submission_date')[:6])
    
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
    from ..models import Review
    from django.db.models import Count
    
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
    
    # Calculate rating distribution for breakdown visualization
    rating_distribution = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    if review_count > 0:
        dist_qs = book.reviews.filter(is_visible=True).values('rating').annotate(count=Count('id'))
        for item in dist_qs:
            rating_distribution[item['rating']] = item['count']
    
    # Check if user has already reviewed
    user_has_reviewed = False
    user_review = None
    can_review = False
    if request.user.is_authenticated:
        user_review = book.reviews.filter(user=request.user).first()
        user_has_reviewed = user_review is not None
        can_review = user_owns_book and not user_has_reviewed
    
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
        'rating_distribution': rating_distribution,
        'user_has_reviewed': user_has_reviewed,
        'user_review': user_review,
        'can_review': can_review,
        'more_by_author': more_by_author,
    }
    return render(request, 'core/book_detail.html', context)


# =============================================================================
# Review Management Views
# Per Planning Document Section 10 (Reviews & Ratings)
# =============================================================================

@login_required
@require_POST
def submit_review(request, book_id):
    """
    Submit a new review for a book.
    User must own the book and not have already reviewed it.
    """
    from ..models import Review
    import json
    
    book = get_object_or_404(Book, id=book_id)
    
    # Check ownership
    if not LibraryEntry.objects.filter(user=request.user, book=book).exists():
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'You must own this book to review it.'}, status=403)
        messages.error(request, 'You must own this book to review it.')
        return redirect('core:book_detail', slug=book.slug)
    
    # Check for existing review
    if Review.objects.filter(user=request.user, book=book).exists():
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'You have already reviewed this book.'}, status=400)
        messages.error(request, 'You have already reviewed this book.')
        return redirect('core:book_detail', slug=book.slug)
    
    # Get data
    if request.content_type == 'application/json':
        data = json.loads(request.body)
        rating = data.get('rating')
        review_text = data.get('review_text', '').strip()
    else:
        rating = request.POST.get('rating')
        review_text = request.POST.get('review_text', '').strip()
    
    # Validate rating
    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            raise ValueError
    except (TypeError, ValueError):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Please select a rating between 1 and 5 stars.'}, status=400)
        messages.error(request, 'Please select a rating between 1 and 5 stars.')
        return redirect('core:book_detail', slug=book.slug)
    
    # Truncate review text if too long
    if len(review_text) > 1000:
        review_text = review_text[:1000]
    
    # Create review
    review = Review.objects.create(
        user=request.user,
        book=book,
        rating=rating,
        review_text=review_text
    )
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'review_id': review.id,
            'message': 'Your review has been submitted!',
            'new_average': float(book.average_rating),
            'new_count': book.reviews.filter(is_visible=True).count()
        })
    
    messages.success(request, 'Your review has been submitted!')
    return redirect('core:book_detail', slug=book.slug)


@login_required
@require_POST
def edit_review(request, review_id):
    """
    Edit an existing review. Users can only edit their own reviews.
    """
    from ..models import Review
    import json
    
    review = get_object_or_404(Review, id=review_id)
    
    # Check ownership
    if review.user != request.user:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'You can only edit your own reviews.'}, status=403)
        messages.error(request, 'You can only edit your own reviews.')
        return redirect('core:book_detail', slug=review.book.slug)
    
    # Get data
    if request.content_type == 'application/json':
        data = json.loads(request.body)
        rating = data.get('rating')
        review_text = data.get('review_text', '').strip()
    else:
        rating = request.POST.get('rating')
        review_text = request.POST.get('review_text', '').strip()
    
    # Validate rating
    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            raise ValueError
    except (TypeError, ValueError):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Please select a rating between 1 and 5 stars.'}, status=400)
        messages.error(request, 'Please select a rating between 1 and 5 stars.')
        return redirect('core:book_detail', slug=review.book.slug)
    
    # Truncate review text if too long
    if len(review_text) > 1000:
        review_text = review_text[:1000]
    
    # Update review
    review.rating = rating
    review.review_text = review_text
    review.save()  # This will also update book.average_rating
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': 'Your review has been updated!',
            'new_average': float(review.book.average_rating),
            'new_count': review.book.reviews.filter(is_visible=True).count()
        })
    
    messages.success(request, 'Your review has been updated!')
    return redirect('core:book_detail', slug=review.book.slug)


@login_required
@require_POST
def delete_review(request, review_id):
    """
    Delete a review. Users can only delete their own reviews.
    """
    from ..models import Review
    
    review = get_object_or_404(Review, id=review_id)
    book = review.book
    
    # Check ownership
    if review.user != request.user:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'You can only delete your own reviews.'}, status=403)
        messages.error(request, 'You can only delete your own reviews.')
        return redirect('core:book_detail', slug=book.slug)
    
    # Delete review (this will trigger book.update_average_rating in the model's delete method)
    review.delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': 'Your review has been deleted.',
            'new_average': float(book.average_rating),
            'new_count': book.reviews.filter(is_visible=True).count()
        })
    
    messages.success(request, 'Your review has been deleted.')
    return redirect('core:book_detail', slug=book.slug)


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


# =============================================================================
# Author Publishing Views
# Per Planning Document Section 3 and Architecture Document Section 6
# =============================================================================

@login_required
def publish_book(request):
    """
    Book submission page for authors.
    Per Planning Document Section 3.
    """
    from ..forms import BookSubmissionForm
    
    if request.method == 'POST':
        form = BookSubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            book = form.save(commit=False)
            book.author = request.user
            book.status = Book.Status.IN_REVIEW
            book.save()
            
            messages.success(
                request,
                f'Your book "{book.title}" has been submitted for review. '
                'We will notify you once it\'s been processed.'
            )
            return redirect('core:my_books')
    else:
        form = BookSubmissionForm()
    
    context = {
        'form': form,
        'categories': Book.Category.choices,
    }
    return render(request, 'core/publish_book.html', context)


@login_required
def my_books(request):
    """
    Author's books dashboard with earnings.
    Per Planning Document Section 3.
    """
    # Get filter parameter
    status_filter = request.GET.get('status', 'all')
    
    # Get user's books
    books = Book.objects.filter(author=request.user).order_by('-submission_date')
    
    # Apply status filter
    if status_filter != 'all':
        books = books.filter(status=status_filter)
    
    # Calculate earnings per book (from completed purchases)
    from django.db.models import Sum, Count
    from ..models import Purchase
    
    book_earnings = {}
    for book in books:
        stats = Purchase.objects.filter(
            book=book,
            payment_status=Purchase.PaymentStatus.COMPLETED
        ).aggregate(
            total_earnings=Sum('author_earning'),
            sales_count=Count('id')
        )
        book_earnings[book.id] = {
            'earnings': stats['total_earnings'] or 0,
            'sales': stats['sales_count'] or 0,
        }
    
    # Get pending payout requests
    payout_requests = request.user.payout_requests.order_by('-request_date')[:5]
    
    # Status counts for tabs
    status_counts = {
        'all': Book.objects.filter(author=request.user).count(),
        'in_review': Book.objects.filter(author=request.user, status=Book.Status.IN_REVIEW).count(),
        'approved': Book.objects.filter(author=request.user, status=Book.Status.APPROVED).count(),
        'denied': Book.objects.filter(author=request.user, status=Book.Status.DENIED).count(),
        'completed': Book.objects.filter(author=request.user, status__in=[
            Book.Status.EBOOK_READY,
            Book.Status.AUDIOBOOK_GENERATED,
            Book.Status.COMPLETED
        ]).count(),
    }
    
    context = {
        'books': books,
        'book_earnings': book_earnings,
        'status_filter': status_filter,
        'status_counts': status_counts,
        'payout_requests': payout_requests,
        'can_request_payout': request.user.can_request_payout(),
        'earnings_balance': request.user.earnings_balance,
    }
    return render(request, 'core/my_books.html', context)


@login_required
def edit_book(request, book_id):
    """
    Edit a denied book for resubmission.
    Per Planning Document answer 3.
    """
    from ..forms import BookEditForm
    
    book = get_object_or_404(Book, id=book_id, author=request.user)
    
    # Only allow editing denied books
    if book.status != Book.Status.DENIED:
        messages.error(
            request,
            'You can only edit books that have been denied. '
            'Approved books cannot be modified.'
        )
        return redirect('core:my_books')
    
    if request.method == 'POST':
        form = BookEditForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            book = form.save(commit=False)
            book.status = Book.Status.IN_REVIEW
            book.denial_reason = ''  # Clear denial reason
            book.save()
            
            messages.success(
                request,
                f'Your book "{book.title}" has been resubmitted for review.'
            )
            return redirect('core:my_books')
    else:
        form = BookEditForm(instance=book)
    
    context = {
        'form': form,
        'book': book,
        'categories': Book.Category.choices,
    }
    return render(request, 'core/edit_book.html', context)


@login_required
def request_payout(request):
    """
    Request a payout of earnings.
    Per Planning Document Section 6.
    """
    from ..forms import PayoutRequestForm
    
    # Check if user can request payout
    if not request.user.can_request_payout():
        messages.warning(
            request,
            f'You need at least 5,000 XAF to request a payout. '
            f'Your current balance is {request.user.formatted_earnings}.'
        )
        return redirect('core:my_books')
    
    if request.method == 'POST':
        form = PayoutRequestForm(request.POST, user=request.user)
        if form.is_valid():
            payout = form.save(commit=False)
            payout.author = request.user
            payout.save()
            
            # Deduct from earnings balance (will be restored if failed)
            request.user.earnings_balance -= payout.amount_requested
            request.user.save(update_fields=['earnings_balance'])
            
            messages.success(
                request,
                f'Your payout request for {payout.amount_requested:,.0f} XAF has been submitted. '
                'We will process it within 3-5 business days.'
            )
            return redirect('core:my_books')
    else:
        form = PayoutRequestForm(user=request.user)
    
    # Get pending payout requests
    pending_payouts = request.user.payout_requests.filter(
        status__in=[PayoutRequest.Status.PENDING, PayoutRequest.Status.PROCESSING]
    ).order_by('-request_date')
    
    context = {
        'form': form,
        'earnings_balance': request.user.earnings_balance,
        'pending_payouts': pending_payouts,
    }
    return render(request, 'core/request_payout.html', context)


# =============================================================================
# Purchase & Payment Views
# Per Planning Document Section 5 and Architecture Document Section 9
# =============================================================================

@login_required
def initiate_purchase(request, slug):
    """
    Purchase initiation page.
    Handles ownership check and free book flow.
    """
    book = get_object_or_404(Book, slug=slug)
    
    # Check if book is available for purchase
    if not book.is_available:
        messages.error(request, 'This book is not available for purchase yet.')
        return redirect('core:book_detail', slug=slug)
    
    # Anti-duplicate: Check if user already owns the book
    if LibraryEntry.objects.filter(user=request.user, book=book).exists():
        messages.info(request, 'You already own this book! It\'s in your library.')
        return redirect('core:my_books')
    
    # Handle free books - skip payment completely
    if book.is_free:
        from ..models import Purchase
        
        # Create purchase record
        purchase = Purchase.objects.create(
            buyer=request.user,
            book=book,
            amount_paid=0,
            payment_method=Purchase.PaymentMethod.STRIPE,
            payment_status=Purchase.PaymentStatus.COMPLETED,
            platform_commission=0,
            author_earning=0,
            payment_transaction_id='FREE'
        )
        
        # Create library entry
        LibraryEntry.objects.create(
            user=request.user,
            book=book
        )
        
        # Increment book sales
        book.total_sales += 1
        book.save(update_fields=['total_sales'])
        
        messages.success(request, f'"{book.title}" has been added to your library for free!')
        return redirect('core:my_books')
    
    # For priced books, show payment selection page
    # Calculate balance payment options
    user_balance = request.user.earnings_balance
    can_pay_full_balance = user_balance >= book.price
    can_pay_partial = user_balance > 0 and user_balance < book.price
    balance_to_use = min(user_balance, book.price)
    remaining_amount = max(book.price - user_balance, Decimal('0.00'))
    
    context = {
        'book': book,
        'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
        'user_balance': user_balance,
        'can_pay_full_balance': can_pay_full_balance,
        'can_pay_partial': can_pay_partial,
        'balance_to_use': balance_to_use,
        'remaining_amount': remaining_amount,
        'balance_after_purchase': user_balance - book.price if can_pay_full_balance else Decimal('0.00'),
    }
    return render(request, 'core/purchase_page.html', context)


@login_required
@require_POST
def purchase_with_balance(request, book_id):
    """
    Purchase a book using account balance only.
    User must have sufficient balance to cover the full price.
    """
    from ..models import Purchase, ReferralSettings
    from users.models import User
    
    book = get_object_or_404(Book, id=book_id)
    
    # Anti-duplicate check
    if LibraryEntry.objects.filter(user=request.user, book=book).exists():
        messages.info(request, 'You already own this book!')
        return redirect('core:my_books')
    
    # Verify sufficient balance
    if request.user.earnings_balance < book.price:
        messages.error(request, 'Insufficient balance. Please use a payment method.')
        return redirect('core:initiate_purchase', slug=book.slug)
    
    # Check for referral code
    referral_code = request.POST.get('referral_code', '').strip().upper()
    referred_by = None
    
    if referral_code:
        try:
            referrer = User.objects.get(referral_code=referral_code)
            if referrer != request.user:
                referred_by = referrer
        except User.DoesNotExist:
            pass
    
    # Deduct balance from buyer
    request.user.earnings_balance -= book.price
    request.user.save(update_fields=['earnings_balance'])
    
    # Create purchase record
    purchase = Purchase.objects.create(
        buyer=request.user,
        book=book,
        amount_paid=book.price,
        payment_method=Purchase.PaymentMethod.BALANCE,
        payment_status=Purchase.PaymentStatus.COMPLETED,
        payment_transaction_id=f'BAL-{request.user.id}-{book.id}',
        referred_by=referred_by,
        balance_used=book.price
    )
    
    # Calculate commission using book's effective rate
    commission_rate = book.get_effective_commission_rate()
    purchase.platform_commission = book.price * commission_rate
    purchase.author_earning = book.price - purchase.platform_commission
    purchase.save()
    
    # Process referral commission
    process_referral_commission(purchase)
    
    # Credit author's balance (with upfront recouping)
    author = book.author
    recouped = process_upfront_recouping(purchase, author)
    final_earning = purchase.author_earning - recouped
    author.earnings_balance += final_earning
    author.save(update_fields=['earnings_balance'])
    
    # Create library entry
    LibraryEntry.objects.get_or_create(
        user=request.user,
        book=book
    )
    
    # Increment book sales
    book.total_sales += 1
    book.save(update_fields=['total_sales'])
    
    messages.success(request, f'Successfully purchased "{book.title}" using your balance!')
    return redirect('core:my_books')


@login_required
def create_stripe_checkout(request, book_id):
    """
    Create Stripe checkout session and redirect to Stripe.
    """
    import stripe
    from ..models import Purchase, ReferralSettings
    from users.models import User
    
    # Require POST
    if request.method != 'POST':
        return redirect('core:book_detail', slug=get_object_or_404(Book, id=book_id).slug)
    
    book = get_object_or_404(Book, id=book_id)
    
    # Anti-duplicate check
    if LibraryEntry.objects.filter(user=request.user, book=book).exists():
        messages.info(request, 'You already own this book!')
        return redirect('core:my_books')
    
    # Check for referral code
    referral_code = request.POST.get('referral_code', '').strip().upper()
    referred_by = None
    
    if referral_code:
        try:
            referrer = User.objects.get(referral_code=referral_code)
            # Validate: not self-referral
            if referrer != request.user:
                referred_by = referrer
            else:
                messages.warning(request, 'You cannot use your own referral code.')
        except User.DoesNotExist:
            messages.warning(request, 'Invalid referral code.')
    
    # Check if user wants to use balance for partial payment
    use_balance = request.POST.get('use_balance') == 'on'
    balance_to_use = Decimal('0.00')
    amount_to_charge = book.price
    
    if use_balance and request.user.earnings_balance > 0:
        balance_to_use = min(request.user.earnings_balance, book.price)
        amount_to_charge = book.price - balance_to_use
        
        # Deduct balance immediately
        request.user.earnings_balance -= balance_to_use
        request.user.save(update_fields=['earnings_balance'])
    
    # Configure Stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    
    # Determine payment method
    payment_method = Purchase.PaymentMethod.PARTIAL if balance_to_use > 0 else Purchase.PaymentMethod.STRIPE
    
    # Create pending purchase record
    purchase = Purchase.objects.create(
        buyer=request.user,
        book=book,
        amount_paid=book.price,  # Total book price
        payment_method=payment_method,
        payment_status=Purchase.PaymentStatus.PENDING,
        referred_by=referred_by,
        balance_used=balance_to_use
    )
    
    # Build URLs
    domain = request.build_absolute_uri('/').rstrip('/')
    success_url = f"{domain}/purchase/success/{purchase.id}/?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{domain}/books/{book.slug}/?cancelled=1"
    
    try:
        # Convert remaining XAF to EUR for Stripe
        XAF_TO_EUR_RATE = 655
        price_in_eur = float(amount_to_charge) / XAF_TO_EUR_RATE
        # Stripe uses cents, so multiply by 100 and round
        price_in_cents = int(round(price_in_eur * 100))
        
        # Create Stripe Checkout Session
        checkout_session = stripe.checkout.Session.create(
            customer_email=request.user.email,
            line_items=[{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {
                        'name': book.title,
                        'description': f"Remaining: {int(amount_to_charge):,} XAF (Balance used: {int(balance_to_use):,} XAF)" if balance_to_use > 0 else (f"{book.short_description[:100]}..." if book.short_description else f"Price: {int(book.price):,} XAF"),
                    },
                    'unit_amount': price_in_cents,  # EUR in cents
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                'purchase_id': str(purchase.id),
                'user_id': str(request.user.id),
                'book_id': str(book.id),
                'original_xaf_amount': str(book.price),
            }
        )
        
        # Store session ID
        purchase.payment_transaction_id = checkout_session.id
        purchase.save(update_fields=['payment_transaction_id'])
        
        # Redirect to Stripe
        return redirect(checkout_session.url)
        
    except stripe.error.StripeError as e:
        # Log error and show message
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Stripe error for purchase {purchase.id}: {str(e)}")
        
        purchase.payment_status = Purchase.PaymentStatus.FAILED
        purchase.save(update_fields=['payment_status'])
        
        messages.error(request, 'There was an error processing your payment. Please try again.')
        return redirect('core:book_detail', slug=book.slug)


@login_required
@never_cache
def purchase_success(request, purchase_id):
    """
    Handle successful payment return from Stripe.
    Verifies payment and creates library entry.
    """
    import stripe
    from ..models import Purchase
    from decimal import Decimal
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    import logging
    
    logger = logging.getLogger(__name__)
    
    purchase = get_object_or_404(Purchase, id=purchase_id, buyer=request.user)
    
    # If already completed, just show success
    if purchase.payment_status == Purchase.PaymentStatus.COMPLETED:
        context = {
            'purchase': purchase,
            'book': purchase.book,
            'already_processed': True,
        }
        return render(request, 'core/purchase_success.html', context)
    
    # Get session_id from URL
    session_id = request.GET.get('session_id')
    
    if not session_id:
        messages.error(request, 'Invalid payment session.')
        return redirect('core:book_detail', slug=purchase.book.slug)
    
    # Verify payment with Stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        
        if session.payment_status == 'paid':
            # Payment successful!
            logger.info(f"Payment verified for purchase {purchase.id}")
            
            # Update purchase record
            purchase.payment_status = Purchase.PaymentStatus.COMPLETED
            purchase.payment_transaction_id = session.payment_intent or session_id
            
            # Calculate commission based on book's effective rate
            # Uses custom per-book rate if set, otherwise global CommissionSettings
            amount = purchase.amount_paid
            commission_rate = purchase.book.get_effective_commission_rate()
            
            purchase.platform_commission = amount * commission_rate
            purchase.author_earning = amount - purchase.platform_commission
            purchase.save()
            
            # Process referral commission (deducted from author earning)
            process_referral_commission(purchase)
            
            # Update author's earnings balance (after recouping for upfront payments)
            author = purchase.book.author
            recouped = process_upfront_recouping(purchase, author)
            final_earning = purchase.author_earning - recouped
            author.earnings_balance += final_earning
            author.save(update_fields=['earnings_balance'])
            
            # Create library entry (check for duplicates)
            LibraryEntry.objects.get_or_create(
                user=request.user,
                book=purchase.book
            )
            
            # Increment book sales
            purchase.book.total_sales += 1
            purchase.book.save(update_fields=['total_sales'])
            
            # Send email receipt
            try:
                html_content = render_to_string('emails/purchase_receipt.html', {
                    'purchase': purchase,
                    'book': purchase.book,
                    'user': request.user,
                })
                send_mail(
                    subject=f'Your Xanula Purchase Receipt - {purchase.book.title}',
                    message=f'Thank you for purchasing {purchase.book.title}!',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[request.user.email],
                    html_message=html_content,
                    fail_silently=True,
                )
                logger.info(f"Receipt email sent for purchase {purchase.id}")
            except Exception as e:
                logger.error(f"Failed to send receipt email: {str(e)}")
            
            context = {
                'purchase': purchase,
                'book': purchase.book,
                'success': True,
            }
            return render(request, 'core/purchase_success.html', context)
        else:
            # Payment not completed
            logger.warning(f"Payment not completed for purchase {purchase.id}: {session.payment_status}")
            context = {
                'purchase': purchase,
                'book': purchase.book,
                'success': False,
                'error_message': 'Payment was not completed. Please try again.',
            }
            return render(request, 'core/purchase_success.html', context)
            
    except stripe.error.StripeError as e:
        logger.error(f"Stripe verification error for purchase {purchase.id}: {str(e)}")
        context = {
            'purchase': purchase,
            'book': purchase.book,
            'success': False,
            'error_message': 'Unable to verify payment. Please contact support if you were charged.',
        }
        return render(request, 'core/purchase_success.html', context)


@login_required
def purchase_history(request):
    """
    Display user's purchase history.
    """
    from ..models import Purchase
    from django.core.paginator import Paginator
    
    # Get filter
    status_filter = request.GET.get('status', 'all')
    
    # Base queryset
    purchases = Purchase.objects.filter(buyer=request.user).select_related('book', 'book__author')
    
    # Apply filter
    if status_filter == 'completed':
        purchases = purchases.filter(payment_status=Purchase.PaymentStatus.COMPLETED)
    elif status_filter == 'pending':
        purchases = purchases.filter(payment_status=Purchase.PaymentStatus.PENDING)
    elif status_filter == 'failed':
        purchases = purchases.filter(payment_status=Purchase.PaymentStatus.FAILED)
    
    # Paginate
    paginator = Paginator(purchases, 20)
    page = request.GET.get('page', 1)
    page_obj = paginator.get_page(page)
    
    # Status counts
    status_counts = {
        'all': Purchase.objects.filter(buyer=request.user).count(),
        'completed': Purchase.objects.filter(buyer=request.user, payment_status=Purchase.PaymentStatus.COMPLETED).count(),
        'pending': Purchase.objects.filter(buyer=request.user, payment_status=Purchase.PaymentStatus.PENDING).count(),
        'failed': Purchase.objects.filter(buyer=request.user, payment_status=Purchase.PaymentStatus.FAILED).count(),
    }
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'status_counts': status_counts,
    }
    return render(request, 'core/purchase_history.html', context)


# =============================================================================
# User Library Views
# Per Planning Document Section 7 (Library & Book Access)
# =============================================================================

@login_required
def user_library(request):
    """
    Display user's library of owned books with filtering and sorting.
    """
    from django.utils import timezone
    
    # Get all library entries for this user
    entries = LibraryEntry.objects.filter(user=request.user).select_related('book', 'book__author')
    
    # Get filter
    filter_type = request.GET.get('filter', 'all')
    
    if filter_type == 'ebook':
        # All books have ebook by default
        pass
    elif filter_type == 'audiobook':
        entries = entries.filter(book__audiobook_file__isnull=False).exclude(book__audiobook_file='')
    elif filter_type == 'in_progress':
        entries = entries.filter(completion_status=LibraryEntry.CompletionStatus.IN_PROGRESS)
    elif filter_type == 'completed':
        entries = entries.filter(completion_status=LibraryEntry.CompletionStatus.COMPLETED)
    
    # Get sort
    sort_by = request.GET.get('sort', 'last_accessed')
    
    if sort_by == 'date_added':
        entries = entries.order_by('-date_added')
    elif sort_by == 'title':
        entries = entries.order_by('book__title')
    else:  # last_accessed (default)
        entries = entries.order_by('-last_accessed', '-date_added')
    
    # Count for filters
    all_entries = LibraryEntry.objects.filter(user=request.user)
    filter_counts = {
        'all': all_entries.count(),
        'ebook': all_entries.count(),  # All books have ebook
        'audiobook': all_entries.filter(book__audiobook_file__isnull=False).exclude(book__audiobook_file='').count(),
        'in_progress': all_entries.filter(completion_status=LibraryEntry.CompletionStatus.IN_PROGRESS).count(),
        'completed': all_entries.filter(completion_status=LibraryEntry.CompletionStatus.COMPLETED).count(),
    }
    
    context = {
        'entries': entries,
        'filter_type': filter_type,
        'sort_by': sort_by,
        'filter_counts': filter_counts,
    }
    return render(request, 'core/library.html', context)


@login_required
def toggle_download_status(request, entry_id):
    """
    Toggle download status for a library entry.
    """
    if request.method == 'POST':
        entry = get_object_or_404(LibraryEntry, id=entry_id, user=request.user)
        
        if entry.download_status == LibraryEntry.DownloadStatus.DOWNLOADED:
            entry.download_status = LibraryEntry.DownloadStatus.NOT_DOWNLOADED
            messages.success(request, f'"{entry.book.title}" removed from offline storage.')
        else:
            entry.download_status = LibraryEntry.DownloadStatus.DOWNLOADED
            messages.success(request, f'"{entry.book.title}" saved for offline reading.')
        
        entry.save(update_fields=['download_status'])
    
    return redirect('core:library')


@login_required
def update_reading_progress(request, entry_id):
    """
    Update reading/listening progress for a library entry.
    """
    from django.utils import timezone
    from django.http import JsonResponse
    
    if request.method == 'POST':
        entry = get_object_or_404(LibraryEntry, id=entry_id, user=request.user)
        
        reading_progress = request.POST.get('reading_progress')
        listening_progress = request.POST.get('listening_progress')
        
        if reading_progress:
            entry.reading_progress = int(reading_progress)
        if listening_progress:
            entry.listening_progress = int(listening_progress)
        
        # Update last accessed
        entry.last_accessed = timezone.now()
        
        # Auto-update completion status
        if entry.reading_progress > 0 or entry.listening_progress > 0:
            if entry.completion_status == LibraryEntry.CompletionStatus.NOT_STARTED:
                entry.completion_status = LibraryEntry.CompletionStatus.IN_PROGRESS
        
        entry.save()
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def access_book(request, entry_id):
    """
    Access a book for reading/listening. Updates last_accessed.
    """
    from django.utils import timezone
    
    entry = get_object_or_404(LibraryEntry, id=entry_id, user=request.user)
    
    # Update last accessed
    entry.last_accessed = timezone.now()
    
    # Mark as in progress if not started
    if entry.completion_status == LibraryEntry.CompletionStatus.NOT_STARTED:
        entry.completion_status = LibraryEntry.CompletionStatus.IN_PROGRESS
    
    entry.save(update_fields=['last_accessed', 'completion_status'])
    
    # Redirect to the reader
    return redirect('core:book_reader', slug=entry.book.slug)


@login_required
def book_reader(request, slug):
    """
    Ebook reader page using epub.js.
    Per Architecture Document Section 10 (Ebook Reading System).
    """
    from django.utils import timezone
    
    book = get_object_or_404(Book, slug=slug)
    
    # Check if user owns this book
    try:
        entry = LibraryEntry.objects.get(user=request.user, book=book)
    except LibraryEntry.DoesNotExist:
        messages.error(request, 'You need to purchase this book first.')
        return redirect('core:book_detail', slug=slug)
    
    # Update last accessed
    entry.last_accessed = timezone.now()
    if entry.completion_status == LibraryEntry.CompletionStatus.NOT_STARTED:
        entry.completion_status = LibraryEntry.CompletionStatus.IN_PROGRESS
    entry.save(update_fields=['last_accessed', 'completion_status'])
    
    # Get ebook file URL
    ebook_url = None
    if book.ebook_file:
        ebook_url = book.ebook_file.url
    
    context = {
        'book': book,
        'entry': entry,
        'ebook_url': ebook_url,
        'reading_progress': entry.reading_progress,
    }
    return render(request, 'core/reader.html', context)


@login_required
def update_reading_progress_api(request):
    """
    API endpoint to update reading progress.
    Called via AJAX every 30 seconds during reading.
    """
    from django.http import JsonResponse
    from django.utils import timezone
    import json
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    # Verify AJAX request
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    try:
        data = json.loads(request.body)
        book_id = data.get('book_id')
        current_page = data.get('current_page', 0)
        total_pages = data.get('total_pages', 0)
        current_cfi = data.get('current_cfi', '')  # epub.js location
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    if not book_id:
        return JsonResponse({'error': 'book_id required'}, status=400)
    
    # Get library entry
    try:
        entry = LibraryEntry.objects.get(user=request.user, book_id=book_id)
    except LibraryEntry.DoesNotExist:
        return JsonResponse({'error': 'Book not in library'}, status=404)
    
    # Update progress
    entry.reading_progress = current_page
    entry.last_accessed = timezone.now()
    
    # Calculate completion status
    if total_pages > 0:
        progress_percent = (current_page / total_pages) * 100
        if progress_percent >= 98:  # Consider 98%+ as completed
            entry.completion_status = LibraryEntry.CompletionStatus.COMPLETED
        elif current_page > 0:
            entry.completion_status = LibraryEntry.CompletionStatus.IN_PROGRESS
    
    entry.save()
    
    return JsonResponse({
        'success': True,
        'progress': entry.reading_progress,
        'status': entry.completion_status,
    })


# =============================================================================
# Audiobook Player Views
# Per Architecture Document Section 11 (Audiobook Playback System)
# =============================================================================

@login_required
def audiobook_player(request, slug):
    """
    Audiobook player page using HTML5 audio.
    Per Architecture Document Section 11 and Planning Document Section 9.
    """
    from django.utils import timezone
    
    book = get_object_or_404(Book, slug=slug)
    
    # Check if user owns this book
    try:
        entry = LibraryEntry.objects.get(user=request.user, book=book)
    except LibraryEntry.DoesNotExist:
        messages.error(request, 'You need to purchase this book first.')
        return redirect('core:book_detail', slug=slug)
    
    # Check if audiobook exists
    if not book.audiobook_file:
        messages.error(request, 'This book does not have an audiobook version.')
        return redirect('core:library')
    
    # Update last accessed
    entry.last_accessed = timezone.now()
    if entry.completion_status == LibraryEntry.CompletionStatus.NOT_STARTED:
        entry.completion_status = LibraryEntry.CompletionStatus.IN_PROGRESS
    entry.save(update_fields=['last_accessed', 'completion_status'])
    
    # Get audiobook file URL
    audiobook_url = book.audiobook_file.url
    
    # Get cover image URL
    cover_url = book.cover_image.url if book.cover_image else None
    
    context = {
        'book': book,
        'entry': entry,
        'audiobook_url': audiobook_url,
        'cover_url': cover_url,
        'listening_progress': entry.listening_progress,
    }
    return render(request, 'core/audiobook_player.html', context)


@login_required
def update_listening_progress_api(request):
    """
    API endpoint to update listening progress.
    Called via AJAX every 30 seconds during playback.
    Per Architecture Document Section 11.
    """
    from django.utils import timezone
    import json
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    # Verify AJAX request
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    try:
        data = json.loads(request.body)
        book_id = data.get('book_id')
        current_time = data.get('current_time', 0)  # in seconds
        total_duration = data.get('total_duration', 0)  # in seconds
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    if not book_id:
        return JsonResponse({'error': 'book_id required'}, status=400)
    
    # Get library entry
    try:
        entry = LibraryEntry.objects.get(user=request.user, book_id=book_id)
    except LibraryEntry.DoesNotExist:
        return JsonResponse({'error': 'Book not in library'}, status=404)
    
    # Update progress (store as integer seconds)
    entry.listening_progress = int(current_time)
    entry.last_accessed = timezone.now()
    
    # Calculate completion status
    if total_duration > 0:
        progress_percent = (current_time / total_duration) * 100
        if progress_percent >= 98:  # Consider 98%+ as completed
            entry.completion_status = LibraryEntry.CompletionStatus.COMPLETED
        elif current_time > 0:
            entry.completion_status = LibraryEntry.CompletionStatus.IN_PROGRESS
    
    entry.save()
    
    return JsonResponse({
        'success': True,
        'progress': entry.listening_progress,
        'status': entry.completion_status,
    })


# =============================================================================
# Fapshi Mobile Money Payment Views
# Per Architecture Document Section 9 (Payment Processing)
# =============================================================================

@login_required
def create_fapshi_checkout(request, book_id):
    """
    Create Fapshi mobile money payment and redirect to Fapshi.
    """
    from ..models import Purchase
    from .. import fapshi_utils
    from users.models import User
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Require POST
    if request.method != 'POST':
        return redirect('core:book_detail', slug=get_object_or_404(Book, id=book_id).slug)
    
    book = get_object_or_404(Book, id=book_id)
    
    # Anti-duplicate check
    if LibraryEntry.objects.filter(user=request.user, book=book).exists():
        messages.info(request, 'You already own this book!')
        return redirect('core:my_books')
    
    # Check if book is free (shouldn't reach here but safety check)
    if book.is_free:
        return redirect('core:initiate_purchase', slug=book.slug)
    
    # Check for referral code
    referral_code = request.POST.get('referral_code', '').strip().upper()
    referred_by = None
    
    if referral_code:
        try:
            referrer = User.objects.get(referral_code=referral_code)
            # Validate: not self-referral
            if referrer != request.user:
                referred_by = referrer
            else:
                messages.warning(request, 'You cannot use your own referral code.')
        except User.DoesNotExist:
            messages.warning(request, 'Invalid referral code.')
    
    # Check if user wants to use balance for partial payment
    use_balance = request.POST.get('use_balance') == 'on'
    balance_to_use = Decimal('0.00')
    amount_to_charge = book.price
    
    if use_balance and request.user.earnings_balance > 0:
        balance_to_use = min(request.user.earnings_balance, book.price)
        amount_to_charge = book.price - balance_to_use
        
        # Deduct balance immediately
        request.user.earnings_balance -= balance_to_use
        request.user.save(update_fields=['earnings_balance'])
    
    # Determine payment method
    payment_method = Purchase.PaymentMethod.PARTIAL if balance_to_use > 0 else Purchase.PaymentMethod.FAPSHI
    
    # Create pending purchase record
    purchase = Purchase.objects.create(
        buyer=request.user,
        book=book,
        amount_paid=book.price,  # Total book price
        payment_method=payment_method,
        payment_status=Purchase.PaymentStatus.PENDING,
        referred_by=referred_by,
        balance_used=balance_to_use
    )
    
    # Build return URL
    domain = request.build_absolute_uri('/').rstrip('/')
    return_url = f"{domain}/purchase/fapshi/return/{purchase.id}/"
    
    # Call Fapshi API with remaining amount (after balance deduction)
    result = fapshi_utils.create_payment(
        amount=int(amount_to_charge),
        email=request.user.email,
        redirect_url=return_url,
        user_id=str(request.user.id),
        external_id=str(purchase.id),
        message=f"Purchase: {book.title}"
    )
    
    if result['success']:
        # Save transaction ID
        purchase.payment_transaction_id = result['trans_id']
        purchase.save(update_fields=['payment_transaction_id'])
        
        logger.info(f"Fapshi checkout created for purchase {purchase.id}, redirecting to {result['link']}")
        
        # Redirect to Fapshi payment page
        return redirect(result['link'])
    else:
        # API error
        logger.error(f"Fapshi checkout failed for purchase {purchase.id}: {result.get('error')}")
        
        purchase.payment_status = Purchase.PaymentStatus.FAILED
        purchase.save(update_fields=['payment_status'])
        
        messages.error(
            request, 
            'Mobile money payment is temporarily unavailable. Please try card payment.'
        )
        return redirect('core:initiate_purchase', slug=book.slug)


@login_required
@never_cache
def fapshi_return(request, purchase_id):
    """
    Handle return from Fapshi after payment attempt.
    Verifies payment and creates library entry.
    """
    from ..models import Purchase
    from .. import fapshi_utils
    from decimal import Decimal
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    import logging
    
    logger = logging.getLogger(__name__)
    
    purchase = get_object_or_404(Purchase, id=purchase_id, buyer=request.user)
    
    # If already completed, just show success
    if purchase.payment_status == Purchase.PaymentStatus.COMPLETED:
        context = {
            'purchase': purchase,
            'book': purchase.book,
            'success': True,
            'already_processed': True,
        }
        return render(request, 'core/purchase_success.html', context)
    
    # Check payment status with Fapshi
    trans_id = purchase.payment_transaction_id
    
    if not trans_id:
        logger.error(f"No transaction ID for purchase {purchase_id}")
        context = {
            'purchase': purchase,
            'book': purchase.book,
            'success': False,
            'error_message': 'Payment reference not found. Please try again.',
        }
        return render(request, 'core/purchase_success.html', context)
    
    # Query Fapshi for status
    result = fapshi_utils.check_payment_status(trans_id)
    
    if result['success']:
        status = result['status']
        logger.info(f"Fapshi status for purchase {purchase_id}: {status}")
        
        if fapshi_utils.is_payment_successful(status):
            # Payment successful!
            purchase.payment_status = Purchase.PaymentStatus.COMPLETED
            
            # Calculate commission based on book format
            amount = purchase.amount_paid
            if purchase.book.has_audiobook:
                commission_rate = Decimal('0.30')
            else:
                commission_rate = Decimal('0.10')
            
            purchase.platform_commission = amount * commission_rate
            purchase.author_earning = amount - purchase.platform_commission
            purchase.save()
            
            # Process referral commission (deducted from author earning)
            process_referral_commission(purchase)
            
            # Update author's earnings balance (after recouping for upfront payments)
            author = purchase.book.author
            recouped = process_upfront_recouping(purchase, author)
            final_earning = purchase.author_earning - recouped
            author.earnings_balance += final_earning
            author.save(update_fields=['earnings_balance'])
            
            # Create library entry
            LibraryEntry.objects.get_or_create(
                user=request.user,
                book=purchase.book
            )
            
            # Increment book sales
            purchase.book.total_sales += 1
            purchase.book.save(update_fields=['total_sales'])
            
            # Send email receipt
            try:
                html_content = render_to_string('emails/purchase_receipt.html', {
                    'purchase': purchase,
                    'book': purchase.book,
                    'user': request.user,
                })
                send_mail(
                    subject=f'Your Xanula Purchase Receipt - {purchase.book.title}',
                    message=f'Thank you for purchasing {purchase.book.title}!',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[request.user.email],
                    html_message=html_content,
                    fail_silently=True,
                )
            except Exception as e:
                logger.error(f"Failed to send receipt email: {str(e)}")
            
            context = {
                'purchase': purchase,
                'book': purchase.book,
                'success': True,
            }
            return render(request, 'core/purchase_success.html', context)
            
        elif fapshi_utils.is_payment_pending(status):
            # Payment still pending - show polling page
            context = {
                'purchase': purchase,
                'book': purchase.book,
                'pending': True,
            }
            return render(request, 'core/fapshi_pending.html', context)
            
        else:
            # Payment failed or expired
            purchase.payment_status = Purchase.PaymentStatus.FAILED
            purchase.save(update_fields=['payment_status'])
            
            context = {
                'purchase': purchase,
                'book': purchase.book,
                'success': False,
                'error_message': 'Payment was not completed. Please try again.',
            }
            return render(request, 'core/purchase_success.html', context)
    else:
        # Could not check status
        logger.error(f"Fapshi status check failed for purchase {purchase_id}: {result.get('error')}")
        context = {
            'purchase': purchase,
            'book': purchase.book,
            'pending': True,  # Show pending page with polling
        }
        return render(request, 'core/fapshi_pending.html', context)


@login_required
def check_purchase_status_api(request, purchase_id):
    """
    API endpoint for polling purchase status (used by Fapshi pending page).
    """
    from ..models import Purchase
    from .. import fapshi_utils
    from django.http import JsonResponse
    from decimal import Decimal
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Verify this is an AJAX request
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    # Get and verify purchase
    try:
        purchase = Purchase.objects.get(id=purchase_id, buyer=request.user)
    except Purchase.DoesNotExist:
        return JsonResponse({'error': 'Purchase not found'}, status=404)
    
    # If already completed or failed, return immediately
    if purchase.payment_status == Purchase.PaymentStatus.COMPLETED:
        return JsonResponse({
            'status': 'completed',
            'message': 'Payment successful!',
            'redirect_url': '/my-books/',
        })
    elif purchase.payment_status == Purchase.PaymentStatus.FAILED:
        return JsonResponse({
            'status': 'failed',
            'message': 'Payment failed.',
        })
    
    # Check with Fapshi
    if not purchase.payment_transaction_id:
        return JsonResponse({
            'status': 'error',
            'message': 'No transaction reference.',
        })
    
    result = fapshi_utils.check_payment_status(purchase.payment_transaction_id)
    
    if result['success']:
        status = result['status']
        
        if fapshi_utils.is_payment_successful(status):
            # Process the payment
            purchase.payment_status = Purchase.PaymentStatus.COMPLETED
            
            amount = purchase.amount_paid
            if purchase.book.has_audiobook:
                commission_rate = Decimal('0.30')
            else:
                commission_rate = Decimal('0.10')
            
            purchase.platform_commission = amount * commission_rate
            purchase.author_earning = amount - purchase.platform_commission
            purchase.save()
            
            # Update author earnings (after recouping for upfront payments)
            author = purchase.book.author
            recouped = process_upfront_recouping(purchase, author)
            final_earning = purchase.author_earning - recouped
            author.earnings_balance += final_earning
            author.save(update_fields=['earnings_balance'])
            
            # Create library entry
            LibraryEntry.objects.get_or_create(
                user=request.user,
                book=purchase.book
            )
            
            # Increment sales
            purchase.book.total_sales += 1
            purchase.book.save(update_fields=['total_sales'])
            
            return JsonResponse({
                'status': 'completed',
                'message': 'Payment successful!',
                'redirect_url': '/my-books/',
            })
            
        elif fapshi_utils.is_payment_pending(status):
            return JsonResponse({
                'status': 'pending',
                'message': 'Payment is being processed...',
            })
        else:
            purchase.payment_status = Purchase.PaymentStatus.FAILED
            purchase.save(update_fields=['payment_status'])
            return JsonResponse({
                'status': 'failed',
                'message': 'Payment failed or expired.',
            })
    else:
        return JsonResponse({
            'status': 'pending',
            'message': 'Checking payment status...',
        })


# =============================================================================
# PWA / Offline Views
# Per Planning Document Section 7 and Architecture Document Section 12
# =============================================================================

def offline_page(request):
    """
    Offline fallback page for service worker.
    """
    return render(request, 'core/offline.html')


@login_required
def download_book_api(request, book_id):
    """
    API endpoint for PWA to get book file URLs for caching.
    Returns URLs that the service worker can cache for offline use.
    """
    book = get_object_or_404(Book, id=book_id)
    
    # Verify user owns the book
    entry = LibraryEntry.objects.filter(user=request.user, book=book).first()
    if not entry:
        return JsonResponse({'error': 'You do not own this book.'}, status=403)
    
    # Build file URLs
    files = {}
    
    if book.ebook_file:
        files['ebook_url'] = book.ebook_file.url
        try:
            files['ebook_size'] = book.ebook_file.size
        except:
            files['ebook_size'] = 0
    
    if book.audiobook_file:
        files['audiobook_url'] = book.audiobook_file.url
        try:
            files['audiobook_size'] = book.audiobook_file.size
        except:
            files['audiobook_size'] = 0
    
    if book.cover_image:
        files['cover_url'] = book.cover_image.url
    
    # Update download status
    entry.download_status = LibraryEntry.DownloadStatus.DOWNLOADED
    entry.save(update_fields=['download_status'])
    
    return JsonResponse({
        'success': True,
        'book_id': book.id,
        'book_title': book.title,
        'files': files,
        'message': 'Book ready for offline use'
    })


@login_required
@require_POST
def remove_download_api(request, book_id):
    """
    API endpoint to mark book as not downloaded (after service worker clears cache).
    """
    book = get_object_or_404(Book, id=book_id)
    
    # Verify user owns the book
    entry = LibraryEntry.objects.filter(user=request.user, book=book).first()
    if not entry:
        return JsonResponse({'error': 'You do not own this book.'}, status=403)
    
    # Update download status
    entry.download_status = LibraryEntry.DownloadStatus.NOT_DOWNLOADED
    entry.save(update_fields=['download_status'])
    
    # Build file URLs for service worker to remove from cache
    files = {}
    if book.ebook_file:
        files['ebook_url'] = book.ebook_file.url
    if book.audiobook_file:
        files['audiobook_url'] = book.audiobook_file.url
    if book.cover_image:
        files['cover_url'] = book.cover_image.url
    
    return JsonResponse({
        'success': True,
        'book_id': book.id,
        'files': files,
        'message': 'Download removed'
    })


# =============================================================================
# User Settings Views
# =============================================================================

@login_required
def user_settings(request):
    """
    User profile settings page.
    """
    user = request.user
    
    if request.method == 'POST':
        # Handle profile update
        user.first_name = request.POST.get('first_name', '').strip()
        user.last_name = request.POST.get('last_name', '').strip()
        user.bio = request.POST.get('bio', '').strip()[:500]
        
        # Handle profile picture
        if 'profile_picture' in request.FILES:
            user.profile_picture = request.FILES['profile_picture']
        
        user.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('core:user_settings')
    
    context = {
        'user': user,
        'referral_percent': ReferralSettings.get_referral_percent(),
    }
    return render(request, 'core/settings.html', context)


@login_required
@require_POST
def notification_settings(request):
    """
    Update notification preferences.
    """
    import json
    user = request.user
    
    try:
        data = json.loads(request.body)
        user.email_notifications = data.get('email_notifications', True)
        user.reading_reminders = data.get('reading_reminders', True)
        user.save(update_fields=['email_notifications', 'reading_reminders'])
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# =============================================================================
# Book Preview View
# =============================================================================

def book_preview(request, slug):
    """
    Preview first 10% of a book (for non-owners).
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
    
    # Check if user already owns the book
    user_owns_book = False
    if request.user.is_authenticated:
        user_owns_book = LibraryEntry.objects.filter(
            user=request.user, book=book
        ).exists()
    
    context = {
        'book': book,
        'user_owns_book': user_owns_book,
        'preview_mode': True,
        'preview_percent': 10,
    }
    return render(request, 'core/book_preview.html', context)


# =============================================================================
# Book Embed Widget (for external websites)
# =============================================================================

from django.views.decorators.clickjacking import xframe_options_exempt

@xframe_options_exempt
def book_embed(request, slug):
    """
    Embeddable widget for external websites.
    Returns a minimal page with book cover, title, price, and buy button.
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
    
    # Build the absolute URL for the book detail page and site base
    book_url = request.build_absolute_uri(book.get_absolute_url())
    base_url = request.build_absolute_uri('/').rstrip('/')
    
    context = {
        'book': book,
        'book_url': book_url,
        'base_url': base_url,
    }
    return render(request, 'core/book_embed.html', context)


# =============================================================================
# Author Analytics Dashboard
# =============================================================================

@login_required
def author_analytics(request):
    """
    Author analytics dashboard with sales charts, earnings data, and reading engagement stats.
    """
    from ..models import Purchase
    from django.db.models import Sum, Count, Q
    from django.db.models.functions import TruncDate, TruncMonth
    from datetime import datetime, timedelta
    
    user = request.user
    
    # Get author's books
    author_books = Book.objects.filter(author=user)
    
    if not author_books.exists():
        messages.info(request, 'You haven\'t published any books yet.')
        return redirect('core:my_books')
    
    # Get book IDs for efficient queries
    book_ids = list(author_books.values_list('id', flat=True))
    
    # ===== SALES STATS =====
    total_sales = author_books.aggregate(total=Sum('total_sales'))['total'] or 0
    total_earnings = user.earnings_balance
    total_reviews = Review.objects.filter(book__author=user).count()
    
    # ===== READING ENGAGEMENT STATS =====
    # Total unique readers (users with author's books in library)
    total_readers = LibraryEntry.objects.filter(book_id__in=book_ids).values('user').distinct().count()
    
    # Active readers (accessed in last 7 days)
    seven_days_ago = datetime.now() - timedelta(days=7)
    active_readers = LibraryEntry.objects.filter(
        book_id__in=book_ids,
        last_accessed__gte=seven_days_ago
    ).values('user').distinct().count()
    
    # Completion rate (% of library entries that are completed)
    total_entries = LibraryEntry.objects.filter(book_id__in=book_ids).count()
    completed_entries = LibraryEntry.objects.filter(
        book_id__in=book_ids,
        completion_status=LibraryEntry.CompletionStatus.COMPLETED
    ).count()
    completion_rate = round((completed_entries / total_entries * 100) if total_entries > 0 else 0, 1)
    
    # In-progress readers
    in_progress_count = LibraryEntry.objects.filter(
        book_id__in=book_ids,
        completion_status=LibraryEntry.CompletionStatus.IN_PROGRESS
    ).count()
    
    # Get purchases for the last 30 days
    thirty_days_ago = datetime.now() - timedelta(days=30)
    recent_purchases = Purchase.objects.filter(
        book__author=user,
        payment_status=Purchase.PaymentStatus.COMPLETED,
        purchase_date__gte=thirty_days_ago
    ).select_related('book', 'buyer')
    
    # Book performance (sales + reading)
    book_performance = []
    for book in author_books:
        # Reading stats for this book
        book_entries = LibraryEntry.objects.filter(book=book)
        readers = book_entries.count()
        completed = book_entries.filter(completion_status=LibraryEntry.CompletionStatus.COMPLETED).count()
        in_progress = book_entries.filter(completion_status=LibraryEntry.CompletionStatus.IN_PROGRESS).count()
        
        book_performance.append({
            'id': book.id,
            'title': book.title,
            'sales': book.total_sales,
            'rating': float(book.average_rating),
            'reviews': book.reviews.filter(is_visible=True).count(),
            'earnings': Purchase.objects.filter(
                book=book,
                payment_status=Purchase.PaymentStatus.COMPLETED
            ).aggregate(total=Sum('author_earning'))['total'] or 0,
            # Reading stats
            'readers': readers,
            'completed': completed,
            'in_progress': in_progress,
            'completion_rate': round((completed / readers * 100) if readers > 0 else 0, 1),
        })
    
    # Sort by readers (most read first)
    book_performance.sort(key=lambda x: x['readers'], reverse=True)
    
    context = {
        # Sales stats
        'total_sales': total_sales,
        'total_earnings': total_earnings,
        'total_reviews': total_reviews,
        'book_count': author_books.count(),
        'recent_purchases': recent_purchases[:10],
        'book_performance': book_performance,
        # Reading engagement stats
        'total_readers': total_readers,
        'active_readers': active_readers,
        'completion_rate': completion_rate,
        'in_progress_count': in_progress_count,
    }
    return render(request, 'core/author_analytics.html', context)


@login_required
def analytics_data_api(request):
    """
    API endpoint for analytics chart data.
    Returns daily sales and reading activity for the last 30 days.
    """
    from ..models import Purchase
    from django.db.models import Count, Sum
    from django.db.models.functions import TruncDate
    from datetime import datetime, timedelta
    import json
    
    user = request.user
    thirty_days_ago = datetime.now() - timedelta(days=30)
    
    # Get author's book IDs
    book_ids = list(Book.objects.filter(author=user).values_list('id', flat=True))
    
    # Daily sales
    daily_sales = Purchase.objects.filter(
        book__author=user,
        payment_status=Purchase.PaymentStatus.COMPLETED,
        purchase_date__gte=thirty_days_ago
    ).annotate(
        date=TruncDate('purchase_date')
    ).values('date').annotate(
        count=Count('id'),
        earnings=Sum('author_earning')
    ).order_by('date')
    
    # Daily reading activity (unique users who accessed books)
    daily_readers = LibraryEntry.objects.filter(
        book_id__in=book_ids,
        last_accessed__gte=thirty_days_ago
    ).annotate(
        date=TruncDate('last_accessed')
    ).values('date').annotate(
        readers=Count('user', distinct=True)
    ).order_by('date')
    
    # Format for Chart.js
    labels = []
    sales_data = []
    earnings_data = []
    readers_data = []
    
    # Fill in all dates (including zeros)
    current = thirty_days_ago.date()
    end = datetime.now().date()
    sales_by_date = {s['date']: s for s in daily_sales}
    readers_by_date = {r['date']: r for r in daily_readers}
    
    while current <= end:
        labels.append(current.strftime('%b %d'))
        if current in sales_by_date:
            sales_data.append(sales_by_date[current]['count'])
            earnings_data.append(float(sales_by_date[current]['earnings'] or 0))
        else:
            sales_data.append(0)
            earnings_data.append(0)
        
        if current in readers_by_date:
            readers_data.append(readers_by_date[current]['readers'])
        else:
            readers_data.append(0)
        
        current += timedelta(days=1)
    
    return JsonResponse({
        'labels': labels,
        'sales': sales_data,
        'earnings': earnings_data,
        'readers': readers_data,
    })


# =============================================================================
# Hard Copy Request View
# =============================================================================

@login_required
def request_hard_copy(request, book_id):
    """
    Handle hard copy book request from library.
    Users can request physical copies of books they own.
    """
    from ..models import HardCopyRequest
    from django_q.tasks import async_task
    
    book = get_object_or_404(Book, id=book_id)
    
    # Verify user owns the book
    entry = LibraryEntry.objects.filter(user=request.user, book=book).first()
    if not entry:
        messages.error(request, 'You do not own this book.')
        return redirect('core:library')
    
    # Check for existing pending request
    existing_request = HardCopyRequest.objects.filter(
        user=request.user,
        book=book,
        status__in=[
            HardCopyRequest.Status.REQUESTED,
            HardCopyRequest.Status.PROCESSING,
            HardCopyRequest.Status.SHIPPED
        ]
    ).first()
    
    if existing_request:
        messages.info(request, f'You already have a pending request for "{book.title}". Status: {existing_request.get_status_display()}')
        return redirect('core:library')
    
    if request.method == 'POST':
        # Create the request
        hard_copy_request = HardCopyRequest.objects.create(
            user=request.user,
            book=book,
            full_name=request.POST.get('full_name', '').strip(),
            phone_number=request.POST.get('phone_number', '').strip(),
            shipping_address=request.POST.get('shipping_address', '').strip(),
            city=request.POST.get('city', '').strip(),
            additional_notes=request.POST.get('additional_notes', '').strip(),
        )
        
        # Queue async email notifications to admin and author
        try:
            async_task(
                'core.tasks.send_hard_copy_request_notification',
                hard_copy_request.id,
                task_name=f'hardcopy_notification_{hard_copy_request.id}',
            )
        except Exception as e:
            # Email notification failed, but request is still created
            pass
        
        messages.success(request, f'Your request for a hard copy of "{book.title}" has been submitted! We will contact you soon.')
        return redirect('core:library')
    
    # Pre-fill with user info
    context = {
        'book': book,
        'entry': entry,
        'user': request.user,
    }
    return render(request, 'core/request_hardcopy.html', context)


def terms_page(request):
    """Terms and Conditions page."""
    return render(request, 'core/terms.html')


def privacy_page(request):
    """Privacy Policy page."""
    return render(request, 'core/privacy.html')


def legal_page(request):
    """Legal Notice page."""
    return render(request, 'core/legal.html')


# ===== UPFRONT PAYMENT VIEWS =====

@login_required
def upfront_applications_list(request):
    """
    List all upfront payment applications for the logged-in author.
    """
    applications = UpfrontPaymentApplication.objects.filter(
        author=request.user
    ).select_related('book').order_by('-created_at')
    
    context = {
        'applications': applications,
    }
    return render(request, 'core/upfront_applications.html', context)


@login_required
def apply_upfront_payment(request):
    """
    Apply for an upfront payment (advance) on a book.
    """
    # Get author's books that are approved/ready
    author_books = Book.objects.filter(
        author=request.user,
        status__in=[Book.Status.APPROVED, Book.Status.EBOOK_READY, 
                    Book.Status.AUDIOBOOK_GENERATED, Book.Status.COMPLETED]
    ).order_by('title')
    
    if not author_books.exists():
        messages.warning(request, 'You need at least one published book to apply for upfront payment.')
        return redirect('core:my_books')
    
    # Check for existing pending application
    existing_pending = UpfrontPaymentApplication.objects.filter(
        author=request.user,
        status=UpfrontPaymentApplication.Status.IN_REVIEW
    ).exists()
    
    if existing_pending:
        messages.warning(request, 'You already have a pending application. Please wait for it to be reviewed.')
        return redirect('core:upfront_applications')
    
    if request.method == 'POST':
        book_id = request.POST.get('book_id')
        amount = request.POST.get('amount')
        reason = request.POST.get('reason', '').strip()
        terms_accepted = request.POST.get('terms_accepted') == 'on'
        
        if not terms_accepted:
            messages.error(request, 'You must accept the terms and conditions.')
            return redirect('core:apply_upfront_payment')
        
        try:
            amount = Decimal(amount)
            if amount < 1000:
                messages.error(request, 'Minimum amount is 1,000 XAF.')
                return redirect('core:apply_upfront_payment')
        except:
            messages.error(request, 'Invalid amount.')
            return redirect('core:apply_upfront_payment')
        
        # Get book if specified
        book = None
        if book_id and book_id != 'all':
            book = get_object_or_404(Book, id=book_id, author=request.user)
        
        # Create application
        application = UpfrontPaymentApplication.objects.create(
            author=request.user,
            book=book,
            amount_requested=amount,
            reason=reason,
            terms_accepted=True,
        )
        
        messages.success(request, 'Your upfront payment application has been submitted and is now under review.')
        return redirect('core:upfront_applications')
    
    context = {
        'author_books': author_books,
    }
    return render(request, 'core/upfront_apply.html', context)


@login_required
@require_POST
def cancel_upfront_application(request, application_id):
    """
    Cancel an upfront payment application (only if still in review).
    """
    application = get_object_or_404(
        UpfrontPaymentApplication,
        id=application_id,
        author=request.user
    )
    
    if application.status != UpfrontPaymentApplication.Status.IN_REVIEW:
        messages.error(request, 'Only pending applications can be cancelled.')
        return redirect('core:upfront_applications')
    
    application.status = UpfrontPaymentApplication.Status.CANCELLED
    application.save()
    
    messages.success(request, 'Your application has been cancelled.')
    return redirect('core:upfront_applications')


def upfront_terms_content(request):
    """
    Return the terms and conditions content for upfront payments.
    Used by the modal popup.
    """
    return render(request, 'core/upfront_terms_content.html')


# Import Decimal for upfront payment amount handling
from decimal import Decimal


# ===== DONATION / SUPPORT ME VIEWS =====

@login_required
def support_author(request, author_id, book_id=None):
    """
    Display the support/donation form for an author.
    """
    from users.models import User
    
    author = get_object_or_404(User, id=author_id)
    book = None
    if book_id:
        book = get_object_or_404(Book, id=book_id)
    
    # Can't donate to yourself
    if author == request.user:
        messages.error(request, "You cannot support yourself.")
        return redirect('core:library')
    
    if request.method == 'POST':
        amount = request.POST.get('amount')
        message = request.POST.get('message', '')
        payment_method = request.POST.get('payment_method', 'fapshi')
        terms_accepted = request.POST.get('terms_accepted') == 'on'
        
        # Validation
        if not terms_accepted:
            messages.error(request, 'You must accept the terms and conditions.')
            return render(request, 'core/support_author.html', {
                'author': author,
                'book': book,
            })
        
        try:
            amount = Decimal(amount)
            if amount < 500:
                messages.error(request, 'Minimum donation is 500 XAF.')
                return render(request, 'core/support_author.html', {
                    'author': author,
                    'book': book,
                })
            if amount > 327500:
                messages.error(request, 'Maximum donation is 327,500 XAF (~500 EUR).')
                return render(request, 'core/support_author.html', {
                    'author': author,
                    'book': book,
                })
        except (ValueError, TypeError):
            messages.error(request, 'Invalid amount.')
            return render(request, 'core/support_author.html', {
                'author': author,
                'book': book,
            })
        
        # Create donation record
        donation = Donation.objects.create(
            donor=request.user,
            recipient=author,
            book=book,
            amount=amount,
            message=message,
            terms_accepted=True,
            payment_method=Donation.PaymentMethod.STRIPE if payment_method == 'stripe' else Donation.PaymentMethod.FAPSHI,
        )
        
        # Redirect to payment
        if payment_method == 'stripe':
            return redirect('core:donation_stripe_payment', donation_id=donation.id)
        else:
            return redirect('core:donation_fapshi_payment', donation_id=donation.id)
    
    return render(request, 'core/support_author.html', {
        'author': author,
        'book': book,
    })


@login_required
def donation_stripe_payment(request, donation_id):
    """Handle Stripe checkout for donation."""
    import stripe
    
    donation = get_object_or_404(Donation, id=donation_id, donor=request.user)
    
    if donation.payment_status != Donation.PaymentStatus.PENDING:
        messages.error(request, 'This donation has already been processed.')
        return redirect('core:library')
    
    stripe.api_key = settings.STRIPE_SECRET_KEY
    
    # Build URLs
    domain = request.build_absolute_uri('/').rstrip('/')
    success_url = f"{domain}/support/success/{donation.id}/?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{domain}/library/?cancelled=1"
    
    try:
        # Convert XAF to EUR
        XAF_TO_EUR_RATE = 655
        price_in_eur = float(donation.amount) / XAF_TO_EUR_RATE
        price_in_cents = int(round(price_in_eur * 100))
        
        checkout_session = stripe.checkout.Session.create(
            customer_email=request.user.email,
            line_items=[{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {
                        'name': f"Support {donation.recipient.get_display_name()}",
                        'description': f"Donation of {int(donation.amount):,} XAF",
                    },
                    'unit_amount': price_in_cents,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                'donation_id': str(donation.id),
                'type': 'donation',
            }
        )
        
        donation.payment_transaction_id = checkout_session.id
        donation.save(update_fields=['payment_transaction_id'])
        
        return redirect(checkout_session.url)
        
    except stripe.error.StripeError as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Stripe error for donation {donation.id}: {str(e)}")
        donation.payment_status = Donation.PaymentStatus.FAILED
        donation.save(update_fields=['payment_status'])
        messages.error(request, 'Payment failed. Please try again.')
        return redirect('core:library')


@login_required
def donation_fapshi_payment(request, donation_id):
    """Handle Fapshi payment for donation."""
    from .. import fapshi_utils
    
    donation = get_object_or_404(Donation, id=donation_id, donor=request.user)
    
    if donation.payment_status != Donation.PaymentStatus.PENDING:
        messages.error(request, 'This donation has already been processed.')
        return redirect('core:library')
    
    # Build URLs
    domain = request.build_absolute_uri('/').rstrip('/')
    
    result = fapshi_utils.create_payment(
        amount=int(donation.amount),
        email=request.user.email,
        redirect_url=f"{domain}/support/fapshi-callback/{donation.id}/",
        user_id=str(request.user.id),
        external_id=f"DON-{donation.id}",
        message=f"Support {donation.recipient.get_display_name()}"
    )
    
    if result['success']:
        donation.payment_transaction_id = result.get('trans_id', '')
        donation.save(update_fields=['payment_transaction_id'])
        return redirect(result['link'])
    else:
        donation.payment_status = Donation.PaymentStatus.FAILED
        donation.save(update_fields=['payment_status'])
        messages.error(request, f"Payment initiation failed: {result.get('error', 'Unknown error')}")
        return redirect('core:library')


@login_required
def donation_fapshi_callback(request, donation_id):
    """Handle Fapshi callback for donation."""
    from .. import fapshi_utils
    from django.utils import timezone
    
    donation = get_object_or_404(Donation, id=donation_id)
    
    if donation.payment_status == Donation.PaymentStatus.COMPLETED:
        return redirect('core:donation_success', donation_id=donation.id)
    
    # Check payment status
    trans_id = request.GET.get('transId') or donation.payment_transaction_id
    if trans_id:
        result = fapshi_utils.check_payment_status(trans_id)
        
        if result['success'] and fapshi_utils.is_payment_successful(result['status']):
            donation.payment_status = Donation.PaymentStatus.COMPLETED
            donation.completed_at = timezone.now()
            donation.save()
            
            # Credit author's earnings
            author = donation.recipient
            author.earnings_balance += donation.author_earning
            author.save(update_fields=['earnings_balance'])
            
            return redirect('core:donation_success', donation_id=donation.id)
    
    # Still pending - poll
    return render(request, 'core/donation_pending.html', {
        'donation': donation,
    })


@login_required
def donation_success(request, donation_id):
    """Display thank you page after successful donation."""
    import stripe
    from django.utils import timezone
    
    donation = get_object_or_404(Donation, id=donation_id)
    
    # Verify Stripe payment if needed
    session_id = request.GET.get('session_id')
    if session_id and donation.payment_status == Donation.PaymentStatus.PENDING:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status == 'paid':
                donation.payment_status = Donation.PaymentStatus.COMPLETED
                donation.completed_at = timezone.now()
                donation.save()
                
                # Credit author's earnings
                author = donation.recipient
                author.earnings_balance += donation.author_earning
                author.save(update_fields=['earnings_balance'])
        except Exception:
            pass
    
    if donation.payment_status != Donation.PaymentStatus.COMPLETED:
        messages.error(request, 'Donation was not completed.')
        return redirect('core:library')
    
    return render(request, 'core/donation_success.html', {
        'donation': donation,
    })


@login_required
def author_donations(request):
    """Display donations received by the author."""
    from django.db.models import Sum
    
    donations = Donation.objects.filter(
        recipient=request.user,
        payment_status=Donation.PaymentStatus.COMPLETED
    ).select_related('donor', 'book').order_by('-created_at')
    
    total_received = donations.aggregate(total=Sum('author_earning'))['total'] or Decimal('0.00')
    donation_count = donations.count()
    
    return render(request, 'core/author_donations.html', {
        'donations': donations,
        'total_received': total_received,
        'donation_count': donation_count,
    })


# =============================================================================
# Referral System Views
# =============================================================================

def validate_referral_code_api(request, code):
    """API endpoint to validate a referral code."""
    from users.models import User
    
    code = code.strip().upper()
    
    # Check format
    if not code.match(r'^REEPLS-[A-Z0-9]{4}$') if hasattr(code, 'match') else not __import__('re').match(r'^REEPLS-[A-Z0-9]{4}$', code):
        return JsonResponse({'valid': False, 'error': 'Invalid format'})
    
    try:
        referrer = User.objects.get(referral_code=code)
        
        # Check if user is trying to use their own code
        is_self = request.user.is_authenticated and referrer == request.user
        
        return JsonResponse({
            'valid': not is_self,
            'is_self': is_self,
        })
    except User.DoesNotExist:
        return JsonResponse({'valid': False, 'error': 'Code not found'})


def process_referral_commission(purchase):
    """
    Process referral commission for a purchase.
    Called after successful payment verification.
    """
    from ..models import ReferralSettings
    from decimal import Decimal
    
    if not purchase.referred_by:
        return
    
    # Get referral settings
    referral_percent = ReferralSettings.get_referral_percent()
    if referral_percent <= 0:
        return
    
    # Calculate referral commission
    commission_rate = referral_percent / Decimal('100')
    referral_commission = (purchase.amount_paid * commission_rate).quantize(Decimal('0.01'))
    
    # Update purchase record
    purchase.referral_commission = referral_commission
    
    # Deduct from author earning (not platform commission)
    purchase.author_earning = purchase.author_earning - referral_commission
    purchase.save(update_fields=['referral_commission', 'author_earning'])
    
    # Credit referrer's earnings balance
    purchase.referred_by.earnings_balance += referral_commission
    purchase.referred_by.save(update_fields=['earnings_balance'])

