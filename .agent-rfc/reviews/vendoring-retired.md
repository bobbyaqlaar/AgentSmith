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

# Commit 2 — vendoring removed, templates on the ports (C9a + C9b)

**Built evidence:**

- **Removed:**
  - `hooks/` (the four machine-wide git hooks) and the Enterprise Pack's hook bundle;
  - `agentsmith upgrade` and `runtime/machine/upgrade.py`, with the `ai-stack-upgrade` alias;
  - the release's `hooks.tar.gz` and `github-actions.tar.gz`;
  - `eval-ttft-live.yml` and `shadow-eval.yml`.
- **The installer** puts back the `init.templateDir` it recorded and removes AgentSmith's own
  templates. `agentsmith mode` and `uninstall` touch git's global config only while it is still
  AgentSmith's.
- **Every workflow template** asks AgentSmith through `{{PROVIDER_SETUP}}` and the launcher:
  - evals, with `--fail-below` for the CD smoke;
  - security, `check` and `redaction`;
  - the new gate verb `kg check`.

  Composite actions are referenced at the provider at the declared release.
- **`tenant init`** declares its providers (security `"emitter": "none"`, the judged suites warn
  until it has data), writes the gates and sync workflows, takes `--framework-ref`, seeds only the
  security placeholders, and vendors nothing.
- **`sync`** names a copy and never refreshes it. **`adopt`** says a copy is no longer run.
- **Nothing runs a tenant's copy:** neither the launcher, `find_script` nor `_candidate_dirs`.
  An old install's provisioning hooks are never chained.
- **`verify_system --governed`** names each framework copy by path, with what replaces it.
- **The scratch tenants** are built with `tenant init`, the scaffold committed through the
  tenant's own gate on a fresh history, force-pushed (owner-approved), and the job waits on both of
  each tenant's workflows.
- **Tests:**
  - `test_vendoring_retired.py` (13) is new;
  - eight files that tested only the retired transport are deleted;
  - the rest follow the new behaviour.
- **Curated mutations:** a new `vendoring_retired` suite (9); eight mutations of retired code
  removed.

## Pass 7 — findings: 13

Found while building and in the first full runs (209 failures, then 3), each checked in code
before it was changed:

1. **`tenant init` wrote no `providers.json`.** An init'd repository's ports said "no provider
   declared" and judged nothing, its gate fell back to paths, and the vendored scripts had masked
   it. **Fix:** init declares its providers and writes the gates and sync workflows, as adopt
   does.
2. **The templates were rendered before the declaration existed**, so every pin fell back to the
   installed release. **Fix:** the setup is resolved first and passed to `render_workflow`.
   `--framework-ref` names it.
3. **A second placeholder name for one thing:** `{{AGENTSMITH_SETUP}}` beside the gates templates'
   `{{PROVIDER_SETUP}}`. **Fix:** one name.
4. **The provider's setup step placed after the CI job's `setup-python`** would have switched the
   interpreter for the steps after it, as OTS's review found once before. **Fix:** first, right
   after checkout.
5. **The knowledge-graph step was dropped on a premise that was half wrong.**
   `verify_system --check-kg`'s staleness half checks a tenant's own graph; only its "AgentSmith's
   scripts are in the graph" half was vendoring-specific. **Fix:** a gate verb `kg check`
   (contract/gate/v3, additive) that the launcher asks the declared gate provider, without the
   framework-specific half. The templates run it.
6. **The five scratch tenants' commits would fail the gates workflow init now writes.** **Fix,
   with the owner:** a fresh history each run, the scaffold committed through the tenant's own
   gate, force-pushed.
7. **The scratch build job waited only on each tenant's stack CI.** **Fix:** it waits on the gates
   workflow too, and the job summary keeps its table header.
8. **The placeholder warning claimed SEC-RISK-001 and SEC-AGENCY-001 would fail** even when only
   the other two templates were seeded. **Fix:** it names exactly the graded files it seeded.
9. **The rules renderer told agents `uv run pytest` where CI installs with pip** (both
   `requirements.txt` and `uv.lock` present). The hook had agreed with CI and hid this. **Fix:**
   the renderer follows the install action's precedence, on exactly `requirements.txt`.
10. **A fresh tenant's security job failed SEC-PII-002 (no emitter declared) and SEC-EVAL-001**
    (the seeded base cases have no `actual_output`), and **its eval jobs failed `not_gradable`.**
    The hook-era scaffold skipped all three silently. **Fix:** init stops seeding the base eval
    data and declares `"emitter": "none"` and the suites' warnings. A built scratch tenant now
    passes security, warns on each suite, passes `kg check`, and passes its gate's `ci`.
11. **Claims no code backs:**
    - "post-checkout moves a pre-0.4 graph", which the hook never did;
    - documentation of `DISABLE_AI_STACK`, `AGENTSMITH_AUTOPUSH`, `AGENTSMITH_TENANT_VISIBILITY` and
      `SEMVER_LOOP_GUARD`, which only the retired hooks read;
    - `agentsmith status` reporting hooks "muted".

    **Fix:** corrected or removed. `mode off`'s now-vestigial meaning is on the backlog.
12. **Dead behaviour:** `chain_hooks` set `agentsmith.autopush`, which only AgentSmith's own
    `post-commit` read, and that hook is never chained now. **Fix:** removed, with its tests and
    its mutation.
13. **Small misses the suite caught:**
    - the compat script's `ai-stack-upgrade` still called the removed command;
    - `--framework-ref` was missing from the command reference;
    - `verify_system --help` did not list `--check-kg-fresh`;
    - a hand-rolled script loader in a test;
    - adopt's "runtime/, scripts/ still holds";
    - an unused import.

## Pass 8 — findings: 0

Over pass 7's fixes and the branch:

- A tenant built by `build.sh` holds nothing of AgentSmith (the `--governed` check is clean), and
  its scaffold commit passes its own gate locally and in `ci`.
- The launcher refuses `kg` verbs other than `check` (exit 2), and an older provider's usage error
  fails the step with the fix named.
- The installer only ever restores or unsets `init.templateDir` (a test holds it), and removes only
  templates whose second line says AgentSmith.
- `uninstall` acts only while the template dir is AgentSmith's.
- No template runs a script, a runtime module or a copied action (a test holds it).
- The design, CHANGELOG, `process-gates.md`, the User Manual, DESIGN, README, `scratch-tenants.md`
  and `enterprise/README.md` say what the code does.

## Pass 9 — findings: 5

The curated mutations over the branch (`--changed-since origin/main`), and a sweep of every live file
for each retired piece by name. Pass 8 was wrong to find nothing in the docs:

1. **A mutation survived:** the release could stop building `githooks.tar.gz` and the suite stayed
   green. Its test looked for the name in `release.yml`, and this commit's new header comment names
   it. **Fix:** the test asserts the build command. `installed_machine` 4/4.
2. **The CHANGELOG said the CI templates drop the knowledge-graph check**, which pass 7's fix 5 had
   put back as `kg check`. Neither it, the User Manual's `agentsmith gate` row nor
   `process-gates.md` named the new verb. **Fix:** all three say what it does.
3. **A clone made before 3.0.0 keeps the hooks git copied into its `.git/hooks`.** The installer
   cannot find it. Under the gates they are never chained, but in a clone that never adopted them
   `post-commit` still tags and pushes, and nothing said so. **Fix:** the CHANGELOG says how to
   find and remove them. The backlog item about old clones is rewritten around it, with a trigger.
4. **The backlog still held five items this commit closes:**
   - a new hook guardrail getting no vouch;
   - the hook guardrails outside the mechanical checks;
   - old tenants' `rollback-notify` copies;
   - new tenants not getting the gates;
   - `ai-stack-upgrade` overwriting a file by name.

   Others named `agentsmith upgrade` or the retired archives. **Fix:** the five are closed in the
   archive's C9 entry, and the rest are corrected.
5. **Live text about retired pieces:**
   - `release.yml`'s signing note (the hook bundle);
   - DESIGN's release artifacts and its "Vendors (Option A)" row;
   - the TTFT and shadow-eval docs (DESIGN, the manual, `shadow-eval.py`, `TTFT_LIVE` in two env
     examples);
   - the org-policy example (the hook bundle, a bypass by re-linking `init.templateDir`);
   - three test and installer comments, and `test_scaffold_review.py`'s section comment with its
     dead fixture import.

   **Fix:** each says what 3.0.0 does. The design's scope gains `portal/.env.example`.

## Pass 10 — findings: 4

Pass 9's fixes, then the static gates CI runs and a sweep of code (not only docs) for the retired
`hooks/`:

1. **`verify_system --check-hooks` still drove the deleted `hooks/pre-commit` and
   `hooks/commit-msg`.** It failed all four scenarios. CI's self-test runs it, and so does
   SEC-CHANGE-001 in AgentSmith's own checkout, so both would have gone red on the first push.
   **Fix:** it commits through this checkout's `.githooks` in throwaway repositories:
   - guardrails off, a marker goes in;
   - on by default, the marker is refused, naming the line;
   - with an org policy, a message without `RFC-NNN` is refused, and one with it passes.

   The control's component guard is `.githooks`. The CI step, the validation checklist, the manual
   and the security framework map say what it checks. The strict harness passes 22 with CI's
   `MODERATION_HOOK`, SEC-CHANGE-001 among them.
2. **The `tenant_adopt` mutation suite named two deleted test files.** Its baseline could not
   run. It also watched `hooks/*`. **Fix:** removed.
3. **`hooks/**` was still a path "a tenant receives":** in `process-gates.json`'s changelog paths
   and the scratch workflow's trigger, which a test keeps equal. **Fix:** removed from both. It
   stays gated, so a `hooks/` re-created by mistake still needs a design.
4. **`agentsmith hooks bypass-check` said it was called by the git hooks** (its help, its
   docstring, `policy.py`, `runtime/machine/__init__.py`). **Fix:** they say `mode off` asks it.
   What is left of the bypass policy is the backlog item pass 7 opened.

## Pass 11 — findings: 3

The full suite, then the `installed_machine`, `vendoring_retired` and `tenant_adopt` mutations, then
the static gates:

1. **`test_vendoring_retired.py` hand-rolled a script loader**, which the suite allows only in
   `_shared`. Moved onto `load_script`, an assertion that the module came from this checkout failed:
   it had loaded `~/.agent-framework`'s copy, because `_shared` was first imported after
   `init_tenant` put the install's `scripts/` first. **Fix:** `load_script` is bound when the test
   module loads, and the assertion stays.
2. **A `tenant_adopt` mutation survived:** the gate could stop looking for `@framework/` files
   past its own directory. The tests that held this were the vendoring ones this commit deletes, and
   its docstring and the mutation's name still gave a vendored copy as the reason. The fallback is
   still live: an install from the release tarballs has no `docs/`, and the installer tells that
   user to set `AGENTSMITH_DIR`. **Fix:** a test that such an install finds the lever doc through
   `AGENTSMITH_DIR`, and none without it. The docstring and the mutation name give the real
   reason. Applied by hand, the mutation fails it, and the file is restored byte for byte. An
   installer comment still naming `post-checkout` is corrected too.
3. **Two lines over the line limit**, from pass 10's fixes. **Fix:** wrapped.

## Pass 12 — findings: 0

Over pass 11's fixes, on the staged tree:

- the full suite before them (2355 passed, 10 skipped), and the ten affected test files after
  (300 passed);
- `installed_machine` 4/4, `vendoring_retired` 9/9, and `tenant_adopt` 17/18 by the runner, its
  survivor caught by hand after the fix, with the tree clean after every run;
- `ruff check .`; `mypy`; py_compile; the repo-tree check; redaction for both profiles;
  `--check-hooks` (4/4 through the gate); `--check-kg`; the delivery evidence pack;
- the strict security harness with CI's `MODERATION_HOOK`: 22 passed, SEC-CHANGE-001 among them.

Each retired piece searched for by name returns only history: the archive, the CHANGELOG's earlier
releases, designs and reviews, and a legacy shell-profile fixture.

# Commit 3 — the provider's CI setup installs what `kg check` imports

## Pass 13 — findings: 2

The first scratch-tenant build after #54 merged: five of six tenants red, the adopted one green.
Each built, committed through its gate and pushed, and its gates workflow passed. Its stack CI
failed one step, `Knowledge Graph is current`: `kg check` raised `ImportError: networkx`.

1. **The setup action installs `scripts/requirements-gate.txt` and nothing else**, and the list
   had no `networkx`. Locally the framework environment has it, so the tests, the review and my
   own `kg check` runs all passed. **Fix:** the list carries `networkx`. A test blocks it and shows
   `kg check` fails without it, and that the list names it.
2. **This record said commit 2 added 15 tests in `test_vendoring_retired.py`; it added 13.**
   **Fix:** 13 there; 14 with this commit's, in the sign-off.

## Pass 14 — findings: 0

- **CI's environment, rebuilt:** a clean Python 3.12 venv with only `requirements-gate.txt`, the
  setup action's `agentsmith` wrapper, and a fresh `tenant init` scaffold committed through its
  gate. `kg check` passes. With `networkx` removed from that venv it fails with CI's exact error,
  so the rebuild is faithful.
- **Nothing else missing:** `kg check`'s import path (`verify_system`, `map_codebase`,
  `local_knowledge_graph`) has no other third-party import.
- **The rest of that run:** every other job of the five tenants passed (security, the three
  evals, the gates). In the stack CI job, the steps after the graph step were skipped, not run:
  the RFC gate, the stack's tests, coverage, and pnpm's setup. C9 left them byte for byte as they
  were when the pre-C9 builds passed (diffed against `bffd4d2`). The scratch build this merge
  triggers is the first to run them, and is the proof.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one decision (`commit_verdict`) for the hook and gate contract 3's `commit`; the guardrails reuse `check_bare_except.find_violations` and `vouched_files.vouched`; init and adopt share `providers_declaration` and `provider_workflows`; the test loads scripts through `_shared.load_script`.
Group 2 · Quality / safety — [x] checked — `test_gate_guardrails.py` (15), `test_vendoring_retired.py` (14) and the rewritten suites; `--check-hooks` commits through the gate; curated mutations `commit_guardrails` 5/5, `vendoring_retired` 9/9, `installed_machine` 4/4, `tenant_adopt` 18/18 (one by hand, pass 11); the provider's setup environment rebuilt and `kg check` run in it (pass 14).
Group 3 · Architecture / hygiene — [x] checked — no dependency added; a tenant holds no copy of AgentSmith and asks the providers it declares; no hook is armed outside a repository; dead code and stale text removed.
Group 4 · Process — [x] checked — design before code, with the owner's decisions recorded; CHANGELOG Unreleased (breaking); backlog and archive; the User Manual, DESIGN, README, `process-gates.md`, `scratch-tenants.md` and `enterprise/README.md`.
Group 5 · Intuitive UI — [x] n/a — no screen or control.
Group 6 · Signal integrity — [x] checked — a copy left behind is named with what replaces it, never run; a fresh tenant's suites warn that they proved nothing rather than skip silently; an old provider's usage error names the fix.
Group 7 · Auth & session integrity — [x] n/a — no credential handling; the workflows' tokens are unchanged.

Tests added: `scripts/test/test_gate_guardrails.py` (15), `scripts/test/test_vendoring_retired.py` (14), `test_an_install_without_the_docs_finds_them_in_agentsmith_dir`, the `--fail-below` and `kg check` cases; eight files that tested only the retired transport deleted.
Mutation-checked: `commit_guardrails` 5/5, `vendoring_retired` 9/9, `installed_machine` 4/4, `tenant_adopt` 18/18.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json` — rebuilt on the final staged tree.
Gates run: full `pytest` on the staged tree (2355 passed, 10 skipped), then the affected files after pass 11 (300 passed); `ruff check .`; `mypy` (1.14.1, Python 3.11 with `requirements.lock`); py_compile; the repo-tree check; redaction for both profiles; `--check-hooks`; `--check-kg`; the delivery evidence pack; the strict security harness.

Levers reviewed: `grep-for-siblings`, `declared-vs-enforced`, `failure-mode-visibility`, `docs-match-behaviour`, `run-the-gates-ci-lists`, `every-line-earns-its-place`, `guards-must-be-able-to-fail`, `backlog-discipline`.

KG query: kg:01bb14907e83
