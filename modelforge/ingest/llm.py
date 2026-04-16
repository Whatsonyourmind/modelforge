"""LLM backend abstraction — Anthropic API vs Claude CLI subprocess.

Two backends, same interface:
    AnthropicAPIBackend  — uses anthropic SDK + tool_use + prompt caching.
                           Requires ANTHROPIC_API_KEY env var.
    ClaudeCLIBackend     — uses `claude -p` subprocess. No API key needed;
                           uses the user's existing Claude Code subscription.

Both return (payload_dict, cache_hit_bool, input_tokens, output_tokens).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Any, Optional, Protocol


@dataclass
class LLMResponse:
    payload: dict
    cache_hit: bool = False
    input_tokens: int = 0
    output_tokens: int = 0


class LLMBackend(Protocol):
    """Minimal interface both backends satisfy."""

    def call_json(
        self,
        system_prompt: str,
        user_prompt: str,
        tool_name: str | None = None,
        tool_schema: dict | None = None,
    ) -> LLMResponse:
        """Send a prompt and get back a parsed JSON dict."""
        ...


# ─────────────────────────────────────────────────────────────────
# Backend 1: Anthropic SDK (requires ANTHROPIC_API_KEY)
# ─────────────────────────────────────────────────────────────────

class AnthropicAPIBackend:
    """Uses anthropic SDK with tool_use forcing + prompt caching."""

    def __init__(self, model: str = "claude-opus-4-6", use_cache: bool = True):
        from anthropic import Anthropic
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Use --backend cli to use "
                "your Claude Code subscription instead, or set the key."
            )
        self._client = Anthropic()
        self._model = model
        self._use_cache = use_cache

    def call_json(
        self,
        system_prompt: str,
        user_prompt: str,
        tool_name: str | None = None,
        tool_schema: dict | None = None,
    ) -> LLMResponse:
        system_block: dict[str, Any] = {"type": "text", "text": system_prompt}
        if self._use_cache:
            system_block["cache_control"] = {"type": "ephemeral"}

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 4096,
            "system": [system_block],
            "messages": [{"role": "user", "content": user_prompt}],
        }

        if tool_name and tool_schema:
            tool_block: dict[str, Any] = {
                "name": tool_name,
                "description": f"Emit structured JSON for {tool_name}.",
                "input_schema": tool_schema,
            }
            if self._use_cache:
                tool_block["cache_control"] = {"type": "ephemeral"}
            kwargs["tools"] = [tool_block]
            kwargs["tool_choice"] = {"type": "tool", "name": tool_name}

        response = self._client.messages.create(**kwargs)

        # Extract payload
        payload: dict = {}
        if tool_name:
            for block in response.content:
                if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
                    payload = block.input
                    break
            if not payload:
                raise RuntimeError(f"No tool_use block for {tool_name}")
        else:
            text = response.content[0].text if response.content else ""
            payload = _parse_json_from_text(text)

        cache_read = getattr(response.usage, "cache_read_input_tokens", 0) or 0
        return LLMResponse(
            payload=payload,
            cache_hit=cache_read > 0,
            input_tokens=getattr(response.usage, "input_tokens", 0) or 0,
            output_tokens=getattr(response.usage, "output_tokens", 0) or 0,
        )


# ─────────────────────────────────────────────────────────────────
# Backend 2: Claude CLI subprocess (no API key needed)
# ─────────────────────────────────────────────────────────────────

class ClaudeCLIBackend:
    """Uses `claude -p` subprocess — runs on the user's Claude Code subscription.

    No API key needed. Prompt-engineers for JSON output instead of tool_use.
    Slightly slower (subprocess overhead) but zero additional cost.
    """

    def __init__(self, timeout: int = 120):
        self._timeout = timeout
        # Verify claude CLI is available
        try:
            r = subprocess.run(
                ["claude", "--version"],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode != 0:
                raise RuntimeError("claude CLI returned non-zero")
        except FileNotFoundError:
            raise RuntimeError(
                "claude CLI not found. Install Claude Code: "
                "https://docs.anthropic.com/en/docs/claude-code"
            )

    def call_json(
        self,
        system_prompt: str,
        user_prompt: str,
        tool_name: str | None = None,
        tool_schema: dict | None = None,
    ) -> LLMResponse:
        # Build a single prompt that asks for JSON output
        parts = [system_prompt, "\n---\n", user_prompt]

        if tool_schema:
            schema_str = json.dumps(tool_schema, indent=2)
            parts.append(
                "\n\n# OUTPUT FORMAT\n"
                "Return ONLY valid JSON matching this schema. "
                "No explanation, no markdown fences, no prose before or after.\n\n"
                f"```json-schema\n{schema_str}\n```"
            )
        else:
            parts.append(
                "\n\n# OUTPUT FORMAT\n"
                "Return ONLY valid JSON. No explanation, no markdown fences."
            )

        full_prompt = "\n".join(parts)

        result = subprocess.run(
            ["claude", "-p", full_prompt, "--output-format", "text"],
            capture_output=True,
            text=True,
            timeout=self._timeout,
        )

        if result.returncode != 0:
            stderr = result.stderr.strip()[:500]
            raise RuntimeError(f"claude CLI failed (exit {result.returncode}): {stderr}")

        raw = result.stdout.strip()
        payload = _parse_json_from_text(raw)
        # CLI backend has no token accounting; estimate from prompt length
        return LLMResponse(
            payload=payload,
            cache_hit=False,
            input_tokens=len(full_prompt) // 4,  # rough estimate
            output_tokens=len(raw) // 4,
        )


# ─────────────────────────────────────────────────────────────────
# Shared JSON parser — handles markdown fences, leading prose, etc.
# ─────────────────────────────────────────────────────────────────

def _parse_json_from_text(text: str) -> dict:
    """Extract the first valid JSON object from text that may include
    markdown fences, leading prose, or trailing explanation."""
    text = text.strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip markdown fences
    fenced = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Find first { ... } block (greedy from first { to last })
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group())
        except json.JSONDecodeError:
            pass

    raise RuntimeError(
        f"Could not parse JSON from LLM response. First 300 chars: {text[:300]}"
    )


# ─────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────

def get_backend(
    backend: str = "cli",
    model: str = "claude-opus-4-6",
    use_cache: bool = True,
) -> LLMBackend:
    """Create the requested backend.

    backend="cli"  — Claude CLI subprocess (default, no API key)
    backend="api"  — Anthropic SDK (requires ANTHROPIC_API_KEY)
    """
    if backend == "api":
        return AnthropicAPIBackend(model=model, use_cache=use_cache)
    if backend == "cli":
        return ClaudeCLIBackend()
    raise ValueError(f"Unknown backend {backend!r}. Use 'cli' or 'api'.")
