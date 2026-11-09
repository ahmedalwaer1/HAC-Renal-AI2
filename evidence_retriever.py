"""Evidence retrieval (RAG) over the approved knowledge base.

Retrieval is scoped to the files the drug registry declares for the drug under
discussion, so a recommendation can never cite another drug's guidance. Every
returned item keeps its file and heading so callers can show a traceable
citation next to the recommendation.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data.clinical_data import get_interaction, get_safety_rule, get_source
from data.drug_registry import DRUG_REGISTRY, resolve_drug

KB_DIR = os.path.join(ROOT, "knowledge_base")

# Internal rule ids such as MER-001 or VAN-012 mislead clinicians; they are
# stripped from anything a pharmacist may read.
_RULE_ID = re.compile(r"\s*\(\s*[A-Za-z]{2,6}-\d{1,4}\s*\)|\b[A-Za-z]{2,6}-\d{1,4}\b")


def _clean_text(text):
    """Remove internal rule ids and collapse the result to one clean line."""
    cleaned = _RULE_ID.sub("", text or "")
    return " ".join(cleaned.split()).strip(" :—-.،")


def _read_kb_file(fname):
    path = os.path.join(KB_DIR, fname)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _sections(text):
    """Split a markdown file into (heading, body) sections."""
    sections = []
    heading = ""
    body = []
    for line in text.splitlines():
        if line.startswith("#"):
            if heading or body:
                sections.append((heading, "\n".join(body).strip()))
            heading = line.lstrip("#").strip()
            body = []
        else:
            body.append(line)
    if heading or body:
        sections.append((heading, "\n".join(body).strip()))
    return [(h, b) for h, b in sections if b]


def _files_for(drug):
    """Knowledge-base files allowed for this drug (all files when unspecified)."""
    key = resolve_drug(drug) if drug else None
    if key:
        return list(DRUG_REGISTRY[key]["kb_files"])
    if not os.path.isdir(KB_DIR):
        return []
    return sorted(f for f in os.listdir(KB_DIR) if f.endswith(".md"))


def search(query, drug=None, max_sections=3):
    """Return the knowledge-base sections matching `query`, with citations."""
    terms = [
        term for term in str(query or "").lower().replace("/", " ").split()
        if len(term) > 2
    ]
    if not terms:
        return []

    scored = []
    for fname in _files_for(drug):
        text = _read_kb_file(fname)
        if text is None:
            continue
        for heading, body in _sections(text):
            haystack = (heading + " " + body).lower()
            score = sum(haystack.count(term) for term in terms)
            if score:
                scored.append((score, fname, heading, body))
    scored.sort(key=lambda row: -row[0])

    return [
        {
            "file": fname,
            "section": _clean_text(heading),
            "snippet": _clean_text(body)[:500],
            "citation": _clean_text(heading),
        }
        for _, fname, heading, body in scored[:max_sections]
    ]


def _referenced_sources(drug_key, safety, interaction):
    keys = list(DRUG_REGISTRY[drug_key]["source_keys"]) if drug_key else []
    for extra in ((safety or {}).get("source"), (interaction or {}).get("source")):
        if extra and extra not in keys:
            keys.append(extra)
    sources = []
    for source_key in keys:
        src = get_source(source_key)
        if src:
            sources.append({
                "key": source_key,
                "title": src.get("title"),
                "organization": src.get("organization"),
                "url": src.get("url"),
            })
    return sources


def _format_evidence(rule_id, note, safety, interaction, sources, sections):
    """Phrase the audit trail the way a clinical pharmacist reads it.

    The text is handed to the language model as EVIDENCE, so it never contains
    internal rule ids, file names or code-style labels - only clinical wording
    and the responsible body/document behind each statement.
    """
    parts = []
    if note:
        parts.append("المبدأ السريري المعتمد: %s" % note)
    if safety:
        parts.append("الإجراء الوقائي المطلوب: %s" % safety.get("system_action", ""))
    if interaction:
        parts.append("الإجراء المطلوب للتداخل: %s" % interaction.get("action", ""))
    for src in sources:
        label = " — ".join(
            part for part in (src.get("organization"), src.get("title")) if part
        )
        if label:
            parts.append("المرجع: %s" % label)
    for section in sections:
        heading = section.get("section") or section.get("citation") or "المراجع"
        parts.append("مقتطف من المراجع (%s): %s"
                     % (heading, section["snippet"][:240]))
    return " | ".join(p for p in parts if p and not p.endswith(": "))


def retrieve_evidence(result):
    """Return sources and retrieved sections for a rules-engine result."""
    result = result or {}
    drug = result.get("drug")
    drug_key = resolve_drug(drug) if drug else None

    rule_id = result.get("rule_id") or result.get("source_rule") or result.get("alert_code")
    safety = get_safety_rule(rule_id) if rule_id else None
    interaction = get_interaction(result.get("alert_code")) if result.get("alert_code") else None

    note = result.get("note") or result.get("message") or ""
    if safety:
        note = safety.get("rule", note)
    if interaction:
        note = interaction.get("message", note)

    sources = _referenced_sources(drug_key, safety, interaction)

    query = " ".join(str(part) for part in (
        rule_id,
        result.get("drug"),
        result.get("crcl_band"),
        result.get("weight_band"),
        result.get("dose_type"),
        note,
    ) if part)
    sections = search(query, drug=drug)

    return {
        "source_rule": rule_id,
        "source_note": note,
        "sources": sources,
        "sections": sections,
        "evidence_text": _format_evidence(
            rule_id, note, safety, interaction, sources, sections
        ),
    }
