"""Entrypoint script for testing the RSS parser inside Docker."""

import logging
import sys

from src.sourcing.rss_parser import parse_feeds

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Starting RSS feed test for topic 'ai_agentic'…")
    outcome = parse_feeds(topic="ai_agentic")

    all_titles: list[str] = []
    for result in outcome.results:
        for entry in result.entries:
            all_titles.append(entry.title)

    logger.info(
        "Fetched %d entries across %d feed(s) (%d failed).",
        outcome.total_entries,
        outcome.total_feeds_processed - outcome.total_feeds_failed,
        outcome.total_feeds_failed,
    )

    if not all_titles:
        logger.warning("No entries retrieved — check network / feed URLs.")
        return

    print("\n=== Fetched Entry Titles ===")
    for i, title in enumerate(all_titles, start=1):
        print(f"{i:>3}. {title}")
    print(f"\nTotal: {len(all_titles)} entries.\n")


if __name__ == "__main__":
    main()