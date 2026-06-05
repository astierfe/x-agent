"""
OpenRouter API client for the x-agent Intelligence Engine.

Provides a generic completion interface targeting the OpenRouter
chat-completions endpoint, with built-in model routing, structured
logging, and exponential-backoff retry logic for rate limits and
transient network failures.

All code, type hints, comments, and log messages are written
strictly in English.  Target: Python 3.11+.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import time
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_OPENROUTER_URL: str = "https://openrouter.ai/api/v1/chat/completions"

# Model routing table — keyed by logical alias for safe budget control.
MODEL_MAP: dict[str, str] = {
    "sandbox": "google/gemma-4-31b-it:free",  # $0 cost — safe for testing
    "production": "deepseek/deepseek-chat",
    "social": "xai/grok-2",
}

# Retry / backoff defaults
_DEFAULT_MAX_RETRIES: int = 3
_DEFAULT_BASE_DELAY: float = 2.0  # seconds
_DEFAULT_BACKOFF_FACTOR: float = 2.0

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _api_key() -> str:
    """Return the OpenRouter API key from the environment.

    Raises
    ------
    RuntimeError
        If ``OPENROUTER_API_KEY`` is not set.
    """
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "OPENROUTER_API_KEY environment variable is not set. "
            "Pass it via --env-file .env or -e OPENROUTER_API_KEY=..."
        )
    return key


def _resolve_model(model: str) -> str:
    """Resolve a logical model alias to its full OpenRouter model ID.

    If *model* is not a recognised alias it is returned as-is (allowing
    callers to pass raw model IDs directly).
    """
    return MODEL_MAP.get(model, model)


def _build_request_body(
    messages: list[dict[str, str]],
    model: str,
    temperature: float,
    max_tokens: int,
    response_format: dict[str, str] | None,
) -> bytes:
    """Serialize the JSON payload for the OpenRouter chat-completions API."""
    body: dict[str, Any] = {
        "model": _resolve_model(model),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format is not None:
        body["response_format"] = response_format
    return json.dumps(body).encode("utf-8")


def _handle_http_response(response_data: bytes) -> str:
    """Extract the assistant's message content from the API response.

    Raises
    ------
    RuntimeError
        If the response structure is unexpected or contains an error.
    """
    try:
        payload: dict[str, Any] = json.loads(response_data)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to decode OpenRouter JSON response: {exc}") from exc

    # Check for API-level errors
    if "error" in payload:
        error_detail = payload["error"]
        raise RuntimeError(f"OpenRouter API returned an error: {error_detail}")

    choices: list[dict[str, Any]] = payload.get("choices", [])
    if not choices:
        raise RuntimeError("OpenRouter response contained no 'choices' array.")

    message: dict[str, Any] | None = choices[0].get("message")
    if message is None:
        raise RuntimeError("First choice in OpenRouter response has no 'message'.")

    content: str | None = message.get("content")
    if content is None:
        raise RuntimeError("OpenRouter response message has no 'content' field.")

    return content


def _retry_with_backoff(
    request: urllib.request.Request,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    base_delay: float = _DEFAULT_BASE_DELAY,
    backoff_factor: float = _DEFAULT_BACKOFF_FACTOR,
) -> str:
    """POST *request* with exponential-backoff retry on transient failures.

    Retries on HTTP 429 (rate limit), HTTP 5xx (server errors), and
    socket timeouts.  Other errors are re-raised immediately.

    Returns the decoded assistant message content (``str``).
    """
    last_exception: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=60) as resp:
                body = resp.read()
                return _handle_http_response(body)
        except urllib.error.HTTPError as exc:
            status = exc.code
            if status == 429 or status >= 500:
                last_exception = exc
                logger.warning(
                    "OpenRouter HTTP %d on attempt %d/%d — %s",
                    status,
                    attempt,
                    max_retries,
                    exc.reason if hasattr(exc, "reason") else "",
                )
            else:
                raise RuntimeError(
                    f"OpenRouter HTTP {status}: {exc.reason}"
                ) from exc
        except (socket.timeout, OSError) as exc:
            last_exception = exc
            logger.warning(
                "Network error on attempt %d/%d: %s",
                attempt,
                max_retries,
                exc,
            )

        # Don't sleep after the last failed attempt.
        if attempt < max_retries:
            delay = base_delay * (backoff_factor ** (attempt - 1))
            logger.info("Retrying in %.1f seconds...", delay)
            time.sleep(delay)

    raise RuntimeError(
        f"OpenRouter request failed after {max_retries} attempt(s). "
        f"Last error: {last_exception}"
    ) from last_exception


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def complete(
    messages: list[dict[str, str]],
    *,
    model: str = "sandbox",
    temperature: float = 0.3,
    max_tokens: int = 1024,
    response_format: dict[str, str] | None = None,
) -> str:
    """Send a chat-completion request to OpenRouter and return the response.

    Parameters
    ----------
    messages:
        List of message dicts with ``"role"`` and ``"content"`` keys
        (system / user / assistant).
    model:
        Logical model alias (``"sandbox"``, ``"production"``,
        ``"social"``) or a raw OpenRouter model ID.  Defaults to
        ``"sandbox"`` (Gemma, $0 cost).
    temperature:
        Sampling temperature (0.0 – 2.0).  Lower values produce more
        deterministic output.
    max_tokens:
        Maximum number of tokens in the generated response.
    response_format:
        Optional dict to enforce structured output, e.g.
        ``{"type": "json_object"}``.

    Returns
    -------
    str
        The raw text content of the assistant's response message.

    Raises
    ------
    RuntimeError
        If the API key is missing, the request fails after all retries,
        or the response cannot be parsed.
    """
    resolved = _resolve_model(model)
    logger.info(
        "OpenRouter request → model=%s (resolved: %s), messages=%d, "
        "temperature=%.2f, max_tokens=%d",
        model,
        resolved,
        len(messages),
        temperature,
        max_tokens,
    )

    body_bytes = _build_request_body(
        messages, model, temperature, max_tokens, response_format
    )

    request = urllib.request.Request(
        _OPENROUTER_URL,
        data=body_bytes,
        headers={
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/astierfe/x-agent",
            "X-Title": "x-agent",
        },
        method="POST",
    )

    result = _retry_with_backoff(request)
    logger.info("OpenRouter response received — %d characters.", len(result))
    return result