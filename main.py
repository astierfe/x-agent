"""Entrypoint script for the x-agent pipeline.

Orchestrates RSS sourcing, SQLite persistence, LLM-based relevance
filtering, and draft-post generation.  All code, type hints, comments,
and log messages are written strictly in English.

Target: Python 3.11+
"""

import logging
import sys
from typing import Any

from src.database.db_manager import (
    get_unprocessed_articles,
    initialize_db,
    save_draft,
    save_entries,
)
from src.intelligence.filter import check_relevance
from src.intelligence.post_generator import generate_draft
from src.sourcing.rss_parser import FeedEntry, parse_feeds

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)


def _run_intelligence_pipeline() -> tuple[int, int]:
    """Process unanalyzed articles through the filter → draft pipeline.

    Queries articles that have no matching row in ``drafts`` (idempotent
    across runs), evaluates relevance via LLM, and generates draft posts
    for relevant articles.  Every article — relevant or not — gets a row
    in ``drafts`` to prevent re-processing on subsequent runs.

    Returns
    -------
    tuple[int, int]
        ``(analyzed_count, relevant_count)`` — total articles processed
        and how many were deemed relevant.
    """
    unprocessed: list[dict[str, Any]] = get_unprocessed_articles()

    if not unprocessed:
        logger.info("No unprocessed articles — intelligence pipeline skipped.")
        return 0, 0

    logger.info(
        "Intelligence pipeline starting for %d unprocessed article(s)…",
        len(unprocessed),
    )

    analyzed = 0
    relevant = 0

    for article in unprocessed:
        article_id: int = article["id"]
        title: str = article["title"]
        summary: str = article.get("summary", "")
        source_name: str = article.get("source_name", "")

        # ------------------------------------------------------------------
        # Step 1 — Relevance filter
        # ------------------------------------------------------------------
        result = check_relevance(title, summary, source_name)
        is_relevant: bool = result.get("relevant", False)
        reason: str = result.get("reason", "")
        tags: list[str] = result.get("tags", [])

        # ------------------------------------------------------------------
        # Step 2 — Draft generation (only if relevant)
        # ------------------------------------------------------------------
        draft_text = ""
        if is_relevant:
            draft_text = generate_draft(title, summary, source_name)
            if draft_text:
                relevant += 1
                logger.info(
                    "✓ Relevant article #%d: '%s' — draft ready (%d chars).",
                    article_id,
                    title[:80],
                    len(draft_text),
                )
            else:
                logger.warning(
                    "Relevant article #%d but draft generation returned empty.",
                    article_id,
                )

        # ------------------------------------------------------------------
        # Step 3 — Persist result (ALWAYS — ensures idempotency)
        # ------------------------------------------------------------------
        save_draft(
            article_id=article_id,
            is_relevant=is_relevant,
            reason=reason,
            draft_text=draft_text,
        )
        analyzed += 1

    logger.info(
        "Intelligence pipeline complete: %d analyzed, %d relevant, "
        "%d drafts generated.",
        analyzed,
        relevant,
        relevant,
    )
    return analyzed, relevant


def main() -> None:
    # ------------------------------------------------------------------
    # 1. Initialize the database (safe to call every startup)
    # ------------------------------------------------------------------
    initialize_db()

    # ------------------------------------------------------------------
    # 2. Fetch RSS feeds
    # ------------------------------------------------------------------
    logger.info("Starting RSS feed fetch for topic 'ai_agentic'…")
    outcome = parse_feeds(topic="ai_agentic")

    all_entries: list[FeedEntry] = []
    for result in outcome.results:
        all_entries.extend(result.entries)

    logger.info(
        "Fetched %d entries across %d feed(s) (%d failed).",
        outcome.total_entries,
        outcome.total_feeds_processed - outcome.total_feeds_failed,
        outcome.total_feeds_failed,
    )

    if not all_entries:
        logger.warning("No entries retrieved — check network / feed URLs.")
        # Even without new articles, we may have unprocessed ones from
        # a previous run.  Run the intelligence pipeline anyway.
        _run_intelligence_pipeline()
        return

    # ------------------------------------------------------------------
    # 3. Persist entries (INSERT OR IGNORE handles duplicates)
    # ------------------------------------------------------------------
    new_count = save_entries(all_entries)
    duplicate_count = len(all_entries) - new_count

    # ------------------------------------------------------------------
    # 4. Intelligence pipeline — filter & draft for unprocessed articles
    # ------------------------------------------------------------------
    analyzed, relevant = _run_intelligence_pipeline()

    # ------------------------------------------------------------------
    # 5. Print summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 50)
    print("  x-agent — Session Run Summary")
    print("=" * 50)
    print(f"  Total fetched      : {len(all_entries)}")
    print(f"  Newly inserted     : {new_count}")
    print(f"  Duplicates skipped : {duplicate_count}")
    print(f"  Articles analyzed  : {analyzed}")
    print(f"  Relevant articles  : {relevant}")
    print(f"  Drafts generated   : {relevant}")
    print("=" * 50 + "\n")

    # ------------------------------------------------------------------
    # 6. Show newly inserted entry titles (up to a reasonable limit)
    # ------------------------------------------------------------------
    if new_count > 0:
        print("Titles of newly fetched entries:")
        displayed = 0
        for entry in all_entries:
            print(f"  - {entry.title}")
            displayed += 1
            if displayed >= 20:
                remaining = len(all_entries) - 20
                if remaining > 0:
                    print(f"  ... and {remaining} more.")
                break
        print()


if __name__ == "__main__":
    main()