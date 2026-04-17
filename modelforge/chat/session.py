"""REPL session for `modelforge chat`.

Supports two backends:

* ``api``  — Anthropic SDK (requires ANTHROPIC_API_KEY). Uses prompt
  caching on the system prompt so subsequent turns are cheap.
* ``dry``  — prints the constructed prompt + waits for user paste.
  Useful when no API key is available and for tests / demos.

Conversation history is in-memory. Export to markdown via
``ChatSession.to_markdown()``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

from modelforge.chat.context import build_system_prompt


Backend = Literal["api", "dry"]
DEFAULT_MODEL = "claude-opus-4-7"


@dataclass
class ChatTurn:
    role: Literal["user", "assistant"]
    content: str


@dataclass
class ChatSession:
    xlsx_path: Path
    graph_db: Optional[Path] = None
    model: str = DEFAULT_MODEL
    backend: Backend = "api"
    system_prompt: str = ""
    history: list[ChatTurn] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.system_prompt:
            self.system_prompt = build_system_prompt(self.xlsx_path, self.graph_db)

    # ── Ask a question ────────────────────────────────────────────────────

    def ask(self, question: str) -> str:
        """Send one user turn; return assistant's reply. Updates history."""
        self.history.append(ChatTurn(role="user", content=question))
        if self.backend == "api":
            reply = self._ask_via_anthropic(question)
        else:
            reply = self._ask_dry(question)
        self.history.append(ChatTurn(role="assistant", content=reply))
        return reply

    # ── Backends ──────────────────────────────────────────────────────────

    def _ask_via_anthropic(self, question: str) -> str:
        try:
            import anthropic
        except ImportError as e:
            raise RuntimeError(
                "Anthropic SDK not installed. Install with "
                "`pip install 'modelforge[ingest]'` or pass --backend dry."
            ) from e

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. Export it, or pass --backend dry."
            )

        client = anthropic.Anthropic(api_key=api_key)

        # Build messages from history (without the latest user turn,
        # which goes in the final `messages` entry).
        msgs: list[dict] = []
        # All but the last (just-appended) user turn
        for t in self.history[:-1]:
            msgs.append({"role": t.role, "content": t.content})
        msgs.append({"role": "user", "content": question})

        resp = client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": self.system_prompt,
                    "cache_control": {"type": "ephemeral"},
                },
            ],
            messages=msgs,
        )
        reply = "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        )
        return reply or "(empty response)"

    def _ask_dry(self, question: str) -> str:
        # Return a stub that summarizes the prompt — useful for tests
        # and for dev-laptops without API key.
        return (
            f"[dry-run backend] System prompt is {len(self.system_prompt)} "
            f"chars. Question: {question!r}. Cannot call Claude without "
            f"ANTHROPIC_API_KEY."
        )

    # ── Export ────────────────────────────────────────────────────────────

    def to_markdown(self) -> str:
        lines = [f"# ModelForge chat — {self.xlsx_path.name}", ""]
        for t in self.history:
            prefix = "**You:**" if t.role == "user" else "**ModelForge:**"
            lines.append(prefix)
            lines.append("")
            lines.append(t.content)
            lines.append("")
        return "\n".join(lines)


__all__ = ["ChatSession", "ChatTurn"]
