---
status: done
scope:
  - scripts/send_dev_record.py
  - scripts/test/test_send_dev_record.py
  - scripts/mutation_check.py
---
# The ingest token does not follow a redirect

## Problem

`scripts/send_dev_record.py` posts an app's gate record to the portal with the
app's ingest token as a bearer. It opens the request with `urllib.request.urlopen`,
which follows redirects, and `urllib`'s `HTTPRedirectHandler.redirect_request`
copies every header but the content ones onto the redirected request —
`Authorization` included. For a POST it follows 301, 302 and 303. So a portal
address that redirects — a moved domain, a misconfigured proxy, a hijacked DNS
name — hands the ingest token to wherever the redirect points. The script's
https-or-localhost check runs on the address it was given, never on the one it
is sent to.

Found while building `runtime/intake.py`, which refuses redirects for this
reason; recorded as a backlog row on 2026-10-01 with "a three-line fix" as its
size.

## Approach

The same opener `runtime/intake.py` uses: a `HTTPRedirectHandler` whose
`redirect_request` raises instead of building the next request, so no second
request is ever made. Caught beside the existing errors, and answered as the
operator's fix — exit 1 with an `::error` annotation naming the address it
redirected to and saying to set `AGENTSMITH_PORTAL_URL` to the final address.
Not a warning: a misconfigured address is not "the portal is down", and a
green build would hide that every record since was going nowhere.

## Pillars

- P1 applies — `.agent-rfc/designs/send-dev-record-redirects.md`, from the backlog row.
- P2 applies — `runtime/intake.py`'s `_NoRedirect` is the existing answer; the same
  twelve lines, not a shared module, because `scripts/` runs in CI from the
  framework checkout and `runtime/` is vendored into tenants — the address rule is
  already duplicated across the two for that reason and pinned by
  `runtime/test/test_intake.py`. No dependencies.
- P3 n/a — a CI step script with no tracing; no new execution path.
- P4 applies — `scripts/test/test_send_dev_record.py` gains a stub portal that
  redirects to a second stub: the step fails, the second stub receives nothing, and
  the token is not printed. A mutation that restores the default opener goes into
  `scripts/mutation_check.py`.
- P7 n/a — standard-library Python, no models.
- P8 n/a — emits no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no LLM call.
- P11 n/a — reads no new untrusted content; the change narrows where a request goes.
- P12 applies — `scripts/send_dev_record.py` sends the ingest token only to the
  address it was configured with and checked against; a redirect is refused before
  any second request exists, so the token cannot follow it.
- P13 applies — `scripts/send_dev_record.py` gets stricter, and one behaviour that
  worked changes: a portal reached through a redirect now fails the step where it
  used to store the record. That is the intent; the message names the final address
  to configure instead.
- P14 n/a — no fixtures or baselines.
- P15 applies — `scripts/send_dev_record.py` reports a redirect as its own error,
  with the address it pointed to — not as "refused" or "unreachable", which would
  send an operator looking at the token or the network.
- P16 applies — `scripts/send_dev_record.py` fails the step with the fix in the
  message; nothing is sent, so there is nothing to undo, and the next push sends
  the record once the address is corrected.

## Deviations

none

## Dependencies

none

## Levers

- `pin-unremovable-duplicates` — the refusal now exists in both scripts that send a
  token to the portal; the address rule they share is already pinned to each other.
- `failure-is-not-a-result` — a redirect fails the step rather than warning, so a
  misconfigured address cannot hide behind a green build.
- `guards-must-be-able-to-fail` — the test proves the token does not reach the
  redirect target, and a mutation proves the test.
