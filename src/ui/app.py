"""
Streamlit operator dashboard for the x-agent project.

Provides a lightweight local UI to review, edit, and copy generated
drafts, inspect LLM rejection reasons, and generate interactive replies
to X (Twitter) interactions.

All code, type hints, comments, and log messages are written strictly
in English.  Target: Python 3.11+.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import streamlit as st

from src.database.db_manager import get_pending_drafts
from src.intelligence.llm_client import MODEL_MAP, complete

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="x-agent · Operator Dashboard",
    page_icon="🤖",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_X_MAX_CHARS: int = 280

# System prompt for Tab 3 — single LLM call returning all 3 tones as JSON.
_REPLY_SYSTEM_PROMPT: str = (
    "You are a social media assistant for a technology-focused X (Twitter) "
    "account covering Web3, blockchain, cross-chain interoperability, "
    "AI/agentic frameworks, and enterprise legacy architectures.\n\n"
    "Given a user interaction (a tweet reply, mention, or comment), generate "
    "exactly THREE short response options, each with a distinct tone.  Every "
    "response MUST be strictly under 280 characters.\n\n"
    "You MUST respond with a single JSON object using this exact schema:\n"
    "{\n"
    '  "professional": "A concise, expert-level reply. Tone: knowledgeable, '
    'respectful, measured.",\n'
    '  "friendly": "A concise, warm reply. Tone: approachable, '
    'conversational, human.",\n'
    '  "provocative": "A concise, thought-provoking reply. Tone: bold, '
    "challenges assumptions, but ALWAYS respectful — never aggressive, "
    'never personal attacks."\n'
    "}\n\n"
    "Return ONLY the JSON object.  Do not wrap it in markdown code fences "
    "or add any text before or after."
)


# ---------------------------------------------------------------------------
# JSON extraction helper (brace-nesting, same algorithm as filter.py)
# ---------------------------------------------------------------------------


def _extract_json(raw_text: str) -> dict[str, Any]:
    """Extract the outermost JSON object from *raw_text* using brace counting.

    Returns a ``dict`` on success, or an empty dict if no valid JSON
    object can be isolated.
    """
    start = raw_text.find("{")
    if start == -1:
        logger.warning("No opening brace found in LLM reply response.")
        return {}

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
                candidate = raw_text[start : i + 1]
                try:
                    parsed: dict[str, Any] = json.loads(candidate)
                    if not isinstance(parsed, dict):
                        logger.warning(
                            "Extracted JSON is not a dict (type=%s).",
                            type(parsed).__name__,
                        )
                        return {}
                    return parsed
                except json.JSONDecodeError as exc:
                    logger.warning(
                        "Brace-nesting extracted a candidate but "
                        "json.loads failed: %s",
                        exc,
                    )
                    return {}

    logger.warning(
        "Reached end of response without closing the outermost JSON brace."
    )
    return {}


# ---------------------------------------------------------------------------
# Cached data loader
# ---------------------------------------------------------------------------


@st.cache_data(ttl=60)
def _load_drafts() -> list[dict[str, Any]]:
    """Load all drafts from the database (read-only).

    Cached for 60 seconds to avoid hitting the SQLite database on every
    Streamlit rerun.  Call ``st.cache_data.clear()`` to force a refresh.
    """
    logger.info("Loading drafts from database (read-only)…")
    return get_pending_drafts(read_only=True)


# ---------------------------------------------------------------------------
# Character counter badge
# ---------------------------------------------------------------------------


def _char_counter_badge(text: str) -> None:
    """Render a small coloured character-count badge below a text area."""
    count = len(text)
    if count <= _X_MAX_CHARS:
        st.caption(f"✅ {count} / {_X_MAX_CHARS} chars")
    elif count <= 300:
        st.caption(f"⚠️ {count} / {_X_MAX_CHARS} chars — getting tight")
    else:
        st.caption(f"🔴 {count} / {_X_MAX_CHARS} chars — too long for X")


# ---------------------------------------------------------------------------
# Tab 1 — Pending Queue (relevant drafts)
# ---------------------------------------------------------------------------


def _render_pending_queue(drafts: list[dict[str, Any]]) -> None:
    """Render the Pending Queue tab — editable drafts for relevant articles."""
    relevant = [d for d in drafts if d["is_relevant"]]

    st.metric("Pending Drafts", len(relevant))

    if not relevant:
        st.info(
            "No pending drafts yet. Run the main pipeline "
            "(`docker run --rm x-agent`) to generate some."
        )
        return

    for draft in relevant:
        draft_id: int = draft["draft_id"]
        title: str = draft["title"]
        source_name: str = draft["source_name"]
        source_url: str = draft.get("source_url", "")
        link: str = draft.get("link", "")
        reason: str = draft.get("reason", "")
        original_text: str = draft.get("draft_text", "")
        draft_created: str = draft.get("draft_created_at", "")

        with st.expander(
            f"📝 {title[:100]} — {source_name}",
            expanded=len(relevant) <= 3,
        ):
            # Metadata
            st.caption(
                f"**Source:** [{source_name}]({source_url}) | "
                f"**Article:** [link]({link}) | "
                f"**Processed:** {draft_created[:19]}"
            )
            st.caption(f"**Classification reason:** {reason}")

            # Editable text area bound to session state via unique key
            text_key = f"draft_{draft_id}"
            edited = st.text_area(
                "Draft text",
                value=original_text,
                key=text_key,
                height=120,
                label_visibility="collapsed",
            )

            # Read the live value from session state (updates on every keystroke)
            current_text = st.session_state.get(text_key, original_text)

            # Character counter
            _char_counter_badge(current_text)

            # Copy badge — compact st.code block with built-in 📋 button
            st.code(current_text, language=None)


# ---------------------------------------------------------------------------
# Tab 2 — Audit Logs / Rejections
# ---------------------------------------------------------------------------


def _render_audit_log(drafts: list[dict[str, Any]]) -> None:
    """Render the Audit Log tab — rejected articles with LLM reasoning."""
    rejected = [d for d in drafts if not d["is_relevant"]]

    st.metric("Rejected Articles", len(rejected))

    if not rejected:
        st.info(
            "No rejected articles found. Every processed article has "
            "been deemed relevant so far — or the pipeline hasn't run yet."
        )
        return

    for draft in rejected:
        draft_id: int = draft["draft_id"]
        title: str = draft["title"]
        source_name: str = draft["source_name"]
        link: str = draft.get("link", "")
        reason: str = draft.get("reason", "")
        draft_created: str = draft.get("draft_created_at", "")

        with st.expander(
            f"❌ {title[:100]} — {source_name}",
            expanded=False,
        ):
            st.markdown(f"**Article:** [{title}]({link})")
            st.caption(f"**Source:** {source_name} | **Processed:** {draft_created[:19]}")
            st.caption(f"**Rejection reason:** {reason}")


# ---------------------------------------------------------------------------
# Tab 3 — X Interactive Replies
# ---------------------------------------------------------------------------


def _render_reply_generator() -> None:
    """Render the Reply Generator tab — generate 3 tone variants from user input."""
    st.subheader("Generate Reply Options")

    col_input, col_output = st.columns([1, 1])

    with col_input:
        model_alias: str = st.selectbox(
            "Model",
            options=list(MODEL_MAP.keys()),
            index=0,
            help=(
                "**sandbox** — Gemma (free, $0 cost) | "
                "**production** — DeepSeek | "
                "**social** — Grok"
            ),
        )

        user_interaction: str = st.text_area(
            "Paste the interaction (tweet reply, mention, or comment)",
            height=200,
            placeholder=(
                "@someuser: What do you think about the new EIP-7702 "
                "account abstraction proposal?"
            ),
            key="reply_input",
        )

        generate_clicked: bool = st.button(
            "✨ Generate Replies", type="primary", use_container_width=True
        )

    with col_output:
        if not generate_clicked:
            st.info(
                "Paste an interaction on the left and click "
                "**Generate Replies** to create three response options."
            )
            return

        if not user_interaction.strip():
            st.warning("Paste an interaction first before generating replies.")
            return

        try:
            with st.spinner(
                f"Generating three response options with **{model_alias}**…"
            ):
                raw_response: str = complete(
                    messages=[
                        {"role": "system", "content": _REPLY_SYSTEM_PROMPT},
                        {"role": "user", "content": user_interaction},
                    ],
                    model=model_alias,
                    temperature=0.8,
                    max_tokens=512,
                    response_format={"type": "json_object"},
                )

            # Parse the structured JSON response
            try:
                parsed = json.loads(raw_response)
            except json.JSONDecodeError:
                logger.warning(
                    "Direct json.loads failed on reply response — "
                    "attempting brace-nesting extraction."
                )
                parsed = _extract_json(raw_response)

            tones: list[tuple[str, str, str]] = [
                (
                    "professional",
                    "🟢 Professional",
                    "Expert, knowledgeable, respectful",
                ),
                (
                    "friendly",
                    "🟡 Friendly",
                    "Approachable, conversational, human",
                ),
                (
                    "provocative",
                    "🔴 Provocative-but-safe",
                    "Bold, thought-provoking, always respectful",
                ),
            ]

            for key, label, description in tones:
                text = parsed.get(key, "")
                if not text:
                    text = f"(LLM did not return a '{key}' variant — try again.)"

                with st.container(border=True):
                    st.caption(f"**{label}** — {description}")
                    st.code(text, language=None)
                    _char_counter_badge(text)

        except RuntimeError as exc:
            st.error(
                f"LLM request failed: {exc}\n\n"
                "Make sure ``OPENROUTER_API_KEY`` is set (pass "
                "``--env-file .env`` to ``docker run``)."
            )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Render the x-agent operator dashboard with three tabs."""
    st.title("🤖 x-agent · Operator Dashboard")
    st.caption("Review, edit, and approve drafts before publishing.")

    # Refresh button
    col_title, col_refresh = st.columns([4, 1])
    with col_refresh:
        if st.button("🔄 Refresh Drafts", use_container_width=True):
            _load_drafts.clear()  # type: ignore[attr-defined]
            st.rerun()

    drafts = _load_drafts()

    tab1, tab2, tab3 = st.tabs(
        [
            "📝 Pending Queue",
            "📋 Audit Log (Rejections)",
            "💬 X Interactive Replies",
        ]
    )

    with tab1:
        _render_pending_queue(drafts)

    with tab2:
        _render_audit_log(drafts)

    with tab3:
        _render_reply_generator()


if __name__ == "__main__":
    main()