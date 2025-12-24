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
    
    # User Library
    path('library/', views.user_library, name='library'),
    path('library/<int:entry_id>/toggle-download/', views.toggle_download_status, name='toggle_download'),
    path('library/<int:entry_id>/progress/', views.update_reading_progress, name='update_progress'),
    path('library/<int:entry_id>/access/', views.access_book, name='access_book'),
    
    # Ebook Reader
    path('read/<slug:slug>/', views.book_reader, name='book_reader'),
    path('api/update-reading-progress/', views.update_reading_progress_api, name='update_reading_progress_api'),
    
    # Audiobook Player
    path('listen/<slug:slug>/', views.audiobook_player, name='audiobook_player'),
    path('api/update-listening-progress/', views.update_listening_progress_api, name='update_listening_progress_api'),
    
    # Reviews
    path('reviews/submit/<int:book_id>/', views.submit_review, name='submit_review'),
    path('reviews/<int:review_id>/edit/', views.edit_review, name='edit_review'),
    path('reviews/<int:review_id>/delete/', views.delete_review, name='delete_review'),
    
    # PWA / Offline
    path('offline/', views.offline_page, name='offline'),
    path('api/download-book/<int:book_id>/', views.download_book_api, name='download_book_api'),
    path('api/remove-download/<int:book_id>/', views.remove_download_api, name='remove_download_api'),
    
    # User Settings
    path('settings/', views.user_settings, name='user_settings'),
    path('settings/notifications/', views.notification_settings, name='notification_settings'),
    
    # Book Preview
    path('preview/<slug:slug>/', views.book_preview, name='book_preview'),
    
    # Author Analytics
    path('my-books/analytics/', views.author_analytics, name='author_analytics'),
    path('api/analytics-data/', views.analytics_data_api, name='analytics_data_api'),
    
    # Hard Copy Requests
    path('library/request-hardcopy/<int:book_id>/', views.request_hard_copy, name='request_hard_copy'),
    
    # Legal Pages
    path('terms/', views.terms_page, name='terms'),
    path('privacy/', views.privacy_page, name='privacy'),
    path('legal/', views.legal_page, name='legal'),
    
    # Upfront Payment
    path('my-books/upfront/', views.upfront_applications_list, name='upfront_applications'),
    path('my-books/upfront/apply/', views.apply_upfront_payment, name='apply_upfront_payment'),
    path('my-books/upfront/cancel/<int:application_id>/', views.cancel_upfront_application, name='cancel_upfront_application'),
    path('upfront-terms/', views.upfront_terms_content, name='upfront_terms_content'),
    
    # Donations / Support Me
    path('support/<int:author_id>/', views.support_author, name='support_author'),
    path('support/<int:author_id>/book/<int:book_id>/', views.support_author, name='support_author_book'),
    path('support/pay/stripe/<int:donation_id>/', views.donation_stripe_payment, name='donation_stripe_payment'),
    path('support/pay/fapshi/<int:donation_id>/', views.donation_fapshi_payment, name='donation_fapshi_payment'),
    path('support/fapshi-callback/<int:donation_id>/', views.donation_fapshi_callback, name='donation_fapshi_callback'),
    path('support/success/<int:donation_id>/', views.donation_success, name='donation_success'),
    path('my-books/donations/', views.author_donations, name='author_donations'),
]


