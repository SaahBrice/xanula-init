import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from .models import Manuscript


@login_required
def write_landing(request):
    manuscripts = Manuscript.objects.filter(user=request.user)
    return render(request, 'write/landing.html', {'manuscripts': manuscripts})


@login_required
@require_POST
def create_manuscript(request):
    title = request.POST.get('title', '').strip()
    if not title:
        title = 'Untitled'
    manuscript = Manuscript.objects.create(user=request.user, title=title)
    return redirect('write:editor', manuscript_id=manuscript.pk)


@login_required
def editor(request, manuscript_id):
    manuscript = get_object_or_404(Manuscript, pk=manuscript_id, user=request.user)
    return render(request, 'write/editor.html', {
        'manuscript': manuscript,
        'content_json': json.dumps(manuscript.content or {}),
    })


@login_required
@require_POST
def save_manuscript(request, manuscript_id):
    manuscript = get_object_or_404(Manuscript, pk=manuscript_id, user=request.user)
    try:
        data = json.loads(request.body)
        manuscript.content = data.get('content', {})
        title = data.get('title', '').strip()
        if title:
            manuscript.title = title
        manuscript.save()
        return JsonResponse({'status': 'ok', 'updated_at': manuscript.updated_at.isoformat()})
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({'status': 'error', 'message': 'Invalid data'}, status=400)
