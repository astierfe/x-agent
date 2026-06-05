"""
Article relevance filter for the x-agent Intelligence Engine.

Uses an LLM (via ``llm_client``) to evaluate whether a fetched article
is relevant to the project's scope.  Returns a structured dict with a
boolean ``relevant`` flag, a human-readable ``reason``, and a list of
``tags``.

The JSON extraction logic uses a brace-nesting counter rather than
fragile regex, making it robust against conversational text that contains
stray curly braces outside the JSON payload.

All code, type hints, comments, and log messages are written strictly
in English.  Target: Python 3.11+.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.intelligence.llm_client import complete

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt sent to the LLM for relevance classification
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT: str = (
    "You are a content curator for a technology-focused X (Twitter) account. "
    "Your job is to determine whether a given article is relevant to the "
    "following topics: Web3 & blockchain engineering, cross-chain "
    "interoperability protocols, AI & agentic frameworks, and enterprise "
    "legacy architectures (SOA, ESB, enterprise integration).\n\n"
    "You MUST respond with a single JSON object containing exactly these "
    "three fields:\n"
    '  - "relevant": boolean (true if the article fits the scope)\n'
    '  - "reason": string (brief explanation, max ~200 characters)\n'
    '  - "tags": list of strings (1-5 relevant topic keywords)\n\n'
    "Return ONLY the JSON object.  Do not wrap it in markdown code fences "
    "or add any conversational text before or after it."
)

# ---------------------------------------------------------------------------
# Default fallback structure used when JSON parsing fails
# ---------------------------------------------------------------------------

_FALLBACK_RESULT: dict[str, Any] = {
    "relevant": False,
    "reason": "JSON parsing failed — unable to determine relevance.",
    "tags": [],
}


# ---------------------------------------------------------------------------
# JSON extraction — brace-nesting approach
# ---------------------------------------------------------------------------


def _extract_json(raw_text: str) -> dict[str, Any]:
    """Extract the outermost JSON object from *raw_text* using brace counting.

    Scans character-by-character from the first ``{``, tracking nesting
    depth.  This correctly handles nested objects, escaped braces inside
    strings, and stray braces in surrounding conversational text.

    Returns a ``dict`` on success, or ``_FALLBACK_RESULT`` if no valid
    JSON object can be isolated or parsed.
    """
    start = raw_text.find("{")
    if start == -1:
        logger.warning("No opening brace found in LLM response.")
        return _FALLBACK_RESULT

    depth = 0
    in_string = False
    escape_next = False

    for i in range(start, len(raw_text)):
        ch = raw_text[i]

        if escape_next:
            escape_next = False
            continue

        if ch == "\\":
            escape_next = True
            continue

        if ch == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                # Found the matching closing brace.
                candidate = raw_text[start : i + 1]
                try:
                    parsed: dict[str, Any] = json.loads(candidate)
                    if not isinstance(parsed, dict):
                        logger.warning(
                            "Extracted JSON is not a dict (type=%s).",
                            type(parsed).__name__,
                        )
                        return _FALLBACK_RESULT
                    return parsed
                except json.JSONDecodeError as exc:
                    logger.warning(
                        "Brace-nesting extracted a candidate but "
                        "json.loads failed: %s",
                        exc,
                    )
                    return _FALLBACK_RESULT

    logger.warning(
        "Reached end of response without closing the outermost JSON brace."
    )
    return _FALLBACK_RESULT


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_relevance(
    title: str,
    summary: str,
    source_name: str,
    *,
    model: str = "sandbox",
) -> dict[str, Any]:
    """Evaluate whether an article is relevant to the project's scope.

    Sends the article metadata to the LLM and parses the structured
    JSON response.

    Parameters
    ----------
    title:
        Article title.
    summary:
        Article summary or description (may be empty).
    source_name:
        Human-readable name of the source feed (e.g. "OpenAI Blog").
    model:
        Logical model alias forwarded to :func:`llm_client.complete`.
        Defaults to ``"sandbox"`` (Gemma, $0 cost).

    Returns
    -------
    dict[str, Any]
        A dictionary with keys ``"relevant"`` (bool), ``"reason"``
        (str), and ``"tags"`` (list[str]).  On parsing failure the
        fallback dict ``{"relevant": False, ...}`` is returned.
    """
    user_content = (
        f"Title: {title}\n"
        f"Source: {source_name}\n"
        f"Summary: {summary or '(no summary available)'}"
    )

    messages: list[dict[str, str]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    logger.info(
        "Checking relevance for article '%s' (source: %s)…",
        title[:80],
        source_name,
    )

    try:
        raw_response = complete(
            messages,
            model=model,
            temperature=0.1,  # low temperature for deterministic classification
            max_tokens=512,
            response_format={"type": "json_object"},
        )
    except RuntimeError as exc:
        logger.error("LLM call failed for article '%s': %s", title[:80], exc)
        return {
            "relevant": False,
            "reason": f"LLM call failed: {exc}",
            "tags": [],
        }

    result = _extract_json(raw_response)

    # Validate expected keys are present (defensive — LLMs can be creative).
    if "relevant" not in result:
        logger.warning("LLM response missing 'relevant' key — assuming False.")
        result["relevant"] = False
    if "reason" not in result:
        result["reason"] = "No reason provided."
    if "tags" not in result:
        result["tags"] = []

    logger.info(
        "Relevance result for '%s': relevant=%s, tags=%s",
        title[:80],
        result["relevant"],
        result.get("tags", []),
    )
    return result