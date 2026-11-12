# Review: image-final-stage-and-mcp-reads

Each fix has tests that fail without it, in `scripts/test/test_compliance_checks.py`. P2-R10: the review's multi-stage
Dockerfile passed, and `COPY --chown=… .`, `COPY ./` and `ADD .` failed; the `.dockerignore` negation the second pass
found untested now has a case. P2-R11: a commented `.vscode/mcp.json` raised; a changed `title`, `annotations` or
`outputSchema` kept the same hash; `.codex/config.toml` was not read; an unreadable file raised instead of being named.

## Pass 1 — findings: 1

Against `docs/review-levers.md`, by hand mutants (fourteen).

1. **`COPY --from=<stage>` was excluded by rule and by nothing in the tests.** From another stage, `.` is that stage's
   filesystem root, not the build context, so it says nothing about the declaration; the mutant that counted it
   survived. A case now holds it: `COPY --from=build . /app` in the final stage does not ship the declaration.

## Pass 2 — findings: 0

- The fourteen mutants again, and the `--from` one: all killed. Among them: the whole file judged instead of the last
  stage; flags refused; `./` refused; `ADD` refused; the "must be mounted" note dropped; the `.dockerignore` negation
  ignored; comments not stripped; strings not protected (`https://` read as a comment); escaped quotes not handled; an
  unreadable file raised; the narrow hash; no Codex; trailing commas kept.
- `scripts/test/test_compliance_checks.py` and `agentsmith/test`: 988 passed, 18 skipped. ruff and mypy 1.14.1: clean.
- Siblings: `pin`, `verify`, `scope_note` and `static_problems` all read servers through one function, so each gets the
  JSONC reading, the Codex file and the named failures; `pin` refuses to write pins while a server file is unreadable.
  The security map's ASI04 row now lists `.codex/config.toml`.
- Compatibility, stated in the CHANGELOG: the tool hash is wider, so pins made before it no longer match. The profile
  ships for the first time in 4.1.0, so only pins made from a pre-release build are affected.
- The JSONC reader is a small scanner, not a parser: it removes comments and trailing commas outside strings and hands
  the rest to `json.loads`, so anything else malformed is still refused, and named.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one server reader for pin, verify, the note and the check; one stage reader.
Group 2 · Quality / safety — [x] checked — the image that runs is judged; an unreadable server file is a named problem.
Group 3 · Architecture / hygiene — [x] checked — two modules changed in place; `tomllib` from the standard library.
Group 4 · Process — [x] checked — design first; CHANGELOG, backlog and the security map updated.
Group 5 · Intuitive UI — [x] n/a — no screen.
Group 6 · Signal integrity — [x] checked — "passes, but must be mounted" is said, not folded into "ships".
Group 7 · Auth & session integrity — [x] n/a — no auth code.

Tests added: eleven cases in `scripts/test/test_compliance_checks.py` for the final stage, the mount note, JSONC, an unreadable file, the wider hash and Codex.
Mutation-checked: yes, by hand; fifteen mutants, all killed after pass 1.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the suites above; ruff; mypy; `scripts/verify_system.py --check-kg`; the process gate against the commit.

Levers reviewed: `gate-integrity`, `aggregates-name-their-scope`, `grep-for-siblings`, `docs-match-behaviour`, `test-that-cannot-fail`

KG query: kg:3aabc9a15e62
