# Review: first-run-security-message

## Pass 1 — findings: 2

1. `declared-vs-enforced` — **The risk template sent a new user to `docs/security-framework-map.md`,** which their repository does not have. `tenant init` writes only its own `docs/` stubs. **Fix:** the comment points to the check's own report.
2. `test-the-contract` — **The other two templates kept "Copy to",** the same stale line the design set out to remove, though `tenant init` has already copied them. **Fix:** removed from `tool_allowlist.yaml` and `nist_profile.yaml`.

## Pass 2 — findings: 0

- **The control still fails:** `test_a_shipped_template_fails_and_says_where_and_what` asserts it on the shipped text.
- **Detection did not move:** the agency template's commented example is not parsed, and the sentinel ids stay in place.
- **The way to green was run:** the replaced files pass through the real port, and earlier in a real repository at 4.0.0, where a plain commit took them with no design.
- **A path outside the repository** is shown whole. The older tests' `ctx` has no `tenant_root`, and they still pass.
- **`tenant adopt` is untouched:** it seeds no placeholder and adds no Security job, so the note has nothing to say there.
- **A second `tenant init` is silent,** because the files were not written by that run. Tested.

## Sign-off

Group 1 · DRY & shared code — [x] checked — `shown_path` is one helper used by both runners; the note is one function.
Group 2 · Quality / safety — [x] checked — no verdict changes; "expected" is text beside a failure.
Group 3 · Architecture / hygiene — [x] n/a — no dependency or structural change.
Group 4 · Process — [x] checked — design before the change; CHANGELOG, manual and backlog updated; five mutations.
Group 5 · Intuitive UI — [x] checked — each failure names the file, says why and lists what to write; `tenant init` says it last.
Group 6 · Signal integrity — [x] checked — the agency template now says the check reads a declaration, not that the approval happens.
Group 7 · Auth & session integrity — [x] n/a — no credential handling.

Tests added: `scripts/test/test_security_first_run.py`.
Mutation-checked: `scripts/mutation_check.py security_contract`, 16 of 16 caught, including the five new ones.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: `test_security_first_run.py`, `test_security_contract.py`, `test_security_risk_register.py`, `test_first_commit.py`, `test_vendoring_retired.py`, `test_installer_templates.py` (98 passed); ruff; artifacts; process gate. A real `tenant init` from this tree printed the note last. Self-Test runs the full suite, the other mutation suites, and the portal and widget gates.

Levers reviewed: `declared-vs-enforced`, `test-the-contract`, `when-the-fallback-fails`.

KG query: kg:31ed21c49a5c
