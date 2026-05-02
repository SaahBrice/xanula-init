import re


SUPPORTED_LANGUAGES = {
    "en": "English",
    "fr": "French",
}

FRENCH_MARKERS = {
    " le ", " la ", " les ", " des ", " une ", " un ", " dans ", " pour ", " avec ",
    " que ", " qui ", " est ", " sont ", " pas ", " mais ", " elle ", " lui ", " nous ",
    " vous ", " leur ", " cette ", " ces ", " aux ", " au ", " du ",
}

ENGLISH_MARKERS = {
    " the ", " and ", " with ", " that ", " this ", " from ", " for ", " not ", " but ",
    " she ", " he ", " they ", " was ", " were ", " have ", " had ", " into ", " about ",
}


def language_label(code):
    return SUPPORTED_LANGUAGES.get(normalize_language_code(code), "English")


def normalize_language_code(value="", text=""):
    raw = str(value or "").strip().lower()
    normalized = raw.replace("ç", "c").replace("é", "e").replace("è", "e").replace("ê", "e").replace("à", "a")
    if normalized in {"fr", "fra", "fre", "french", "francais", "francaise"}:
        return "fr"
    if normalized in {"en", "eng", "english", "anglais", "anglaise"}:
        return "en"
    if any(term in normalized for term in ("french", "francais", "francaise", "francophone")):
        return "fr"
    if any(term in normalized for term in ("english", "anglais", "anglophone")):
        return "en"
    return detect_text_language(text)


def detect_text_language(text=""):
    sample = f" {str(text or '')[:6000].lower()} "
    sample = re.sub(r"\s+", " ", sample)
    french_score = sum(sample.count(marker) for marker in FRENCH_MARKERS)
    english_score = sum(sample.count(marker) for marker in ENGLISH_MARKERS)
    french_score += len(re.findall(r"[àâçéèêëîïôùûüÿœ]", sample))
    return "fr" if french_score > english_score and french_score >= 3 else "en"


def normalize_profile_language(profile, text=""):
    data = dict(profile or {})
    data["language"] = language_label(normalize_language_code(data.get("language"), text))
    return data


def language_code_from_profile(profile, text=""):
    profile = profile if isinstance(profile, dict) else {}
    return normalize_language_code(profile.get("language"), text)


def language_instruction(profile=None, text=""):
    code = language_code_from_profile(profile or {}, text)
    label = language_label(code)
    return (
        f"The manuscript language is {label}. Keep all generated prose, summaries, outlines, "
        f"profile fields, memory notes, and publication descriptions in {label} unless the user explicitly asks otherwise."
    )
