# Review — release 3.0.0

Design: `.agent-rfc/designs/release-3-0-0.md`. Owner request, 2026-10-14: cut the release after C9's
fixes, then the CI optimisation.

**Built evidence:**
- The version is `3.0.0` in `pyproject.toml`, `install-ai-stack.sh` and `docs/DESIGN.md`'s header.
  `scripts/test/test_version_consistency.py` passes over all three and the new `CHANGELOG.md` section.
- The section is C9's notes, as merged (#54, #55, #56). The 3.0.x row and DESIGN's mirror are new.
- The scratch tenants are all green on `16ec71e`, the commit this release is cut from: the five
  built by `tenant init` and the adopted one. That is their first green build since C9, and the
  first in which every stack CI step ran.

## Pass 1 — findings: 4

Each claim in the 3.0.x row was checked in code, and against what OTS and KYC Sentinel run, read
from GitHub on 2026-10-14:

1. `docs-match-behaviour` — **the row said the installer "puts back the `init.templateDir` it
   recorded."** It acts only while the value is AgentSmith's, and unsets it when nothing was
   recorded before. **Fix:** the row says both.
2. `declared-vs-enforced` — **the row said the commit guardrails are "made by every repository's
   gate".** Only a 3.0.0 gate makes them, and the row told a tenant to opt out with a key it had
   not shown a 2.x gate tolerates. 2.4.0's `parse_config`, run on a config with
   `"commit_guardrails": "off"`, accepts it with no problem. **Fix:** "a 3.0.0 gate in every
   repository it governs", and "a 2.x gate ignores the key".
3. `docs-match-behaviour` — **`install-python-deps`, which the row now tells tenants to reference
   at `@v3.0.0`, described itself in stale terms:**
   - shared with `eval-security.yml`, which no longer uses it;
   - feeding later steps that run bare `pytest` and `python3 scripts/...`;
   - pinned to `hooks/post-checkout`.

   **Fix:** it says what is true now: the provider's release, `ruff` and `python -m pytest`, the
   rules renderer. The design's scope gains the file, a comment and description only.
4. `failure-mode-visibility` — **OTS and KYC declare every provider `"version": "^2"`.** Nothing
   reads that range: the only readers of a `version` key in `runtime/`, `scripts/` and the
   launcher are unrelated. So a 3.0.0 provider still answers them. `agentsmith sync` rewrites a
   declaration to `^{major}` only while it is the one the framework wrote. Both tenants edited
   theirs, so after moving they would keep a `^2` that no longer says what they run. **Fix:** step
   (2) of the row says so.

Confirmed and kept:
- **Nothing a 2.x tenant runs stops at once.** OTS's CD runs `python3 scripts/run-evals.py
  --fail-below`, its CI `map_codebase.py` and `verify_system.py`, its TTFT workflow
  `verify_ttft.py`, and both CDs `uses: ./.github/actions/*`. Each is its own tracked copy, run by
  path. `sync` names a copy and never deletes or refreshes one (`test_vendoring_retired.py`).
  Both tenants pin `setup-agentsmith@v2.4.0`.
- **The order is forced.** `evals run --fail-below` and `kg check` exist only from 3.0.0, so the
  pin and sync come before the swap.
- **Referencing the actions at the provider is sound.** They use only marketplace actions and their
  own `action_path`, never a path in the tenant.
- **A 2.x installer script** run outside a checkout reports the two missing assets and carries on:
  its `error` does not exit (read at `bffd4d2`).
- **No wire change.** No new field reaches the Ops Portal, so the Wire Contract table gains no row.

## Pass 2 — findings: 0

- The corrected row and DESIGN's mirror agree, and each command the row names exists:
  `verify_system.py --governed`, `process-gate kg check`, `evals run --fail-below`, the installer
  step.
- The backlog, the archive and the C9 design's `done` status agree. The governance-contracts design
  stays active until OTS and KYC have moved.
- The declaration examples in the User Manual and `process-gates.md` show `^2` and `@v2.1.0`.
  They illustrate the shape, as they did through 2.2 to 2.4, and were left.

## Sign-off

Group 1 · DRY & shared code — [x] n/a — version strings, records, and one action's comment; one test holds the three declarations together.
Group 2 · Quality / safety — [x] checked — `test_version_consistency.py` over the installer, the package, the design header and the new CHANGELOG section; the C9 code it carries is reviewed in `.agent-rfc/reviews/vendoring-retired.md`; the scratch tenants green on the release commit.
Group 3 · Architecture / hygiene — [x] n/a — no code changes in this commit.
Group 4 · Process — [x] checked — design before the version moved; backlog current state dated and C9 marked released; the C9 design marked done; archive entry; the release goes through a pull request merged by rebase and CI, then a tag on the merged commit.
Group 5 · Intuitive UI — [x] n/a — no screen or control.
Group 6 · Signal integrity — [x] checked — the 3.0.x row names what a 2.x tenant and machine lose, what keeps running stale, the order to move in, and the stale range a moved tenant would keep.
Group 7 · Auth & session integrity — [x] n/a — no credential handling; the release workflow's signing secrets are unchanged and read by name.

Tests added: none — the existing version pin covers the release.
Mutation-checked: n/a — no logic changed.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json` — this design's node.
Gates run: full `pytest` on the staged tree (2357 passed, 10 skipped); every gate of the self-test's Python job that runs here — the repo-tree check, `ruff`, `mypy` (1.14.1, Python 3.11 with `requirements.lock`), py_compile, redaction for both profiles, `--check-hooks`, `--check-kg`, the delivery evidence pack — and `bash -n install-ai-stack.sh`, and the edited action parsed as YAML; portal not run — no portal file changed since #56, whose CI built and tested it.

Levers reviewed: `declared-vs-enforced`, `docs-match-behaviour`, `failure-mode-visibility`, `two-owners-two-cadences`, `run-the-gates-ci-lists`.

KG query: kg:74416a305db5
