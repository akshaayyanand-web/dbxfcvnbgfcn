"""Open-web fallback via the Claude API, used only when structured sources
return nothing.

The output of this module is deliberately kept out of the graph. It renders in a
separate, clearly-labelled panel because it is unverified narrative text, not a
registry record — and a due-diligence tool that blurs that line is worse than
one that has no web search at all.
"""
import json
import re
from typing import Optional

import config
from config import ANTHROPIC_API_KEY

MODEL = "claude-opus-5"

PROMPT = """You are assisting a corporate lawyer with open-source due diligence.

Search the web for material on the subject below and report only what you can \
attribute to a source you actually retrieved.

Subject: {name}
{context}

Return a single JSON object, no prose around it:
{{
  "summary": "two or three sentences on who or what this is, or \
'No reliable open-source information found.'",
  "findings": [
    {{"claim": "one specific factual claim",
      "source_title": "publication or site name",
      "source_url": "https://...",
      "date": "YYYY-MM-DD or null",
      "category": "litigation|regulatory|sanctions|corporate|political|other"}}
  ],
  "related_entities": ["names of companies or people linked to the subject"]
}}

Rules: never invent a URL; omit any claim you cannot attribute; if nothing \
credible surfaces, return an empty findings list."""


def available() -> bool:
    return bool(ANTHROPIC_API_KEY)


def _extract_json(text: str) -> Optional[dict]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def research(name: str, context_bits: Optional[dict] = None) -> dict:
    if not available():
        return {"available": False, "summary": "", "findings": [], "related_entities": []}

    try:
        import anthropic
    except ImportError:
        return {
            "available": False,
            "error": "The `anthropic` package is not installed.",
            "summary": "", "findings": [], "related_entities": [],
        }

    context_lines = []
    for label, key in (("Nationality/country", "nationality"),
                       ("Date of birth", "birth_date"),
                       ("Registration number", "reg_number"),
                       ("Jurisdiction", "jurisdiction")):
        value = (context_bits or {}).get(key)
        if value:
            context_lines.append(f"{label}: {value}")
    context = "\n".join(context_lines) or "No additional identifying details supplied."

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4000,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 6}],
            messages=[{"role": "user",
                       "content": PROMPT.format(name=name, context=context)}],
        )
    except Exception as exc:  # network, auth, rate limit — surface, don't crash the search
        return {"available": True, "error": config.redact(str(exc))[:300],
                "summary": "", "findings": [], "related_entities": []}

    if getattr(response, "stop_reason", None) == "refusal":
        return {"available": True, "error": "The model declined this request.",
                "summary": "", "findings": [], "related_entities": []}

    text = "".join(
        block.text for block in response.content
        if getattr(block, "type", None) == "text"
    )
    parsed = _extract_json(text) or {}
    findings = [f for f in (parsed.get("findings") or []) if isinstance(f, dict)]
    return {
        "available": True,
        "unverified": True,
        "model": MODEL,
        "summary": parsed.get("summary") or text.strip()[:600],
        "findings": findings,
        "related_entities": parsed.get("related_entities") or [],
    }
