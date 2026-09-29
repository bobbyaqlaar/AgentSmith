---
status: active
scope:
  - hooks/**
  - runtime/**
  - scripts/**
---
# A scaffold that satisfies the enterprise gate, and guardrails that skip what the tenant did not write

## Problem

Two halves of one failure, agreed with the owner on 2026-09-29.

**A. An enterprise machine still cannot make a scaffolded tenant's first commit.**
`hooks/pre-commit` Guardrail 4 requires at least one `*.md` at `.agent-rfc/`
**depth 1** wherever `~/.agent-framework/agenticframework-org.yaml` exists.
`agentsmith tenant init` writes `.agent-rfc/designs/scaffold.md` — depth 2 — so the
commit the CLI itself prints is refused with "Enterprise policy requires at least
one RFC under `.agent-rfc/`". Verified on an isolated HOME carrying a policy file
(.agent-rfc/designs/first-commit-guardrail.md, Pass 4).

**B. A tenant is held to guardrails over code it did not write.** The same hook
runs Guardrails 1–3 over every staged file, including the `scripts/` and
`runtime/` the scaffold vendored. That is what blocked every first commit until
2026-09-29, and the fix then was to clean the framework's own code — which works
until the next unmarked handler, and leaves a tenant reading errors about files
it cannot change.

The owner proposed the shape: `tenant init` creates a template artefact, and the
gates are relaxed for the scaffold. This design takes the first as proposed and
scopes the second by manifest rather than by commit, because "the initial commit"
also carries whatever the user already had in the working tree — their own code
would go unchecked on exactly the commit that sets the baseline.

### Two things checked that turned out not to be constraints

- **The RFC does not need to be in the manifest for the escape to work.**
  `.agenticframework/process-gates.json` lists `**.md` and `.agent-rfc/**` under
  `not_gated`, and `manifest_problems()` only examines gated paths. An earlier
  note of mine said the escape would break without it; that was wrong. It is
  recorded in the manifest anyway, because `--force` uses the manifest to know
  what is its own to replace.
- **The vendored trees carry no AI markers today.** `git ls-files scripts/*
  runtime/*` minus the two test trees, grepped for `ponytail:|TODO: agent|@agent-ignore`,
  returns nothing — so part B grants a skip over files that currently pass anyway.

## Approach

**A. The scaffold writes `.agent-rfc/001-scaffold.md`.** Depth 1, the
naming convention `docs/UserManual.md` › Writing Agent Specifications documents
(`NNN-short-description.md`), and the three sections it calls the minimum:
Objective, Files to Modify, Acceptance Criteria. Written beside the scaffold
design in `write_scaffold_records`, and added to `written` so
`_scaffold_files` records it in the manifest without special handling.

It is a template, so it says so — indented, never at column 0, because
`.github/scratch-tenants/build.sh` fails a build on any column-0 `⚠️`/`❌` and the
security pack's own placeholder warning is indented for that reason.

Not written when one already exists: a tenant that has real RFCs must not have a
stub dropped among them, and a `--force` re-run must not overwrite an edited one.

**Both commands, not just `tenant init`.** `write_scaffold_records` is shared with
`tenant adopt`, and Guardrail 4 is a repository-level rule, so an adoption on an
enterprise machine hits exactly the same refusal. Both therefore write the RFC,
and both print an `RFC-NNN` trailer in the commit command they tell the user to
run — `hooks/commit-msg` requires that reference separately from Guardrail 4, and
satisfying one without the other would leave the command still refused. The
reference is read off disk rather than assumed to be 001, so a repository that
already had RFCs cites its own.

**B. Guardrails 1–3 skip a staged file the manifest vouches for.** Vouched means
both: the path is in `.agenticframework/scaffold.json`'s `files`, and the staged
blob's SHA-256 still matches what is recorded. Edit a vendored file and it is
checked again, because the hash no longer matches.

The list is computed once by `scripts/vouched_files.py`, resolved the way the
hook already resolves `check_bare_except.py` — `~/.agent-framework/scripts/`
first, then the repo's own copy. It reads the staged blobs through one
`git cat-file --batch`, not one process per file, because a first commit stages
166 of them.

**Fail-safe by construction.** No helper, no `python3`, no manifest, an
unparseable manifest, or any error: the vouched list is **empty** and every file
is checked, which is today's behaviour. The skip can only ever be granted by a
positive hash match, never by the absence of evidence.

Guardrail 4 is untouched. It is a repository-level question — does any RFC exist
— not a per-file one, so no skip can reach it. Part A is what answers it.

**What stops this from being a hole.** The rules keep running over the framework's
own code, in the framework's own suite: `scripts/test/test_bare_except_tree.py`
already checks every tracked `.py` for Guardrail 2, and this slice adds the same
sweep for Guardrail 1 over the two trees that get vendored. So the skip moves
where a defect is caught — from a tenant who cannot fix it to the repository that
can — rather than removing the check.

## Pillars

- P1 applies — this design before the edit; scope `hooks/**`, `runtime/**`, `scripts/**`, reviewed in `.agent-rfc/reviews/scaffold-rfc-and-vouched-skip.md`, with `docs/process-gates.md` and `docs/UserManual.md` updated for the new behaviour and `CHANGELOG.md` for the tenant-facing half.
- P2 applies — the manifest, its hashes and `manifest_problems()` already exist in `scripts/process_gate.py` and `runtime/cli.py`; this reuses them rather than adding a second notion of "what the framework wrote". One new file, `scripts/vouched_files.py`, because `hooks/pre-commit` is POSIX shell and cannot parse JSON — the same reason `scripts/check_bare_except.py` exists, and resolved by the same path order. No dependencies added.
- P3 n/a — a shell hook and a scaffold writer; neither is on a traced execution path and neither gains one here.
- P4 applies — tests that fail before and pass after: the RFC lands at depth 1 and is recorded in the manifest; an enterprise scaffold's printed commit succeeds (`scripts/test/test_first_commit.py` gains the org-policy case that is currently the recorded gap); a vouched file is skipped; an **edited** vouched file is checked again; a file absent from the manifest is checked; and the vouched list is empty when the manifest is missing or unparseable. Mutation targets on the two halves of the vouch — deleting the hash comparison, and deleting the path membership test — must each fail a test.
- P7 applies — POSIX shell in the hook with the existing `while IFS= read -r` idiom; Python 3.11+ in the helper, standard library only, no pydantic since the hook must run where the framework venv may not.
- P8 n/a — no telemetry; `hooks/pre-commit` emits none today.
- P9 n/a — no orchestration.
- P10 n/a — no LLM call.
- P11 applies — `.agenticframework/scaffold.json` is repository content and therefore untrusted input to the helper: it is parsed with `json.loads` into a dict of string keys, every path is compared as an exact string against the staged list rather than globbed or joined onto the filesystem, and a malformed manifest yields an empty list. A manifest cannot name a path outside the staged set, so it cannot grant a skip for a file the commit does not contain.
- P12 applies — no credential is read or written. The helper runs `git cat-file` against the index only, and writes nothing.
- P13 applies — **this is the pillar the slice turns on, and the control is split.** Weakened: Guardrails 1–3 in `hooks/pre-commit` no longer run over vendored framework files in a tenant. Held: `scripts/vouched_files.py` grants a skip only on a positive SHA-256 match against `.agenticframework/scaffold.json` in the same commit, so an edited file is checked again (`test_an_edited_file_loses_its_vouch`); Guardrail 4 keeps its full strength and takes no skip; every failure mode of the helper yields an empty list (`test_no_manifest_vouches_for_nothing`, `test_an_unparseable_manifest_vouches_for_nothing`, `test_a_manifest_that_is_not_a_mapping_vouches_for_nothing`); and the same two rules now run over the framework's whole tree in `scripts/test/test_bare_except_tree.py` and `scripts/test/test_vendored_markers.py`, so the defect is caught where it can be fixed. The unprovable half — that no *other* guardrail added later will need the same treatment — is declared, not assumed.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` re-pinned with `map_codebase.run_map(force=True)` and `scripts/test/test_kg_drift_gate.py` re-run. The five scratch tenants gain a file at `.agent-rfc/001-*.md` on their next rebuild; `.github/scratch-tenants/build.sh` compares `.gitignore` and hook warnings, not a file list, so the fixture comparison does not go stale.
- P15 applies — a skipped file must not read as a passed file. The hook prints how many staged files the manifest vouched for and that they were not checked, indented so `build.sh`'s column-0 warning grep does not fire on an informational line. Silence would make "the guardrail found nothing" and "the guardrail did not look" identical, which is the defect class this repository keeps finding.
- P16 applies — every rung of the helper's failure path ends in "check everything": helper missing, interpreter missing, manifest missing, manifest unparseable, `git cat-file` failing. The hook's existing behaviour is the floor, and nothing here can lower it. Where the vouch succeeds but Guardrail 4 still refuses (an enterprise machine before Part A reaches it), the tenant sees the Guardrail 4 message, which names the file to create.

## Deviations

none

## Dependencies

none

## Levers

- `declared-vs-enforced` — the manifest already declares what the framework wrote; nothing read it at pre-commit time.
- `guards-must-be-able-to-fail` — the skip is granted only by a positive hash match, so losing the helper cannot silently disable a guardrail.
- `ambiguous-signals` — "not checked" must not print as "checked and clean".
- `provenance-and-precedence` — two sources now decide whether a file is checked (the manifest, and the staged content); the hash is what makes the manifest lose when they disagree.
- `check-that-fires-on-everything` — the rules move to the framework's own tree, where they run over all of it, instead of firing per-tenant on files a tenant cannot change.
- `fixture-truth` — the scratch tenants will carry the new RFC; the build compares behaviour, not a file list, so the fixture stays honest.
- `every-line-earns-its-place` — one helper, one template, no second manifest and no allowlist.
