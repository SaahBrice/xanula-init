"""
Blog views for Xanula.
"""

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import F

from ..models import Article


def blog_list(request):
    """
    Blog listing page — shows all published articles, paginated.
    """
    articles = Article.objects.filter(is_published=True).select_related('author')
    
    paginator = Paginator(articles, 9)  # 9 per page for 3-col grid
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'articles': page_obj,
    }
    return render(request, 'core/blog_list.html', context)


def article_detail(request, slug):
    """
    Single article detail page with full content, audio players, and OG meta tags.
    """
    article = get_object_or_404(
        Article.objects.select_related('author'),
        slug=slug,
        is_published=True,
    )
    
    # Get related articles (exclude current)
    related_articles = Article.objects.filter(
        is_published=True
    ).exclude(id=article.id)[:3]
    
    context = {
        'article': article,
        'related_articles': related_articles,
    }
    return render(request, 'core/article_detail.html', context)


@require_POST
@login_required
def like_article(request, article_id):
    """
    Like an article — increments the likes count (no toggle, each click = +1).
    Uses F() expression for atomic increment.
    Returns JSON with the new count.
    """
    article = get_object_or_404(Article, id=article_id, is_published=True)
    
    # Atomic increment
    Article.objects.filter(id=article_id).update(likes_count=F('likes_count') + 1)
    
    # Refresh from DB to get new count
    article.refresh_from_db()
    
    return JsonResponse({
        'success': True,
        'likes': article.likes_count,
    })
