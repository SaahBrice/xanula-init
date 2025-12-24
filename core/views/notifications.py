"""
Notifications views for in-app notification system.
"""
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils.translation import gettext_lazy as _

from core.models import Notification


@login_required
def notifications_page(request):
    """
    Notifications page/modal - returns HTML fragment for modal or full page.
    """
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:50]
    unread_count = Notification.get_unread_count(request.user)
    
    context = {
        'notifications': notifications,
        'unread_count': unread_count,
    }
    
    # Check if it's an AJAX/modal request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'core/partials/notifications_list.html', context)
    
    return render(request, 'core/notifications.html', context)


@login_required
@require_POST
def mark_notifications_read(request):
    """
    Mark all notifications as read for the current user.
    """
    Notification.mark_all_read(request.user)
    return JsonResponse({'success': True, 'message': _('All notifications marked as read.')})


@login_required
def notifications_count_api(request):
    """
    API endpoint to get unread notification count.
    Used for live badge updates.
    """
    count = Notification.get_unread_count(request.user)
    return JsonResponse({'count': count})
