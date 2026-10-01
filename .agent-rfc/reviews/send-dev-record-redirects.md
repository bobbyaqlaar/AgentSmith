# Review — send-dev-record-redirects

Design: `.agent-rfc/designs/send-dev-record-redirects.md`
Levers: `docs/review-levers.md`

## Pass 1 — findings: 1

1. **`failure-is-not-a-result` — which exit code a redirect gets was a real
   choice, and the script's existing pattern pointed the wrong way.** The script
   answers a 5xx or an unreachable portal with a warning and exit 0, because the
   gate's verdict stands without the portal. Catching the redirect beside those
   would have made it a warning too — and a green build would then hide that every
   record since was going nowhere. A redirect means the configured address is
   wrong, which is the operator's fix, so it is an `::error` with exit 1 like a
   refused record, and the message names the address it pointed to. The test
   asserts the exit code, and a mutation that turns it back into exit 0 is caught.

## Pass 2 — findings: 0

Re-read `scripts/send_dev_record.py` and the test against the levers.

- `pin-unremovable-duplicates` — the opener now exists in both scripts that send a
  token to the portal. They ship to different places (`scripts/` runs in CI from the
  framework checkout; `runtime/` is vendored into tenants), which is also why their
  address rule was already duplicated and is pinned by `runtime/test/test_intake.py`.
- `guards-must-be-able-to-fail` — the test stands up a second portal as the redirect
  target and asserts it receives nothing; both mutations are caught.
- The token is not printed on the new path: asserted.
- The 302 is handled for the POST this script makes; `urllib` would also follow a
  301 or 303 for a POST, and the handler refuses every redirect code alike, since it
  raises in `redirect_request` whatever the code.

## Sign-off

Group 1 · DRY & shared code — [x] checked — the same opener as `runtime/intake.py`, kept as two copies on purpose because the scripts ship to different places; the rule they share is pinned.
Group 2 · Quality / safety — [x] checked — a test with a real redirecting portal and a real target; a `send_dev_record` mutation suite, 2 of 2 caught.
Group 3 · Architecture / hygiene — [x] n/a — no structure changes; one opener replaces one call.
Group 4 · Process — [x] checked — from a backlog row to a design to the fix; the row is archived with the evidence in the same change.
Group 5 · Intuitive UI — [x] n/a — no screen; the CI annotation names the address to configure.
Group 6 · Signal integrity — [x] checked — a redirect is its own error, not "refused" or "unreachable", and fails the step rather than warning.
Group 7 · Auth & session integrity — [x] checked — the ingest token goes only to the configured, checked address; a redirect is refused before a second request exists.

Tests added: `test_security_a_redirect_fails_the_step_and_the_token_does_not_follow_it` in `scripts/test/test_send_dev_record.py`.
Mutation-checked: yes — `send_dev_record` suite in `scripts/mutation_check.py`, 2 mutations, both caught.
Fixtures re-pinned: none.
Gates run: `pytest` over `scripts/test/test_send_dev_record.py` and `runtime/test/test_intake.py`, the pinned `ruff==0.15.20` over the whole repository, the mutation suite, and `python3 scripts/process_gate.py ci --base origin/main --head HEAD` before pushing.

Levers reviewed: `pin-unremovable-duplicates`, `failure-is-not-a-result`, `guards-must-be-able-to-fail`, `every-line-earns-its-place`, `docs-match-behaviour`.

KG query: kg:372935b489d9
