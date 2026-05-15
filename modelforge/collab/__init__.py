"""Collaboration primitives — comments anchored to named ranges,
4-eyes reviewer approval flow, version diff between workbook builds.

This package ships the **data model + state machine + storage** for
multi-user review workflows. The *realtime sync* layer (Yjs CRDT over
Cloudflare Workers Durable Objects, or Liveblocks, or Y-Sweet) is the
Phase-B integration layer that wraps these primitives — but the full
single-user, async, audit-grade workflow already works today, locally,
zero spend.

Why both layers?
- The state machine and audit trail must be deterministic and testable
  even without realtime presence — auditors and committee reviewers
  often work async via comment threads, not live cursors.
- Realtime sync (Yjs) is a UX upgrade, not a correctness primitive:
  it lets multiple users see each others' edits live but doesn't
  change the data model or approval flow.

Public API:

    from modelforge.collab import (
        Comment, CommentStore,
        ApprovalStatus, ReviewerRole, ReviewState,
        request_review, sign_off, reject,
        WorkbookDiff, diff_workbooks,
    )
"""
from __future__ import annotations

from modelforge.collab.comments import Comment, CommentStore
from modelforge.collab.review import (
    ApprovalStatus,
    ReviewerRole,
    ReviewState,
    request_review,
    sign_off,
    reject,
    InvalidStateTransition,
)
from modelforge.collab.diff import WorkbookDiff, CellChange, diff_workbooks
from modelforge.collab.realtime import (
    RealtimeClient,
    RealtimeError,
    sync_store_to_remote,
)

__all__ = [
    "Comment",
    "CommentStore",
    "ApprovalStatus",
    "ReviewerRole",
    "ReviewState",
    "request_review",
    "sign_off",
    "reject",
    "InvalidStateTransition",
    "WorkbookDiff",
    "CellChange",
    "diff_workbooks",
    "RealtimeClient",
    "RealtimeError",
    "sync_store_to_remote",
]
