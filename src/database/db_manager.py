"""
SQLite database management module for x-agent persistence.

Provides safe schema creation, batch article insertion with deduplication,
and retrieval of stored articles — all using Python context managers
and strict type hints.

Target: Python 3.11+
Database path: data/x_agent.db (relative to the project root)
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

from src.sourcing.rss_parser import FeedEntry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database location
# ---------------------------------------------------------------------------

# The data/ directory is at the project root (i.e. the directory where
# main.py lives).  Inside Docker this resolves to /app/data/x_agent.db.
_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "x_agent.db"

# ---------------------------------------------------------------------------
# Schema definition
# ---------------------------------------------------------------------------

_CREATE_ARTICLES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS articles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    link        TEXT    NOT NULL UNIQUE,
    summary     TEXT    NOT NULL DEFAULT '',
    published_at TIMESTAMP,
    author      TEXT    NOT NULL DEFAULT '',
    source_name TEXT    NOT NULL DEFAULT '',
    source_url  TEXT    NOT NULL DEFAULT '',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_INSERT_ARTICLE_SQL = """
INSERT OR IGNORE INTO articles
    (title, link, summary, published_at, author, source_name, source_url)
VALUES
    (:title, :link, :summary, :published_at, :author, :source_name, :source_url);
"""

_SELECT_PENDING_SQL = """
SELECT
    id,
    title,
    link,
    summary,
    published_at,
    author,
    source_name,
    source_url,
    created_at
FROM articles
ORDER BY published_at DESC, created_at DESC;
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection to the x_agent database.

    Ensures the parent directory exists before connecting.
    """
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def initialize_db() -> None:
    """Create the ``articles`` table if it does not already exist.

    Safe to call multiple times — uses ``CREATE TABLE IF NOT EXISTS``.
    """
    logger.info("Initializing database at %s ...", _DB_PATH)
    with _get_connection() as conn:
        conn.execute(_CREATE_ARTICLES_TABLE_SQL)
        conn.commit()
    logger.info("Database schema is up-to-date.")


def save_entries(entries: list[FeedEntry]) -> int:
    """Persist a batch of parsed feed entries into the database.

    Uses ``INSERT OR IGNORE`` so that duplicate articles (identified by
    their unique ``link`` field) are silently skipped.

    Parameters
    ----------
    entries:
        List of ``FeedEntry`` objects returned by the RSS parser.

    Returns
    -------
    int
        Number of rows that were **actually inserted** (i.e. new entries).
    """
    if not entries:
        logger.debug("save_entries called with an empty list — nothing to do.")
        return 0

    rows_before: int = 0
    rows_after: int = 0

    with _get_connection() as conn:
        rows_before = conn.execute(
            "SELECT COUNT(*) FROM articles;"
        ).fetchone()[0]  # type: ignore[index]

        params_list: list[dict[str, Any]] = [
            {
                "title": entry.title,
                "link": entry.link,
                "summary": entry.summary,
                "published_at": (
                    entry.published.isoformat() if entry.published else None
                ),
                "author": entry.author,
                "source_name": entry.source_feed_name,
                "source_url": entry.source_feed_url,
            }
            for entry in entries
        ]

        conn.executemany(_INSERT_ARTICLE_SQL, params_list)
        conn.commit()

        rows_after = conn.execute(
            "SELECT COUNT(*) FROM articles;"
        ).fetchone()[0]  # type: ignore[index]

    inserted = rows_after - rows_before
    skipped = len(entries) - inserted
    logger.info(
        "save_entries: %d total, %d inserted, %d skipped (duplicates).",
        len(entries),
        inserted,
        skipped,
    )
    return inserted


def get_pending_articles(limit: int | None = None) -> list[dict[str, Any]]:
    """Retrieve stored articles ordered by publication date (newest first).

    Parameters
    ----------
    limit:
        Optional maximum number of rows to return.

    Returns
    -------
    list[dict[str, Any]]
        Each dict represents one article row, with keys matching the
        column names (``id``, ``title``, ``link``, ``summary``,
        ``published_at``, ``author``, ``source_name``, ``source_url``,
        ``created_at``).
    """
    query = _SELECT_PENDING_SQL
    params: tuple = ()

    if limit is not None:
        query = _SELECT_PENDING_SQL.rstrip(";") + " LIMIT ?;"
        params = (limit,)

    with _get_connection() as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

    articles = [dict(row) for row in rows]
    logger.debug("get_pending_articles returned %d row(s).", len(articles))
    return articles