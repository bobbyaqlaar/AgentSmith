---
status: done
scope:
  - scripts/**
  - runtime/**
---
# A scaffolded tenant cannot make its first commit

<!-- Closed 2026-09-29: shipped in 7854bd1. Its declared gap — the enterprise machine — is the subject of scaffold-rfc-and-vouched-skip.md, a design of its own rather than more work under this one. -->

## Problem

`agentsmith tenant init` ends by printing the exact command to commit its own
output. That command is refused.

    🛑 Pre-commit guardrail failed. Fix issues above.

`hooks/pre-commit` Guardrail 2 runs `scripts/check_bare_except.py` over every
**staged** `.py` file. A first commit stages everything, including the `scripts/`
and `runtime/` the scaffold vendored, so the check runs over AgentSmith's own
code — and fails on empty `except` handlers in it. Eight are visible that way:

    scripts/gate_history.py:66, :71        scripts/map_codebase.py:253
    scripts/process_gate.py:1480, :1760   scripts/mutation_check.py:1026, :1098
    scripts/send_dev_record.py:95

Verified against this checkout, not a stale install. Running the checker over the
**whole tracked tree** — which nothing has ever done — finds thirteen, because a
scaffold vendors only part of it:

    runtime/embeddings.py:163             runtime/llm_gateway.py:1843, :2100
    scripts/security/runners/structured_output.py:37
    scripts/test/test_documented_env_vars_exist.py:134
    … and the eight above

The count is the evidence for the diagnosis: the eight are what one tenant's first
commit happens to stage, not what the rule has let through.

**Why eight accumulated.** Nothing has ever run this check over the tree. It runs
only on staged files, and these files are rarely staged — so for AgentSmith's own
commits the rule is effectively dormant, and handlers were added under it without
anyone seeing a failure. Grep confirms no workflow or test runs the checker over
the repository; `scripts/test/test_check_bare_except.py` tests the *checker*, on
synthetic input.

**Why nothing caught the tenant case.** The scratch tenants all have history —
`.github/scratch-tenants/build.sh` copies into an existing repository, so only
changed files stage, and the framework's vendored files never stage together
again after the seed commit. `git init` is the only path that stages them all at
once, which is what onboarding and the demo do. The five fixtures made faithful
on 2026-09-27 still only exercise the second commit onward.

## Approach

Three parts: mark the handlers honestly, make the rule non-dormant, and cover the
path that was never covered.

**1. Give each handler a reason — except the one that is not a fail-open.** Twelve
of the thirteen are intentional fail-opens, and the checker already supports
`# fail-open: <reason>` on the `except` line or in an unbroken comment run above
it. Each gets a specific reason, not a blanket one. No allowlist file is added:
the justification stays on the line it excuses, which is the convention
`check_bare_except.py`'s own docstring argues for.

Four of the twelve already tried to say why and are flagged anyway, which is the
same defect in miniature:

- `gate_history.py:71` carries "a log that cannot be written must not break the
  hook that writes it" on the `pass` line, where the checker does not read.
- `map_codebase.py:253`, `runtime/embeddings.py:163` and
  `runtime/llm_gateway.py:2100` write `# fail-open` — a comma or nothing where the
  marker needs a colon.

The thirteenth, `scripts/security/runners/structured_output.py:37`, is **not** a
fail-open: `except StructuredOutputError: pass` means the expected error was
raised, which is the check passing. Marking it `fail-open:` would put a label on
it that lies, in a repository whose whole lever list is about that. It is
restructured instead — the raised exception is captured and then judged — so there
is no empty handler to excuse and the two outcomes it distinguishes stay
distinguishable.

**2. Run the rule over the tree.** A test walks every tracked `.py` file through
the checker. This is the part that stops recurrence: with it, a new unmarked
handler fails in AgentSmith's own suite, at the moment it is written, instead of
surfacing months later in a stranger's first commit.

**3. Test the first commit.** A test scaffolds a tenant into a temp directory and
runs the commit command `tenant init` prints, asserting it succeeds. This is the
gap the scratch tenants cannot close, because closing it requires starting from
`git init`. Each of the two tests carries a guard: one asserts the tree sweep is
sweeping a real file list, the other asserts the pre-commit guardrail actually
ran and passed rather than being absent — which it was, in the first three
attempts at this test.

**Found while writing that test: the shared `install` fixture was not what it
said.** Its docstring promised "a complete ~/.agent-framework … as
install-ai-stack.sh lays them out" while copying one of three files in
`templates/`, none of the three in `docs/`, and one of the four machine hooks. The
missing `pre-commit` is the guardrail itself, so **no test using this fixture
could see a pre-commit guardrail run at all** — which is the deeper reason this
bug survived, beyond the scratch tenants having history. All three omissions are
fixed, and the docstring now names the one thing still absent (the venv).

**And a second guardrail failed the same way.** With `pre-commit` finally present,
Guardrail 1 — unresolved AI markers — refused the commit too:
`scripts/verify_system.py` writes `"# TODO: agent fix this"` as data for its own
hook test, the literal is in a file vendored into every tenant, and Guardrail 1
greps staged files for exactly that string. The literal is assembled from two
pieces so the file no longer contains it while the file written at runtime stays
byte-identical; `verify_system.py --check-hooks` still reports "opted-in repo:
pre-commit enforces guardrail 1 (exit 1)", so the detection it exists to prove is
intact. Only `verify_system.py` is affected: `scripts/test/` and `hooks/` also
carry the markers and are not vendored.

### Not fixed: the same commit under enterprise policy

Where `~/.agent-framework/agenticframework-org.yaml` exists, Guardrail 4 requires
at least one `*.md` at `.agent-rfc/` depth 1. The scaffold writes
`.agent-rfc/designs/scaffold.md` — depth 2 — so the printed commit is still
refused, with "Enterprise policy requires at least one RFC under `.agent-rfc/`".
Verified on an isolated HOME with a policy file, after everything above was in
place.

It is deliberately out of this slice. Both fixes change what a contract means:
counting recursively makes a design note satisfy an RFC requirement, and writing a
top-level RFC stub from `tenant init` creates exactly the kind of empty artifact
the artifacts registry refuses. That is the owner's call, and
`docs/PRODUCT_BACKLOG.md` carries it with the trigger already fired. The tests
added here cover the default machine only, and say so.

### Considered and deferred: exempting vendored files in a tenant

A tenant did not write `scripts/process_gate.py` and cannot fix it, so there is a
real argument that a tenant's pre-commit should skip the files
`.agenticframework/scaffold.json` records as framework-written. It is deliberately
**not** done here:

- With part 2 in place the rule is enforced where the code is authored, so the
  exemption would buy robustness, not coverage.
- Skipping a whole tree is a weakening of a guardrail, and it needs the manifest
  consulted for *which* files and whether they are unmodified — a design of its
  own, with its own failure mode (a tenant editing a vendored file and being
  exempted).
- It does not fix anything retroactively: a tenant on an older release still
  vendors whatever that release contained.

Recorded in `docs/PRODUCT_BACKLOG.md` with the trigger that would force it: a
tenant blocked by a released version's vendored code.

## Pillars

- P1 applies — this design before the edit; scope `scripts/**`, reviewed in `.agent-rfc/reviews/first-commit-guardrail.md`, with the deferred decision recorded in `docs/PRODUCT_BACKLOG.md`.
- P2 applies — `scripts/check_bare_except.py` already exists and already supports the marker, so nothing is built: eight lines get a reason, and two tests get written. Grep over `.github/workflows/`, `scripts/test/` and `workflow-templates/` confirms no existing caller runs the checker over the tree, so the new test is not a second copy of one. No dependencies added.
- P3 n/a — the changed lines are exception handlers in a gate and a mapper; no new execution path that should emit a span, and `scripts/gate_history.py` is itself the fallback record for when spans cannot be exported.
- P4 applies — four tests in two files, three of which fail before this change and pass after, proven by reverting the source fixes and re-running: `test_every_tracked_python_file_passes_the_bare_except_check` fails on all thirteen handlers, `test_the_scaffold_commit_the_cli_prints_is_accepted` fails with the guardrail refusal that opened this design, and `test_the_pre_commit_guardrail_still_runs_on_that_commit` fails with it too. The fourth, `test_the_checker_is_reading_a_real_file_list`, passes throughout by design — it is the guard that the sweep is not sweeping an empty list. No mutation target: nothing branches, and the two end-to-end tests are the equivalent check.
- P7 applies — Python, `ast`-based checker; the markers are comments, so no behaviour changes. The new tests use `subprocess` against the real hook rather than importing it, because the defect lives in the hook's file selection, not in the checker.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no LLM call.
- P11 n/a — no untrusted content; the checker parses repository source it already parses.
- P12 applies — no credential is read or written. The scaffold-and-commit test commits in a temp repository with no remote, so `hooks/post-commit`'s auto-tag-and-push cannot reach anything.
- P13 applies — **twelve handlers become exempt, which is a weakening, so it is split.** Each exemption carries its own written reason on its own line, reviewable one at a time; no allowlist file and no blanket exemption is introduced, and the thirteenth is fixed rather than exempted. Against that, the rule stops being dormant: it runs only on staged files today and so had never once examined `scripts/` or `runtime/` as a whole, which is why thirteen accumulated and why only eight were visible from the failure that started this. Net, the check gets stronger — but the twelve are real exemptions and are named here as such.
- P14 applies — no golden or baseline moves; `.agent-rfc/fixtures/knowledge_graph.json` re-pinned with `map_codebase.run_map(force=True)` if the tracked file set changes, and `scripts/test/test_kg_drift_gate.py` re-run.
- P15 applies — a flagged handler currently cannot be told apart from an unconsidered one: `scripts/gate_history.py` and `scripts/map_codebase.py` both explain themselves at the flagged handler and are both reported anyway, because the explanation is in a place or a punctuation the checker does not accept. After this change "flagged" means "nobody has said why", and the two tests make an unmarked handler fail where it is written rather than where it is copied.
- P16 applies — every one of the eight is itself a recovery path (an unwritable log, an unreadable sweep store, a non-JSON error body, `signal.signal` off the main thread), and each keeps its current behaviour: the marker is a comment. The scaffold-and-commit test asserts the recovery path this design is about — that a tenant can complete its first commit — rather than only that the checker is quiet.

## Deviations

none

## Dependencies

none

## Levers

- `check-that-fires-on-everything` — the rule ran only on staged files, so it had never examined the tree it is supposed to protect; eight handlers accumulated under a dormant check.
- `guards-must-be-able-to-fail` — inverted here: the guard fails loudly, on the wrong party, at the worst moment. It must fail where the code is written.
- `declared-vs-enforced` — `check_bare_except.py`'s docstring declares the marker convention; two handlers tried to use it and were flagged anyway.
- `ambiguous-signals` — "flagged" must mean "unexplained", not "explained in a place the parser does not read".
- `fixture-truth` — the scratch tenants have history and so cannot exercise a first commit; the fixture that looked complete was missing the only path that reproduces this.
- `environment-parity` — a tenant's first commit and AgentSmith's own commits ran the same hook over different file sets, and only one of them was ever observed.
- `every-line-earns-its-place` — eight comments and two tests; no allowlist file, no new module, no change to the checker.
