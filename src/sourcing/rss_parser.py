"""
RSS feed parser module for the x-agent Sourcing engine.

Uses the `feedparser` library to fetch and parse RSS/Atom feeds
configurable via `feed_config.py`. Provides robust error handling
for network issues, malformed feeds, timeouts, and rate-limiting
scenarios.

Target Python: 3.11+
"""

from __future__ import annotations

import logging
import socket
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.error import URLError

import feedparser

from src.sourcing.feed_config import ALL_FEEDS, TOPIC_FEEDS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class FeedEntry:
    """A single parsed entry (article / post) from an RSS feed."""

    title: str
    link: str
    summary: str
    published: datetime | None = None
    author: str = ""
    source_feed_name: str = ""
    source_feed_url: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class FeedResult:
    """Result of parsing a single RSS feed."""

    feed_name: str
    feed_url: str
    entries: list[FeedEntry] = field(default_factory=list)
    error: str | None = None
    fetched_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FetchOutcome:
    """Aggregated outcome of fetching one or many feeds."""

    results: list[FeedResult] = field(default_factory=list)
    total_entries: int = 0
    total_feeds_processed: int = 0
    total_feeds_failed: int = 0


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _safe_parse_date(struct_time_parsed: Any) -> datetime | None:
    """Convert a feedparser time.struct_time tuple into a datetime.

    Returns ``None`` when conversion is not possible (missing / malformed
    dates are common in RSS feeds).
    """
    if struct_time_parsed is None:
        return None
    try:
        return datetime(*struct_time_parsed[:6])
    except (TypeError, ValueError):
        logger.debug("Could not parse date from: %r", struct_time_parsed)
        return None


def _clean_summary(raw_summary: str, max_len: int = 2000) -> str:
    """Strip HTML tags from a feed entry summary and truncate if needed.

    Uses feedparser-compatible heuristics: if the feed already provides a
    ``summary_detail.value`` we prefer that; otherwise strip tags via a
    simple regex fallback (for cases where feedparser did not decode HTML
    entities).
    """
    import re

    if not raw_summary:
        return ""
    # Remove HTML tags
    clean = re.sub(r"<[^>]+>", " ", raw_summary)
    # Collapse whitespace
    clean = re.sub(r"\s+", " ", clean).strip()
    if len(clean) > max_len:
        clean = clean[:max_len].rsplit(" ", 1)[0] + "…"
    return clean


# ---------------------------------------------------------------------------
# Core parser
# ---------------------------------------------------------------------------


def parse_feed(feed_name: str, feed_url: str, timeout: int = 30) -> FeedResult:
    """Fetch and parse a single RSS/Atom feed.

    Parameters
    ----------
    feed_name:
        Human-readable label (e.g. "OpenAI Blog").
    feed_url:
        Full URL of the RSS/Atom feed.
    timeout:
        Socket timeout in seconds forwarded to feedparser / urllib.

    Returns
    -------
    FeedResult
        Always returns a result object.  On failure the ``error`` field is
        populated and ``entries`` will be empty.
    """
    logger.info("Fetching feed '%s' from <%s>", feed_name, feed_url)
    result = FeedResult(feed_name=feed_name, feed_url=feed_url)

    try:
        default_timeout = socket.getdefaulttimeout()
        try:
            socket.setdefaulttimeout(timeout)
            parsed = feedparser.parse(feed_url, agent="x-agent/0.1")
        finally:
            socket.setdefaulttimeout(default_timeout)
    except URLError as exc:
        msg = f"Network error fetching '{feed_name}': {exc}"
        logger.error(msg)
        result.error = msg
        return result
    except Exception as exc:
        msg = f"Unexpected error fetching '{feed_name}': {exc}"
        logger.exception(msg)
        result.error = msg
        return result

    # feedparser may return a "bozo" flag for malformed feeds without
    # raising an exception.
    if parsed.bozo:
        bozo_msg = (
            f"Feed '{feed_name}' is malformed (bozo). "
            f"Exception: {parsed.bozo_exception}"
        )
        logger.warning(bozo_msg)
        # We still attempt to extract entries; many feeds are partially valid.

    if not parsed.entries:
        logger.info("Feed '%s' returned zero entries.", feed_name)

    for entry in parsed.entries:
        published = _safe_parse_date(entry.get("published_parsed"))
        summary_raw = entry.get("summary", "") or entry.get("description", "")
        summary = _clean_summary(summary_raw)

        feed_entry = FeedEntry(
            title=entry.get("title", "(no title)"),
            link=entry.get("link", ""),
            summary=summary,
            published=published,
            author=entry.get("author", ""),
            source_feed_name=feed_name,
            source_feed_url=feed_url,
            raw=dict(entry),
        )
        result.entries.append(feed_entry)

    logger.info(
        "Fetched %d entries from '%s'.", len(result.entries), feed_name
    )
    return result


def parse_feeds(
    feeds: list[dict[str, str]] | None = None,
    topic: str | None = None,
    timeout: int = 30,
) -> FetchOutcome:
    """Fetch and parse multiple feeds.

    Parameters
    ----------
    feeds:
        Optional explicit list of ``{"name": ..., "url": ...}`` dicts.
        When ``None``, falls back to ``ALL_FEEDS`` unless *topic* is given.
    topic:
        Optional topic slug referencing a subset of feeds defined in
        ``TOPIC_FEEDS`` (e.g. ``"ai_agentic"``).
    timeout:
        Per-feed socket timeout in seconds.

    Returns
    -------
    FetchOutcome
        Aggregated outcome with individual ``FeedResult`` objects and
        overall success/failure counts.
    """
    if feeds is not None:
        feed_list = feeds
    elif topic is not None:
        feed_list = TOPIC_FEEDS.get(topic, [])
        if not feed_list:
            logger.warning(
                "Unknown topic '%s'. Available: %s",
                topic,
                list(TOPIC_FEEDS.keys()),
            )
            return FetchOutcome()
    else:
        feed_list = ALL_FEEDS

    logger.info(
        "Starting batch fetch for %d feed(s).", len(feed_list)
    )

    outcome = FetchOutcome()
    for feed in feed_list:
        result = parse_feed(
            feed_name=feed["name"],
            feed_url=feed["url"],
            timeout=timeout,
        )
        outcome.results.append(result)
        outcome.total_feeds_processed += 1
        if result.error:
            outcome.total_feeds_failed += 1
        else:
            outcome.total_entries += len(result.entries)

    logger.info(
        "Batch fetch complete: %d entries from %d/%d successful feeds.",
        outcome.total_entries,
        outcome.total_feeds_processed - outcome.total_feeds_failed,
        outcome.total_feeds_processed,
    )
    return outcome


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def get_entries_by_topic(topic: str, timeout: int = 30) -> list[FeedEntry]:
    """Return all entries for a single topic as a flat list."""
    outcome = parse_feeds(topic=topic, timeout=timeout)
    entries: list[FeedEntry] = []
    for result in outcome.results:
        entries.extend(result.entries)
    return entries