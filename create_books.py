from users.models import User
from core.models import Book
from decimal import Decimal

author = User.objects.first()

books_data = [
    {'title': 'The African Dream', 'category': 'african_literature', 'price': 2500, 'desc': 'A captivating journey through modern Africa.'},
    {'title': 'Python Mastery', 'category': 'academic', 'price': 5000, 'desc': 'Complete guide to Python programming.'},
    {'title': 'Love in Lagos', 'category': 'romance', 'price': 1500, 'desc': 'A heartwarming Nigerian love story.'},
    {'title': 'The Dark Forest', 'category': 'thriller_mystery', 'price': 2000, 'desc': 'A thrilling mystery in the Cameroon rainforest.'},
    {'title': 'Building Wealth', 'category': 'business_money', 'price': 3500, 'desc': 'Financial wisdom for African entrepreneurs.'},
    {'title': 'Mindful Living', 'category': 'self_help', 'price': 1800, 'desc': 'Transform your life with mindfulness.'},
    {'title': 'Tales of Ancestors', 'category': 'fiction', 'price': 0, 'desc': 'Free collection of African folktales.'},
    {'title': 'Digital Marketing 101', 'category': 'business_money', 'price': 4000, 'desc': 'Master online marketing strategies.'},
    {'title': 'The Healer', 'category': 'drama', 'price': 2200, 'desc': 'A dramatic tale of traditional medicine.'},
    {'title': 'Space Chronicles', 'category': 'scifi_fantasy', 'price': 2800, 'desc': 'African sci-fi adventure among the stars.'},
]

created = 0
for b in books_data:
    book = Book.objects.create(
        author=author,
        title=b['title'],
        short_description=b['desc'],
        long_description=f"{b['desc']} This is a longer description for the book detail page.",
        category=b['category'],
        language='en',
        price=Decimal(str(b['price'])),
        status='completed'
    )
    created += 1
    print(f"Created: {book.title} - {book.formatted_price}")

print(f"\nTotal books created: {created}")
