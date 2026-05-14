"""Cell-comments — annotations on graph nodes for review workflow.

Adds a `cell_comments` table to the existing ``graph/store.py`` SQLite DB.
Comments are append-only (resolved comments stay in the log but become hidden
by default). Each comment carries:

    - node_ref (sheet!cell or sheet!named_range)
    - author (email or username)
    - body (markdown)
    - created_at (Unix timestamp)
    - resolved (bool)
    - resolved_by / resolved_at

Used by the v0.10 collaboration story: a reviewer leaves comments on a
generated workbook → author addresses → comments resolve. Mirrors the
Google Docs / Word review-pane UX without requiring a hosted SaaS.

Lightweight schema — kept in the same SQLite as the linkage graph so that
a single .graph.db is the canonical review surface.
"""
from __future__ import annotations

import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


COMMENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS cell_comments (
    comment_id TEXT PRIMARY KEY,
    node_ref TEXT NOT NULL,
    author TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at REAL NOT NULL,
    resolved INTEGER NOT NULL DEFAULT 0,
    resolved_by TEXT,
    resolved_at REAL
);
CREATE INDEX IF NOT EXISTS idx_comments_node ON cell_comments(node_ref);
CREATE INDEX IF NOT EXISTS idx_comments_resolved ON cell_comments(resolved);
CREATE INDEX IF NOT EXISTS idx_comments_author ON cell_comments(author);
"""


@dataclass
class Comment:
    comment_id: str
    node_ref: str
    author: str
    body: str
    created_at: float
    resolved: bool
    resolved_by: Optional[str] = None
    resolved_at: Optional[float] = None


class CommentStore:
    """SQLite-backed cell-comment store.

    Co-located with ``graph/store.py`` SQLite — both use the same .graph.db.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.executescript(COMMENTS_SCHEMA)
        self._conn.commit()

    def add(self, node_ref: str, author: str, body: str) -> Comment:
        """Add a new comment. Returns the persisted Comment."""
        cid = str(uuid.uuid4())
        now = time.time()
        self._conn.execute(
            """INSERT INTO cell_comments (comment_id, node_ref, author, body, created_at, resolved)
               VALUES (?,?,?,?,?,0)""",
            (cid, node_ref, author, body, now),
        )
        self._conn.commit()
        return Comment(
            comment_id=cid, node_ref=node_ref, author=author, body=body,
            created_at=now, resolved=False,
        )

    def resolve(self, comment_id: str, resolver: str) -> bool:
        """Mark a comment resolved. Returns True if a row was updated."""
        now = time.time()
        cur = self._conn.execute(
            """UPDATE cell_comments SET resolved=1, resolved_by=?, resolved_at=?
               WHERE comment_id=? AND resolved=0""",
            (resolver, now, comment_id),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def list_for_node(self, node_ref: str, include_resolved: bool = False) -> list[Comment]:
        """All comments on a specific cell/node, newest-first."""
        if include_resolved:
            sql = "SELECT * FROM cell_comments WHERE node_ref=? ORDER BY created_at DESC"
            params = (node_ref,)
        else:
            sql = "SELECT * FROM cell_comments WHERE node_ref=? AND resolved=0 ORDER BY created_at DESC"
            params = (node_ref,)
        cur = self._conn.execute(sql, params)
        return [self._row_to_comment(row) for row in cur.fetchall()]

    def list_all(self, include_resolved: bool = False, limit: int = 500) -> list[Comment]:
        """All comments in the store, newest-first."""
        if include_resolved:
            sql = "SELECT * FROM cell_comments ORDER BY created_at DESC LIMIT ?"
        else:
            sql = "SELECT * FROM cell_comments WHERE resolved=0 ORDER BY created_at DESC LIMIT ?"
        cur = self._conn.execute(sql, (limit,))
        return [self._row_to_comment(row) for row in cur.fetchall()]

    def summary(self) -> dict[str, int]:
        """Counts: total, open, resolved, distinct authors, distinct nodes."""
        cur = self._conn.execute(
            "SELECT COUNT(*), SUM(CASE WHEN resolved=0 THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN resolved=1 THEN 1 ELSE 0 END), "
            "COUNT(DISTINCT author), COUNT(DISTINCT node_ref) "
            "FROM cell_comments"
        )
        total, open_, resolved, authors, nodes = cur.fetchone()
        return {
            "total": total or 0,
            "open": open_ or 0,
            "resolved": resolved or 0,
            "distinct_authors": authors or 0,
            "distinct_nodes": nodes or 0,
        }

    @staticmethod
    def _row_to_comment(row) -> Comment:
        return Comment(
            comment_id=row[0], node_ref=row[1], author=row[2], body=row[3],
            created_at=row[4], resolved=bool(row[5]),
            resolved_by=row[6], resolved_at=row[7],
        )

    def close(self) -> None:
        self._conn.close()
