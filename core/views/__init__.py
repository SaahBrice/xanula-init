"""
Core views package.
All views are re-exported here for backward compatibility.
"""

from ._views import (
    # Utility functions
    process_upfront_recouping,
    get_available_books,
    
    # Book browsing views
    homepage,
    book_list,
    search_books,
    category_books,
    book_detail,
    
    # Review views
    submit_review,
    edit_review,
    delete_review,
    
    # Author/User views
    author_profile,
    toggle_wishlist,
    my_wishlist,
    
    # Author publishing views
    publish_book,
    my_books,
    edit_book,
    request_payout,
    
    # Purchase views
    initiate_purchase,
    create_stripe_checkout,
    purchase_success,
    purchase_history,
    
    # Fapshi views
    create_fapshi_checkout,
    fapshi_return,
    check_purchase_status_api,
    
    # Balance payment view
    purchase_with_balance,
    
    # Library views
    user_library,
    toggle_download_status,
    update_reading_progress,
    access_book,
    book_reader,
    update_reading_progress_api,
    
    # Audiobook views
    audiobook_player,
    update_listening_progress_api,
    
    # PWA/Offline views
    offline_page,
    download_book_api,
    remove_download_api,
    
    # Settings views
    user_settings,
    notification_settings,
    
    # Preview and Embed views
    book_preview,
    book_embed,
    
    # Analytics views
    author_analytics,
    analytics_data_api,
    
    # Hard copy view
    request_hard_copy,
    
    # Legal pages
    terms_page,
    privacy_page,
    legal_page,
    
    # Upfront payment views
    upfront_applications_list,
    apply_upfront_payment,
    cancel_upfront_application,
    upfront_terms_content,
    
    # Donation views
    support_author,
    donation_stripe_payment,
    donation_fapshi_payment,
    donation_fapshi_callback,
    donation_success,
    author_donations,
    
    # Referral views
    validate_referral_code_api,
    process_referral_commission,
)

from .notifications import (
    notifications_page,
    mark_notifications_read,
    notifications_count_api,
)

from .blog import (
    blog_list,
    article_detail,
    like_article,
)
