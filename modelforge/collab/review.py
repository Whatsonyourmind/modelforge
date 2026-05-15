"""4-eyes reviewer approval state machine.

The state machine enforces that every workbook destined for a senior
sign-off goes through:

    DRAFT
      ↓ request_review(reviewer)
    UNDER_REVIEW
      ↓                 ↓
    sign_off()        reject(reason)
      ↓                 ↓
    APPROVED          REJECTED → request_review (loops back)

Authorship rules ("4-eyes"):
- The author of the workbook (recorded at request_review time) cannot
  also be the reviewer. Calling sign_off / reject with author == reviewer
  raises InvalidStateTransition.
- Multiple reviewers can be configured (e.g., compliance + MD); all must
  sign_off before status flips to APPROVED.

State is a dataclass with an event log so the entire history is
auditable. Persistable via JSON for storage alongside the workbook
manifest.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class ApprovalStatus(str, Enum):
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewerRole(str, Enum):
    AUTHOR = "author"
    REVIEWER = "reviewer"
    COMPLIANCE = "compliance"
    MD = "md"


class InvalidStateTransition(RuntimeError):
    """Raised when a workflow operation is invalid for the current state."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class ReviewEvent:
    """One entry in the audit log."""
    at: str
    actor: str
    role: ReviewerRole
    action: str        # e.g. "request_review", "sign_off", "reject"
    note: str = ""


@dataclass
class ReviewState:
    """Full state of one workbook review."""
    workbook: str
    author: str
    status: ApprovalStatus = ApprovalStatus.DRAFT
    required_reviewers: list[str] = field(default_factory=list)
    signed_off_by: list[str] = field(default_factory=list)
    rejected_by: Optional[str] = None
    rejection_note: Optional[str] = None
    events: list[ReviewEvent] = field(default_factory=list)

    # ── serialization ─────────────────────────────────────────────────────

    def to_json(self) -> str:
        return json.dumps(asdict(self), default=str, indent=2)

    @classmethod
    def from_json(cls, s: str) -> "ReviewState":
        d = json.loads(s)
        events = [ReviewEvent(**e) for e in d.pop("events", [])]
        d["status"] = ApprovalStatus(d["status"])
        return cls(events=events, **d)


# ── transitions ──────────────────────────────────────────────────────────


def request_review(
    state: ReviewState,
    *,
    reviewers: list[str],
    actor: str,
) -> ReviewState:
    """Move from DRAFT or REJECTED into UNDER_REVIEW."""
    if state.status not in (ApprovalStatus.DRAFT, ApprovalStatus.REJECTED):
        raise InvalidStateTransition(
            f"Cannot request_review from status={state.status.value}"
        )
    if not reviewers:
        raise InvalidStateTransition("At least one reviewer required")
    if state.author in reviewers:
        raise InvalidStateTransition(
            f"4-eyes violation: author {state.author!r} cannot be a reviewer"
        )
    state.status = ApprovalStatus.UNDER_REVIEW
    state.required_reviewers = list(reviewers)
    state.signed_off_by = []
    state.rejected_by = None
    state.rejection_note = None
    state.events.append(ReviewEvent(
        at=_now_iso(), actor=actor, role=ReviewerRole.AUTHOR,
        action="request_review",
        note=f"Reviewers: {', '.join(reviewers)}",
    ))
    return state


def sign_off(
    state: ReviewState,
    *,
    reviewer: str,
    role: ReviewerRole = ReviewerRole.REVIEWER,
    note: str = "",
) -> ReviewState:
    """Reviewer signs off. When ALL required reviewers sign, status → APPROVED."""
    if state.status != ApprovalStatus.UNDER_REVIEW:
        raise InvalidStateTransition(
            f"Cannot sign_off from status={state.status.value}"
        )
    if reviewer == state.author:
        raise InvalidStateTransition(
            f"4-eyes violation: author {state.author!r} cannot sign off"
        )
    if reviewer not in state.required_reviewers:
        raise InvalidStateTransition(
            f"Reviewer {reviewer!r} not in required set: "
            f"{state.required_reviewers}"
        )
    if reviewer in state.signed_off_by:
        raise InvalidStateTransition(
            f"Reviewer {reviewer!r} already signed off"
        )
    state.signed_off_by.append(reviewer)
    state.events.append(ReviewEvent(
        at=_now_iso(), actor=reviewer, role=role,
        action="sign_off", note=note,
    ))
    if set(state.signed_off_by) >= set(state.required_reviewers):
        state.status = ApprovalStatus.APPROVED
        state.events.append(ReviewEvent(
            at=_now_iso(), actor=reviewer, role=role,
            action="status_change",
            note=f"All required reviewers signed → APPROVED",
        ))
    return state


def reject(
    state: ReviewState,
    *,
    reviewer: str,
    role: ReviewerRole = ReviewerRole.REVIEWER,
    reason: str,
) -> ReviewState:
    """One reject sends the workbook back to author (status → REJECTED)."""
    if state.status != ApprovalStatus.UNDER_REVIEW:
        raise InvalidStateTransition(
            f"Cannot reject from status={state.status.value}"
        )
    if reviewer == state.author:
        raise InvalidStateTransition(
            f"4-eyes violation: author {state.author!r} cannot reject"
        )
    if reviewer not in state.required_reviewers:
        raise InvalidStateTransition(
            f"Reviewer {reviewer!r} not in required set: "
            f"{state.required_reviewers}"
        )
    state.status = ApprovalStatus.REJECTED
    state.rejected_by = reviewer
    state.rejection_note = reason
    state.events.append(ReviewEvent(
        at=_now_iso(), actor=reviewer, role=role,
        action="reject", note=reason,
    ))
    return state
