---
status: done
scope:
  - runtime/tracing.py
  - runtime/llm_gateway.py
  - runtime/moderation.py
  - runtime/workflows/base_workflow.py
  - runtime/config.py
  - scripts/agent_logger.py
  - scripts/local_agent_stack.py
  - scripts/multi_agent_system.py
  - scripts/local_knowledge_graph.py
  - scripts/promote-learning.py
  - scripts/security/report.py
  - portal/lib/devRead.ts
  - scripts/security/registry.py
  - scripts/run-security-checks.py
  - scripts/test/**
  - runtime/test/**
  - docs/DESIGN.md
  - docs/review-levers.md
  - docs/review-lever-notes.md
  - docs/design-review-checklist.md
  - CHANGELOG.md
  - .agent-rfc/fixtures/knowledge_graph.json
---
# Code volume sweep

Owner, 2026-09-24: a thorough multi-pass review against `docs/review-levers.md`, plus a new lever —
`every-line-earns-its-place` — aimed at code volume, so the repository does not read as machine
output nobody edited.

## Problem

Pass 1 of that review measured the repository before judging it, which matters because the obvious
answer here is wrong. 63k lines of Python at 24% prose looks like padding; reading it, most of that
prose is load-bearing — it records why a thing is the way it is, which the code cannot say. Four
cross-file duplicate regions of eight lines or more in the whole non-test tree, no dead module-level
functions, and no test that cannot fail. The repository is not bloated in the way the question
implies.

What it does carry is **residue from its own fixes** — and that is a different defect, with a
pattern worth naming:

1. **Three byte-identical 12-line shims.** `_repo_root` once had five disagreeing implementations.
   They were correctly unified into `runtime.config.repo_root` — and each caller kept a local
   `_repo_root()` that does nothing but call it, carrying a nine-line docstring recounting the
   incident. The duplication was removed from the logic and preserved in the prose about the logic,
   three times over, in modules that can all import `runtime.config` directly.

2. **A helper nobody calls, beside a copy of it somebody does.** `AgentLogger.resolve_hitl` (33
   lines) has zero callers anywhere in the repository. `promote-learning.py::_mark_log_resolved` is
   a near-verbatim copy and is the only one that runs — so the rule for what counts as an
   unresolved MAJOR/CRITICAL entry lives in two places, and the live one is the copy.

3. **The wiring helper, not invoked at the two sites it was written for.** `configure_tracing`'s own
   docstring says it exists because assembling a TracerProvider by hand is three steps that get
   half-done. `scripts/local_agent_stack.py` and `scripts/multi_agent_system.py` assemble it by
   hand — and omit `AgentIdentityProcessor` and `TraceRedactor`. Those two are what `README.md`
   offers as "a shape to copy", so the shape on offer exports **unredacted** spans.

4. **A declared graph edge nothing creates.** `IMPLEMENTS` is documented in `docs/DESIGN.md` and in
   `local_knowledge_graph.py`'s own header; the only method that would add one,
   `link_file_to_guardrail`, has no callers, so no knowledge graph has ever held one.

5. **A catalogue stated five times.** The four compliance frameworks are written out in
   `FrameworkTags`' fields, the registry loader, `_filter_controls`, the JSON projection and
   `run-security-checks.py`'s `choices`. A fifth framework means five edits, and the one in
   `_filter_controls` fails by returning nothing rather than by failing.

6. **Two smaller ones:** `AgentWorkflowInput` is a dataclass nothing constructs, and
   `docs/DESIGN.md` carries `### CD Golden Dataset Commits` twice, 650 lines apart.

## Approach

Delete the residue, wire the helpers that already exist, and leave the prose that earns its place.

- **The shims go.** `runtime/{tracing,llm_gateway,moderation}.py` import `repo_root` from
  `runtime.config` and call it. The explanation stays where the implementation is, once.
- **One resolver for the HITL sweep.** `agent_logger.resolve_hitl` keeps the logic — it is the
  considered copy and the one with a class around the log path — and `promote-learning.py` calls it
  instead of restating it (`merge-the-right-copy`).
- **The two reference stacks call `configure_tracing`.** This is the finding that is not about
  volume: they gain identity stamping and redaction, which is what they were always supposed to
  demonstrate. Their hand-rolled no-op tracers go with the hand-rolled provider.
- **`IMPLEMENTS` gets decided, not left ambiguous.** Nothing creates one and nothing reads one, so
  the method, the module header line and the `docs/DESIGN.md` bullet go together. Reinstating it
  later is one method; documenting an edge that has never existed is a lie the graph tells.
- **`_filter_controls` reads the catalogue instead of restating it**, so the tags dataclass is the
  one place the frameworks are named.
- **The two small ones**: delete `AgentWorkflowInput`; merge the duplicated `docs/DESIGN.md`
  section into the one that carries the example.

What this deliberately does **not** do is compress the repository's explanatory prose. The lever
says shorter, never denser; a nine-line paragraph that appears once and says why is the reason this
codebase can be reviewed at all.

## Pillars

- P1 applies — this design precedes the code; the passes and their findings are recorded in `.agent-rfc/reviews/code-volume-sweep.md`.
- P2 applies — the change is subtractive: every helper it routes to already exists (`repo_root`, `resolve_hitl`, `configure_tracing`). `.agent-rfc/fixtures/knowledge_graph.json` is re-pinned.
- P3 applies — it changes which spans carry identity: `local_agent_stack.py` and `multi_agent_system.py` move onto `configure_tracing`, so their spans gain `AgentIdentityProcessor`'s attributes, which they never had.
- P4 applies — tests first: `test_tracing_bootstrap_is_not_hand_rolled` asserts both scripts route through `configure_tracing`; the existing suites pin the rest, and `runtime/test/test_otlp_endpoint.py` already parses both files.
- P7 applies — no new typed boundary; `_filter_controls` keeps its `ControlSpec` types and reads `FrameworkTags` by field.
- P8 applies — the endpoint still resolves through `runtime/otlp.py`; only the provider assembly moves.
- P9 n/a — no orchestration added or moved.
- P10 n/a — no model call added; `llm_gateway` changes only its root resolution.
- P11 applies — the point of the tracing change: `TraceRedactor` now rewrites spans from both reference stacks before export, which is where untrusted content reaches a collector.
- P12 applies — no credential is read, written or moved; `runtime/trace_redactor.py` is what now keeps values out of the spans `scripts/local_agent_stack.py` exports.
- P13 applies — no check, threshold or allowlist gets weaker; two get stronger. `runtime/test/test_config.py` asserted the property through the shims it was meant to forbid and now asserts the property itself, and `runtime/test/test_tracing.py` pins the wiring the two reference stacks had half-done. A graph edge that nothing created is removed from `docs/DESIGN.md` because nothing enforced it, rather than left declared.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is re-pinned; removing `link_file_to_guardrail` and `AgentWorkflowInput` changes the graph's symbol set.
- P15 applies — `_filter_controls` with an unknown framework name currently returns an empty list that reads as "no controls match"; reading the catalogue makes an unknown name an `AttributeError` at the one place that knows the names, and argparse still rejects it first.
- P16 applies — `configure_tracing` already fails open (no OTel installed returns None); the two scripts keep their try/except, so a machine without the SDK still runs them.

## Deviations

none

## Dependencies

None added; two removed from the import surface of `local_agent_stack.py` and `multi_agent_system.py`
(they stop importing `TracerProvider` and `BatchSpanProcessor` directly).

## Levers

- `every-line-earns-its-place` — the lever this sweep added, and the one that found the shims.
- `one-catalog` — the frameworks list, and the unresolved-entry rule.
- `merge-the-right-copy` — keep `resolve_hitl`, delete the copy, expect the merged one to face a caller it never had.
- `implemented-not-invoked` — `configure_tracing`, `resolve_hitl` and `link_file_to_guardrail` were all written and never called.
- `declared-vs-enforced` — `IMPLEMENTS` is documented and unenforceable; decide it rather than leave it.
- `no-redundant-artifacts` — the dead dataclass and the doubled documentation section.
- `search-before-writing` — every site in this sweep had a correct helper already in the tree.
