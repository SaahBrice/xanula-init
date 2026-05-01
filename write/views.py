import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone

from core.ai_tokens import (
    InsufficientAITokens,
    assert_can_start_ai_request,
    deduct_ai_tokens,
    get_purchase_options,
    token_status_for_user,
)
from .ai import (
    AIConfigurationError,
    AIServiceError,
    analyze_manuscript,
    extract_tiptap_text,
    generate_draft,
    normalize_memory,
    normalize_profile,
)
from .intelligence import (
    agent_steps_for_inspect,
    build_chapter_memory,
    build_longform_engine_state,
    inspect_content,
    memory_freshness,
    next_memory_meta,
    mark_stale_from_change,
    normalize_chapter_map,
    normalize_chapter_memory,
    normalize_consistency,
    normalize_cost_mode,
    normalize_entities,
    normalize_memory_meta,
    normalize_stale,
    normalize_usage,
    normalize_voice,
    reset_stale_for,
)
from .models import Manuscript


def _token_payload(request, token_data=None):
    status = token_data or token_status_for_user(request.user, grant_if_needed=False)
    return {
        'token_balance': status.get('balance', 0),
        'token_delta': status.get('delta', 0),
        'token_status': status,
        'purchase_options': get_purchase_options(),
    }


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
        'ai_memory_meta': normalize_memory_meta(manuscript.ai_memory_meta),
        'ai_memory_freshness': memory_freshness(manuscript.ai_memory_meta, manuscript.ai_memory_stale),
        'ai_chapter_memory': normalize_chapter_memory(manuscript.ai_chapter_memory),
        'ai_cost_mode': normalize_cost_mode(manuscript.ai_cost_mode),
        'ai_longform_state': build_longform_engine_state(manuscript),
        'ai_usage': normalize_usage(manuscript.ai_usage),
        'ai_memory_stale': normalize_stale(manuscript.ai_memory_stale),
        'ai_token_status': token_status_for_user(request.user, grant_if_needed=False),
        'ai_token_purchase_options': get_purchase_options(),
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


def _insufficient_tokens_response(request, exc):
    payload = _token_payload(request, token_status_for_user(request.user, grant_if_needed=False))
    return JsonResponse({
        'status': 'error',
        'code': 'insufficient_tokens',
        'message': str(exc),
        **payload,
    }, status=402)


@login_required
@require_POST
def ai_analyze(request, manuscript_id):
    manuscript = get_object_or_404(Manuscript, pk=manuscript_id, user=request.user)
    try:
        assert_can_start_ai_request(request.user)
        profile, memory = analyze_manuscript(manuscript)
        local = inspect_content(manuscript.content, profile=profile)
        manuscript.ai_profile = profile
        manuscript.ai_memory = memory
        manuscript.ai_voice = local['voice']
        manuscript.ai_chapter_map = local['chapter_map']
        manuscript.ai_entities = local['entities']
        manuscript.ai_memory_meta = next_memory_meta(manuscript.ai_memory_meta, manuscript.content, 'analyze', timezone.now())
        manuscript.ai_chapter_memory = build_chapter_memory(manuscript.content, memory, manuscript.ai_memory_meta['version'])
        manuscript.ai_memory_stale = reset_stale_for(manuscript.content)
        manuscript.ai_profile_confirmed = False
        manuscript.save(update_fields=[
            'ai_profile',
            'ai_memory',
            'ai_voice',
            'ai_chapter_map',
            'ai_entities',
            'ai_memory_meta',
            'ai_chapter_memory',
            'ai_memory_stale',
            'ai_profile_confirmed',
            'updated_at',
        ])
        text = extract_tiptap_text(manuscript.content, max_chars=45000)
        _, _, charged_status = deduct_ai_tokens(
            request.user,
            'analyze',
            input_chars=len(text),
            output_chars=len(json.dumps({'profile': profile, 'memory': memory}, ensure_ascii=False)),
            metadata={'manuscript_id': manuscript.pk, 'usage_hint': 'memory refresh'},
        )
        return JsonResponse({
            'status': 'ok',
            'profile': profile,
            'memory': memory,
            'voice': manuscript.ai_voice,
            'chapter_map': manuscript.ai_chapter_map,
            'entities': manuscript.ai_entities,
            'memory_freshness': memory_freshness(manuscript.ai_memory_meta, manuscript.ai_memory_stale),
            'chapter_memory': normalize_chapter_memory(manuscript.ai_chapter_memory),
            'cost_mode': normalize_cost_mode(manuscript.ai_cost_mode),
            'stale': manuscript.ai_memory_stale,
            'engine_state': build_longform_engine_state(manuscript),
            'agent_steps': [
                {'name': 'Memory Agent', 'status': 'ready', 'detail': 'Refreshed DeepSeek memory.'},
                *agent_steps_for_inspect(local.get('warnings')),
            ],
            'warnings': local.get('warnings', []),
            'confirmed': manuscript.ai_profile_confirmed,
            **_token_payload(request, charged_status),
        })
    except InsufficientAITokens as exc:
        return _insufficient_tokens_response(request, exc)
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
    manuscript.ai_memory_meta = next_memory_meta(manuscript.ai_memory_meta, manuscript.content, 'profile edit', timezone.now())
    manuscript.ai_chapter_memory = build_chapter_memory(manuscript.content, manuscript.ai_memory, manuscript.ai_memory_meta['version'])
    manuscript.ai_profile_confirmed = bool(data.get('confirmed', True))
    manuscript.save(update_fields=['ai_profile', 'ai_memory', 'ai_memory_meta', 'ai_chapter_memory', 'ai_profile_confirmed', 'updated_at'])
    return JsonResponse({
        'status': 'ok',
        'profile': manuscript.ai_profile,
        'memory': normalize_memory(manuscript.ai_memory),
        'memory_freshness': memory_freshness(manuscript.ai_memory_meta, manuscript.ai_memory_stale),
        'chapter_memory': normalize_chapter_memory(manuscript.ai_chapter_memory),
        'cost_mode': normalize_cost_mode(manuscript.ai_cost_mode),
        'confirmed': manuscript.ai_profile_confirmed,
        **_token_payload(request),
    })


@login_required
@require_POST
def ai_inspect(request, manuscript_id):
    manuscript = get_object_or_404(Manuscript, pk=manuscript_id, user=request.user)
    local = inspect_content(manuscript.content, manuscript.ai_memory_stale, profile=manuscript.ai_profile)
    manuscript.ai_voice = local['voice']
    manuscript.ai_chapter_map = local['chapter_map']
    manuscript.ai_entities = local['entities']
    manuscript.ai_memory_meta = next_memory_meta(manuscript.ai_memory_meta, manuscript.content, 'inspect', timezone.now())
    manuscript.ai_chapter_memory = build_chapter_memory(manuscript.content, manuscript.ai_memory, manuscript.ai_memory_meta['version'])
    manuscript.ai_memory_stale = local['stale']
    manuscript.save(update_fields=[
        'ai_voice',
        'ai_chapter_map',
        'ai_entities',
        'ai_memory_meta',
        'ai_chapter_memory',
        'ai_memory_stale',
        'updated_at',
    ])
    warnings = local.get('warnings', [])
    return JsonResponse({
        'status': 'ok',
        'voice': manuscript.ai_voice,
        'chapter_map': manuscript.ai_chapter_map,
        'entities': manuscript.ai_entities,
        'memory_freshness': memory_freshness(manuscript.ai_memory_meta, manuscript.ai_memory_stale),
        'chapter_memory': normalize_chapter_memory(manuscript.ai_chapter_memory),
        'cost_mode': normalize_cost_mode(manuscript.ai_cost_mode),
        'stale': manuscript.ai_memory_stale,
        'engine_state': build_longform_engine_state(manuscript),
        'warnings': warnings,
        'agent_steps': agent_steps_for_inspect(warnings),
        'usage_hint': 'local only',
        **_token_payload(request),
    })


@login_required
@require_POST
def ai_generate(request, manuscript_id):
    manuscript = get_object_or_404(Manuscript, pk=manuscript_id, user=request.user)
    try:
        data = json.loads(request.body)
        assert_can_start_ai_request(request.user)
        result = generate_draft(
            manuscript,
            data.get('action', ''),
            selected_text=data.get('selected_text', ''),
            cursor_context=data.get('cursor_context', ''),
            user_prompt=data.get('user_prompt', ''),
            regeneration_instruction=data.get('regeneration_instruction', ''),
            cost_mode=data.get('cost_mode', manuscript.ai_cost_mode),
        )
        if isinstance(result, str):
            return JsonResponse({'status': 'ok', 'draft': result})
        manuscript.ai_usage = result.get('usage', manuscript.ai_usage)
        manuscript.ai_consistency = result.get('consistency_report', manuscript.ai_consistency)
        manuscript.ai_cost_mode = normalize_cost_mode(result.get('cost_mode', manuscript.ai_cost_mode))
        manuscript.save(update_fields=['ai_usage', 'ai_consistency', 'ai_cost_mode', 'updated_at'])
        context_summary = result.get('context_summary', {})
        _, _, charged_status = deduct_ai_tokens(
            request.user,
            data.get('action', ''),
            input_chars=context_summary.get('input_chars', 0),
            output_chars=len(result.get('draft', '')),
            provider_usage=context_summary.get('provider_usage', {}),
            metadata={
                'manuscript_id': manuscript.pk,
                'usage_hint': result.get('usage_hint', ''),
                'cost_mode': result.get('cost_mode', normalize_cost_mode(manuscript.ai_cost_mode)),
            },
        )
        return JsonResponse({
            'status': 'ok',
            'draft': result.get('draft', ''),
            'placement': result.get('placement', ''),
            'intent_preview': result.get('intent_preview', {}),
            'diff_available': result.get('diff_available', False),
            'suggestion_diff': result.get('suggestion_diff', []),
            'agent_steps': result.get('agent_steps', []),
            'usage_hint': result.get('usage_hint', ''),
            'safety_warnings': result.get('safety_warnings', []),
            'consistency_report': result.get('consistency_report', {}),
            'engine_state': result.get('engine_state', build_longform_engine_state(manuscript)),
            'memory_freshness': result.get('memory_freshness', memory_freshness(manuscript.ai_memory_meta, manuscript.ai_memory_stale)),
            'chapter_memory': result.get('chapter_memory', normalize_chapter_memory(manuscript.ai_chapter_memory)),
            'cost_mode': result.get('cost_mode', normalize_cost_mode(manuscript.ai_cost_mode)),
            'context_summary': context_summary,
            'usage': manuscript.ai_usage,
            **_token_payload(request, charged_status),
        })
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except InsufficientAITokens as exc:
        return _insufficient_tokens_response(request, exc)
    except (AIConfigurationError, AIServiceError) as exc:
        return _ai_error_response(exc)
