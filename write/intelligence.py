import json
import math
import re
from collections import Counter

from django.conf import settings


DEFAULT_VOICE = {
    "sentence_rhythm": "",
    "average_sentence_words": 0,
    "average_paragraph_words": 0,
    "dialogue_ratio": 0,
    "descriptive_density": "",
    "vocabulary_level": "",
    "pov_tense_clues": "",
    "reading_level": "",
    "book_lens": "",
    "genre_signals": [],
    "continuity_priorities": [],
    "style_warnings": [],
}

DEFAULT_CHAPTER_MAP = {
    "total_words": 0,
    "section_count": 0,
    "headings": [],
    "sections": [],
}

DEFAULT_ENTITIES = {
    "characters": [],
    "locations": [],
    "dates": [],
    "proper_nouns": [],
    "relationship_hints": [],
    "unresolved_unknowns": [],
}

DEFAULT_CONSISTENCY = {
    "status": "clear",
    "issues": [],
    "retrieved_sections": [],
    "reviewed_action": "",
}

DEFAULT_USAGE = {
    "request_count": 0,
    "input_chars": 0,
    "output_chars": 0,
    "actions": {},
    "last_request": {},
}

DEFAULT_MEMORY_META = {
    "version": 0,
    "last_refreshed_at": "",
    "last_refreshed_words": 0,
    "source": "",
}

DEFAULT_CHAPTER_MEMORY = {
    "sections": [],
    "version": 0,
}

DEFAULT_STALE = {
    "is_stale": False,
    "changed_words": 0,
    "changed_chars": 0,
    "reason": "",
    "last_analyzed_words": 0,
}

LONGFORM_TARGET_CHARS = 700000
SECTION_CHUNK_CHARS = 2400
MAX_INDEXED_CHUNKS = 360
COST_MODES = {"fast", "balanced", "deep"}
SELECTION_TRANSFORM_ACTIONS = {"rewrite", "expand", "improve", "summarize"}
DEEP_SELECTION_CHUNK_CHARS = 12000
DEEP_SELECTION_MAX_CHARS = 60000
BALANCED_SELECTION_MAX_CHARS = 18000
CUSTOM_SELECTION_REPLACEMENT_TERMS = {
    "rewrite", "improve", "polish", "shorten", "condense", "summarize", "summary",
    "expand this", "expand it", "fix", "edit", "revise", "change this", "replace",
}

ACTION_AGENT_LABELS = {
    "continue": "Continuing from cursor",
    "rewrite": "Rewriting selection",
    "expand": "Expanding selection",
    "improve": "Improving style",
    "summarize": "Summarizing context",
    "outline": "Planning outline",
    "custom": "Following your instruction",
}

REPLACEMENT_ACTIONS = {"rewrite", "expand", "improve"}
COMMON_CAPITALIZED = {
    "A", "An", "And", "As", "At", "But", "By", "For", "From", "He", "Her", "His", "I",
    "In", "It", "Its", "Of", "On", "Or", "She", "So", "That", "The", "Their", "Then",
    "They", "This", "To", "We", "When", "Where", "With", "You",
}

BOOK_LENSES = {
    "fiction": {
        "keywords": {"novel", "fiction", "fantasy", "romance", "thriller", "mystery", "sci-fi", "science fiction", "horror", "literary"},
        "priorities": ["character continuity", "scene causality", "timeline", "POV and tense", "emotional arc"],
        "prompt": "Prioritize character continuity, scene causality, emotional arc, POV, tense, and natural scene flow.",
    },
    "memoir": {
        "keywords": {"memoir", "autobiography", "biography", "life story", "personal essay"},
        "priorities": ["truthful personal voice", "timeline", "relationships", "reflection", "emotional honesty"],
        "prompt": "Prioritize truthful personal voice, chronology, relationships, reflection, and emotional honesty.",
    },
    "nonfiction": {
        "keywords": {"nonfiction", "guide", "manual", "history", "essay", "report", "analysis", "education"},
        "priorities": ["claim consistency", "argument flow", "definitions", "examples", "reader usefulness"],
        "prompt": "Prioritize claim consistency, argument flow, clear definitions, examples, and reader usefulness.",
    },
    "business": {
        "keywords": {"business", "startup", "marketing", "sales", "leadership", "management", "strategy"},
        "priorities": ["framework clarity", "actionability", "case examples", "reader outcome", "concise authority"],
        "prompt": "Prioritize practical frameworks, actionability, concise authority, case examples, and reader outcomes.",
    },
    "self_help": {
        "keywords": {"self-help", "self help", "personal development", "wellness", "productivity", "mindset"},
        "priorities": ["empathetic tone", "practical steps", "reader motivation", "examples", "ethical guidance"],
        "prompt": "Prioritize empathetic guidance, practical steps, reader motivation, examples, and ethical care.",
    },
    "academic": {
        "keywords": {"academic", "research", "thesis", "dissertation", "scholarly", "paper"},
        "priorities": ["argument rigor", "terms", "claims", "citation placeholders", "structure"],
        "prompt": "Prioritize argument rigor, precise terms, careful claims, citation placeholders when needed, and structure.",
    },
    "children": {
        "keywords": {"children", "kids", "middle grade", "young readers", "picture book"},
        "priorities": ["age suitability", "simple clarity", "warmth", "rhythm", "safe content"],
        "prompt": "Prioritize age suitability, simple clarity, warmth, rhythm, and safe content.",
    },
    "poetry": {
        "keywords": {"poetry", "poem", "poems", "verse", "collection"},
        "priorities": ["line rhythm", "imagery", "compression", "repetition", "form"],
        "prompt": "Prioritize line rhythm, imagery, compression, repetition, form, and musicality.",
    },
    "general": {
        "keywords": set(),
        "priorities": ["voice", "structure", "reader flow", "consistency"],
        "prompt": "Prioritize voice, structure, reader flow, and consistency.",
    },
}


def _word_count(text):
    return len(re.findall(r"\b[\w'-]+\b", text or ""))


def infer_book_lens(profile=None, text=""):
    profile = profile if isinstance(profile, dict) else {}
    profile_text = " ".join(
        str(profile.get(key, ""))
        for key in ("genre", "book_type", "target_audience", "tone", "style_notes")
    ).lower()
    sample_text = (text or "")[:8000].lower()
    combined = f"{profile_text} {sample_text}"
    scores = {}
    for lens, config in BOOK_LENSES.items():
        if lens == "general":
            continue
        scores[lens] = sum(1 for keyword in config["keywords"] if keyword in combined)

    if not any(scores.values()):
        if re.search(r'\b(chapter|scene|dialogue|protagonist|character)\b', combined):
            lens = "fiction"
        elif re.search(r'\b(step|framework|lesson|principle|guide|strategy)\b', combined):
            lens = "nonfiction"
        elif re.search(r'\b(stanza|line break|verse|metaphor)\b', combined):
            lens = "poetry"
        else:
            lens = "general"
    else:
        lens = max(scores, key=scores.get)

    config = BOOK_LENSES[lens]
    return {
        "lens": lens,
        "prompt": config["prompt"],
        "priorities": config["priorities"],
        "signals": [key for key, value in scores.items() if value],
    }


def _truncate(text, max_chars):
    text = (text or "").strip()
    if not max_chars or len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0].strip()
    return cut or text[:max_chars].strip()


def _sentence_stop(text):
    text = (text or "").strip()
    if not text:
        return ""
    matches = list(re.finditer(r"[^.!?\n]+[.!?][\"')\]]*", text))
    if matches:
        return matches[-1].group(0).strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines:
        return lines[-1][-220:].strip()
    return text[-220:].strip()


def sentence_aware_clip(text, max_chars):
    text = (text or "").strip()
    if not max_chars or len(text) <= max_chars:
        return text, _sentence_stop(text), False

    window = text[:max_chars]
    min_usable = max(160, int(max_chars * 0.35))
    cut = 0
    for match in re.finditer(r"[.!?][\"')\]]*(?:\s+|$)", window):
        if match.end() >= min_usable:
            cut = match.end()
    if not cut:
        para_cut = max(window.rfind("\n\n"), window.rfind("\n"))
        if para_cut >= min_usable:
            cut = para_cut
    if not cut:
        space_cut = window.rfind(" ")
        cut = space_cut if space_cut >= min_usable else max_chars

    clipped = text[:cut].strip()
    return clipped, _sentence_stop(clipped), True


def sentence_aware_chunks(text, max_chars):
    text = (text or "").strip()
    if not text:
        return []
    chunks = []
    remaining = text
    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining.strip())
            break
        chunk, _, _ = sentence_aware_clip(remaining, max_chars)
        if not chunk:
            chunk = remaining[:max_chars].strip()
        chunks.append(chunk)
        remaining = remaining[len(chunk):].strip()
    return [chunk for chunk in chunks if chunk]


def _selection_limit(action, cost_mode=None):
    base_limit, policy = _context_limit(action, cost_mode)
    if policy == "deep":
        configured = getattr(settings, "REEPLS_AI_DEEP_SELECTION_CHUNK_CHARS", DEEP_SELECTION_CHUNK_CHARS)
        if action in {"rewrite", "improve", "custom"}:
            return min(configured, 4500), policy
        if action == "expand":
            return min(configured, 3000), policy
        return configured, policy
    if policy == "balanced":
        if action in {"rewrite", "improve", "custom"}:
            return 2500, policy
        if action == "expand":
            return 1800, policy
        if action == "summarize":
            return min(6000, max(2500, math.floor(base_limit * 0.7))), policy
    return max(1200, math.floor(base_limit * 0.5)), policy


def _selection_uses_ai_coverage(action, selected_text="", user_prompt=""):
    if not (selected_text or "").strip():
        return False
    if action in SELECTION_TRANSFORM_ACTIONS:
        return True
    if action == "custom":
        return bool((user_prompt or "").strip())
    return False


def _selection_is_chunkable(action, user_prompt=""):
    if action in SELECTION_TRANSFORM_ACTIONS:
        return True
    if action != "custom":
        return False
    prompt = (user_prompt or "").lower()
    return any(term in prompt for term in CUSTOM_SELECTION_REPLACEMENT_TERMS)


def selection_coverage_for(action, selected_text="", user_prompt="", cost_mode=None):
    selected_text = (selected_text or "").strip()
    policy = normalize_cost_mode(cost_mode or getattr(settings, "REEPLS_AI_CONTEXT_POLICY", "balanced"))
    uses_selection = _selection_uses_ai_coverage(action, selected_text, user_prompt)
    limit, policy = _selection_limit(action, policy)
    selection_chars = len(selected_text)
    selection_words = len(re.findall(r"\S+", selected_text))
    clipped, stop_sentence, truncated = sentence_aware_clip(selected_text, limit)
    deep_max = getattr(settings, "REEPLS_AI_DEEP_MAX_SELECTION_CHARS", DEEP_SELECTION_MAX_CHARS)
    balanced_max = getattr(settings, "REEPLS_AI_BALANCED_MAX_SELECTION_CHARS", BALANCED_SELECTION_MAX_CHARS)

    coverage = {
        "allowed": True,
        "action": action,
        "cost_mode": policy,
        "uses_selection": uses_selection,
        "selection_chars": selection_chars,
        "selection_words": selection_words,
        "limit_chars": limit,
        "chunk_chars": limit if policy in {"balanced", "deep"} else 0,
        "usable_chars": len(clipped),
        "stop_sentence": stop_sentence,
        "recommended_mode": "",
        "chunking_available": False,
        "chunkable": _selection_is_chunkable(action, user_prompt),
        "estimated_chunks": 1 if selected_text else 0,
        "selection_truncated": False,
        "coverage_message": "",
    }
    if not uses_selection:
        coverage["coverage_message"] = "This action does not need to transform the selected text."
        return coverage
    if not truncated:
        coverage["coverage_message"] = f"{policy.title()} can cover the full selection."
        return coverage
    if policy in {"balanced", "deep"}:
        if not coverage["chunkable"]:
            coverage["allowed"] = False
            coverage["recommended_mode"] = "split_selection"
            coverage["coverage_message"] = (
                f"{policy.title()} can use a large custom selection when the instruction rewrites, summarizes, or expands it. "
                "For idea/context prompts, select a smaller passage so Reepls does not guess which parts matter."
            )
            return coverage
        max_chars = deep_max if policy == "deep" else balanced_max
        coverage["chunking_available"] = selection_chars <= max_chars
        coverage["estimated_chunks"] = math.ceil(selection_chars / max(limit, 1))
        coverage["limit_chars"] = max_chars
        coverage["chunk_chars"] = limit
        if selection_chars > max_chars:
            coverage["allowed"] = False
            coverage["recommended_mode"] = "split_selection" if policy == "deep" else "deep"
            coverage["coverage_message"] = (
                f"{policy.title()} can process up to {max_chars:,} selected characters at once. "
                + ("Switch to Deep or split this selection into smaller parts." if policy == "balanced" else "Split this selection into smaller parts and try again.")
            )
        else:
            coverage["coverage_message"] = (
                f"{policy.title()} will process the full selection in {coverage['estimated_chunks']} chunks. "
                "This may use more tokens."
            )
        return coverage

    coverage["allowed"] = False
    coverage["selection_truncated"] = True
    coverage["recommended_mode"] = "balanced" if policy == "fast" else "deep"
    coverage["coverage_message"] = (
        f"{policy.title()} can work with the first {len(clipped):,} characters of this selection. "
        f"It would stop after: \"{stop_sentence}\""
    )
    return coverage


def _inline_text(node):
    if not isinstance(node, dict):
        return ""
    node_type = node.get("type")
    if node_type == "text":
        return node.get("text", "")
    if node_type == "hardBreak":
        return "\n"
    return "".join(_inline_text(child) for child in node.get("content", []) if isinstance(child, dict))


def _block_lines(node, ordered_index=None):
    if not isinstance(node, dict):
        return []
    node_type = node.get("type")
    content = node.get("content", [])

    if node_type == "heading":
        text = _inline_text(node).strip()
        level = int(node.get("attrs", {}).get("level", 1) or 1)
        return [("#" * max(1, min(level, 6))) + f" {text}"] if text else []
    if node_type == "paragraph":
        text = _inline_text(node).strip()
        return [text] if text else []
    if node_type == "listItem":
        child_lines = []
        for child in content if isinstance(content, list) else []:
            child_lines.extend(_block_lines(child))
        text = " ".join(line.strip("- ").strip() for line in child_lines if line).strip()
        if not text:
            return []
        prefix = f"{ordered_index}. " if ordered_index else "- "
        return [prefix + text]
    if node_type == "orderedList":
        lines = []
        index = 1
        for child in content if isinstance(content, list) else []:
            if isinstance(child, dict) and child.get("type") == "listItem":
                lines.extend(_block_lines(child, ordered_index=index))
                index += 1
        return lines
    if node_type == "bulletList":
        lines = []
        for child in content if isinstance(content, list) else []:
            lines.extend(_block_lines(child))
        return lines
    if node_type == "horizontalRule":
        return ["---"]

    lines = []
    for child in content if isinstance(content, list) else []:
        lines.extend(_block_lines(child))
    return lines


def extract_text(content, max_chars=None):
    if not isinstance(content, dict):
        return ""
    lines = []
    for node in content.get("content", []) if isinstance(content.get("content", []), list) else []:
        lines.extend(_block_lines(node))
    return _truncate("\n\n".join(line for line in lines if line).strip(), max_chars)


def extract_blocks(content):
    if not isinstance(content, dict):
        return []
    blocks = []
    for index, node in enumerate(content.get("content", []) if isinstance(content.get("content", []), list) else []):
        lines = _block_lines(node)
        text = "\n".join(lines).strip()
        if not text:
            continue
        entry = {
            "index": index,
            "type": node.get("type"),
            "text": text,
            "words": _word_count(text),
        }
        if node.get("type") == "heading":
            entry["level"] = int(node.get("attrs", {}).get("level", 1) or 1)
            entry["title"] = _inline_text(node).strip()
        blocks.append(entry)
    return blocks


def normalize_voice(voice):
    data = dict(DEFAULT_VOICE)
    if isinstance(voice, dict):
        for key, default in data.items():
            value = voice.get(key, default)
            if isinstance(default, (int, float)):
                data[key] = value if isinstance(value, (int, float)) else default
            else:
                data[key] = value if isinstance(value, type(default)) else default
    return data


def normalize_chapter_map(chapter_map):
    data = dict(DEFAULT_CHAPTER_MAP)
    if isinstance(chapter_map, dict):
        data["total_words"] = int(chapter_map.get("total_words") or 0)
        data["section_count"] = int(chapter_map.get("section_count") or 0)
        data["headings"] = chapter_map.get("headings") if isinstance(chapter_map.get("headings"), list) else []
        data["sections"] = chapter_map.get("sections") if isinstance(chapter_map.get("sections"), list) else []
    return data


def normalize_entities(entities):
    data = dict(DEFAULT_ENTITIES)
    if isinstance(entities, dict):
        for key in data:
            value = entities.get(key, [])
            data[key] = value if isinstance(value, list) else []
    return data


def normalize_consistency(consistency):
    data = dict(DEFAULT_CONSISTENCY)
    if isinstance(consistency, dict):
        data["status"] = str(consistency.get("status") or "clear")
        data["issues"] = consistency.get("issues") if isinstance(consistency.get("issues"), list) else []
        data["retrieved_sections"] = consistency.get("retrieved_sections") if isinstance(consistency.get("retrieved_sections"), list) else []
        data["reviewed_action"] = str(consistency.get("reviewed_action") or "")
    return data


def normalize_usage(usage):
    data = dict(DEFAULT_USAGE)
    if isinstance(usage, dict):
        data["request_count"] = int(usage.get("request_count") or 0)
        data["input_chars"] = int(usage.get("input_chars") or 0)
        data["output_chars"] = int(usage.get("output_chars") or 0)
        data["actions"] = usage.get("actions") if isinstance(usage.get("actions"), dict) else {}
        data["last_request"] = usage.get("last_request") if isinstance(usage.get("last_request"), dict) else {}
    return data


def normalize_memory_meta(meta):
    data = dict(DEFAULT_MEMORY_META)
    if isinstance(meta, dict):
        data["version"] = int(meta.get("version") or 0)
        data["last_refreshed_at"] = str(meta.get("last_refreshed_at") or "")
        data["last_refreshed_words"] = int(meta.get("last_refreshed_words") or 0)
        data["source"] = str(meta.get("source") or "")
    return data


def next_memory_meta(previous_meta, content, source, timestamp=None):
    meta = normalize_memory_meta(previous_meta)
    meta["version"] += 1
    meta["last_refreshed_at"] = timestamp.isoformat() if timestamp else ""
    meta["last_refreshed_words"] = _word_count(extract_text(content))
    meta["source"] = source
    return meta


def memory_freshness(meta, stale):
    meta = normalize_memory_meta(meta)
    stale = normalize_stale(stale)
    if stale.get("is_stale"):
        label = "Refresh suggested"
    elif meta.get("version"):
        label = f"Memory v{meta['version']}"
    else:
        label = "Memory not refreshed"
    return {
        "label": label,
        "version": meta.get("version", 0),
        "last_refreshed_at": meta.get("last_refreshed_at", ""),
        "last_refreshed_words": meta.get("last_refreshed_words", 0),
        "source": meta.get("source", ""),
        "is_stale": stale.get("is_stale", False),
    }


def normalize_cost_mode(mode):
    normalized = str(mode or "").strip().lower()
    return normalized if normalized in COST_MODES else "balanced"


def normalize_chapter_memory(chapter_memory):
    data = dict(DEFAULT_CHAPTER_MEMORY)
    if isinstance(chapter_memory, dict):
        data["sections"] = chapter_memory.get("sections") if isinstance(chapter_memory.get("sections"), list) else []
        data["version"] = int(chapter_memory.get("version") or 0)
    return data


def normalize_stale(stale):
    data = dict(DEFAULT_STALE)
    if isinstance(stale, dict):
        data["is_stale"] = bool(stale.get("is_stale", False))
        data["changed_words"] = int(stale.get("changed_words") or 0)
        data["changed_chars"] = int(stale.get("changed_chars") or 0)
        data["reason"] = str(stale.get("reason") or "")
        data["last_analyzed_words"] = int(stale.get("last_analyzed_words") or 0)
    return data


def build_chapter_memory(content, existing_memory=None, version=0):
    chapter_map = analyze_structure(content)
    text = extract_text(content)
    sections = []
    indexed = build_section_index(content, max_sections=120)
    summary_lookup = {}
    if isinstance(existing_memory, dict):
        for item in existing_memory.get("chapter_summaries", []) if isinstance(existing_memory.get("chapter_summaries"), list) else []:
            if isinstance(item, dict):
                title = str(item.get("title") or item.get("chapter") or "").lower()
                if title:
                    summary_lookup[title] = str(item.get("summary") or item.get("text") or "")
            elif isinstance(item, str):
                summary_lookup.setdefault("", item)

    for section in chapter_map.get("sections", [])[:80]:
        title = section.get("title") or "Opening"
        related = [
            chunk for chunk in indexed
            if chunk.get("title", "").lower().startswith(title.lower())
        ][:3]
        sample = "\n\n".join(chunk.get("snippet", "") for chunk in related)
        entities = analyze_entities(sample)
        summary = summary_lookup.get(title.lower()) or _truncate(sample, 260)
        sections.append({
            "title": title,
            "level": section.get("level", 1),
            "word_count": section.get("word_count", 0),
            "summary": summary,
            "characters": entities.get("characters", [])[:10],
            "locations": entities.get("locations", [])[:8],
            "dates": entities.get("dates", [])[:8],
            "open_threads": _memory_items(existing_memory, "open_threads")[:6],
            "continuity_notes": _memory_items(existing_memory, "consistency_notes")[:6],
        })

    if not sections and text:
        entities = analyze_entities(text)
        sections.append({
            "title": "Opening",
            "level": 1,
            "word_count": _word_count(text),
            "summary": _truncate(text, 260),
            "characters": entities.get("characters", [])[:10],
            "locations": entities.get("locations", [])[:8],
            "dates": entities.get("dates", [])[:8],
            "open_threads": _memory_items(existing_memory, "open_threads")[:6],
            "continuity_notes": _memory_items(existing_memory, "consistency_notes")[:6],
        })
    return {
        "sections": sections,
        "version": int(version or 0),
    }


def analyze_structure(content):
    blocks = extract_blocks(content)
    headings = []
    sections = []
    current = None
    total_words = 0

    for block in blocks:
        total_words += block["words"]
        if block["type"] == "heading":
            heading = {
                "level": block.get("level", 1),
                "title": block.get("title", ""),
                "block_index": block["index"],
            }
            headings.append(heading)
            current = {
                "title": heading["title"],
                "level": heading["level"],
                "start_block": block["index"],
                "end_block": block["index"],
                "word_count": 0,
                "preview": "",
                "stale": False,
            }
            sections.append(current)
            continue
        if current is None:
            current = {
                "title": "Opening",
                "level": 1,
                "start_block": block["index"],
                "end_block": block["index"],
                "word_count": 0,
                "preview": "",
                "stale": False,
            }
            sections.append(current)
        current["end_block"] = block["index"]
        current["word_count"] += block["words"]
        if not current["preview"]:
            current["preview"] = _truncate(block["text"], 260)

    return {
        "total_words": total_words,
        "section_count": len(sections),
        "headings": headings[:80],
        "sections": sections[:80],
    }


def analyze_voice(text, profile=None):
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text or "") if p.strip()]
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]
    sentence_counts = [_word_count(sentence) for sentence in sentences if _word_count(sentence)]
    paragraph_counts = [_word_count(paragraph) for paragraph in paragraphs if _word_count(paragraph)]
    avg_sentence = round(sum(sentence_counts) / len(sentence_counts), 1) if sentence_counts else 0
    avg_paragraph = round(sum(paragraph_counts) / len(paragraph_counts), 1) if paragraph_counts else 0
    dialogue_chars = len(re.findall(r'["“”][^"“”]+["“”]', text or ""))
    dialogue_ratio = round(min(1, dialogue_chars / max(len(text or ""), 1)), 2)
    descriptive_density = "lean"
    if avg_sentence >= 22 or avg_paragraph >= 95:
        descriptive_density = "lush"
    elif avg_sentence >= 15 or avg_paragraph >= 55:
        descriptive_density = "moderate"
    vocab = "direct"
    unique_words = set(word.lower() for word in re.findall(r"\b[a-zA-Z]{4,}\b", text or ""))
    if len(unique_words) > 350:
        vocab = "varied"
    if len(unique_words) > 800:
        vocab = "rich"

    lower = f" {(text or '').lower()} "
    first_person = sum(lower.count(token) for token in [" i ", " me ", " my ", " we ", " our "])
    third_person = sum(lower.count(token) for token in [" he ", " she ", " they ", " his ", " her ", " their "])
    present = sum(lower.count(token) for token in [" is ", " are ", " does ", " says ", " goes ", " feels "])
    past = sum(lower.count(token) for token in [" was ", " were ", " did ", " said ", " went ", " felt "])
    pov = "first-person" if first_person > third_person else "third-person" if third_person else "unclear POV"
    tense = "past tense" if past >= present else "present tense" if present else "unclear tense"

    warnings = []
    if avg_sentence > 30:
        warnings.append("Long sentence rhythm detected.")
    if dialogue_ratio < 0.02 and _word_count(text) > 1000:
        warnings.append("Little dialogue detected.")

    reading_level = "general"
    if avg_sentence <= 10 and avg_paragraph <= 45:
        reading_level = "simple"
    elif avg_sentence >= 24 or avg_paragraph >= 110:
        reading_level = "advanced"
    lens = infer_book_lens(profile, text)

    return {
        "sentence_rhythm": "long and flowing" if avg_sentence >= 22 else "balanced" if avg_sentence >= 12 else "short and direct",
        "average_sentence_words": avg_sentence,
        "average_paragraph_words": avg_paragraph,
        "dialogue_ratio": dialogue_ratio,
        "descriptive_density": descriptive_density,
        "vocabulary_level": vocab,
        "pov_tense_clues": f"{pov}, {tense}",
        "reading_level": reading_level,
        "book_lens": lens["lens"],
        "genre_signals": lens["signals"],
        "continuity_priorities": lens["priorities"],
        "style_warnings": warnings,
    }


def analyze_entities(text):
    text = re.sub(r"\s+", " ", text or "")
    proper = Counter()
    for match in re.findall(r"\b[A-Z][a-z]+(?: [A-Z][a-z]+){0,2}\b", text):
        if match in COMMON_CAPITALIZED:
            continue
        first = match.split()[0]
        if first in COMMON_CAPITALIZED:
            continue
        proper[match] += 1
        for part in match.split():
            if part not in COMMON_CAPITALIZED:
                proper[part] += 1
    dates = Counter(re.findall(r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}|January|February|March|April|May|June|July|August|September|October|November|December)\b", text))
    location_hints = Counter()
    for match in re.findall(r"\b(?:in|at|near|from|to) ([A-Z][a-z]+(?: [A-Z][a-z]+){0,2})", text):
        if match not in COMMON_CAPITALIZED:
            location_hints[match] += 1
    relationships = []
    for match in re.findall(r"\b([A-Z][a-z]+) (?:and|with) ([A-Z][a-z]+)\b", text):
        if match[0] not in COMMON_CAPITALIZED and match[1] not in COMMON_CAPITALIZED:
            relationships.append(f"{match[0]} and {match[1]}")

    top_proper = [name for name, _count in proper.most_common(40)]
    return {
        "characters": top_proper[:20],
        "locations": [name for name, _count in location_hints.most_common(20)],
        "dates": [date for date, _count in dates.most_common(20)],
        "proper_nouns": top_proper,
        "relationship_hints": relationships[:20],
        "unresolved_unknowns": [],
    }


def inspect_content(content, existing_stale=None, profile=None):
    text = extract_text(content)
    chapter_map = analyze_structure(content)
    return {
        "voice": analyze_voice(text, profile=profile),
        "chapter_map": chapter_map,
        "entities": analyze_entities(text),
        "stale": {
            **normalize_stale(existing_stale),
            "last_analyzed_words": chapter_map["total_words"],
        },
        "warnings": _inspect_warnings(text, chapter_map),
    }


def _inspect_warnings(text, chapter_map):
    warnings = []
    if not text:
        warnings.append("The manuscript is empty, so book awareness is limited.")
    if chapter_map["section_count"] == 0 and chapter_map["total_words"] > 800:
        warnings.append("No chapter headings detected yet.")
    if chapter_map["total_words"] > 0 and chapter_map["total_words"] < 120:
        warnings.append("Very little manuscript text is available, so voice detection is early.")
    return warnings


def mark_stale_from_change(previous_content, next_content, previous_stale):
    previous_text = extract_text(previous_content)
    next_text = extract_text(next_content)
    changed_chars = abs(len(next_text) - len(previous_text))
    changed_words = abs(_word_count(next_text) - _word_count(previous_text))
    stale = normalize_stale(previous_stale)
    stale["changed_chars"] += changed_chars
    stale["changed_words"] += changed_words
    if stale["changed_words"] >= 80 or stale["changed_chars"] >= 1000:
        stale["is_stale"] = True
        stale["reason"] = "The manuscript changed enough that memory may need a refresh."
    return stale


def reset_stale_for(content):
    words = _word_count(extract_text(content))
    return {
        "is_stale": False,
        "changed_words": 0,
        "changed_chars": 0,
        "reason": "",
        "last_analyzed_words": words,
    }


def _current_section(chapter_map, cursor_context):
    sections = chapter_map.get("sections", [])
    if not sections:
        return {}
    if not cursor_context:
        return sections[-1]
    cursor_words = set(word.lower() for word in re.findall(r"\b[a-zA-Z]{4,}\b", cursor_context))
    best = None
    best_score = -1
    for section in sections:
        section_words = set(word.lower() for word in re.findall(r"\b[a-zA-Z]{4,}\b", section.get("preview", "")))
        score = len(cursor_words & section_words)
        if score > best_score:
            best = section
            best_score = score
    return best or sections[-1]


def _keywords(text, limit=80):
    words = []
    stop = {
        "about", "after", "again", "against", "also", "because", "before", "between",
        "could", "every", "from", "have", "into", "just", "like", "more", "only",
        "other", "should", "some", "that", "their", "there", "these", "they", "this",
        "through", "with", "would", "your",
    }
    for word in re.findall(r"\b[a-zA-Z][a-zA-Z'-]{3,}\b", text or ""):
        lower = word.lower()
        if lower not in stop:
            words.append(lower)
    return [word for word, _count in Counter(words).most_common(limit)]


def _chunk_text(text, max_chars=SECTION_CHUNK_CHARS):
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks = []
    current = ""
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
    for paragraph in paragraphs or [text]:
        if len(paragraph) > max_chars:
            sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", paragraph) if part.strip()]
            for sentence in sentences or [paragraph]:
                if len(current) + len(sentence) + 1 <= max_chars:
                    current = f"{current} {sentence}".strip()
                else:
                    if current:
                        chunks.append(current)
                    current = sentence[:max_chars].strip()
                    remainder = sentence[max_chars:].strip()
                    while remainder:
                        chunks.append(current)
                        current = remainder[:max_chars].strip()
                        remainder = remainder[max_chars:].strip()
            continue

        if len(current) + len(paragraph) + 2 <= max_chars:
            current = f"{current}\n\n{paragraph}".strip()
        else:
            if current:
                chunks.append(current)
            current = paragraph
    if current:
        chunks.append(current)
    return chunks


def build_section_index(content, max_sections=MAX_INDEXED_CHUNKS):
    blocks = extract_blocks(content)
    sections = []
    current = None
    for block in blocks:
        if block["type"] == "heading":
            current = {
                "title": block.get("title") or f"Section {len(sections) + 1}",
                "level": block.get("level", 1),
                "start_block": block["index"],
                "end_block": block["index"],
                "text": "",
                "word_count": 0,
            }
            sections.append(current)
            continue
        if current is None:
            current = {
                "title": "Opening",
                "level": 1,
                "start_block": block["index"],
                "end_block": block["index"],
                "text": "",
                "word_count": 0,
            }
            sections.append(current)
        current["end_block"] = block["index"]
        current["text"] = f"{current['text']}\n\n{block['text']}".strip()
        current["word_count"] += block["words"]

    indexed = []
    for index, section in enumerate(sections):
        text = section.get("text", "")
        chunks = _chunk_text(text)
        if not chunks:
            continue
        for chunk_index, chunk in enumerate(chunks, start=1):
            if len(indexed) >= max_sections:
                return indexed
            entities = analyze_entities(chunk)
            chunk_count = len(chunks)
            title = section.get("title") or f"Section {index + 1}"
            if chunk_count > 1:
                title = f"{title}, part {chunk_index}"
            indexed.append({
                "id": f"section-{index + 1}-part-{chunk_index}",
                "title": title,
                "level": section.get("level", 1),
                "start_block": section.get("start_block", 0),
                "end_block": section.get("end_block", 0),
                "word_count": _word_count(chunk),
                "keywords": _keywords(chunk, 70),
                "proper_nouns": entities.get("proper_nouns", [])[:28],
                "dates": entities.get("dates", [])[:12],
                "snippet": _truncate(chunk, 1000),
            })
    return indexed


def retrieve_relevant_sections(content, query_text="", entities=None, limit=5):
    index = build_section_index(content)
    if not index:
        return []
    query_terms = set(_keywords(query_text, 80))
    query_analysis = analyze_entities(query_text)
    query_entities = set(query_analysis.get("proper_nouns", []))
    query_dates = set(query_analysis.get("dates", []))
    if isinstance(entities, dict):
        query_entities |= set(entities.get("proper_nouns", [])[:40])
    scored = []
    for section in index:
        score = 0
        score += len(query_terms & set(section.get("keywords", []))) * 2
        score += len(query_entities & set(section.get("proper_nouns", []))) * 4
        if section.get("dates"):
            score += len(set(section["dates"]) & query_dates) * 3
        title = section.get("title", "").lower()
        if title and title in (query_text or "").lower():
            score += 2
        if score:
            scored.append((score, section))

    if not scored:
        return index[-min(limit, len(index)):]
    scored.sort(key=lambda item: item[0], reverse=True)
    return [section for _score, section in scored[:limit]]


def build_longform_engine_state(manuscript, consistency_report=None, context_summary=None):
    text = extract_text(manuscript.content)
    chapter_map = normalize_chapter_map(manuscript.ai_chapter_map) if manuscript.ai_chapter_map else analyze_structure(manuscript.content)
    stale = normalize_stale(manuscript.ai_memory_stale)
    consistency = normalize_consistency(consistency_report or manuscript.ai_consistency)
    indexed_sections = build_section_index(manuscript.content)
    issues = consistency.get("issues", [])
    high_or_review = [issue for issue in issues if issue.get("severity") in {"high", "review"}]
    warnings = []

    if not manuscript.ai_profile_confirmed:
        warnings.append("Confirm the book profile before relying on longform writing.")
    if stale.get("is_stale"):
        warnings.append(stale.get("reason") or "Memory may need a refresh.")
    if not chapter_map.get("section_count") and chapter_map.get("total_words", 0) > 800:
        warnings.append("Add chapter or section headings so retrieval can stay precise.")
    if high_or_review:
        warnings.append("Resolve continuity warnings before accepting major new passages.")
    if len(text) > LONGFORM_TARGET_CHARS and len(indexed_sections) >= MAX_INDEXED_CHUNKS:
        warnings.append("The manuscript is beyond the current index window; refresh memory around major milestones.")

    score = 100
    if not manuscript.ai_profile_confirmed:
        score -= 15
    if stale.get("is_stale"):
        score -= 18
    score -= min(24, len(high_or_review) * 8)
    if chapter_map.get("total_words", 0) > 800 and not chapter_map.get("section_count"):
        score -= 12
    score = max(0, score)

    if high_or_review:
        readiness = "needs_review"
    elif not manuscript.ai_profile_confirmed:
        readiness = "needs_profile_confirmation"
    elif stale.get("is_stale"):
        readiness = "needs_memory_refresh"
    elif warnings:
        readiness = "ready_with_warnings"
    else:
        readiness = "ready"

    next_actions = []
    if not manuscript.ai_profile_confirmed:
        next_actions.append("Confirm or edit the book profile.")
    if stale.get("is_stale"):
        next_actions.append("Refresh memory before broad planning or major continuation.")
    if high_or_review:
        next_actions.append("Review the latest continuity warnings before confirming AI text.")
    if not next_actions:
        next_actions.append("Use Continue, Rewrite, Expand, Summarize, or Outline with retrieved context.")

    return {
        "readiness": readiness,
        "integrity_score": score,
        "target_characters": LONGFORM_TARGET_CHARS,
        "current_characters": len(text),
        "current_words": _word_count(text),
        "progress_ratio": round(min(1, len(text) / LONGFORM_TARGET_CHARS), 4),
        "chapter_count": chapter_map.get("section_count", 0),
        "indexed_chunks": len(indexed_sections),
        "index_limit": MAX_INDEXED_CHUNKS,
        "retrieval": {
            "chunk_chars": SECTION_CHUNK_CHARS,
            "strategy": "section-aware local retrieval",
            "last_retrieved_sections": (context_summary or {}).get("retrieved_sections", len(consistency.get("retrieved_sections", []))),
        },
        "memory_freshness": memory_freshness(manuscript.ai_memory_meta, manuscript.ai_memory_stale),
        "cost_mode": normalize_cost_mode(getattr(manuscript, "ai_cost_mode", "balanced")),
        "continuity": {
            "status": consistency.get("status", "clear"),
            "issue_count": len(issues),
            "review_issue_count": len(high_or_review),
        },
        "warnings": warnings[:5],
        "next_actions": next_actions[:4],
        "autonomy_contract": "draft-first: agents can plan, retrieve, check, and suggest, but manuscript text changes only after confirmation.",
    }


def _fact_states(text):
    states = {}
    for match in re.finditer(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+){0,2})\s+(?:is|was|were|became|becomes)\s+(alive|dead|married|single|pregnant|missing|injured|blind|deaf|ill|sick)\b", text or "", flags=re.IGNORECASE):
        name = match.group(1).strip()
        value = match.group(2).lower()
        if name.split()[0] not in COMMON_CAPITALIZED:
            states.setdefault(name, set()).add(value)
    return states


def _memory_items(memory, key):
    if not isinstance(memory, dict):
        return []
    value = memory.get(key, [])
    if isinstance(value, list):
        return [json.dumps(item, ensure_ascii=False) if isinstance(item, dict) else str(item) for item in value]
    if isinstance(value, str) and value:
        return [value]
    return []


def check_consistency(draft, manuscript, action="", selected_text="", retrieved_sections=None):
    draft = draft or ""
    retrieved_sections = retrieved_sections or []
    entities = normalize_entities(manuscript.ai_entities)
    memory = manuscript.ai_memory if isinstance(manuscript.ai_memory, dict) else {}
    issues = []

    draft_entities = analyze_entities(draft)
    known_names = set(entities.get("proper_nouns", []))
    memory_names = set()
    for key in ("characters", "locations", "terms"):
        for item in _memory_items(memory, key):
            memory_names.update(analyze_entities(item).get("proper_nouns", []))
    known_names |= memory_names

    introduced = [
        name for name in draft_entities.get("proper_nouns", [])
        if known_names and name not in known_names and name not in (selected_text or "")
    ]
    if len(introduced) >= 3:
        issues.append({
            "type": "new_entities",
            "severity": "review",
            "message": "The suggestion introduces several new named entities.",
            "reason": f"New names not found in current memory: {', '.join(introduced[:6])}.",
            "suggestion": "Confirm these are intentional, or revise the suggestion to use established names.",
            "source": "Book memory and local entity index",
        })

    memory_dates = set()
    for key in ("timeline_notes", "chapter_summaries", "book_summary"):
        for item in _memory_items(memory, key):
            memory_dates.update(analyze_entities(item).get("dates", []))
    new_dates = [date for date in draft_entities.get("dates", []) if memory_dates and date not in memory_dates]
    if new_dates and action in {"continue", "rewrite", "improve", "expand"}:
        issues.append({
            "type": "timeline",
            "severity": "review",
            "message": "The suggestion introduces timeline details not found in memory.",
            "reason": f"Dates or timeline markers appear new: {', '.join(new_dates[:5])}.",
            "suggestion": "Check whether these dates match the established timeline before confirming.",
            "source": "Timeline memory",
        })

    draft_states = _fact_states(draft)
    previous_text = "\n\n".join(section.get("snippet", "") for section in retrieved_sections)
    previous_states = _fact_states(previous_text)
    opposites = {
        "alive": "dead",
        "dead": "alive",
        "married": "single",
        "single": "married",
        "missing": "alive",
    }
    for name, values in draft_states.items():
        prior_values = previous_states.get(name, set())
        for value in values:
            opposite = opposites.get(value)
            if opposite and opposite in prior_values:
                source = next((section for section in retrieved_sections if name in section.get("snippet", "")), {})
                issues.append({
                    "type": "contradiction",
                    "severity": "high",
                    "message": f"{name} appears to have a contradictory state.",
                    "reason": f"The draft says {name} is {value}, while earlier context suggests {opposite}.",
                    "suggestion": "Revise the generated passage or update the book memory if the change is intentional.",
                    "source": source.get("title", "Retrieved manuscript context"),
                })

    lens = (manuscript.ai_voice or {}).get("book_lens", "")
    if lens == "fiction" and action == "continue":
        if not any(name in draft for name in entities.get("characters", [])[:6]) and entities.get("characters"):
            issues.append({
                "type": "character_flow",
                "severity": "note",
                "message": "The continuation may drift away from established characters.",
                "reason": "None of the main tracked character names appear in the generated passage.",
                "suggestion": "Check whether this transition intentionally shifts focus.",
                "source": "Character memory",
            })

    return {
        "status": "needs_review" if any(issue["severity"] in {"high", "review"} for issue in issues) else "clear",
        "issues": issues,
        "retrieved_sections": [
            {
                "id": section.get("id"),
                "title": section.get("title"),
                "snippet": section.get("snippet"),
            }
            for section in retrieved_sections[:5]
        ],
        "reviewed_action": action,
    }


def _context_limit(action, cost_mode=None):
    policy = normalize_cost_mode(cost_mode or getattr(settings, "REEPLS_AI_CONTEXT_POLICY", "balanced"))
    if action in {"rewrite", "improve", "expand"}:
        limit = getattr(settings, "REEPLS_AI_MAX_INPUT_CHARS_REWRITE", 9000)
    elif action == "outline":
        limit = getattr(settings, "REEPLS_AI_MAX_INPUT_CHARS_OUTLINE", 22000)
    else:
        limit = getattr(settings, "REEPLS_AI_MAX_INPUT_CHARS_CONTINUE", 16000)
    if policy == "fast":
        return math.floor(limit * 0.65), policy
    if policy == "deep":
        return math.floor(limit * 1.25), policy
    return limit, policy


def _chapter_memory_for_section(chapter_memory, current_section):
    data = normalize_chapter_memory(chapter_memory)
    title = str((current_section or {}).get("title") or "").lower()
    if not title:
        return {}
    for section in data.get("sections", []):
        if str(section.get("title") or "").lower() == title:
            return section
    for section in data.get("sections", []):
        if title and title in str(section.get("title") or "").lower():
            return section
    return {}


def build_generation_context(manuscript, action, selected_text="", cursor_context="", user_prompt="", cost_mode=None):
    text = extract_text(manuscript.content)
    original_selected_chars = len((selected_text or "").strip())
    voice = normalize_voice(manuscript.ai_voice) if manuscript.ai_voice else analyze_voice(text, profile=manuscript.ai_profile)
    lens = infer_book_lens(manuscript.ai_profile, text)
    if not voice.get("book_lens"):
        voice["book_lens"] = lens["lens"]
        voice["continuity_priorities"] = lens["priorities"]
        voice["genre_signals"] = lens["signals"]
    chapter_map = normalize_chapter_map(manuscript.ai_chapter_map) if manuscript.ai_chapter_map else analyze_structure(manuscript.content)
    entities = normalize_entities(manuscript.ai_entities) if manuscript.ai_entities else analyze_entities(text)
    stale = normalize_stale(manuscript.ai_memory_stale)
    limit, policy = _context_limit(action, cost_mode or getattr(manuscript, "ai_cost_mode", "balanced"))
    selection_budget, _ = _selection_limit(action, policy)
    selected_text = _truncate(selected_text, selection_budget)
    cursor_context = _truncate(cursor_context, min(4000, limit // 3))
    current_section = _current_section(chapter_map, cursor_context)
    retrieval_query = "\n\n".join(part for part in [user_prompt, selected_text, cursor_context, current_section.get("preview", "")] if part)
    retrieve_limit = 3 if policy == "fast" else 7 if policy == "deep" else 5
    retrieved_sections = retrieve_relevant_sections(
        manuscript.content,
        retrieval_query,
        entities=entities,
        limit=retrieve_limit,
    )
    chapter_memory = _chapter_memory_for_section(manuscript.ai_chapter_memory, current_section)

    if action in REPLACEMENT_ACTIONS:
        excerpt_budget = min(1400, max(500, limit - len(selected_text) - len(cursor_context) - 2400))
        manuscript_excerpt = _truncate(text, excerpt_budget)
        usage_hint = "small context"
    elif action == "custom" and selected_text:
        excerpt_budget = min(1800, max(600, limit - len(selected_text) - len(cursor_context) - len(user_prompt) - 2600))
        manuscript_excerpt = _truncate(text, excerpt_budget)
        usage_hint = "small context"
    elif action == "outline":
        excerpt_budget = max(5000, limit - 5000)
        manuscript_excerpt = _truncate(text, excerpt_budget)
        usage_hint = "broad context"
    elif action == "summarize" and selected_text:
        manuscript_excerpt = ""
        usage_hint = "small context"
    else:
        excerpt_budget = max(3500, limit - len(cursor_context) - 4200)
        manuscript_excerpt = _truncate(text, excerpt_budget)
        usage_hint = "chapter context"

    warnings = []
    if stale.get("is_stale"):
        warnings.append(stale.get("reason") or "Memory may be stale.")
    if action in REPLACEMENT_ACTIONS and not selected_text:
        warnings.append("This action works best with selected text.")
    if action == "custom" and not user_prompt:
        warnings.append("Add an instruction before sending.")
    if usage_hint == "broad context":
        warnings.append("Broad context used for this planning action.")

    payload = {
        "action": action,
        "title": manuscript.title,
        "context_policy": policy,
        "profile": manuscript.ai_profile or {},
        "memory": manuscript.ai_memory or {},
        "voice": voice,
        "book_lens": {
            "name": voice.get("book_lens") or lens["lens"],
            "guidance": lens["prompt"],
            "continuity_priorities": voice.get("continuity_priorities") or lens["priorities"],
        },
        "chapter_map": {
            "total_words": chapter_map.get("total_words", 0),
            "section_count": chapter_map.get("section_count", 0),
            "headings": chapter_map.get("headings", [])[:40],
            "current_section": current_section,
        },
        "chapter_memory": chapter_memory,
        "entities": {
            "characters": entities.get("characters", [])[:25],
            "locations": entities.get("locations", [])[:20],
            "dates": entities.get("dates", [])[:20],
            "proper_nouns": entities.get("proper_nouns", [])[:40],
            "relationship_hints": entities.get("relationship_hints", [])[:15],
        },
        "retrieved_context": [
            {
                "title": section.get("title", ""),
                "snippet": section.get("snippet", ""),
                "dates": section.get("dates", []),
                "proper_nouns": section.get("proper_nouns", []),
            }
            for section in retrieved_sections
        ],
        "continuity_contract": (
            "Use retrieved_context to preserve continuity. If the requested draft would contradict an earlier "
            "section, prefer the earlier established fact unless the user's selected text clearly changes it."
        ),
        "selected_text": selected_text,
        "cursor_context": cursor_context,
        "user_prompt": _truncate(user_prompt, 3000),
        "manuscript_excerpt": manuscript_excerpt,
    }
    input_chars = len(json.dumps(payload, ensure_ascii=False))
    return {
        "payload": payload,
        "usage_hint": usage_hint,
        "warnings": warnings,
        "agent_steps": [
            _agent_step("Context Agent", "ready", f"Prepared {usage_hint}."),
            _agent_step("Voice Agent", "ready", "Loaded local voice profile."),
            _agent_step("Continuity Agent", "ready", "Loaded tracked names and timeline clues."),
            _agent_step("Writing Agent", "working", ACTION_AGENT_LABELS.get(action, "Writing suggestion")),
        ],
        "context_summary": {
            "policy": policy,
            "usage_hint": usage_hint,
            "input_chars": input_chars,
            "selected_chars": len(selected_text),
            "original_selected_chars": original_selected_chars,
            "selection_limit_chars": selection_budget,
            "selection_truncated": original_selected_chars > len(selected_text),
            "cursor_chars": len(cursor_context),
            "prompt_chars": len(user_prompt),
            "excerpt_chars": len(manuscript_excerpt),
            "current_section": current_section.get("title", ""),
            "book_lens": voice.get("book_lens") or lens["lens"],
            "retrieved_sections": len(retrieved_sections),
            "chapter_memory_title": chapter_memory.get("title", ""),
        },
        "retrieved_sections": retrieved_sections,
    }


def validate_output(action, draft, selected_text, entities):
    warnings = []
    draft = (draft or "").strip()
    if not draft:
        return ["The AI returned an empty suggestion."]
    if len(draft) > 12000:
        warnings.append("The suggestion is unusually long.")
    if action in REPLACEMENT_ACTIONS and selected_text:
        selected_words = set(word.lower() for word in re.findall(r"\b[a-zA-Z]{4,}\b", selected_text))
        draft_words = set(word.lower() for word in re.findall(r"\b[a-zA-Z]{4,}\b", draft))
        if selected_words and len(selected_words & draft_words) / max(len(selected_words), 1) < 0.12:
            warnings.append("The rewrite may have drifted away from the selected text.")
    tracked = set((entities or {}).get("proper_nouns", [])[:40])
    introduced = []
    for name in re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b", draft):
        if name not in COMMON_CAPITALIZED and tracked and name not in tracked and name not in selected_text:
            introduced.append(name)
    if len(set(introduced)) >= 4:
        warnings.append("The suggestion introduces several new names; review continuity.")
    if not warnings:
        warnings.append("Suggestion passed local safety checks.")
    return warnings


def record_usage(usage, action, input_chars, output_chars, usage_hint):
    data = normalize_usage(usage)
    data["request_count"] += 1
    data["input_chars"] += int(input_chars or 0)
    data["output_chars"] += int(output_chars or 0)
    action_data = data["actions"].get(action, {"count": 0, "input_chars": 0, "output_chars": 0})
    action_data["count"] += 1
    action_data["input_chars"] += int(input_chars or 0)
    action_data["output_chars"] += int(output_chars or 0)
    data["actions"][action] = action_data
    data["last_request"] = {
        "action": action,
        "input_chars": int(input_chars or 0),
        "output_chars": int(output_chars or 0),
        "usage_hint": usage_hint,
    }
    return data


def agent_steps_for_inspect(warnings=None):
    status = "warning" if warnings else "ready"
    return [
        _agent_step("Memory Agent", "ready", "Refreshed local book awareness."),
        _agent_step("Structure Agent", "ready", "Mapped chapters and sections."),
        _agent_step("Voice Agent", "ready", "Profiled rhythm and style clues."),
        _agent_step("Continuity Agent", status, "Checked names, locations, and dates."),
    ]


def _agent_step(name, status, detail):
    return {"name": name, "status": status, "detail": detail}
