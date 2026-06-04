"""Entrypoint script for testing the RSS parser and SQLite persistence."""

import logging
import sys

from src.database.db_manager import initialize_db, save_entries
from src.sourcing.rss_parser import FeedEntry, parse_feeds

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)


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
        return

    # ------------------------------------------------------------------
    # 3. Persist entries (INSERT OR IGNORE handles duplicates)
    # ------------------------------------------------------------------
    new_count = save_entries(all_entries)
    duplicate_count = len(all_entries) - new_count

    # ------------------------------------------------------------------
    # 4. Print summary
    # ------------------------------------------------------------------
    print("\n=== Persistence Summary ===")
    print(f"Total fetched : {len(all_entries)}")
    print(f"Newly inserted: {new_count}")
    print(f"Duplicates    : {duplicate_count}")
    print(f"Total in DB   : {new_count} (new) + existing entries\n")

    # Optional: list newly inserted entries (up to a reasonable limit)
    if new_count > 0:
        print("=== Titles of newly fetched entries ===")
        displayed = 0
        for entry in all_entries:
            # We cannot easily distinguish which ones were actually inserted
            # without a second query, so we simply list all fetched titles
            # and let the summary numbers speak for deduplication.
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