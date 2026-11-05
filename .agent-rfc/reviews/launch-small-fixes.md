# Review: launch-small-fixes

## Pass 1 — findings: 2

1. `test-the-contract` — **The denylist test looped over the constant it was testing,** so dropping the variable from `AMBIENT_ENV` would have passed it. **Fix:** `scripts/test/test_evals_contract.py` names `PROMPT_DENYLIST_PATH` itself, and the mutation is caught.
2. `every-line-earns-its-place` — **The installer's closing lines still said "3.0.0 arms none machine-wide",** which reads wrongly in any later install. **Fix:** no version in the sentence.

## Pass 2 — findings: 0

- **The digest is the tag:** `docker buildx imagetools inspect` on `version-17.10.0` returns the pinned digest, it is multi-architecture, and `docker compose config` accepts the reference. It is the image running on this machine, so no data migration follows.
- **The confirmation says what is true:** a discarded entry is resolved, and `replayDlqEntry` refuses a resolved one.
- **`window.confirm` runs only on a click** in a client component, so server rendering never reaches it.
- **Requiring `widgetScriptUrl`** breaks only a caller who already got no widget. The template has no type-check lane, so the compiler has not read `AgentStatus.tsx` here.
- **A machine's old `ai-compat.sh` stays,** so a profile sourcing it still works. `$FRAMEWORK_DIR/shell` is no longer created, and nothing else used it.
- **The tutorial keeps `oil-price-demo`:** a name the reader creates, from an example that exists.

## Sign-off

Group 1 · DRY & shared code — [x] checked — `AMBIENT_ENV` builds on `THRESHOLD_ENV`; a dead wrapper file and its test are gone.
Group 2 · Quality / safety — [x] checked — a destructive action asks first; a graded score no longer takes input from the caller's environment.
Group 3 · Architecture / hygiene — [x] checked — Phoenix pinned by digest; no dependency added.
Group 4 · Process — [x] checked — design before the changes; CHANGELOG and backlog; three new mutations and one re-pointed.
Group 5 · Intuitive UI — [x] checked — the confirmation names the entry and the consequence.
Group 6 · Signal integrity — [x] checked — two runs of a suite cannot differ by this variable; the widget's source names no host that does not exist.
Group 7 · Auth & session integrity — [x] n/a — no credential handling.

Tests added: `scripts/test/test_launch_small_fixes.py`, with `scripts/test/test_evals_contract.py` extended. The portal and widget rows read source, because neither has a DOM lane for these files.
Mutation-checked: `scripts/mutation_check.py evals_contract`, 14 of 14 caught, including the three new ones.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: `test_launch_small_fixes.py`, `test_evals_contract.py`, `test_cli_install.py`, `test_installer_templates.py`, `test_framework_python_env.py`, `test_design_and_validation_docs.py`, `test_release_install.py` (153 passed); ruff; bash -n; portal `tsc --noEmit`; the widget's `npm test` (8 passed); `docker compose config`. The Discard dialog was not clicked in a browser. Self-Test runs the full suite, the other mutation suites and the portal build.

Levers reviewed: `environment-parity`, `when-the-fallback-fails`, `every-line-earns-its-place`, `test-the-contract`.

KG query: kg:a05cfc35c54c
