from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from django.utils.text import slugify


def manuscript_docx_filename(manuscript):
    base = slugify(manuscript.title or "manuscript") or "manuscript"
    return f"{base}.docx"


def manuscript_to_docx_bytes(manuscript):
    paragraphs = []
    title = (manuscript.title or "").strip()
    if title:
        paragraphs.append(_paragraph(_run(title), style="Title"))
    _append_nodes(paragraphs, manuscript.content.get("content", []) if isinstance(manuscript.content, dict) else [])

    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", _content_types_xml())
        docx.writestr("_rels/.rels", _package_rels_xml())
        docx.writestr("word/_rels/document.xml.rels", _document_rels_xml())
        docx.writestr("word/styles.xml", _styles_xml())
        docx.writestr("word/document.xml", _document_xml("".join(paragraphs)))
    return buffer.getvalue()


def submission_prefill_for(manuscript):
    text = _plain_text(manuscript.content)
    summary = " ".join(text.split())
    short = summary[:197].rstrip()
    if len(summary) > 197:
        short = f"{short}..."

    profile = manuscript.ai_profile if isinstance(manuscript.ai_profile, dict) else {}
    memory = manuscript.ai_memory if isinstance(manuscript.ai_memory, dict) else {}
    long_description = (
        memory.get("book_summary")
        or memory.get("summary")
        or summary[:1200]
        or f"Manuscript for {manuscript.title}."
    )

    return {
        "title": manuscript.title,
        "short_description": short or manuscript.title,
        "long_description": long_description,
        "language": _language_from_profile(profile, text),
        "category": _category_from_profile(profile),
    }


def _append_nodes(paragraphs, nodes):
    if not isinstance(nodes, list):
        return
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_type = node.get("type")
        content = node.get("content", [])
        if node_type == "heading":
            text = _inline_text(content).strip()
            if text:
                level = min(max(int((node.get("attrs") or {}).get("level") or 1), 1), 4)
                paragraphs.append(_paragraph(_run(text), style=f"Heading{level}"))
        elif node_type == "paragraph":
            paragraphs.append(_paragraph(_inline_runs(content)))
        elif node_type == "blockquote":
            for child in content if isinstance(content, list) else []:
                text = _inline_text(child.get("content", []) if isinstance(child, dict) else []).strip()
                if text:
                    paragraphs.append(_paragraph(_run(text), style="Quote"))
        elif node_type == "bulletList":
            _append_list(paragraphs, content, ordered=False)
        elif node_type == "orderedList":
            _append_list(paragraphs, content, ordered=True)
        elif node_type == "listItem":
            _append_nodes(paragraphs, content)
        elif content:
            _append_nodes(paragraphs, content)


def _append_list(paragraphs, items, ordered=False):
    index = 1
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        text = " ".join(_plain_text(item).split())
        if text:
            prefix = f"{index}. " if ordered else "- "
            paragraphs.append(_paragraph(_run(f"{prefix}{text}")))
            index += 1


def _inline_runs(nodes):
    runs = []
    for node in nodes if isinstance(nodes, list) else []:
        if not isinstance(node, dict):
            continue
        node_type = node.get("type")
        if node_type == "text":
            marks = {mark.get("type") for mark in node.get("marks", []) or [] if isinstance(mark, dict)}
            runs.append(_run(
                node.get("text", ""),
                bold="bold" in marks,
                italic="italic" in marks,
                underline="underline" in marks,
                strike="strike" in marks,
            ))
        elif node_type == "hardBreak":
            runs.append("<w:r><w:br/></w:r>")
        elif node.get("content"):
            runs.append(_inline_runs(node.get("content")))
    return "".join(runs)


def _inline_text(nodes):
    parts = []
    for node in nodes if isinstance(nodes, list) else []:
        if not isinstance(node, dict):
            continue
        if node.get("type") == "text":
            parts.append(node.get("text", ""))
        elif node.get("type") == "hardBreak":
            parts.append("\n")
        elif node.get("content"):
            parts.append(_inline_text(node.get("content")))
    return "".join(parts)


def _plain_text(content):
    if not isinstance(content, dict):
        return ""
    parts = []

    def walk(node):
        if not isinstance(node, dict):
            return
        node_type = node.get("type")
        if node_type == "text":
            parts.append(node.get("text", ""))
        elif node_type in {"paragraph", "heading", "listItem"}:
            for child in node.get("content", []) or []:
                walk(child)
            parts.append("\n")
        else:
            for child in node.get("content", []) or []:
                walk(child)

    walk(content)
    return "\n".join(line.strip() for line in "".join(parts).splitlines() if line.strip())


def _paragraph(runs, style=None):
    style_xml = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f"<w:p>{style_xml}{runs}</w:p>"


def _run(text, bold=False, italic=False, underline=False, strike=False):
    props = []
    if bold:
        props.append("<w:b/>")
    if italic:
        props.append("<w:i/>")
    if underline:
        props.append('<w:u w:val="single"/>')
    if strike:
        props.append("<w:strike/>")
    prop_xml = f"<w:rPr>{''.join(props)}</w:rPr>" if props else ""
    return f'<w:r>{prop_xml}<w:t xml:space="preserve">{escape(str(text))}</w:t></w:r>'


def _document_xml(body):
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}"
        '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" '
        'w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>'
        "</w:body></w:document>"
    )


def _content_types_xml():
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        "</Types>"
    )


def _package_rels_xml():
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        "</Relationships>"
    )


def _document_rels_xml():
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
        "</Relationships>"
    )


def _styles_xml():
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/>'
        '<w:qFormat/></w:style>'
        '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/>'
        '<w:qFormat/><w:rPr><w:b/><w:sz w:val="36"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/>'
        '<w:qFormat/><w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/>'
        '<w:qFormat/><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/>'
        '<w:qFormat/><w:rPr><w:b/><w:sz w:val="24"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading4"><w:name w:val="heading 4"/><w:basedOn w:val="Normal"/>'
        '<w:qFormat/><w:rPr><w:b/><w:sz w:val="22"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/><w:basedOn w:val="Normal"/>'
        '<w:qFormat/><w:pPr><w:ind w:left="720"/></w:pPr><w:rPr><w:i/></w:rPr></w:style>'
        "</w:styles>"
    )


def _language_from_profile(profile, text):
    value = str(profile.get("language") or "").strip().lower()
    if value.startswith("fr") or "french" in value or "francais" in value:
        return "fr"
    if value.startswith("en") or "english" in value:
        return "en"
    french_markers = [" le ", " la ", " les ", " des ", " une ", " dans ", " pour ", " avec "]
    sample = f" {text[:2000].lower()} "
    return "fr" if sum(marker in sample for marker in french_markers) >= 3 else "en"


def _category_from_profile(profile):
    value = " ".join(str(profile.get(key) or "") for key in ("genre", "book_type")).lower()
    mapping = [
        ("romance", "romance"),
        ("thriller", "thriller_mystery"),
        ("mystery", "thriller_mystery"),
        ("drama", "drama"),
        ("science fiction", "scifi_fantasy"),
        ("fantasy", "scifi_fantasy"),
        ("horror", "horror"),
        ("poetry", "poetry"),
        ("biography", "biography_memoir"),
        ("memoir", "biography_memoir"),
        ("self", "self_help"),
        ("business", "business_money"),
        ("history", "history"),
        ("health", "health_wellness"),
        ("spiritual", "religion_spirituality"),
        ("religion", "religion_spirituality"),
        ("children", "children_ya"),
        ("academic", "academic"),
        ("course", "course"),
        ("politic", "politics"),
        ("african", "african_literature"),
        ("non", "non_fiction"),
    ]
    for needle, category in mapping:
        if needle in value:
            return category
    return "fiction"
