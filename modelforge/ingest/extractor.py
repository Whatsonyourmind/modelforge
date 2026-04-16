"""Claude-driven per-section extractor.

One Claude call per spec section. Tool schema is derived from the target
Pydantic model via model_json_schema(). System prompt + tool schema are
cached so multi-section runs share a single paid prefix.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ValidationError

from modelforge.ingest.readers.base import DocChunk, DocIndex

_PROMPT_DIR = Path(__file__).parent / "prompts"
_EXTRACTOR_SYSTEM = (_PROMPT_DIR / "extractor_system.md").read_text(encoding="utf-8")


def _load_template_guide(template: str) -> str:
    """Load template-specific extractor guidance from prompts/."""
    path = _PROMPT_DIR / f"template_{template}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


@dataclass
class ExtractionResult:
    section_name: str
    payload: dict[str, Any]
    validation_ok: bool
    validation_error: Optional[str] = None
    cache_hit: bool = False
    input_tokens: int = 0
    output_tokens: int = 0


def _inline_refs(schema: dict) -> dict:
    """Inline all $ref nodes in a JSON schema by substituting from $defs.

    Pydantic emits `{"$ref": "#/$defs/Label"}` for nested models. Anthropic
    tool_use accepts the schema with `$defs` but some picky setups prefer
    inline. This walker makes the schema self-contained.
    """
    defs = schema.get("$defs", {})
    def resolve(node):
        if isinstance(node, dict):
            if "$ref" in node and node["$ref"].startswith("#/$defs/"):
                name = node["$ref"].split("/")[-1]
                resolved = defs.get(name, {})
                # Deep copy + recursive inlining to prevent infinite recursion
                # with mutually-recursive schemas (none in our spec, but safe)
                out = {k: resolve(v) for k, v in resolved.items()}
                # Merge sibling fields (e.g. description override)
                for k, v in node.items():
                    if k != "$ref":
                        out[k] = resolve(v)
                return out
            return {k: resolve(v) for k, v in node.items()}
        if isinstance(node, list):
            return [resolve(x) for x in node]
        return node
    inlined = resolve({k: v for k, v in schema.items() if k != "$defs"})
    return inlined


def _build_tool(section_name: str, section_cls: type[BaseModel]) -> dict:
    """Build an Anthropic tool spec from a Pydantic model section."""
    raw = section_cls.model_json_schema()
    inlined = _inline_refs(raw)
    return {
        "name": f"emit_{section_name}",
        "description": (
            f"Emit the `{section_name}` section of the ModelForge spec. "
            f"Every field must match the ModelForge conventions — see the system prompt."
        ),
        "input_schema": inlined,
    }


def _render_source_table(sources: list[dict]) -> str:
    """Format available sources as a compact markdown table for the prompt."""
    if not sources:
        return "(no sources yet)"
    lines = ["| S-id | Doc | Publisher | Date | Verified |",
             "|---|---|---|---|---|"]
    for s in sources:
        lines.append(
            f"| {s['id']} | {s['doc']} | {s.get('publisher', '?')} | "
            f"{s.get('date', '?')} | {'yes' if s.get('verified') else 'no'} |"
        )
    return "\n".join(lines)


def _render_context_chunks(chunks: list[DocChunk], max_chars: int = 25000) -> str:
    """Concatenate chunks with source tags; cap total chars for context budget."""
    out = []
    used = 0
    for c in chunks:
        tag = f"[{c.doc_filename} p.{c.page}]" if c.page else f"[{c.doc_filename}]"
        body = c.text.strip()
        piece = f"{tag}\n{body}\n"
        if used + len(piece) > max_chars:
            break
        out.append(piece)
        used += len(piece)
    return "\n---\n".join(out)


def _get_client():
    from anthropic import Anthropic
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. `modelforge ingest` requires a "
            "valid Anthropic API key."
        )
    return Anthropic()


def extract_section(
    template: str,
    section_name: str,
    section_cls: type[BaseModel],
    available_sources: list[dict],
    context_chunks: list[DocChunk],
    model: str = "claude-opus-4-6",
    client: Any = None,
    use_cache: bool = True,
    max_context_chars: int = 25000,
    retry_on_validation: bool = True,
) -> ExtractionResult:
    """Extract one section via a single Claude call.

    On Pydantic validation failure, retry once with the error message
    appended to the user prompt. Returns ExtractionResult with payload +
    diagnostics regardless of validity (caller decides what to do with
    invalid payloads).
    """
    client = client or _get_client()
    tool = _build_tool(section_name, section_cls)
    template_guide = _load_template_guide(template)
    sources_md = _render_source_table(available_sources)
    context_md = _render_context_chunks(context_chunks, max_chars=max_context_chars)

    user_prompt = (
        f"# Task: extract the `{section_name}` section\n"
        f"Target template: `{template}`\n\n"
        f"## Template guidance\n{template_guide}\n\n"
        f"## Available sources\n{sources_md}\n\n"
        f"## Data-room excerpts\n{context_md}\n\n"
        f"Call the `emit_{section_name}` tool with a complete payload."
    )

    system_block = {"type": "text", "text": _EXTRACTOR_SYSTEM}
    tool_block: dict[str, Any] = dict(tool)
    if use_cache:
        system_block["cache_control"] = {"type": "ephemeral"}
        tool_block["cache_control"] = {"type": "ephemeral"}

    def _call(messages):
        return client.messages.create(
            model=model,
            max_tokens=4096,
            system=[system_block],
            tools=[tool_block],
            tool_choice={"type": "tool", "name": tool["name"]},
            messages=messages,
        )

    messages = [{"role": "user", "content": user_prompt}]
    response = _call(messages)

    payload = _extract_tool_payload(response, tool["name"])
    cache_read = getattr(response.usage, "cache_read_input_tokens", 0) or 0
    input_tokens = getattr(response.usage, "input_tokens", 0) or 0
    output_tokens = getattr(response.usage, "output_tokens", 0) or 0
    cache_hit = cache_read > 0

    # Validate against Pydantic
    first_error: str | None = None
    try:
        section_cls.model_validate(payload)
        return ExtractionResult(
            section_name=section_name, payload=payload, validation_ok=True,
            cache_hit=cache_hit, input_tokens=input_tokens, output_tokens=output_tokens,
        )
    except ValidationError as e:
        first_error = str(e)
        if not retry_on_validation:
            return ExtractionResult(
                section_name=section_name, payload=payload, validation_ok=False,
                validation_error=first_error, cache_hit=cache_hit,
                input_tokens=input_tokens, output_tokens=output_tokens,
            )

    # One retry with error feedback
    retry_prompt = (
        user_prompt
        + "\n\n---\n\n# Previous attempt failed Pydantic validation\n"
        + "```\n" + (first_error or "")[:3000] + "\n```\n"
        + "Fix the errors and call the tool again."
    )
    messages = [{"role": "user", "content": retry_prompt}]
    response = _call(messages)
    payload = _extract_tool_payload(response, tool["name"])
    cache_read2 = getattr(response.usage, "cache_read_input_tokens", 0) or 0
    input_tokens += getattr(response.usage, "input_tokens", 0) or 0
    output_tokens += getattr(response.usage, "output_tokens", 0) or 0

    try:
        section_cls.model_validate(payload)
        return ExtractionResult(
            section_name=section_name, payload=payload, validation_ok=True,
            cache_hit=cache_hit or cache_read2 > 0,
            input_tokens=input_tokens, output_tokens=output_tokens,
        )
    except ValidationError as e2:
        return ExtractionResult(
            section_name=section_name, payload=payload, validation_ok=False,
            validation_error=str(e2), cache_hit=cache_hit or cache_read2 > 0,
            input_tokens=input_tokens, output_tokens=output_tokens,
        )


def _extract_tool_payload(response, tool_name: str) -> dict:
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
            return block.input
    raise RuntimeError(f"No tool_use block for {tool_name} in response")
