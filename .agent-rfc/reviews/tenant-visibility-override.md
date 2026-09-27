# Review — tenant-visibility-override

Design: `.agent-rfc/designs/tenant-visibility-override.md`
Levers: `docs/review-levers.md`

## Pass 1 — findings: 3

1. **`docs-match-behaviour` — the prompt transcript in `docs/DESIGN.md` was not the
   hook's output.** The section I edited showed a two-line prompt beginning
   "⚠️  AgentSmith: IDE config files contain system prompt content." The hook
   prints "⚠️  This repository appears to be public." followed by the file list
   and the question on its own line. A reader matching the doc against a real run
   would not find that text anywhere. Verified by reading
   `hooks/post-checkout` lines 508-513 against the fenced block. Fixed: the
   transcript is now the hook's actual output.

2. **`declared-vs-enforced` — `docs/DESIGN.md` claimed a behaviour no code
   implements.** "Additionally, if `.agenticframework/tenant.yaml` contains
   non-public tenant metadata (non-default tenant id, non-public endpoint URLs),
   it is also included in the gitignore prompt for public repos." `grep -n
   tenant.yaml hooks/post-checkout` shows four uses — the provisioning gate, the
   tenant-id read, and the enabled check — and none of them adds it to the
   gitignore block, which appends exactly seven IDE-config paths. Nothing has ever
   done this. Fixed by saying what happens and naming the file as *not* covered;
   whether it should be is a real open question — it is also the file
   `agentsmith tenant init` expects to be committed — so it is recorded in
   `docs/PRODUCT_BACKLOG.md` with the trigger that would force the decision,
   rather than implemented under cover of a docs fix.

3. **`ambiguous-signals` — the TTY prompt asks consent for six paths and appends
   seven.** `hooks/post-checkout` names ".cursorrules, CLAUDE.md, AGENTS.md,
   GEMINI.md, .github/copilot-instructions.md and .agents/" and then appends
   those plus `.agent-history.log`. Someone answering "y" agrees to less than
   they get. Pre-existing, in the branch this slice is about, and the same defect
   class as the message this slice exists to fix. Fix pending — the mutation
   harness holds `hooks/post-checkout` while it runs, and editing a file it is
   rewriting would corrupt both.

### Examined and left alone, with reasons

- **The value is echoed unvalidated** into the warning and the declaration
  message. A value containing a newline could forge a column-0 line in the
  build log. The impact is fail-safe, not fail-open: the forged line that
  matters is `^⚠️` or `^❌`, and `.github/scratch-tenants/build.sh` *fails* the
  build on those. The setter is also the process that owns the environment, so
  this is not a privilege boundary. Recorded rather than sanitised, since
  sanitising would add code whose only effect is on a caller attacking itself.
- **A declared-public repo still prompts on a TTY.** Correct: the declaration
  says what the repository is, not that the human has consented to the
  `.gitignore` edit.

## Pass 2 — findings: 3

1. **`test-that-cannot-fail` — the new prompt test passed on my own comment.**
   `test_the_prompt_names_every_path_it_would_ignore` sliced the prompt region as
   *source text* and searched it for each appended path. The comment I had just
   written above the prompt says "`.agent-history.log` was appended and never
   named" — so the path was found in prose, and deleting it from the prompt left
   the test green. Proven by making exactly that cut and watching it pass, then
   watching it fail after the fix. The test now reconstructs what the hook
   **prints**, from the `echo`/`read -r -p` string literals only, so comments
   cannot satisfy it. This is the second time in this repository that prose
   inside a checked region satisfied a check about that region.

2. **`docs-match-behaviour` + `declared-vs-enforced` — `internal` was accepted
   and documented nowhere.** The `case` accepts `internal|INTERNAL` (correctly:
   `gh repo view` returns `INTERNAL` for org-internal repositories, and the
   existing detection already treats it as private), but `docs/UserManual.md`
   and `docs/DESIGN.md` both said `private|public`, and the warning for an
   unrecognised value said "is not private or public" — naming two of the three
   values it accepts. Someone setting `internal` from the docs would have been
   told it was invalid by a message that then accepted it. All three now name
   the same set, and `internal`/`INTERNAL` are parametrised into the
   declared-private test so a documented value has something reading it.

3. **`fixture-truth` — the five fixtures already publish what the rule protects,
   and this slice makes that deliberate.** Worth stating plainly rather than
   leaving in a design doc: AgentSmith itself does **not** track `CLAUDE.md`,
   `.cursorrules`, `AGENTS.md`, `GEMINI.md` or `.github/copilot-instructions.md`,
   while the five scratch repos do — and since 2026-09-27 those repos are public,
   so the generated IDE config files are published today, from the 2026-09-24
   build, before this change lands. Declaring `private` keeps it that way by
   design. Verified before accepting it: the published copies render
   `Owner: unknown@unknown`, carry no email or endpoint, and the 121-commit
   credential scan across all five repositories came back clean, so what is
   published is a rendering of `templates/agent-rules.yaml` — itself public and
   tracked. No secret is exposed; a stated policy is being traded for fixture
   fidelity, which is the owner's decision and is recorded here as one.

## Pass 3 — findings: 1

1. **`environment-parity` — `ruff format --check` would have reformatted the new
   test file.** `ruff check` passed, so lint alone said nothing; the formatter is
   a separate gate and CI runs it. Formatted, and both now pass. The sweep that
   found it also confirmed the thing it was looking for was absent: `grep` for
   `copilot-instructions.md` across `.py`, `.sh`, `.md`, `.yaml`, `.json` and the
   hook returns eighteen files, and **none of them writes a `.gitignore` entry** —
   `install-ai-stack.sh` only names the set in a comment. `hooks/post-checkout`
   is the sole writer, so the two copies the new test pins are all of them, and
   there is no third place for them to drift to.

## Pass 4 — findings: 2

1. **`docs-match-behaviour` — `CHANGELOG.md` announced a smaller accepted set
   than shipped.** It said `AGENTSMITH_TENANT_VISIBILITY=private|public` after
   Pass 2 had already established that `internal` is accepted and documented.
   Corrected. The release note is the surface a tenant upgrading reads, so it is
   the worst of the three places to under-state it.
2. **`docs-match-behaviour`, applied to my own design — the message table in the
   design record did not match what the hook prints.** The design said "three
   distinct messages replace the one" and listed three rows. The implementation
   prints five: the declaration at the decision point, three append variants, and
   the unrecognised-value warning. The design's own table would have misled the
   next reader about the code beside it. Rewritten to the five it actually
   prints, then **verified mechanically** rather than by eye — each row's
   sentence was probed against `hooks/post-checkout`, and all five were found.

## Pass 5 — findings: 0

Fresh sweep over the complete diff, with nothing new found.

- Every sentence the design and docs promise is present in the hook (probed, not
  read).
- Both `.gitignore` append blocks, and the prompt, name the same seven paths —
  pinned by tests proven to fail when any one of them drifts.
- `hooks/post-checkout` is the only writer of that block anywhere in the repo.
- The declared, confirmed-public, unconfirmed and unrecognised paths each have a
  test; the two directions of the override each have a mutation, both caught.
- `bash -n` clean on both shell files; `ruff check` and `ruff format --check`
  clean; `py_compile` sweep, artifacts gate and pillars gate clean.
- Full suite 1955 passed / 10 skipped, up 11 from 1944 — the 11 added here.
- Knowledge graph regenerated with `map_codebase.run_map(force=True)`, not by
  the query script, and `test_kg_drift_gate.py` passes on the result.

### One gate fails locally and is expected to pass in CI

`agentsmith gates run` reports 14 passed, 1 failed, 8 skipped. The failure is
`mutation_check.py (curated)`, and it is the harness refusing to run at all:
"refusing to run: these files have uncommitted changes and this harness rewrites
them — hooks/post-checkout". It is this working tree, not this code. The
`tenant_adopt` suite that covers these changes was run explicitly with
`--allow-dirty`: 22 mutations, all caught, including both added here. Re-checked
after committing.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — one decision site, grep-confirmed as the only
                                          one; the seven-path list exists twice inside the hook and
                                          a test now pins the two copies equal, since a shell hook
                                          with no helper functions has nowhere better to put it
Group 2 · Quality / safety            [x] checked — the value is matched against closed literals,
                                          never interpolated into a command, path or redirect; an
                                          unrecognised value fails safe into the build's own guard
Group 3 · Architecture / hygiene      [x] checked — no helper, no new file, no indirection: a case
                                          at the site that already decided this
Group 4 · Process                     [x] checked — five passes; Pass 2 found the new test passing
                                          on my own comment, Pass 4 found my own design record
                                          describing messages the code does not print
Group 5 · Intuitive UI                [x] checked — the interactive prompt now names all seven
                                          paths it would ignore; it asked consent for six
Group 6 · Signal integrity            [x] checked — "gh could not answer" and "gh answered PUBLIC"
                                          stopped being the same sentence; an unrecognised value is
                                          neither answer
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session; no credential read

Tests added/updated:      10 in scripts/test/test_hook_visibility_override.py (both override
                          directions, internal, the unrecognised value, confirmed-public wording,
                          both append blocks equal, the prompt naming what it ignores, build.sh
                          declaring its intent) and 2 in test_scratch_tenants.py (the guard fails
                          on a stale hook; a public fixture keeps its configs tracked). All proven
                          to fail against the pre-change tree before being trusted.
Mutation-checked:          tenant_adopt — 22 mutations, all caught, including the two added here:
                          the declaration losing to detection, and a misspelt value read as private
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json, regenerated with
                          map_codebase.run_map(force=True); test_kg_drift_gate.py passes
KG query:                 kg:e63069afecf6
Gates run locally:         full suite (1955 passed / 10 skipped), artifacts, pillars, KG drift,
                          ruff check + ruff format --check, bash -n on both shell files,
                          `agentsmith gates run` (14 passed / 8 skipped / 1 refusing on a dirty
                          tree, re-checked after commit)
Declared gaps:             (1) whether .agenticframework/tenant.yaml belongs in the ignore block is
                              undecided and recorded in docs/PRODUCT_BACKLOG.md; (2) the five public
                              fixtures publish generated IDE config content by design — verified to
                              carry no secret and no owner identity, but it is a stated policy
                              traded for fixture fidelity; (3) visibility detection is no longer
                              covered incidentally by where the fixtures live — replaced by direct
                              tests of the decision
```
