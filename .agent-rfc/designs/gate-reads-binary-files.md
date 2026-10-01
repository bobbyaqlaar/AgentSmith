---
status: done
scope:
  - scripts/process_gate.py
  - scripts/test/test_gate_kg.py
  - scripts/test/test_process_gate.py
  - scripts/mutation_check.py
---
# The gate judges a commit that carries a binary file, instead of crashing on it

## Problem

Committing the portal's logos, the commit gate crashed:
`UnicodeDecodeError: 'utf-8' codec can't decode byte 0x89 in position 0` —
0x89 is the first byte of every PNG. `scripts/process_gate.py`'s two file
readers decode as UTF-8 text: `_reader_at` runs `git show <rev>:<path>` with
`text=True` (the commit gate reads the index this way, CI reads each commit),
and `_worktree_reader` uses `read_text(encoding="utf-8")`. `kg_problems` reads
every changed file to see whether the change leaves it in place — so any gated
commit that also carries an image, a font or a PDF crashes the gate, with a
traceback, instead of being judged. In CI as well as at commit time.

It is a framework defect, not a portal one: `scripts/process_gate.py` is
vendored into every tenant, and a tenant that adds a logo beside a gated change
hits it.

`scripts/gate_pillars.py` already handles binaries — it skips `_BINARY`
extensions before reading content — so no content check ever looks inside one.
Only the existence read in the scope check does.

## Approach

Both readers decode with `errors="replace"`: a binary file still EXISTS to the
gate, so `kg_problems` keeps it in the scope — which is what
`local_knowledge_graph.py --impact`, the command an author runs to compute the
hash, already does from `git diff --name-only`. Returning `None` for a binary
instead would read as "deleted", drop it from the gate's scope while the author's
tool kept it, and refuse every such commit for a hash mismatch.

No content check is affected: the mechanical checks skip `_BINARY` before reading,
and every other reader of content reads designs, reviews, configs and the graph,
which are text.

## Pillars

- P1 applies — `.agent-rfc/designs/gate-reads-binary-files.md`, from a crash found
  while committing the portal's logos.
- P2 applies — `scripts/process_gate.py` has exactly two readers that every check
  goes through; both change, nothing else does. `scripts/gate_pillars.py`'s
  `_BINARY` skip is the existing answer for content. No dependencies.
- P3 n/a — no new execution path; the gate's spans are unchanged.
- P4 applies — `scripts/test/test_gate_kg.py` gains a commit carrying a PNG,
  judged by the commit gate and by CI with the knowledge-graph check on; it fails
  before the fix with the same `UnicodeDecodeError`. `scripts/test/test_process_gate.py`
  gains a unit test of the working-tree reader, which the stop gate uses and the
  end-to-end test does not reach. A mutation restoring `text=True`
  goes into `scripts/mutation_check.py`.
- P7 n/a — standard-library Python; no models.
- P8 n/a — no telemetry change.
- P9 n/a — no orchestration.
- P10 n/a — no LLM call.
- P11 applies — `scripts/process_gate.py` reads files the committer controls; a
  file that is not valid UTF-8 is now read with replacement characters instead of
  crashing the gate, and no check interprets a binary's content.
- P12 n/a — no credentials.
- P13 applies — `scripts/process_gate.py` gets more robust, not weaker: a commit
  that crashed the gate was never judged at all. The scope check now counts the
  binary file, as the author's tool already did.
- P14 n/a — no fixtures or baselines.
- P15 applies — `scripts/process_gate.py` answered a binary file with a traceback;
  it now answers with the gate's verdict on the commit.
- P16 n/a — no fallback path changes.

## Deviations

none

## Dependencies

none

## Levers

- `environment-parity` — the commit gate and CI read through the same function and
  both crashed; both are fixed in the one place, and the test runs both.
- `guards-must-be-able-to-fail` — the test fails before the fix with the crash it is
  about, and a mutation restoring `text=True` is caught.
- `failure-is-not-a-result` — a crash is not a verdict; the gate now gives one.
