from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Homepage
    path('', views.homepage, name='homepage'),
    
    # Book browsing
    path('books/', views.book_list, name='book_list'),
    path('books/search/', views.search_books, name='search'),
    path('books/category/<str:category_slug>/', views.category_books, name='category_books'),
    path('books/<slug:slug>/', views.book_detail, name='book_detail'),
    
    # Author profile
    path('authors/<int:user_id>/', views.author_profile, name='author_profile'),
    
    # Wishlist
    path('wishlist/', views.my_wishlist, name='wishlist'),
    path('wishlist/toggle/<int:book_id>/', views.toggle_wishlist, name='toggle_wishlist'),
    
    # Author publishing
    path('publish/', views.publish_book, name='publish_book'),
    path('my-books/', views.my_books, name='my_books'),
    path('my-books/<int:book_id>/edit/', views.edit_book, name='edit_book'),
    path('my-books/payout/', views.request_payout, name='request_payout'),
    
    # Purchase & Payment - Stripe
    path('books/<slug:slug>/purchase/', views.initiate_purchase, name='initiate_purchase'),
    path('purchase/stripe/<int:book_id>/', views.create_stripe_checkout, name='create_stripe_checkout'),
    path('purchase/success/<int:purchase_id>/', views.purchase_success, name='purchase_success'),
    path('account/purchases/', views.purchase_history, name='purchase_history'),
    
    # Purchase & Payment - Fapshi (Mobile Money)
    path('purchase/fapshi/<int:book_id>/', views.create_fapshi_checkout, name='create_fapshi_checkout'),
    path('purchase/fapshi/return/<int:purchase_id>/', views.fapshi_return, name='fapshi_return'),
    path('api/check-purchase-status/<int:purchase_id>/', views.check_purchase_status_api, name='check_purchase_status_api'),
]


