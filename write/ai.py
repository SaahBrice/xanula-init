import json
import re

import requests
from django.conf import settings

from .intelligence import (
    build_longform_engine_state,
    build_generation_context,
    check_consistency,
    memory_freshness,
    normalize_chapter_memory,
    normalize_cost_mode,
    record_usage,
    selection_coverage_for,
    sentence_aware_chunks,
    validate_output,
)


class AIConfigurationError(Exception):
    """Raised when the AI provider is not configured."""


class AIServiceError(Exception):
    """Raised when the AI provider cannot produce a usable response."""


class AISelectionCoverageError(AIServiceError):
    """Raised when a selected passage exceeds the current coverage policy."""

    def __init__(self, coverage):
        self.coverage = coverage
        super().__init__(coverage.get("coverage_message") or "The selected text is too large for this mode.")


DEFAULT_PROFILE = {
    "genre": "",
    "tone": "",
    "target_audience": "",
    "language": "",
    "book_type": "",
    "style_notes": "",
}

DEFAULT_MEMORY = {
    "book_summary": "",
    "chapter_summaries": [],
    "characters": [],
    "locations": [],
    "timeline_notes": [],
    "consistency_notes": [],
    "claims": [],
    "themes": [],
    "terms": [],
    "reader_promises": [],
    "open_threads": [],
}

ACTION_INSTRUCTIONS = {
    "continue": "Continue from the cursor with a short, natural next passage. Do not summarize, explain, or jump ahead.",
    "rewrite": "Rewrite only the selected text. Preserve the same scope, facts, sequence, and approximate length.",
    "expand": "Expand only the selected text or current idea. Add useful detail without turning it into a new scene or chapter.",
    "improve": "Improve only the selected text for clarity, rhythm, and style. Keep the same meaning and approximate length.",
    "summarize": "Condense the selected text into a shorter direct summary. If no text is selected, summarize only the immediate context.",
    "outline": "Create a practical chapter or section outline for continuing this book.",
    "custom": "Follow the user's instruction precisely while preserving the book's established voice, facts, and continuity.",
}


def normalize_profile(profile):
    data = dict(DEFAULT_PROFILE)
    if isinstance(profile, dict):
        for key in data:
            value = profile.get(key, "")
            data[key] = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return data


def normalize_memory(memory):
    data = dict(DEFAULT_MEMORY)
    if isinstance(memory, dict):
        for key, default in data.items():
            value = memory.get(key, default)
            if isinstance(default, list):
                data[key] = value if isinstance(value, list) else []
            else:
                data[key] = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return data


def _inline_text(node):
    if not isinstance(node, dict):
        return ""
    node_type = node.get("type")
    if node_type == "text":
        return node.get("text", "")
    if node_type == "hardBreak":
        return "\n"
    return "".join(_inline_text(child) for child in node.get("content", []) if isinstance(child, dict))


def _block_text(node, ordered_index=None):
    if not isinstance(node, dict):
        return []

    node_type = node.get("type")
    content = node.get("content", [])

    if node_type == "heading":
        level = int(node.get("attrs", {}).get("level", 1) or 1)
        text = _inline_text(node).strip()
        return [f"{'#' * max(1, min(level, 6))} {text}"] if text else []

    if node_type == "paragraph":
        text = _inline_text(node).strip()
        return [text] if text else []

    if node_type == "listItem":
        child_lines = []
        for child in content:
            child_lines.extend(_block_text(child))
        text = " ".join(line.strip("- ").strip() for line in child_lines if line).strip()
        if not text:
            return []
        prefix = f"{ordered_index}. " if ordered_index else "- "
        return [f"{prefix}{text}"]

    if node_type == "orderedList":
        lines = []
        index = 1
        for child in content:
            if isinstance(child, dict) and child.get("type") == "listItem":
                lines.extend(_block_text(child, ordered_index=index))
                index += 1
        return lines

    if node_type == "bulletList":
        lines = []
        for child in content:
            lines.extend(_block_text(child))
        return lines

    if node_type == "horizontalRule":
        return ["---"]

    lines = []
    for child in content if isinstance(content, list) else []:
        lines.extend(_block_text(child))
    return lines


def extract_tiptap_text(content, max_chars=None):
    if not isinstance(content, dict):
        return ""
    lines = []
    for node in content.get("content", []):
        lines.extend(_block_text(node))
    text = "\n\n".join(line for line in lines if line).strip()
    if max_chars and len(text) > max_chars:
        return text[:max_chars].rsplit(" ", 1)[0].strip()
    return text


def extract_tiptap_headings(content, limit=30):
    headings = []

    def walk(node):
        if not isinstance(node, dict) or len(headings) >= limit:
            return
        if node.get("type") == "heading":
            text = _inline_text(node).strip()
            if text:
                headings.append({
                    "level": int(node.get("attrs", {}).get("level", 1) or 1),
                    "text": text,
                })
        for child in node.get("content", []) if isinstance(node.get("content", []), list) else []:
            walk(child)

    walk(content)
    return headings


def _extract_json_object(text):
    if not text:
        raise AIServiceError("AI returned an empty response.")
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            return json.loads(cleaned[start:end + 1])
        raise AIServiceError("AI returned invalid JSON.")


def clean_ai_draft(text):
    cleaned = (text or "").strip()
    if not cleaned:
        return ""

    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<(?:reasoning|analysis)>.*?</(?:reasoning|analysis)>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"^```(?:text|markdown|md)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    internal_prefixes = (
        "thought:",
        "thoughts:",
        "thinking:",
        "reasoning:",
        "analysis:",
        "internal note:",
        "plan:",
        "draft plan:",
    )
    lines = []
    skipping_block = False
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        lower = line.lower()
        if any(lower.startswith(prefix) for prefix in internal_prefixes):
            skipping_block = True
            continue
        if skipping_block and not line:
            skipping_block = False
            continue
        if skipping_block:
            continue
        lines.append(raw_line)

    cleaned = "\n".join(lines).strip()
    cleaned = re.sub(r"^(?:sure|certainly|of course)[,.!]\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(?:here(?:'s| is) (?:the )?(?:draft|rewrite|continuation|outline|summary)[:.\-]\s*)", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _word_count(text):
    return len(re.findall(r"\b[\w'-]+\b", text or ""))


def infer_custom_prompt_intent(user_prompt="", selected_text=""):
    prompt = (user_prompt or "").lower()
    has_selection = bool((selected_text or "").strip())
    replacement_words = (
        "rewrite", "improve", "polish", "make this", "make it", "shorten", "condense",
        "summarize", "summary", "expand this", "expand it", "fix", "edit", "revise",
        "change this", "turn this", "replace",
    )
    insertion_words = (
        "continue", "next part", "next scene", "after this", "following", "write from here",
        "use this idea", "use my idea", "insert", "add a scene", "write a scene", "generate the next",
    )

    if has_selection and any(term in prompt for term in replacement_words):
        return {
            "placement": "replace_selection",
            "intent": "custom_replace",
            "instruction": (
                "Treat selected_text as the target passage. Output only the revised replacement text. "
                "Keep the response inside the user's requested scope."
            ),
        }
    if any(term in prompt for term in insertion_words):
        return {
            "placement": "insert_at_cursor",
            "intent": "custom_insert",
            "instruction": (
                "Treat the user prompt as writing direction. Output only manuscript-ready text to insert at the cursor. "
                "Use selected_text only as context or source material unless the user explicitly asked to rewrite it."
            ),
        }
    if has_selection:
        return {
            "placement": "insert_at_cursor",
            "intent": "custom_contextual",
            "instruction": (
                "Use selected_text as context or source material for the user's instruction. "
                "Output only manuscript-ready text. Do not replace the selected text unless the instruction explicitly asks for a revision."
            ),
        }
    return {
        "placement": "insert_at_cursor",
        "intent": "custom_freeform",
        "instruction": (
            "Use the user prompt as the primary writing direction. Output only manuscript-ready text for the cursor position."
        ),
    }


def intent_preview_for(action, user_prompt="", selected_text="", placement=""):
    labels = {
        "continue": "Insert at cursor",
        "rewrite": "Replace selection",
        "expand": "Replace selection",
        "improve": "Replace selection",
        "summarize": "Summarize selection" if selected_text else "Insert summary at cursor",
        "outline": "Create outline",
    }
    if action == "custom":
        intent = infer_custom_prompt_intent(user_prompt, selected_text)
        label_by_intent = {
            "custom_replace": "Replace selection",
            "custom_insert": "Use as idea",
            "custom_contextual": "Insert at cursor",
            "custom_freeform": "Insert at cursor",
        }
        return {
            "label": label_by_intent.get(intent["intent"], "Revise with instruction"),
            "placement": intent.get("placement", placement or "insert_at_cursor"),
            "intent": intent.get("intent", "custom"),
            "uses_selection": bool(selected_text),
        }
    return {
        "label": labels.get(action, "Revise with instruction"),
        "placement": placement or ("replace_selection" if action in {"rewrite", "expand", "improve", "summarize"} and selected_text else "insert_at_cursor"),
        "intent": action,
        "uses_selection": bool(selected_text),
    }


def build_word_diff(original, draft):
    original_words = re.findall(r"\S+", original or "")
    draft_words = re.findall(r"\S+", draft or "")
    rows = []
    max_len = max(len(original_words), len(draft_words))
    for index in range(max_len):
        before = original_words[index] if index < len(original_words) else ""
        after = draft_words[index] if index < len(draft_words) else ""
        if before == after:
            rows.append({"type": "same", "text": after})
        else:
            if before:
                rows.append({"type": "removed", "text": before})
            if after:
                rows.append({"type": "added", "text": after})
    return rows[:900]


def _apply_cost_mode_to_contract(contract, action, cost_mode="balanced"):
    policy = normalize_cost_mode(cost_mode)
    if policy == "balanced":
        return contract
    if policy == "fast":
        factor = 0.75
    else:
        return contract
    return {
        **contract,
        "max_tokens": max(100, int(contract["max_tokens"] * factor)),
        "max_words": max(30, int(contract["max_words"] * factor)),
    }


def action_output_contract(action, selected_text="", cost_mode="balanced"):
    selected_words = _word_count(selected_text)
    policy = normalize_cost_mode(cost_mode)
    if action == "rewrite":
        if policy == "deep":
            max_words = max(70, min(1200, int(max(selected_words, 40) * 1.15)))
        elif policy == "balanced":
            max_words = max(70, min(760, int(max(selected_words, 40) * 1.18)))
        else:
            max_words = max(70, min(420, int(max(selected_words, 40) * 1.25)))
        return _apply_cost_mode_to_contract({
            "max_tokens": max(180, min(2200 if policy == "deep" else 1300 if policy == "balanced" else 560, int(max_words * 1.7))),
            "max_words": max_words,
            "instruction": (
                "Output only the rewritten selection. Keep the same scope, same moment, and close to the original length. "
                "Do not add new scenes, new sections, explanations, headings, or continuation."
            ),
        }, action, cost_mode)
    if action == "improve":
        if policy == "deep":
            max_words = max(70, min(1200, int(max(selected_words, 40) * 1.08)))
        elif policy == "balanced":
            max_words = max(70, min(720, int(max(selected_words, 40) * 1.1)))
        else:
            max_words = max(70, min(380, int(max(selected_words, 40) * 1.2)))
        return _apply_cost_mode_to_contract({
            "max_tokens": max(180, min(2200 if policy == "deep" else 1250 if policy == "balanced" else 520, int(max_words * 1.7))),
            "max_words": max_words,
            "instruction": (
                "Output only the improved selection. Keep the same meaning, same scope, and similar length. "
                "Do not expand into additional plot, argument, or explanation."
            ),
        }, action, cost_mode)
    if action == "expand":
        if policy == "deep":
            max_words = max(110, min(1400, int(max(selected_words, 50) * 1.8)))
        elif policy == "balanced":
            max_words = max(110, min(900, int(max(selected_words, 50) * 1.85)))
        else:
            max_words = max(110, min(650, int(max(selected_words, 50) * 2.1)))
        return _apply_cost_mode_to_contract({
            "max_tokens": max(260, min(2400 if policy == "deep" else 1500 if policy == "balanced" else 900, int(max_words * 1.65))),
            "max_words": max_words,
            "instruction": (
                "Output only the expanded version of the selected passage. Add depth, texture, or clarity, "
                "but stay within the same moment or idea."
            ),
        }, action, cost_mode)
    if action == "summarize":
        max_words = max(35, min(130, int(max(selected_words, 60) * 0.45))) if selected_words else 130
        return _apply_cost_mode_to_contract({
            "max_tokens": max(110, min(240, int(max_words * 1.8))),
            "max_words": max_words,
            "instruction": (
                "Output only the shorter summary text. If selected text exists, summarize only that selection, "
                "in the same language, as one compact paragraph. Do not say 'the passage', 'the text', "
                "'the selected text', or speak to the author. Do not rewrite, continue, explain, or use bullets."
            ),
        }, action, cost_mode)
    if action == "outline":
        return _apply_cost_mode_to_contract({
            "max_tokens": 850,
            "max_words": 520,
            "instruction": "Output a compact outline with clear next sections. Keep it practical and skimmable.",
        }, action, cost_mode)
    if action == "custom":
        selected_words = selected_words or 140
        if policy == "deep":
            max_words = max(90, min(1400, int(selected_words * 1.4)))
        elif policy == "balanced":
            max_words = max(90, min(900, int(selected_words * 1.35)))
        else:
            max_words = max(90, min(650, int(selected_words * 1.8)))
        return _apply_cost_mode_to_contract({
            "max_tokens": max(220, min(2400 if policy == "deep" else 1500 if policy == "balanced" else 950, int(max_words * 1.7))),
            "max_words": max_words,
            "instruction": (
                "Follow the user's instruction exactly. Return only the resulting manuscript text, summary, outline, "
                "or replacement requested by the user. Do not include commentary, reasoning, labels, or prefaces."
            ),
        }, action, cost_mode)
    return _apply_cost_mode_to_contract({
        "max_tokens": 650,
        "max_words": 420,
        "instruction": "Output a short continuation only. Continue naturally from the cursor and stop before a new major beat.",
    }, action, cost_mode)


def enforce_action_length(text, action, selected_text="", cost_mode="balanced"):
    contract = action_output_contract(action, selected_text, cost_mode)
    max_words = contract["max_words"]
    words = re.findall(r"\S+", text or "")
    if len(words) <= max_words:
        return (text or "").strip()

    clipped = " ".join(words[:max_words]).strip()
    sentence_end = max(clipped.rfind("."), clipped.rfind("!"), clipped.rfind("?"))
    if sentence_end > max(80, len(clipped) * 0.6):
        clipped = clipped[:sentence_end + 1]
    return clipped.strip()


class DeepSeekClient:
    def __init__(self):
        self.api_key = settings.DEEPSEEK_API_KEY
        self.model = settings.DEEPSEEK_MODEL
        self.base_url = settings.DEEPSEEK_API_BASE_URL.rstrip("/")
        self.timeout = settings.DEEPSEEK_TIMEOUT
        self.last_usage = {}

    def chat(self, messages, *, json_response=False, max_tokens=1800, temperature=0.7):
        if not self.api_key:
            raise AIConfigurationError("AI is not configured. Add DEEPSEEK_API_KEY to your environment.")

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "thinking": {"type": "disabled"},
        }
        if json_response:
            payload["response_format"] = {"type": "json_object"}

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout as exc:
            raise AIServiceError("AI request timed out. Please try again.") from exc
        except requests.exceptions.RequestException as exc:
            raise AIServiceError("AI request failed. Please try again.") from exc

        if response.status_code >= 400:
            raise AIServiceError(f"AI provider returned HTTP {response.status_code}.")

        try:
            data = response.json()
            self.last_usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
            return data["choices"][0]["message"]["content"].strip()
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise AIServiceError("AI provider returned an unexpected response.") from exc


def analyze_manuscript(manuscript, client=None):
    text = extract_tiptap_text(manuscript.content, max_chars=45000)
    headings = extract_tiptap_headings(manuscript.content)
    client = client or DeepSeekClient()

    messages = [
        {
            "role": "system",
            "content": (
                "You analyze manuscripts for an AI book-writing app. Return only valid JSON with "
                "two top-level keys: ai_profile and ai_memory. ai_profile must contain genre, tone, "
                "target_audience, language, book_type, style_notes. ai_memory must contain "
                "book_summary, chapter_summaries, characters, locations, timeline_notes, consistency_notes, "
                "claims, themes, terms, reader_promises, open_threads. Adapt the memory to the book type: "
                "fiction should emphasize character, scene, timeline, and open plot threads; nonfiction should "
                "emphasize claims, definitions, examples, reader promises, and argument flow; memoir should "
                "emphasize chronology, relationships, reflection, and factual care; poetry should emphasize "
                "imagery, form, motifs, rhythm, and recurring language."
            ),
        },
        {
            "role": "user",
            "content": json.dumps({
                "title": manuscript.title,
                "headings": headings,
                "manuscript_excerpt": text,
            }, ensure_ascii=False),
        },
    ]
    content = client.chat(messages, json_response=True, max_tokens=2200, temperature=0.2)
    data = _extract_json_object(content)
    return normalize_profile(data.get("ai_profile", {})), normalize_memory(data.get("ai_memory", {}))


def _generate_single_draft(
    manuscript,
    action,
    selected_text="",
    cursor_context="",
    user_prompt="",
    regeneration_instruction="",
    cost_mode="",
    client=None,
    chunk_instruction="",
    coverage=None,
):
    if action not in ACTION_INSTRUCTIONS:
        raise AIServiceError("Unknown AI action.")
    user_prompt = (user_prompt or "").strip()
    custom_intent = infer_custom_prompt_intent(user_prompt, selected_text) if action == "custom" else None
    if action == "custom" and not user_prompt:
        raise AIServiceError("Add an instruction before sending.")

    cost_mode = normalize_cost_mode(cost_mode or getattr(manuscript, "ai_cost_mode", "balanced"))
    context = build_generation_context(
        manuscript,
        action,
        selected_text=selected_text,
        cursor_context=cursor_context,
        user_prompt=user_prompt,
        cost_mode=cost_mode,
    )
    payload = context["payload"]
    payload["instruction"] = ACTION_INSTRUCTIONS[action]
    if custom_intent:
        payload["custom_prompt_intent"] = custom_intent
        payload["instruction"] = f"{payload['instruction']} {custom_intent['instruction']}"
    regeneration_instruction = (regeneration_instruction or "").strip()
    if regeneration_instruction:
        payload["regeneration_instruction"] = regeneration_instruction
        payload["instruction"] = f"{payload['instruction']} Regenerate with this extra direction: {regeneration_instruction}."
    chunk_instruction = (chunk_instruction or "").strip()
    if chunk_instruction:
        payload["chunk_instruction"] = chunk_instruction
        payload["instruction"] = f"{payload['instruction']} {chunk_instruction}"
    output_contract = action_output_contract(action, selected_text, cost_mode)
    payload["output_contract"] = {
        "max_words": output_contract["max_words"],
        "instruction": output_contract["instruction"],
    }
    context["context_summary"]["input_chars"] = len(json.dumps(payload, ensure_ascii=False))
    client = client or DeepSeekClient()

    messages = [
        {
            "role": "system",
            "content": (
                "You are Xanula's book-writing assistant. Write useful manuscript-ready prose. "
                "Respect the author's confirmed book profile, memory, voice profile, chapter map, and continuity clues. "
                "Use the supplied book_lens to adapt to the genre or book type. "
                "Do not mention that you are an AI. Return only the requested draft text, without explanations unless "
                "the requested action is a summary or outline. Do not include internal thoughts, reasoning, analysis, "
                "planning notes, prefaces, or labels like Thought/Reasoning/Analysis. Do not invent major facts that "
                "contradict the supplied memory. Obey the output_contract exactly; selected-text actions must stay "
                "inside the selected text's scope and must not become a continuation. For custom prompts, the user_prompt "
                "is an instruction, not manuscript text to quote back, unless they explicitly ask you to use its wording."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False),
        },
    ]
    draft = clean_ai_draft(client.chat(
        messages,
        max_tokens=min(
            getattr(settings, "REEPLS_AI_MAX_OUTPUT_TOKENS", 1800),
            output_contract["max_tokens"],
        ),
        temperature=0.75,
    ))
    draft = enforce_action_length(draft, action, selected_text, cost_mode)
    safety_warnings = validate_output(action, draft, selected_text, payload.get("entities", {}))
    consistency_report = check_consistency(
        draft,
        manuscript,
        action=action,
        selected_text=selected_text,
        retrieved_sections=context.get("retrieved_sections", []),
    )
    consistency_warnings = [
        f"{issue.get('message')} {issue.get('reason')}".strip()
        for issue in consistency_report.get("issues", [])
    ]
    placement = custom_intent["placement"] if custom_intent else ""
    intent_preview = intent_preview_for(action, user_prompt, selected_text, placement)
    placement = intent_preview.get("placement", placement)
    diff_available = bool(selected_text and intent_preview.get("placement") == "replace_selection")
    suggestion_diff = build_word_diff(selected_text, draft) if diff_available else []
    context["agent_steps"] = [
        *context["agent_steps"],
        {
            "name": "Consistency Agent",
            "status": "warning" if consistency_report.get("issues") else "ready",
            "detail": consistency_warnings[0] if consistency_warnings else "Checked retrieved context.",
        },
        {"name": "Safety Agent", "status": "ready", "detail": safety_warnings[-1] if safety_warnings else "Checked suggestion."},
    ]
    context["usage"] = record_usage(
        manuscript.ai_usage,
        action,
        context["context_summary"].get("input_chars", 0),
        len(draft),
        context["usage_hint"],
    )
    engine_state = build_longform_engine_state(
        manuscript,
        consistency_report=consistency_report,
        context_summary=context["context_summary"],
    )
    return {
        "draft": draft,
        "placement": placement,
        "intent_preview": intent_preview,
        "diff_available": diff_available,
        "suggestion_diff": suggestion_diff,
        "agent_steps": context["agent_steps"],
        "usage_hint": context["usage_hint"],
        "safety_warnings": [*consistency_warnings, *safety_warnings],
        "consistency_report": consistency_report,
        "engine_state": engine_state,
        "memory_freshness": memory_freshness(manuscript.ai_memory_meta, manuscript.ai_memory_stale),
        "chapter_memory": normalize_chapter_memory(manuscript.ai_chapter_memory),
        "cost_mode": cost_mode,
        "context_summary": {
            **context["context_summary"],
            "provider_usage": getattr(client, "last_usage", {}) or {},
            "coverage": coverage or selection_coverage_for(action, selected_text, user_prompt, cost_mode),
        },
        "usage": context["usage"],
    }


def _merge_provider_usage(usages):
    merged = {}
    for usage in usages:
        if not isinstance(usage, dict):
            continue
        for key, value in usage.items():
            if isinstance(value, (int, float)):
                merged[key] = merged.get(key, 0) + value
    return merged


def _generate_chunked_draft(manuscript, action, selected_text="", cursor_context="", user_prompt="", regeneration_instruction="", cost_mode="", client=None, coverage=None):
    chunks = sentence_aware_chunks(selected_text, coverage.get("chunk_chars") if coverage else 12000)
    if not chunks:
        raise AIServiceError("The selected text is empty.")
    client = client or DeepSeekClient()
    drafts = []
    input_chars = 0
    provider_usages = []
    chunk_steps = []
    for index, chunk in enumerate(chunks, start=1):
        previous_tail = chunks[index - 2][-500:] if index > 1 else ""
        next_head = chunks[index][:500] if index < len(chunks) else ""
        chunk_instruction = (
            f"Process chunk {index} of {len(chunks)} from a larger selected passage. "
            "Return only the transformed text for this chunk, not the surrounding chunks. "
            "Preserve continuity with adjacent chunk context. "
            f"Previous chunk ending: {previous_tail!r}. Next chunk beginning: {next_head!r}."
        )
        result = _generate_single_draft(
            manuscript,
            action,
            selected_text=chunk,
            cursor_context=cursor_context,
            user_prompt=user_prompt,
            regeneration_instruction=regeneration_instruction,
            cost_mode=cost_mode,
            client=client,
            chunk_instruction=chunk_instruction,
            coverage={**(coverage or {}), "chunk_index": index, "chunk_count": len(chunks)},
        )
        draft = result.get("draft", "").strip()
        if not draft:
            raise AIServiceError(f"AI returned an empty result for chunk {index}. No tokens were deducted.")
        drafts.append(draft)
        summary = result.get("context_summary", {})
        input_chars += int(summary.get("input_chars", 0) or 0)
        provider_usages.append(summary.get("provider_usage", {}))
        chunk_steps.append({"name": "Writing Agent", "status": "ready", "detail": f"Processed chunk {index} of {len(chunks)}."})

    combined = "\n\n".join(drafts).strip()
    safety_warnings = validate_output(action, combined, selected_text, {})
    consistency_report = check_consistency(combined, manuscript, action=action, selected_text=selected_text)
    consistency_warnings = [
        f"{issue.get('message')} {issue.get('reason')}".strip()
        for issue in consistency_report.get("issues", [])
    ]
    custom_intent = infer_custom_prompt_intent(user_prompt, selected_text) if action == "custom" else None
    placement = custom_intent["placement"] if custom_intent else ""
    intent_preview = intent_preview_for(action, user_prompt, selected_text, placement)
    placement = intent_preview.get("placement", placement)
    diff_available = bool(selected_text and intent_preview.get("placement") == "replace_selection")
    context_summary = {
        "policy": cost_mode,
        "usage_hint": f"{cost_mode} chunked context",
        "input_chars": input_chars,
        "selected_chars": len(selected_text),
        "original_selected_chars": len(selected_text),
        "selection_limit_chars": coverage.get("limit_chars", 0) if coverage else 0,
        "selection_truncated": False,
        "cursor_chars": len(cursor_context or ""),
        "prompt_chars": len(user_prompt or ""),
        "excerpt_chars": 0,
        "current_section": "",
        "retrieved_sections": 0,
        "chunk_count": len(chunks),
        "coverage": coverage or {},
        "provider_usage": _merge_provider_usage(provider_usages),
    }
    return {
        "draft": combined,
        "placement": placement,
        "intent_preview": intent_preview,
        "diff_available": diff_available,
        "suggestion_diff": build_word_diff(selected_text, combined) if diff_available else [],
        "agent_steps": [
            {"name": "Context Agent", "status": "ready", "detail": f"Prepared {len(chunks)} chunks."},
            {"name": "Voice Agent", "status": "ready", "detail": "Loaded local voice profile."},
            *chunk_steps,
            {
                "name": "Consistency Agent",
                "status": "warning" if consistency_report.get("issues") else "ready",
                "detail": consistency_warnings[0] if consistency_warnings else "Checked combined suggestion.",
            },
            {"name": "Safety Agent", "status": "ready", "detail": safety_warnings[-1] if safety_warnings else "Checked combined suggestion."},
        ],
        "usage_hint": f"{cost_mode} chunked context",
        "safety_warnings": [*consistency_warnings, *safety_warnings],
        "consistency_report": consistency_report,
        "engine_state": build_longform_engine_state(manuscript, consistency_report=consistency_report, context_summary=context_summary),
        "memory_freshness": memory_freshness(manuscript.ai_memory_meta, manuscript.ai_memory_stale),
        "chapter_memory": normalize_chapter_memory(manuscript.ai_chapter_memory),
        "cost_mode": cost_mode,
        "context_summary": context_summary,
        "usage": record_usage(manuscript.ai_usage, action, input_chars, len(combined), f"{cost_mode} chunked context"),
    }


def generate_draft(manuscript, action, selected_text="", cursor_context="", user_prompt="", regeneration_instruction="", cost_mode="", client=None):
    if action not in ACTION_INSTRUCTIONS:
        raise AIServiceError("Unknown AI action.")
    cost_mode = normalize_cost_mode(cost_mode or getattr(manuscript, "ai_cost_mode", "balanced"))
    coverage = selection_coverage_for(action, selected_text, user_prompt, cost_mode)
    if not coverage.get("allowed"):
        raise AISelectionCoverageError(coverage)
    if coverage.get("chunking_available") and coverage.get("estimated_chunks", 1) > 1:
        return _generate_chunked_draft(
            manuscript,
            action,
            selected_text=selected_text,
            cursor_context=cursor_context,
            user_prompt=user_prompt,
            regeneration_instruction=regeneration_instruction,
            cost_mode=cost_mode,
            client=client,
            coverage=coverage,
        )
    return _generate_single_draft(
        manuscript,
        action,
        selected_text=selected_text,
        cursor_context=cursor_context,
        user_prompt=user_prompt,
        regeneration_instruction=regeneration_instruction,
        cost_mode=cost_mode,
        client=client,
        coverage=coverage,
    )
