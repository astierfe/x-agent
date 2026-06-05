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

_CREATE_DRAFTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS drafts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id  INTEGER NOT NULL,
    is_relevant BOOLEAN NOT NULL DEFAULT 0,
    reason      TEXT    NOT NULL DEFAULT '',
    draft_text  TEXT    NOT NULL DEFAULT '',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
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

_INSERT_DRAFT_SQL = """
INSERT INTO drafts
    (article_id, is_relevant, reason, draft_text)
VALUES
    (:article_id, :is_relevant, :reason, :draft_text);
"""

# Articles that have NOT been processed by the intelligence pipeline yet.
_SELECT_UNPROCESSED_ARTICLES_SQL = """
SELECT
    a.id,
    a.title,
    a.link,
    a.summary,
    a.published_at,
    a.author,
    a.source_name,
    a.source_url,
    a.created_at
FROM articles a
LEFT JOIN drafts d ON a.id = d.article_id
WHERE d.id IS NULL
ORDER BY a.published_at DESC, a.created_at DESC;
"""

_SELECT_PENDING_DRAFTS_SQL = """
SELECT
    d.id AS draft_id,
    d.is_relevant,
    d.reason,
    d.draft_text,
    d.created_at AS draft_created_at,
    a.id AS article_id,
    a.title,
    a.link,
    a.summary,
    a.source_name,
    a.source_url
FROM drafts d
INNER JOIN articles a ON d.article_id = a.id
ORDER BY d.created_at DESC;
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
    """Create the ``articles`` and ``drafts`` tables if they do not exist.

    Safe to call multiple times — uses ``CREATE TABLE IF NOT EXISTS``.
    """
    logger.info("Initializing database at %s ...", _DB_PATH)
    with _get_connection() as conn:
        conn.execute(_CREATE_ARTICLES_TABLE_SQL)
        conn.execute(_CREATE_DRAFTS_TABLE_SQL)
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


def get_unprocessed_articles(
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Return articles that have NOT yet been processed by the intelligence pipeline.

    Uses a ``LEFT JOIN`` against the ``drafts`` table — every article that
    has gone through the filter (even rejected ones) gets a row in
    ``drafts``, so this query is naturally idempotent across runs.

    Parameters
    ----------
    limit:
        Optional maximum number of rows to return.

    Returns
    -------
    list[dict[str, Any]]
        Each dict represents one article row (same keys as
        :func:`get_pending_articles`).
    """
    query = _SELECT_UNPROCESSED_ARTICLES_SQL
    params: tuple = ()

    if limit is not None:
        query = _SELECT_UNPROCESSED_ARTICLES_SQL.rstrip(";") + " LIMIT ?;"
        params = (limit,)

    with _get_connection() as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

    articles = [dict(row) for row in rows]
    logger.debug(
        "get_unprocessed_articles returned %d row(s).", len(articles)
    )
    return articles


def save_draft(
    article_id: int,
    is_relevant: bool,
    reason: str,
    draft_text: str,
) -> int:
    """Insert a draft row for a processed article.

    Every analyzed article MUST receive a row in ``drafts``, even if it
    was rejected (``is_relevant = False``).  This ensures the
    ``LEFT JOIN`` in :func:`get_unprocessed_articles` won't pick it up
    again on the next run — guaranteeing idempotency and preventing
    duplicate API calls for rejected articles.

    Parameters
    ----------
    article_id:
        The ``id`` of the article in the ``articles`` table.
    is_relevant:
        ``True`` if the filter deemed the article relevant.
    reason:
        Human-readable explanation from the relevance filter.
    draft_text:
        The generated draft post text (empty string if not relevant).

    Returns
    -------
    int
        The ``id`` of the newly inserted draft row.
    """
    logger.info(
        "Saving draft for article_id=%d (relevant=%s)…",
        article_id,
        is_relevant,
    )
    with _get_connection() as conn:
        cursor = conn.execute(
            _INSERT_DRAFT_SQL,
            {
                "article_id": article_id,
                "is_relevant": int(is_relevant),
                "reason": reason,
                "draft_text": draft_text,
            },
        )
        conn.commit()
        draft_id = cursor.lastrowid

    logger.debug("Draft saved with id=%d.", draft_id)
    return draft_id  # type: ignore[return-value]


def get_pending_drafts(
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Retrieve all drafts joined with their parent articles (newest first).

    Parameters
    ----------
    limit:
        Optional maximum number of rows to return.

    Returns
    -------
    list[dict[str, Any]]
        Each dict contains draft fields (``draft_id``, ``is_relevant``,
        ``reason``, ``draft_text``, ``draft_created_at``) and the
        corresponding article fields (``article_id``, ``title``,
        ``link``, ``summary``, ``source_name``, ``source_url``).
    """
    query = _SELECT_PENDING_DRAFTS_SQL
    params: tuple = ()

    if limit is not None:
        query = _SELECT_PENDING_DRAFTS_SQL.rstrip(";") + " LIMIT ?;"
        params = (limit,)

    with _get_connection() as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

    drafts = [dict(row) for row in rows]
    logger.debug("get_pending_drafts returned %d row(s).", len(drafts))
    return drafts
