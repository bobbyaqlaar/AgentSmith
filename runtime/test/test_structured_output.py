from __future__ import annotations

import pytest
from pydantic import BaseModel

from runtime.structured_output import StructuredOutputError, parse_llm_json


class Demo(BaseModel):
    answer: str
    score: int


def test_parse_fenced_json() -> None:
    raw = 'Here:\n```json\n{"answer":"ok","score":1}\n```'
    assert parse_llm_json(raw, Demo).answer == "ok"


def test_parse_bare_json() -> None:
    raw = '{"answer":"bare","score":2}'
    assert parse_llm_json(raw, Demo).answer == "bare"


def test_parse_fenced_without_language_tag() -> None:
    raw = 'Result:\n```\n{"answer":"plain","score":3}\n```'
    assert parse_llm_json(raw, Demo).answer == "plain"


def test_invalid_schema_raises() -> None:
    raw = '{"answer":"ok"}'  # missing required score
    with pytest.raises(StructuredOutputError):
        parse_llm_json(raw, Demo)


def test_malformed_json_raises() -> None:
    raw = "not json at all"
    with pytest.raises(StructuredOutputError):
        parse_llm_json(raw, Demo)
