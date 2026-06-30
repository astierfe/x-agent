"""TweetClaw CSV import helpers for the x-agent sourcing layer.

The importer maps exported X/Twitter source packets into the existing
``FeedEntry`` shape. It does not publish, reply, or mutate accounts. Imported
items still flow through the same relevance, draft, and operator review queue
as RSS articles.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Iterable

from src.sourcing.rss_parser import FeedEntry

_TEXT_COLUMNS = ("text", "fullText", "full_text", "content", "body")
_URL_COLUMNS = ("url", "tweetUrl", "tweet_url", "permalink")
_ID_COLUMNS = ("id", "tweetId", "tweet_id", "postID", "post_id")
_AUTHOR_COLUMNS = (
    "authorUsername",
    "author_username",
    "username",
    "screenName",
    "screen_name",
    "author",
)
_DATE_COLUMNS = ("createdAt", "created_at", "date", "Date", "published_at")
_METRIC_COLUMNS = (
    "likeCount",
    "likes",
    "retweetCount",
    "retweets",
    "replyCount",
    "replies",
    "quoteCount",
    "quotes",
    "viewCount",
    "views",
)


def load_tweetclaw_export(path: str | Path) -> list[FeedEntry]:
    """Load a TweetClaw CSV export as ``FeedEntry`` records."""
    export_path = Path(path)
    with export_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return [
            _row_to_entry(row, source_url=str(export_path))
            for row in reader
            if _value(row, _TEXT_COLUMNS) or _value(row, _URL_COLUMNS)
        ]


def _row_to_entry(row: dict[str, str], *, source_url: str) -> FeedEntry:
    text = _value(row, _TEXT_COLUMNS)
    author = _clean_handle(_value(row, _AUTHOR_COLUMNS))
    tweet_id = _value(row, _ID_COLUMNS)
    link = _value(row, _URL_COLUMNS) or _tweet_url(author, tweet_id)
    title = _title_from_text(text, tweet_id)
    published = _parse_timestamp(_value(row, _DATE_COLUMNS))
    summary = _summary_from_row(text, row)
    return FeedEntry(
        title=title,
        link=link,
        summary=summary,
        published=published,
        author=author,
        source_feed_name="TweetClaw export",
        source_feed_url=source_url,
        raw=dict(row),
    )


def _value(row: dict[str, str], columns: Iterable[str]) -> str:
    for column in columns:
        value = row.get(column)
        if value and value.strip():
            return value.strip()
    return ""


def _clean_handle(value: str) -> str:
    return value.lstrip("@")


def _tweet_url(author: str, tweet_id: str) -> str:
    if author and tweet_id:
        return f"https://x.com/{author}/status/{tweet_id}"
    if tweet_id:
        return f"tweetclaw://tweet/{tweet_id}"
    return "tweetclaw://tweet/unknown"


def _title_from_text(text: str, tweet_id: str) -> str:
    if not text:
        return f"TweetClaw item {tweet_id or 'unknown'}"
    title = " ".join(text.split())
    return title if len(title) <= 96 else f"{title[:93].rstrip()}..."


def _parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _summary_from_row(text: str, row: dict[str, str]) -> str:
    metrics = []
    for column in _METRIC_COLUMNS:
        value = row.get(column)
        if value and value.strip():
            metrics.append(f"{column}={value.strip()}")
    if metrics:
        return f"{text}\n\nTweet metrics: {', '.join(metrics)}"
    return text
