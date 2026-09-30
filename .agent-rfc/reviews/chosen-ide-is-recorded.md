# Review — chosen-ide-is-recorded

Design: `.agent-rfc/designs/chosen-ide-is-recorded.md`
Levers: `docs/review-levers.md`

## Pass 1 — findings: 4

1. **The design's own mechanism could not be built where the design put it.**
   Approach point 1 said argparse `choices=gate_ides.GENERATED`. The parser is
   constructed in `main()`, before `_framework_dir()` has resolved, so computing
   that set there would make `agentsmith --help` fail whenever the machine
   install has moved — a worse failure than a late rejection, and one that hits
   people who are not using the flag. Moved to validation inside `init_tenant`,
   which raises `ValueError`, already caught and printed as `agentsmith: …` with
   exit 2. The allow-list property P11 depends on is unchanged; only where it is
   applied moved. Design corrected before the code was written, not after.

2. **The per-root config cache would have discarded the choice in silence.**
   `tenant_config` caches per root, documented as safe because "the file cannot
   change under a running worker" — true for a worker, false for `tenant init`,
   which WRITES `tenant.yaml` at `runtime/cli.py` and then provisions in the same
   process. A cached read from before the file existed reports no declaration,
   `chosen_ides` falls back to every IDE, and `--ide cursor` would have written
   both configs while printing nothing wrong. Found by reading `tenant_config`
   rather than by a test — so a test and a mutation now pin it
   (`test_the_reader_sees_a_file_written_after_the_process_started`, and the
   `refresh=True` → cached mutation).

3. **My own completeness guard failed on my own code, and was right to.**
   `test_every_writer_routes_the_verified_set_through_the_reader` first read each
   `for` loop's iterator. `scripts/generate-ide-config.py` resolves the set into a
   local first, because it needs a fail-open `except` around the `runtime` import,
   so the guard saw three loops where four writers exist and its own count
   assertion fired — 3 != 4. Reframed per FILE rather than per loop. The finding
   is not the reframing: it is that the guard's vacuity check is what caught it,
   the same pattern as the vacuous-sweep work, and a guard written without one
   would have passed while watching three of four writers.

4. **I asserted what I wanted rather than the function's contract.** The new sync
   test asserted `".cursor/hooks.json" in written`. `written` lists only what
   MOVED — `test_a_sync_lists_only_what_moved` already says so, in the same file
   I was appending to. The property is about the files on disk. Corrected, with
   the reason in a comment so the next reader does not repeat it.

## Pass 2 — findings: 3

1. **`no-copy-paste` — I cloned the `sys.path` + `import gate_ides` dance.** The
   new `generated_ides()` helper repeated what `_provision_governance` already
   did five lines away, and returned only `GENERATED`, so the validation could
   not distinguish an unknown name from an unverified one (finding 2 below
   depended on this one). Replaced with a single `gate_ides_module(framework)`
   returning the module or None; both sites use it, the provisioning site lost
   its own `sys.path.insert`, and the net change is smaller than before the fix.

2. **`denied-vs-missing` — a typo and an unverified IDE got the same answer.**
   `--ide cursro` was told "no verified config schema, so no config can be
   written for it", which sends someone to look for a schema gap when they have
   mistyped `cursor`. The two are now different messages, and
   `test_a_typo_and_an_unverified_ide_get_different_answers` asserts they differ
   rather than asserting either string. `neutral` — a contract profile whose
   `config_path` is `""`, which would have written a config to the repository
   root — is refused by the same check, with its own test.

3. **`docs-match-behaviour` — the command reference omitted the flag.** Caught by
   `scripts/test/test_cli_install.py::test_every_reference_row_lists_the_flags_its_command_accepts`:
   `{'tenant init': ['--ide']}`. `docs/UserManual.md`'s row now lists `--ide NAME`
   and says what it records and which command reads it back. Worth recording that
   this is a mechanical check the repository already had, catching a docs gap I
   had not thought about — the reference table is generated against the real
   parser, so it cannot drift quietly.

## Pass 3 — findings: 1

1. **The design's scope did not cover a file the slice changed.** P4 committed the
   fallback to `scripts/mutation_check.py`, I added the suite there, and left the
   scope naming five source files without it. The stop gate caught it:
   "scripts/mutation_check.py: no complete active design note covers it." Scope
   widened.

   This is the second slice running in which I wrote a design's scope from the
   files I expected to touch rather than from the ones the design's own pillars
   commit me to — `.agent-rfc/reviews/fail-closed-has-a-reader.md` Pass 2 is the
   same mistake with `templates/agent-rules.yaml`. The pattern worth naming: a
   pillar answer that promises a change to a file is a scope entry, and P4 in
   particular almost always implies `scripts/mutation_check.py`.

## Pass 4 — findings: 0

Re-read every changed file against `docs/review-levers.md` after the Pass 2
fixes.

- `every-line-earns-its-place` — `chosen_ides` is nine statements; the four call
  sites changed by one expression each; `gate_ides_module` replaced a clone
  rather than adding a layer. Nothing left to cut without losing a stated reason.
- `single-source-of-truth` — `GENERATED` is back to meaning only "which config
  schemas are verified". Which IDEs a tenant gets is stated once, in
  `tenant.yaml`, and read through one function by all four writers.
- `declared-vs-enforced` — the reader ships in the same commit as the writer,
  `test_a_sync_keeps_the_tenants_declared_ide_choice` proves the command that
  would have reverted the choice honours it, and the source guard fails if a
  fifth writer appears. Verified the guard fails by reverting
  `runtime/sync.py` to the bare loop: it did.
- `guards-must-be-able-to-fail` — four mutations over `chosen_ides`, all caught.
- P15 / P16 — six unreadable-declaration shapes tested, every one falling back to
  every verified IDE rather than to none.
- `docs-match-behaviour` — reference row updated; the mechanical check passes.

## Sign-off

Group 1 · DRY & shared code — [x] checked — four writers cloned one loop over
  `GENERATED`; they now share `chosen_ides`, and Pass 2 finding 1 removed a second
  clone (the `sys.path` + import dance) rather than adding one.
Group 2 · Quality / safety — [x] checked — six unreadable-declaration shapes
  tested, every one falling back to every verified IDE rather than none; four
  mutations over the fallback, all caught; the guard verified to fail by reverting
  `runtime/sync.py` to a bare loop.
Group 3 · Architecture / hygiene — [x] checked — the reader sits in
  `runtime/config.py`, which already owns tenant.yaml and its precedence, and
  deliberately not beside `GENERATED`, to keep pyyaml off the edit-gate path that
  `.githooks/process-gate` runs on every edit.
Group 4 · Process — [x] checked — design written and gate-validated before any
  code; corrected twice mid-slice (Pass 1 finding 1, and the choices→validation
  move) with the design changed first, not retrofitted.
Group 5 · Intuitive UI — [x] gap — no screen or control; the surface is one CLI
  flag and two error messages. `denied-vs-missing` was applied to those messages
  (Pass 2 finding 2), which is the part of this group that reaches a person here.
Group 6 · Signal integrity — [x] checked — the fallback direction is stated,
  tested and mutation-pinned; an unreadable declaration reads as "every verified
  IDE", never "none", and `tenant_config` already logs why the file was ignored.
Group 7 · Auth & session integrity — [x] n/a — no credential, token, session or
  permission is read, written or checked; the change writes local config files
  during provisioning.

Tests added: 18 in `runtime/test/test_chosen_ides.py`, one behavioural test in
`scripts/test/test_framework_sync.py`, and the extended key-set invariant in
`runtime/test/test_cli.py`.
Mutation-checked: yes — `chosen_ides` suite in `scripts/mutation_check.py`, 4
mutations, all caught.
Fixtures re-pinned: none needed — the default path is unchanged, so every
`test_scratch_tenants.py` scenario and every existing fixture passes no `--ide`;
verified by the full suite rather than assumed.
Gates run: `pytest` (full suite), `ruff`, `process_gate.py` design + review
validation, `mutation_check.py chosen_ides`, and the CLI end-to-end for
`--ide cursor`, `--ide gemini` and the default.

Levers reviewed: `every-line-earns-its-place`, `parameterize-dont-clone`,
`no-copy-paste`, `declared-vs-enforced`, `single-source-of-truth`,
`implemented-not-invoked`, `guards-must-be-able-to-fail`, `denied-vs-missing`,
`validate-on-the-receiving-side`, `docs-match-behaviour`, `stale-data-is-labelled`,
`when-the-fallback-fails`, `search-before-writing`, `small-verified-slices`.

KG query: kg:133434474a70
