import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from .ai import (
    AIConfigurationError,
    AIServiceError,
    analyze_manuscript,
    generate_draft,
    normalize_memory,
    normalize_profile,
)
from .intelligence import (
    agent_steps_for_inspect,
    build_longform_engine_state,
    inspect_content,
    mark_stale_from_change,
    normalize_chapter_map,
    normalize_consistency,
    normalize_entities,
    normalize_stale,
    normalize_usage,
    normalize_voice,
    reset_stale_for,
)
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
        'ai_profile': normalize_profile(manuscript.ai_profile),
        'ai_memory': normalize_memory(manuscript.ai_memory),
        'ai_voice': normalize_voice(manuscript.ai_voice),
        'ai_chapter_map': normalize_chapter_map(manuscript.ai_chapter_map),
        'ai_entities': normalize_entities(manuscript.ai_entities),
        'ai_consistency': normalize_consistency(manuscript.ai_consistency),
        'ai_longform_state': build_longform_engine_state(manuscript),
        'ai_usage': normalize_usage(manuscript.ai_usage),
        'ai_memory_stale': normalize_stale(manuscript.ai_memory_stale),
    })


@login_required
@require_POST
def save_manuscript(request, manuscript_id):
    manuscript = get_object_or_404(Manuscript, pk=manuscript_id, user=request.user)
    try:
        data = json.loads(request.body)
        previous_content = manuscript.content or {}
        next_content = data.get('content', {})
        manuscript.content = next_content
        manuscript.ai_memory_stale = mark_stale_from_change(
            previous_content,
            next_content,
            manuscript.ai_memory_stale,
        )
        title = data.get('title', '').strip()
        if title:
            manuscript.title = title
        manuscript.save()
        return JsonResponse({
            'status': 'ok',
            'updated_at': manuscript.updated_at.isoformat(),
            'stale': normalize_stale(manuscript.ai_memory_stale),
        })
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({'status': 'error', 'message': 'Invalid data'}, status=400)


def _ai_error_response(exc):
    status = 503 if isinstance(exc, AIConfigurationError) else 502
    return JsonResponse({'status': 'error', 'message': str(exc)}, status=status)


@login_required
@require_POST
def ai_analyze(request, manuscript_id):
    manuscript = get_object_or_404(Manuscript, pk=manuscript_id, user=request.user)
    try:
        profile, memory = analyze_manuscript(manuscript)
        local = inspect_content(manuscript.content, profile=profile)
        manuscript.ai_profile = profile
        manuscript.ai_memory = memory
        manuscript.ai_voice = local['voice']
        manuscript.ai_chapter_map = local['chapter_map']
        manuscript.ai_entities = local['entities']
        manuscript.ai_memory_stale = reset_stale_for(manuscript.content)
        manuscript.ai_profile_confirmed = False
        manuscript.save(update_fields=[
            'ai_profile',
            'ai_memory',
            'ai_voice',
            'ai_chapter_map',
            'ai_entities',
            'ai_memory_stale',
            'ai_profile_confirmed',
            'updated_at',
        ])
        return JsonResponse({
            'status': 'ok',
            'profile': profile,
            'memory': memory,
            'voice': manuscript.ai_voice,
            'chapter_map': manuscript.ai_chapter_map,
            'entities': manuscript.ai_entities,
            'stale': manuscript.ai_memory_stale,
            'engine_state': build_longform_engine_state(manuscript),
            'agent_steps': [
                {'name': 'Memory Agent', 'status': 'ready', 'detail': 'Refreshed DeepSeek memory.'},
                *agent_steps_for_inspect(local.get('warnings')),
            ],
            'warnings': local.get('warnings', []),
            'confirmed': manuscript.ai_profile_confirmed,
        })
    except (AIConfigurationError, AIServiceError) as exc:
        return _ai_error_response(exc)


@login_required
@require_POST
def ai_profile(request, manuscript_id):
    manuscript = get_object_or_404(Manuscript, pk=manuscript_id, user=request.user)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    manuscript.ai_profile = normalize_profile(data.get('profile', {}))
    if 'memory' in data:
        manuscript.ai_memory = normalize_memory(data.get('memory', {}))
    manuscript.ai_profile_confirmed = bool(data.get('confirmed', True))
    manuscript.save(update_fields=['ai_profile', 'ai_memory', 'ai_profile_confirmed', 'updated_at'])
    return JsonResponse({
        'status': 'ok',
        'profile': manuscript.ai_profile,
        'memory': normalize_memory(manuscript.ai_memory),
        'confirmed': manuscript.ai_profile_confirmed,
    })


@login_required
@require_POST
def ai_inspect(request, manuscript_id):
    manuscript = get_object_or_404(Manuscript, pk=manuscript_id, user=request.user)
    local = inspect_content(manuscript.content, manuscript.ai_memory_stale, profile=manuscript.ai_profile)
    manuscript.ai_voice = local['voice']
    manuscript.ai_chapter_map = local['chapter_map']
    manuscript.ai_entities = local['entities']
    manuscript.ai_memory_stale = local['stale']
    manuscript.save(update_fields=[
        'ai_voice',
        'ai_chapter_map',
        'ai_entities',
        'ai_memory_stale',
        'updated_at',
    ])
    warnings = local.get('warnings', [])
    return JsonResponse({
        'status': 'ok',
        'voice': manuscript.ai_voice,
        'chapter_map': manuscript.ai_chapter_map,
        'entities': manuscript.ai_entities,
        'stale': manuscript.ai_memory_stale,
        'engine_state': build_longform_engine_state(manuscript),
        'warnings': warnings,
        'agent_steps': agent_steps_for_inspect(warnings),
        'usage_hint': 'local only',
    })


@login_required
@require_POST
def ai_generate(request, manuscript_id):
    manuscript = get_object_or_404(Manuscript, pk=manuscript_id, user=request.user)
    try:
        data = json.loads(request.body)
        result = generate_draft(
            manuscript,
            data.get('action', ''),
            selected_text=data.get('selected_text', ''),
            cursor_context=data.get('cursor_context', ''),
            user_prompt=data.get('user_prompt', ''),
        )
        if isinstance(result, str):
            return JsonResponse({'status': 'ok', 'draft': result})
        manuscript.ai_usage = result.get('usage', manuscript.ai_usage)
        manuscript.ai_consistency = result.get('consistency_report', manuscript.ai_consistency)
        manuscript.save(update_fields=['ai_usage', 'ai_consistency', 'updated_at'])
        return JsonResponse({
            'status': 'ok',
            'draft': result.get('draft', ''),
            'placement': result.get('placement', ''),
            'agent_steps': result.get('agent_steps', []),
            'usage_hint': result.get('usage_hint', ''),
            'safety_warnings': result.get('safety_warnings', []),
            'consistency_report': result.get('consistency_report', {}),
            'engine_state': result.get('engine_state', build_longform_engine_state(manuscript)),
            'context_summary': result.get('context_summary', {}),
            'usage': manuscript.ai_usage,
        })
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except (AIConfigurationError, AIServiceError) as exc:
        return _ai_error_response(exc)
