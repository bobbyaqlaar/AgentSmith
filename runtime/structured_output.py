"""
runtime/structured_output.py — extract + validate LLM JSON (SEC-OUTPUT-001).

Parse fenced or bare JSON from model text, then Pydantic model_validate_json.
"""

from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

_FENCED = re.compile(
    r"```(?:json|JSON)?\s*\n?(.*?)\n?```",
    re.DOTALL,
)


class StructuredOutputError(ValueError):
    """Raised when LLM text cannot be parsed into the target Pydantic model."""


def _extract_json_text(raw: str) -> str:
    text = raw.strip()
    if not text:
        raise StructuredOutputError("empty LLM output")

    fenced = _FENCED.search(text)
    if fenced:
        return fenced.group(1).strip()

    # Bare JSON object or array — take outermost braces/brackets.
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]

    return text


def parse_llm_json(raw: str, model: type[T]) -> T:
    """Extract JSON (fenced or bare) and validate against ``model``."""
    candidate = _extract_json_text(raw)
    try:
        # Ensure it's valid JSON first for clearer errors.
        json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise StructuredOutputError(f"invalid JSON: {exc}") from exc

    try:
        return model.model_validate_json(candidate)
    except ValidationError as exc:
        raise StructuredOutputError(f"schema validation failed: {exc}") from exc
