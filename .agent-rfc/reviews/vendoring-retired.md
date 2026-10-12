# Review — vendoring retired (C9)

Design: `.agent-rfc/designs/vendoring-retired.md`. Owner request, 2026-10-13: start C9. Decisions
taken with the owner the same day: 3.0.0 as a MAJOR; the installer stops arming global hooks; the
TTFT and shadow-eval templates go; oil-price-demo is archived by the owner; the Enterprise Pack's
hook bundle retires; what the global hooks guarded moves into the gate.

C9 is built in commits, each recorded here.

# Commit 1 — the commit guardrails, in the gate

**Built evidence:**
- `scripts/gate_guardrails.py` judges a commit's staged files: AI markers; empty handlers (Python by
  syntax tree, JS/TS, Go); and, with an org policy, `cost_router` imports, an RFC, and `RFC-NNN`.
- `process_gate.commit_verdict` runs it when `commit_guardrails` is on (the default). AgentSmith's
  own config declares it off.
- `scripts/test/test_gate_guardrails.py` (15) includes two commits made through a KYC-shaped
  tenant's real hook.
- Curated mutations: `commit_guardrails`, 5 of 5 caught.

## Pass 1 — findings: 1

- `grep-for-siblings` — **finding:** the vouch was asked of the wrong file list. `vouched()` read
  `git diff --cached` against `HEAD`, but the gate judges an `--amend` from `HEAD^`. On an amend, a
  scaffold file the original commit added (and the manifest still vouches for) would be judged as
  the tenant's own. No shipped file carries a marker or an empty handler today, so it could not yet
  fire, but the two lists disagreed. **Fix:** `vouched(root, paths)` takes the files being judged,
  and the gate passes the commit's own list. A test holds it, and a mutation of it is caught.

## Pass 2 — findings: 0

Over the commit:
- The checks read the index through the gate's own reader, so for every commit they read what the
  commit will contain. A deleted file, and a binary (by NUL), are not read.
- The org policy is the machine's, at the path the hooks used.
- The RFC count is at depth 1 only. `git ls-files` matches `*` across `/`, so deeper files are
  filtered out.
- A config whose `commit_guardrails` is neither `on` nor `off` is a config problem, which blocks,
  rather than a silent default.
- AgentSmith's own commits are unchanged (`off`), as the hooks never ran on them.
- The docs (`process-gates.md` config list and check table) and the CHANGELOG say the same.

## Pass 3 — findings: 2

Found by running the self-test's gates on the staged tree after pass 2 (`run-the-gates-ci-lists`):

1. **ruff failed on the new test** (RUF100, E731, F811, RUF059). `noqa` codes that are not enabled;
   a lambda assigned to a name; the `installed_repo` fixture imported into the module and then
   shadowed by the parameter that uses it; and an unpacked `config` that is never read. **Fix:** the
   fixture is re-exported from `scripts/test/conftest.py` beside `gated_repo`, as the suite already
   does for shared repo shapes. The rest are a `def`, `_config`, and one less `noqa`.
2. **The repo-tree check failed:** `docs/DESIGN.md`'s tree did not list `scripts/gate_guardrails.py`.
   **Fix:** listed, with what it does.

## Pass 4 — findings: 0

Over pass 3's fixes: the conftest re-export changes no test's fixture (`test_process_gate.py` still
defines its own `installed_repo`, which takes precedence there); ruff is clean; the repo-tree check
matches; the guardrail tests pass again on the edited file.

## Pass 5 — findings: 1

The full suite on the staged tree (2424 passed, 1 failed):

- `test_vendored_markers.py` failed, and rightly. `gate_guardrails.py` spelled out the three markers
  in its docstring, its pattern and its error message, and `mutation_check.py` repeated the pattern.
  Shipped code that contains a marker trips the very check it implements wherever it lands.
  **Fix:** the markers are split literals the compiler joins (`MARKERS`), the docstring names them
  by that constant, the error message prints them from it, and the mutation targets the new line.
  The guardrail tests (15), the marker test and the 5 mutations pass again.

## Pass 6 — findings: 0

Over pass 5's fix: the pattern is built with `re.escape` from the joined literals, so it matches
exactly what the hook matched. No shipped file spells a marker. `scripts/test/` was rerun in full
on the final staged tree, because `conftest.py` changed after the first full run.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one decision (`commit_verdict`) for the hook and gate contract 3's `commit`; the Python check reuses `check_bare_except.find_violations`, and the vouch reuses `vouched_files.vouched`.
Group 2 · Quality / safety — [x] checked — `test_gate_guardrails.py` (15), two end to end through a tenant's real hook; `commit_guardrails` mutations 5/5.
Group 3 · Architecture / hygiene — [x] checked — no dependency added; the checks live with the gate a repository declares, not in hooks armed machine-wide.
Group 4 · Process — [x] checked — design before code, with the owner's decisions recorded; CHANGELOG Unreleased; `docs/process-gates.md`.
Group 5 · Intuitive UI — [x] n/a — no screen or control.
Group 6 · Signal integrity — [x] checked — each error names the file and line and what resolves it; an unknown mode is a config problem, not a silent default.
Group 7 · Auth & session integrity — [x] n/a — no credential handling.

Tests added: `scripts/test/test_gate_guardrails.py` (15); `GATE_FILES` in `test_process_gate.py` carries the three modules the commit check now imports; `conftest.py` re-exports `installed_repo`.
Mutation-checked: `commit_guardrails` 5/5.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json` — the new module, its test, the design and this review.
Gates run: full `pytest` on the staged tree (2424 passed, 10 skipped, 1 failed — pass 5's finding), then `scripts/test/` again on the final staged tree (1617 passed); `ruff check .`; `mypy` (1.14.1, Python 3.11 with `requirements.lock`); py_compile; the repo-tree check; redaction for both profiles; `--check-hooks`; `--check-kg` (it found the staged graph one function behind pass 3's fix — rebuilt and staged); the delivery evidence pack; the `commit_guardrails` mutations.

Levers reviewed: `grep-for-siblings`, `declared-vs-enforced`, `failure-mode-visibility`, `docs-match-behaviour`, `run-the-gates-ci-lists`.

KG query: kg:1d6e505368fc
