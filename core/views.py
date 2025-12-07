from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.conf import settings

from .models import Book, Review, LibraryEntry, PayoutRequest


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
    from .forms import BookSubmissionForm
    
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
    from .models import Purchase
    
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
    from .forms import BookEditForm
    
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
    from .forms import PayoutRequestForm
    
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
        from .models import Purchase
        
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
    context = {
        'book': book,
        'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
    }
    return render(request, 'core/purchase_page.html', context)


@login_required
def create_stripe_checkout(request, book_id):
    """
    Create Stripe checkout session and redirect to Stripe.
    """
    import stripe
    from .models import Purchase
    
    book = get_object_or_404(Book, id=book_id)
    
    # Anti-duplicate check
    if LibraryEntry.objects.filter(user=request.user, book=book).exists():
        messages.info(request, 'You already own this book!')
        return redirect('core:my_books')
    
    # Configure Stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    
    # Create pending purchase record
    purchase = Purchase.objects.create(
        buyer=request.user,
        book=book,
        amount_paid=book.price,
        payment_method=Purchase.PaymentMethod.STRIPE,
        payment_status=Purchase.PaymentStatus.PENDING
    )
    
    # Build URLs
    domain = request.build_absolute_uri('/').rstrip('/')
    success_url = f"{domain}/purchase/success/{purchase.id}/?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{domain}/books/{book.slug}/?cancelled=1"
    
    try:
        # Create Stripe Checkout Session
        checkout_session = stripe.checkout.Session.create(
            customer_email=request.user.email,
            line_items=[{
                'price_data': {
                    'currency': 'xaf',
                    'product_data': {
                        'name': book.title,
                        'description': book.short_description[:200] if book.short_description else '',
                    },
                    'unit_amount': int(book.price),  # XAF doesn't use cents
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
    from .models import Purchase
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
            
            # Calculate commission based on book format
            # Per Planning Document Section 6:
            # - With audiobook: 30% platform commission
            # - Ebook only: 10% platform commission
            amount = purchase.amount_paid
            if purchase.book.has_audiobook:
                commission_rate = Decimal('0.30')
            else:
                commission_rate = Decimal('0.10')
            
            purchase.platform_commission = amount * commission_rate
            purchase.author_earning = amount - purchase.platform_commission
            purchase.save()
            
            # Update author's earnings balance
            author = purchase.book.author
            author.earnings_balance += purchase.author_earning
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
    from .models import Purchase
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
# Fapshi Mobile Money Payment Views
# Per Architecture Document Section 9 (Payment Processing)
# =============================================================================

@login_required
def create_fapshi_checkout(request, book_id):
    """
    Create Fapshi mobile money payment and redirect to Fapshi.
    """
    from .models import Purchase
    from . import fapshi_utils
    import logging
    
    logger = logging.getLogger(__name__)
    
    book = get_object_or_404(Book, id=book_id)
    
    # Anti-duplicate check
    if LibraryEntry.objects.filter(user=request.user, book=book).exists():
        messages.info(request, 'You already own this book!')
        return redirect('core:my_books')
    
    # Check if book is free (shouldn't reach here but safety check)
    if book.is_free:
        return redirect('core:initiate_purchase', slug=book.slug)
    
    # Create pending purchase record
    purchase = Purchase.objects.create(
        buyer=request.user,
        book=book,
        amount_paid=book.price,
        payment_method=Purchase.PaymentMethod.FAPSHI,
        payment_status=Purchase.PaymentStatus.PENDING
    )
    
    # Build return URL
    domain = request.build_absolute_uri('/').rstrip('/')
    return_url = f"{domain}/purchase/fapshi/return/{purchase.id}/"
    
    # Call Fapshi API
    result = fapshi_utils.create_payment(
        amount=int(book.price),
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
    from .models import Purchase
    from . import fapshi_utils
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
            
            # Update author's earnings balance
            author = purchase.book.author
            author.earnings_balance += purchase.author_earning
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
    from .models import Purchase
    from . import fapshi_utils
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
            
            # Update author earnings
            author = purchase.book.author
            author.earnings_balance += purchase.author_earning
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



