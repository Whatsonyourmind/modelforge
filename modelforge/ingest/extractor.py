"""Claude-driven per-section extractor.

One LLM call per spec section. Tool schema is derived from the target
Pydantic model via model_json_schema(). Uses the LLM backend abstraction
(CLI or API) for the actual call.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ValidationError

from modelforge.ingest.llm import LLMBackend, LLMResponse
from modelforge.ingest.readers.base import DocChunk

_PROMPT_DIR = Path(__file__).parent / "prompts"
_EXTRACTOR_SYSTEM = (_PROMPT_DIR / "extractor_system.md").read_text(encoding="utf-8")


def _load_template_guide(template: str) -> str:
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
    """Inline all $ref nodes in a JSON schema by substituting from $defs."""
    defs = schema.get("$defs", {})
    def resolve(node):
        if isinstance(node, dict):
            if "$ref" in node and node["$ref"].startswith("#/$defs/"):
                name = node["$ref"].split("/")[-1]
                resolved = defs.get(name, {})
                out = {k: resolve(v) for k, v in resolved.items()}
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


def _build_tool_schema(section_name: str, section_cls: type[BaseModel]) -> dict:
    """Derive a JSON schema from a Pydantic model with $refs inlined."""
    raw = section_cls.model_json_schema()
    return _inline_refs(raw)


def _render_source_table(sources: list[dict]) -> str:
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


def extract_section(
    template: str,
    section_name: str,
    section_cls: type[BaseModel],
    available_sources: list[dict],
    context_chunks: list[DocChunk],
    backend: LLMBackend | None = None,
    retry_on_validation: bool = True,
    max_context_chars: int = 25000,
    **kwargs,
) -> ExtractionResult:
    """Extract one section via a single LLM call.

    On Pydantic validation failure, retry once with the error message
    appended to the user prompt.
    """
    if backend is None:
        from modelforge.ingest.llm import get_backend
        backend = get_backend(**kwargs)

    schema = _build_tool_schema(section_name, section_cls)
    template_guide = _load_template_guide(template)
    sources_md = _render_source_table(available_sources)
    context_md = _render_context_chunks(context_chunks, max_chars=max_context_chars)

    user_prompt = (
        f"# Task: extract the `{section_name}` section\n"
        f"Target template: `{template}`\n\n"
        f"## Template guidance\n{template_guide}\n\n"
        f"## Available sources\n{sources_md}\n\n"
        f"## Data-room excerpts\n{context_md}\n\n"
        f"Return a complete `{section_name}` payload."
    )

    tool_name = f"emit_{section_name}"

    resp = backend.call_json(
        system_prompt=_EXTRACTOR_SYSTEM,
        user_prompt=user_prompt,
        tool_name=tool_name,
        tool_schema=schema,
    )

    payload = resp.payload
    total_in = resp.input_tokens
    total_out = resp.output_tokens
    cache_hit = resp.cache_hit

    # Validate against Pydantic
    first_error: str | None = None
    try:
        section_cls.model_validate(payload)
        return ExtractionResult(
            section_name=section_name, payload=payload, validation_ok=True,
            cache_hit=cache_hit, input_tokens=total_in, output_tokens=total_out,
        )
    except ValidationError as e:
        first_error = str(e)
        if not retry_on_validation:
            return ExtractionResult(
                section_name=section_name, payload=payload, validation_ok=False,
                validation_error=first_error, cache_hit=cache_hit,
                input_tokens=total_in, output_tokens=total_out,
            )

    # One retry with error feedback
    retry_prompt = (
        user_prompt
        + "\n\n---\n\n# Previous attempt failed Pydantic validation\n"
        + "```\n" + (first_error or "")[:3000] + "\n```\n"
        + "Fix the errors and return valid JSON."
    )
    resp2 = backend.call_json(
        system_prompt=_EXTRACTOR_SYSTEM,
        user_prompt=retry_prompt,
        tool_name=tool_name,
        tool_schema=schema,
    )
    payload = resp2.payload
    total_in += resp2.input_tokens
    total_out += resp2.output_tokens

    try:
        section_cls.model_validate(payload)
        return ExtractionResult(
            section_name=section_name, payload=payload, validation_ok=True,
            cache_hit=cache_hit or resp2.cache_hit,
            input_tokens=total_in, output_tokens=total_out,
        )
    except ValidationError as e2:
        return ExtractionResult(
            section_name=section_name, payload=payload, validation_ok=False,
            validation_error=str(e2), cache_hit=cache_hit or resp2.cache_hit,
            input_tokens=total_in, output_tokens=total_out,
        )
