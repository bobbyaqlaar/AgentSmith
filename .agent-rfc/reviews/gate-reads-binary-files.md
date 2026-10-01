# Review — gate-reads-binary-files

Design: `.agent-rfc/designs/gate-reads-binary-files.md`
Levers: `docs/review-levers.md`

## Pass 1 — findings: 2

1. **My first regression test could not fail.** Written in
   `scripts/test/test_process_gate.py`, it passed against the unfixed gate:
   that file turns the knowledge-graph check off (`FIXTURE_CONFIG["knowledge_graph"]
   = "off"`), and the crash lives in that check. Its own comment says the rule is
   tested in `test_gate_kg.py`. Removed, and rewritten there with the check on —
   where it fails before the fix with the same `UnicodeDecodeError` the logos
   commit hit, for the commit gate and for CI.

2. **The obvious fix would have refused every commit carrying an image.**
   `scripts/gate_pillars.py` answers a binary with `None`. Here that reads as
   "the change deleted this file": `kg_problems` would drop the PNG from the
   gate's scope while `local_knowledge_graph.py --impact`, the command an author
   runs to compute the hash, keeps it — so the two hashes would differ on every
   such commit. Decoding with replacement keeps the file present in both.

## Pass 2 — findings: 1

1. **The design's scope did not cover a file the review made me change.** The
   unit test for the working-tree reader went into
   `scripts/test/test_process_gate.py`, added during Pass 1; the scope still named
   only `test_gate_kg.py`. The commit gate refused it. This is the third time in
   these slices that a scope was written from the files first expected rather than
   the files a later step committed me to; the scope and P4 now name it.

## Pass 3 — findings: 0

- `guards-must-be-able-to-fail` — the end-to-end test fails before the fix; a unit test
  covers the working-tree reader the stop gate uses, which the end-to-end test does not
  reach; a `gate_binary_files` mutation suite restores strict decoding in each reader,
  and both are caught.
- `environment-parity` — the commit gate and CI share `_reader_at`; the test runs both.
- No content check is affected: `gate_pillars._reads` skips `_BINARY` before reading, and
  every other content read is a design, a review, a config or the graph.
- The pinned `ruff==0.15.20` over the whole repository caught three over-long lines in the
  new mutation suite before anything was pushed — the check that failed `a44e586`, run first
  this time.

## Sign-off

Group 1 · DRY & shared code — [x] checked — both readers every check goes through change in one place each; `gate_pillars`' existing `_BINARY` skip is relied on, not duplicated.
Group 2 · Quality / safety — [x] checked — an end-to-end test for the commit gate and CI, a unit test for the working-tree reader, and a 2-mutation suite, all caught.
Group 3 · Architecture / hygiene — [x] n/a — no structure changes; two decode calls.
Group 4 · Process — [x] checked — found while committing other work; designed and committed on its own, ahead of the commit it was blocking.
Group 5 · Intuitive UI — [x] n/a — no screen.
Group 6 · Signal integrity — [x] checked — a binary file now gets the gate's verdict instead of a traceback, and stays in the scope hash the author's tool computes.
Group 7 · Auth & session integrity — [x] n/a — nothing about auth or sessions.

Tests added: `test_a_commit_carrying_a_binary_file_is_judged_by_both_gates_not_crashed_on` (`scripts/test/test_gate_kg.py`), `test_the_working_tree_reader_returns_a_binary_file_rather_than_crashing` (`scripts/test/test_process_gate.py`).
Mutation-checked: yes — `gate_binary_files` suite in `scripts/mutation_check.py`, 2 mutations, both caught.
Fixtures re-pinned: none.
Gates run: `pytest scripts/test/test_gate_kg.py scripts/test/test_process_gate.py` (128 passed), the mutation suite, the pinned `ruff==0.15.20` over the whole repository, and `python3 scripts/process_gate.py ci --base origin/main --head HEAD` before pushing.

Levers reviewed: `guards-must-be-able-to-fail`, `environment-parity`, `failure-is-not-a-result`, `every-line-earns-its-place`, `use-existing-apis`.

KG query: kg:7e6d2aa32619
