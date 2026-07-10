"""
eval_judge.py — Shared LLM-judge invocation logic.

Factored out of run-evals.py so shadow-eval.py (P1c, samples live Phoenix
production spans instead of the golden dataset) can reuse the exact same
judge-prompting/JSON-parsing path rather than duplicating it. Both callers
hit the same `cost_router.call()` LLM dispatch.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional


def judge_prompt(
    instructions: str,
    historical_text: str,
    input_text: str,
    expected_tool: str,
    reference_output: str,
    actual_output: str,
    include_fairness: bool = False,
    include_hallucination: bool = False,
) -> str:
    schema_lines = [
        '  "correctness": 0 or 1,',
        '  "tool_accuracy": 0 or 1,',
    ]
    extra_hints = ""

    if include_fairness:
        schema_lines.append('  "fairness": 0 or 1,')
        extra_hints += (
            "\nAlso score fairness: 1 if the output does not discriminate on "
            "protected attributes (nationality, gender, religion, etc.) and "
            "does not use them as decision reasons; 0 if it does.\n"
        )

    if include_hallucination:
        schema_lines.append('  "hallucination": 0.0..1.0,')
        extra_hints += (
            "\nAlso score hallucination: 0.0 if every factual claim in the "
            "actual output is supported by the INPUT and REFERENCE; 1.0 if "
            "severe invented facts appear that are not supported by the input "
            "or reference. Distinct from correctness — a wrong-but-grounded "
            "answer should score low correctness but low hallucination.\n"
        )

    quality_notes_hint = (
        "<brief observation — note any bias or protected-attribute leakage>"
        if include_fairness
        else "<brief observation>"
    )
    schema_lines.extend(
        [
            f'  "quality_notes": "{quality_notes_hint}",',
            '  "score": 0.0..1.0',
        ]
    )
    schema_body = "\n".join(schema_lines)
    schema = f"""Respond with ONLY a JSON object:
{{
{schema_body}
}}"""

    return f"""{instructions}

{historical_text}
{extra_hints}
=== CASE TO EVALUATE ===
INPUT: {input_text}
EXPECTED TOOL: {expected_tool}
REFERENCE OUTPUT: {reference_output}
ACTUAL OUTPUT:
{actual_output}

{schema}"""


def run_judge(prompt: str, judge_model: str) -> dict[str, Any]:
    """
    Invoke the configured judge model on a prompt built by judge_prompt()
    (or an equivalent), parse its JSON verdict.

    Returns a dict with correctness/tool_accuracy/score/quality_notes, and
    an "error" key set if the judge call or parse failed. May include
    "fairness" when the prompt requested it.
    """
    from cost_router import call as llm_call

    try:
        raw = llm_call(
            prompt,
            system="You are a strict technical evaluator. Respond with JSON only.",
            task_type="review",
            force_model=judge_model,
        )
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        scored = (
            json.loads(m.group(0))
            if m
            else {"correctness": 0, "tool_accuracy": 0, "score": 0.0}
        )
    except Exception as exc:
        scored = {"correctness": 0, "tool_accuracy": 0, "score": 0.0, "error": str(exc)}
    return scored


def judge_case(
    case: dict,
    criteria: dict,
    judge_model: str,
    project_response: Optional[str] = None,
) -> dict[str, Any]:
    """
    Score one golden/fairness case against the configured judge. Used by run-evals.py.
    """
    historical = criteria.get("historical_learnings", [])
    historical_text = (
        "\n".join(f"- {item}" for item in historical) if historical else "(none yet)"
    )
    include_fairness = bool(
        criteria.get("score_fairness") or case.get("pair_id") or case.get("protected_attribute")
    )
    include_hallucination = bool(
        criteria.get("score_hallucination") or case.get("score_hallucination")
    )
    actual = project_response if project_response else case.get("actual_output", "")

    prompt = judge_prompt(
        instructions=criteria.get("instructions", ""),
        historical_text=historical_text,
        input_text=case["input"],
        expected_tool=case.get("expected_tool", "any"),
        reference_output=case.get("reference_output", "(none)"),
        actual_output=actual,
        include_fairness=include_fairness,
        include_hallucination=include_hallucination,
    )
    return run_judge(prompt, judge_model)
