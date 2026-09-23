"""Open-web fallback used only when structured sources return nothing.

Supports two interchangeable providers, picked automatically from whichever
API key is configured — Anthropic (Claude, with its native web-search tool)
or Google Gemini (with Grounding with Google Search). Set ADVERSE_MEDIA_PROVIDER
to "anthropic" or "gemini" to force one when both keys are present; default
"auto" prefers Anthropic if configured, else Gemini, so existing deployments
keep behaving exactly as before.

The output of this module is deliberately kept out of the graph. It renders in a
separate, clearly-labelled panel because it is unverified narrative text, not a
registry record — and a due-diligence tool that blurs that line is worse than
one that has no web search at all.
"""
import json
import re
from typing import Optional

import config
import keywords
from config import ANTHROPIC_API_KEY, GEMINI_API_KEY

ANTHROPIC_MODEL = "claude-opus-5"

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


def _provider() -> Optional[str]:
    """Which provider a call should use, or None if neither key is configured."""
    forced = config.ADVERSE_MEDIA_PROVIDER
    if forced == "anthropic" and ANTHROPIC_API_KEY:
        return "anthropic"
    if forced == "gemini" and GEMINI_API_KEY:
        return "gemini"
    if ANTHROPIC_API_KEY:
        return "anthropic"
    if GEMINI_API_KEY:
        return "gemini"
    return None


def available() -> bool:
    return _provider() is not None


def provider() -> Optional[str]:
    """Which provider a call would currently use ("anthropic"/"gemini"), or
    None if neither key is configured."""
    return _provider()


def unavailable() -> dict:
    """The shape callers can rely on when no AI provider is configured at
    all — still a valid media dict, just with no AI findings in it. Used so
    the manual/structured keyword search can attach to a result even when
    research() was never called."""
    return _empty(available())


def _extract_json(text: str) -> Optional[dict]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _context_block(context_bits: Optional[dict]) -> str:
    context_lines = []
    for label, key in (("Nationality/country", "nationality"),
                       ("Date of birth", "birth_date"),
                       ("Registration number", "reg_number"),
                       ("Jurisdiction", "jurisdiction")):
        value = (context_bits or {}).get(key)
        if value:
            context_lines.append(f"{label}: {value}")
    return "\n".join(context_lines) or "No additional identifying details supplied."


def _empty(available_: bool, **extra) -> dict:
    return {"available": available_, "summary": "", "findings": [], "related_entities": [],
            "overall_decision": "no_match", **extra}


def _shape_result(provider: str, model: str, text: str) -> dict:
    parsed = _extract_json(text) or {}
    findings = [f for f in (parsed.get("findings") or []) if isinstance(f, dict)]
    # Every AI-surfaced claim starts unreviewed: a language model's guess at
    # "this looks like litigation" is not the same as a human confirming the
    # claim actually belongs to the subject screened. classify_finding() below
    # is how a screener turns this into a real compliance decision.
    for f in findings:
        f.setdefault("classification", "unreviewed")
    return {
        "available": True,
        "unverified": True,
        "provider": provider,
        "model": model,
        "summary": parsed.get("summary") or text.strip()[:600],
        "findings": findings,
        "related_entities": parsed.get("related_entities") or [],
        "overall_decision": keywords.overall_decision(
            f["classification"] for f in findings
        ) if findings else "no_match",
    }


def manual_search(name: str, context_bits: Optional[dict] = None,
                   aka: Optional[str] = None, associated_company: Optional[str] = None,
                   selected_keywords: Optional[list] = None) -> dict:
    """The structured keyword search a screener can run in their own browser
    — needs no API key, no configuration, and works identically whether or
    not an AI provider is set up. Always attached to a search result so the
    AI findings above (when present) can be hand-verified against the exact
    same reproducible query."""
    context_bits = context_bits or {}
    return keywords.manual_search(
        name,
        aka=aka,
        nationality=context_bits.get("nationality"),
        associated_company=associated_company,
        keywords=selected_keywords,
    )


def classify_finding(media: dict, index: int, classification: str) -> dict:
    """Record a screener's decision on one AI-surfaced finding. Returns the
    same media dict, mutated in place, with its overall_decision recomputed —
    call db.save_adverse_media_review() afterward to persist it."""
    if classification not in keywords.CLASSIFICATIONS:
        raise ValueError(f"unknown classification: {classification}")
    findings = media.get("findings") or []
    if not 0 <= index < len(findings):
        raise IndexError(f"no finding at index {index}")
    findings[index]["classification"] = classification
    media["overall_decision"] = keywords.overall_decision(
        f.get("classification", "unreviewed") for f in findings
    )
    return media


def _research_anthropic(name: str, context: str) -> dict:
    try:
        import anthropic
    except ImportError:
        return _empty(False, error="The `anthropic` package is not installed.")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4000,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 6}],
            messages=[{"role": "user",
                       "content": PROMPT.format(name=name, context=context)}],
        )
    except Exception as exc:  # network, auth, rate limit — surface, don't crash the search
        return _empty(True, error=config.redact(str(exc))[:300])

    if getattr(response, "stop_reason", None) == "refusal":
        return _empty(True, error="The model declined this request.")

    text = "".join(
        block.text for block in response.content
        if getattr(block, "type", None) == "text"
    )
    return _shape_result("anthropic", ANTHROPIC_MODEL, text)


def _research_gemini(name: str, context: str) -> dict:
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return _empty(False, error="The `google-genai` package is not installed.")

    client = genai.Client(api_key=GEMINI_API_KEY)
    try:
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=PROMPT.format(name=name, context=context),
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )
    except Exception as exc:  # network, auth, rate limit — surface, don't crash the search
        return _empty(True, error=config.redact(str(exc))[:300])

    text = getattr(response, "text", None) or ""
    if not text:
        # No candidate text at all — usually a safety block or empty response.
        feedback = getattr(response, "prompt_feedback", None)
        reason = getattr(feedback, "block_reason", None)
        if reason:
            return _empty(True, error=f"The model declined this request ({reason}).")
    return _shape_result("gemini", config.GEMINI_MODEL, text)


def research(name: str, context_bits: Optional[dict] = None) -> dict:
    provider = _provider()
    if provider is None:
        return _empty(False)

    context = _context_block(context_bits)
    if provider == "anthropic":
        return _research_anthropic(name, context)
    return _research_gemini(name, context)
