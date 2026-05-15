"""Comment threads anchored to named ranges (or sheet!cell).

The CommentStore is a SQLite-backed append-only log of comment events
(create, reply, resolve, reopen). Comments are anchored to a workbook
named-range (preferred — survives sheet reordering) or to a sheet!cell
address (fallback). Each thread is identified by its first-comment id.

Workflow:

    store = CommentStore("deal.comments.db")

    # MD posts a question on the WACC named range
    c1 = store.create(
        anchor="wacc_rate",
        author="md@firm.com",
        body="Why 8.5% — peer median is 9.2%?",
    )

    # Junior replies
    c2 = store.reply(
        thread=c1.id,
        author="junior@firm.com",
        body="Used Damodaran 2026 mature ERP 4.23%; peer set was 5y avg.",
    )

    # MD resolves the thread
    store.resolve(thread=c1.id, author="md@firm.com")

The store is the source of truth for the comment data model — the
realtime sync (Yjs etc., Phase B) is a presentation layer that
mirrors the same events.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Literal, Optional


CommentEvent = Literal["create", "reply", "resolve", "reopen"]


@dataclass(frozen=True)
class Comment:
    """One immutable comment row (events form the audit log)."""
    id: str
    thread: str                  # = self.id for the first comment in a thread
    anchor: str                  # named range or "Sheet!Cell"
    author: str
    body: str
    created_at: str              # ISO-8601 UTC
    event: CommentEvent          # what kind of event this row represents
    resolved: bool = False       # True when thread was resolved (carried)
    metadata: dict = field(default_factory=dict)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS comment_events (
    id          TEXT PRIMARY KEY,
    thread      TEXT NOT NULL,
    anchor      TEXT NOT NULL,
    author      TEXT NOT NULL,
    body        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    event       TEXT NOT NULL,
    resolved    INTEGER NOT NULL DEFAULT 0,
    metadata    TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_comment_thread  ON comment_events(thread);
CREATE INDEX IF NOT EXISTS idx_comment_anchor  ON comment_events(anchor);
CREATE INDEX IF NOT EXISTS idx_comment_author  ON comment_events(author);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id(prefix: str = "C") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class CommentStore:
    """SQLite-backed append-only comment event log."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(_SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _insert(self, c: Comment) -> Comment:
        with self._conn() as cn:
            cn.execute(
                """INSERT INTO comment_events
                   (id, thread, anchor, author, body, created_at, event, resolved, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (c.id, c.thread, c.anchor, c.author, c.body,
                 c.created_at, c.event, int(c.resolved),
                 json.dumps(c.metadata)),
            )
        return c

    # ── public API ─────────────────────────────────────────────────────────

    def create(self, *, anchor: str, author: str, body: str,
               metadata: Optional[dict] = None) -> Comment:
        """Open a new comment thread anchored to a workbook range."""
        cid = _new_id()
        return self._insert(Comment(
            id=cid, thread=cid, anchor=anchor, author=author,
            body=body, created_at=_now_iso(), event="create",
            metadata=metadata or {},
        ))

    def reply(self, *, thread: str, author: str, body: str,
              metadata: Optional[dict] = None) -> Comment:
        """Append a reply to an existing thread."""
        rows = self.events_for_thread(thread)
        if not rows:
            raise KeyError(f"thread {thread!r} not found")
        anchor = rows[0].anchor  # inherit anchor from thread root
        cid = _new_id()
        return self._insert(Comment(
            id=cid, thread=thread, anchor=anchor, author=author,
            body=body, created_at=_now_iso(), event="reply",
            metadata=metadata or {},
        ))

    def resolve(self, *, thread: str, author: str,
                note: Optional[str] = None) -> Comment:
        """Mark a thread resolved (terminal)."""
        rows = self.events_for_thread(thread)
        if not rows:
            raise KeyError(f"thread {thread!r} not found")
        anchor = rows[0].anchor
        cid = _new_id()
        return self._insert(Comment(
            id=cid, thread=thread, anchor=anchor, author=author,
            body=note or "(resolved)", created_at=_now_iso(),
            event="resolve", resolved=True, metadata={},
        ))

    def reopen(self, *, thread: str, author: str,
               note: Optional[str] = None) -> Comment:
        """Reopen a previously-resolved thread."""
        rows = self.events_for_thread(thread)
        if not rows:
            raise KeyError(f"thread {thread!r} not found")
        anchor = rows[0].anchor
        cid = _new_id()
        return self._insert(Comment(
            id=cid, thread=thread, anchor=anchor, author=author,
            body=note or "(reopened)", created_at=_now_iso(),
            event="reopen", resolved=False, metadata={},
        ))

    # ── queries ────────────────────────────────────────────────────────────

    def _row_to_comment(self, row: sqlite3.Row) -> Comment:
        return Comment(
            id=row["id"], thread=row["thread"], anchor=row["anchor"],
            author=row["author"], body=row["body"],
            created_at=row["created_at"], event=row["event"],
            resolved=bool(row["resolved"]),
            metadata=json.loads(row["metadata"] or "{}"),
        )

    def events_for_thread(self, thread: str) -> list[Comment]:
        # rowid = monotonic insert order; safer than created_at when sub-second
        # collisions occur in tests / fast-paced edits.
        with self._conn() as cn:
            rows = cn.execute(
                "SELECT * FROM comment_events WHERE thread=? ORDER BY rowid",
                (thread,),
            ).fetchall()
        return [self._row_to_comment(r) for r in rows]

    def threads_for_anchor(self, anchor: str) -> list[Comment]:
        """Return the thread-root comment for every thread on an anchor."""
        with self._conn() as cn:
            rows = cn.execute(
                """SELECT * FROM comment_events
                   WHERE anchor=? AND event='create'
                   ORDER BY rowid""",
                (anchor,),
            ).fetchall()
        return [self._row_to_comment(r) for r in rows]

    def open_threads(self) -> list[Comment]:
        """Return the thread-root comment for every thread whose latest
        event left it in an UNresolved state.

        Uses sqlite's implicit ``rowid`` (monotonic insert order) to pick
        the latest event per thread — robust to same-second timestamp
        collisions that ``MAX(created_at)`` alone can't disambiguate.
        """
        with self._conn() as cn:
            latest_rows = cn.execute(
                """SELECT e.*
                   FROM comment_events e
                   INNER JOIN (
                     SELECT thread, MAX(rowid) AS last_rowid
                     FROM comment_events GROUP BY thread
                   ) latest
                     ON e.thread = latest.thread
                    AND e.rowid = latest.last_rowid
                   WHERE e.resolved = 0"""
            ).fetchall()
            open_thread_ids = [r["thread"] for r in latest_rows]
            if not open_thread_ids:
                return []
            placeholders = ",".join("?" for _ in open_thread_ids)
            roots = cn.execute(
                f"""SELECT * FROM comment_events
                    WHERE thread IN ({placeholders}) AND event='create'
                    ORDER BY rowid""",
                open_thread_ids,
            ).fetchall()
        return [self._row_to_comment(r) for r in roots]

    def all_threads(self) -> list[Comment]:
        with self._conn() as cn:
            rows = cn.execute(
                "SELECT * FROM comment_events WHERE event='create' ORDER BY rowid"
            ).fetchall()
        return [self._row_to_comment(r) for r in rows]
