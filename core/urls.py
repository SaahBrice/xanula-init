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
]
