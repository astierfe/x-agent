"""
Draft-post generator for the x-agent Intelligence Engine.

Produces short, engaging X (Twitter) posts (< 280 characters) from
articles that passed the relevance filter.

Uses the **sandbox** model (Gemma, $0 cost) by default for safe budget
control.  The ``social`` model (Grok) must be explicitly requested via
the *model* parameter when a social-media-native tone is desired.

All code, type hints, comments, and log messages are written strictly
in English.  Target: Python 3.11+.
"""

from __future__ import annotations

import logging
from typing import Any

from src.intelligence.llm_client import complete

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT: str = (
    "You are a social media assistant for a technology-focused X (Twitter) "
    "account covering Web3, blockchain, cross-chain interoperability, "
    "AI/agentic frameworks, and enterprise legacy architectures.\n\n"
    "Given an article title and summary, write a single engaging post "
    "suitable for X (Twitter).\n\n"
    "Rules:\n"
    "- The post MUST be strictly under 280 characters.\n"
    "- Use a professional yet accessible tone.\n"
    "- Include 1-2 relevant hashtags at the end.\n"
    "- Do NOT use markdown, quotation marks around the post, or any "
    "prefix/suffix like 'Post:' or 'Draft:'.\n"
    "- Return ONLY the raw post text, nothing else."
)

# ---------------------------------------------------------------------------
# Maximum post length (X / Twitter limit)
# ---------------------------------------------------------------------------

_MAX_CHARS: int = 280


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_draft(
    title: str,
    summary: str,
    source_name: str,
    *,
    model: str = "sandbox",
) -> str:
    """Generate a short draft post for X (Twitter).

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
        Defaults to ``"sandbox"`` (Gemma, $0 cost).  To use the
        social-media-native Grok model, pass ``model="social"``
        explicitly.

    Returns
    -------
    str
        The generated draft text, guaranteed to be ≤ 280 characters.
        On LLM failure, returns an empty string.
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
        "Generating draft for article '%s' (source: %s, model: %s)…",
        title[:80],
        source_name,
        model,
    )

    try:
        raw_response: str = complete(
            messages,
            model=model,
            temperature=0.7,  # slightly creative for engaging posts
            max_tokens=256,
        )
    except RuntimeError as exc:
        logger.error(
            "LLM call failed for draft generation on '%s': %s",
            title[:80],
            exc,
        )
        return ""

    # Clean up common LLM artifacts
    draft = raw_response.strip().strip('"').strip("'")

    # Enforce the 280-character limit with word-boundary truncation
    if len(draft) > _MAX_CHARS:
        logger.warning(
            "Draft is %d chars — truncating to %d.",
            len(draft),
            _MAX_CHARS,
        )
        truncated = draft[:_MAX_CHARS].rsplit(" ", 1)[0]
        draft = truncated + "…"

    logger.info(
        "Draft generated for '%s': %d chars.",
        title[:80],
        len(draft),
    )
    return draft