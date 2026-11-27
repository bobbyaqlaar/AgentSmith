# Review: invariants-not-instances

The design alone: Part A (five invariants, eight commits) and Part B (the framework carries them), written
2026-11-14 to 2026-11-15 against PR #117 at c7da273, and changed on 2026-11-23 to record the owner's answers to
every pending decision (the launch plan's decisions 3–15 and 6b; the design's "B7 — Owner decisions" and "What
changed on 2026-11-23"). No code changes in this commit; each build commit adds its own pass below.

Before this record: the design passed the gate's design check on 2026-11-15 (Part A and Part B, no errors). After
the 2026-11-23 edits, `active_designs` reports it with no errors on `main` `cdf04e1`.

## Pass 1 — findings: 6

The author's own read of the 2026-11-23 edits, against the owner's decisions and `docs/review-levers.md`.

1. **I4 still said "the tests passed"** on the whole tree, after decision 4 made the push stamp KG-impacted. I4 now
   states the impacted tests, the graphs being builds from nothing, and collection; its oracle and cases name the
   reachability walk and the full-suite triggers.
2. **Invariant 4's "Done means" named only the full-suite command.** Now both the full run (once, for A1's own
   commit) and the `--impacted` run, and the review quotes both last lines.
3. **B6's `Ran on: n/a` rule named B1 and B2 only.** With A6 and A7 moved before A1, they cannot produce the line
   either; the rule now names all four and says the "n/a only when none" rule arrives in A1.
4. **`agentsmith gate tree` did not forward `--impacted`.** The verb now passes the options given before `--`.
5. **`select: impacted` was undefined for tenants.** A tenant's graph is off on day one, so `impacted` with
   `knowledge_graph` off is a config problem, and no onboarding path writes it; AgentSmith's config sets it.
6. **A nested backtick** in the checklist placement sentence (B2) broke the Markdown; reworded.

## Pass 2 — findings: 26

An independent read-only reviewer (Opus 5.5 subagent; Fable 5.2 had no usage credits) against the owner's decisions,
`main` `cdf04e1`, #117's `c2583ff`, and `docs/review-levers.md` Groups 1–10. 12 major, 10 minor, 4 wording. Each
was checked against the code it cites before it was fixed; none was rejected.

1. The selection was always `full` here: records, `CHANGELOG.md` and the fixtures are not graph nodes. Fixed with one
   closed rule: a path that is not a node selects the tests reaching a file that names it (`readers`); a path nothing
   names selects everything. Risks now say that a gated push here still selects most of the suite.
2. `.test.ts` files would be appended to a pytest command. `--impacted` now needs a pytest command and appends only
   `test_*.py`/`*_test.py` under `testpaths`.
3. Equality vs "a full stamp is allowed" contradicted. The rule is now cover: `full`, or `tests` ⊇ HEAD's;
   `select_tests` takes a `treeish`; the stamp keeps `command` and `ran` apart.
4. The graphs rule refused every new tenant's first push. It now applies only where `select` is `impacted`, and the
   trace graph only where the repository tracks it.
5. The cited checks read the working tree and rewrite the fixture. One pure function, `graphs_current(root, treeish)`,
   builds in an export and writes nothing; its test kills "built from the working tree".
6. The plan's research dependency was not followed. A1 ships `select: full`; A1b, after the report, switches to
   `impacted` with the report's triggers and a bound approval.
7. Binding was in the prose only. `Change`, `_bound` and the `Approval:` route in `_config_kept` are now in the code
   shapes; every rule gets only the approvals bound to its change.
8. No generated cases for binding or the removal route. K2b, K8b, K8c, K8d added with their mutants.
9. B2 needed `gated_digest`, which A1 builds. B2 parses `Ran on:`; the digest comparison moves to A1.
10. `select` and `command` could weaken unheld. Both are held by `gate-modes-kept` (K12, K13); any command change
    needs a bound approval.
11. The caller side was contradicted by an older sentence and missed forwarded `inputs.*`. The sentence and docstring
    are corrected; `_call_inputs(workflow)` is passed; a forwarded-inputs family and mutant added.
12. ts-react scaffold branches left choices and could turn the tenant's CI red. Each branch is decided; no
    `package.json` stops `tenant init`; one test case per branch.
13. B7 rows and the body used different numbers. B7 gains a "Plan #" column.
14. Stale text after decision 4 (Approach 4, the invariant's (a), a lever line, Enforcement, `Config`, the refusal,
    the last-line format). All brought in line; one last-line format.
15. Which commit builds the collection check, the TypeScript trigger, `npx` fetching, `node_modules`. A1;
    whenever a `package.json` is tracked; `npx --no-install`; a link beside each `package.json`.
16. The Python scaffold test was ungated; the `go` line format and a missing Go. `test/test_scaffold.py`; `go 1.22`
    as a fixed floor; the relative path stated.
17. The CHANGELOG entry missed what newly fails. Four bullets and their claim lines added.
18. Decision 6 softened in Risks and the runner's message. Both now give the three refactors and the warning.
19. Sign-off groups said both "by number" and "by name". By number, as today; the checklist's "only Groups 1–7"
    sentence is replaced in B2.
20. ruff's S rules land first. Stated in "What changed": PR-2–4 build after ruff-s, with the `noqa` form.
21. "Acceptable is the owner's call" was an open question while the text said nothing was pending. It is B7 row 14,
    open, blocking only A1b.
22. Order rows missed what A1 and B3 now hold. Both rows updated; A1b added.
23. "Rebuilt/complete" was not mapped. One sentence maps them.
24. The design cited `2aee5f3`. It cites `c2583ff` and says what was read where.
25. The walk named the wrong function. "The transitive closure of `gate_kg._dependents`".
26. The caller-side message lacked the file prefix; the guard exemption was unlabelled. Both fixed.

Also found while fixing: `test_id_resolves` comes from A2 but B2 needs it; it is now written in B2.

## Pass 3 — findings: 27

A second independent read-only reviewer (Opus 5.5 subagent, the owner's choice of reviewer), with the design as Pass 2
left it plus the edits from the owner's test-time research report (track C, local `test-time-research.md`, delivered
2026-11-23). 6 major, 19 minor, 2 wording: 8 of Pass 2's fixes were partial, and 19 findings are new. All were
checked against the code they cite at `c2583ff` and `cdf04e1`; none was rejected.

Partial Pass 2 fixes, now complete: #4 (a B3 test that a new tenant's first push with a stamp is allowed); #5
(`export` takes a treeish; `graphs_current` uses `check_kg_fresh`'s comparison without its repair); #7 (the three
`gate_pillars` functions take `bind`; `declaration_weakenings` returns `Weakening(key, before, after, text)` records;
every weakening needs its own bound approval; the `Change` for allow entries and the compliance entry is named);
#10 (K12 and K13 in the modes test, with their mutants); #14 (one `Ran on:` format in the template; Done means
quotes it); #15 (the collection trigger and the `impacted`-needs-a-graph rule are in Invariant 4's `Config`); #17
(P16 lists everything that newly fails); #18 (A4 lists the runner's new failure message, word for word).

New: (1, major) under `select: full` an impacted stamp passed: now refused. (2, major) A1b's and the `-n auto`
change's approvals came before `gate-modes-kept` existed: A1b moves after A5, and `-n auto` is set by A1 only if the
owner approves first. (3, major) decision 4's graph check was limited to `impacted`: it now runs wherever
`knowledge_graph` is on (tenants stay off). (4, major) five routes to a red first push for `ts-react`: the test moves
to `lib/`, npm's default script counts as absent, `node --test` takes the file, a missing lock file stops init, jest
gets a plain `.js`; the test runs the template's type-check. (5) K12's base config was invalid and counts were
stale: fixed. (6) K13 compares the effective command. (7) the stamp records `shlex.join(COMMAND)`. (8) a deletion
is a full-suite trigger. (9) the graph source is named per route and `graphs_current` runs once. (10)
`check_review` gains `read`, `invariants` and `digest`. (11) Invariant 5 calls B2's resolver. (12) the guard
exemption narrowed decision 6b: dropped, and asked as B7 row 17. (13) a whole-file `Change` has `before =
"present"`. (14) `-n` without xdist is refused with a sentence; models are unloaded before the stamp. (15) the
per-commit feedback run has a command before and after A1. (16) the always-run list goes in the repository's
config, and the CI-report sentence is dropped (the stamp is never pushed). (17) row 14 folded into row 15 with the
report's figures. (18) wording of B7's header, the document header, "What changed" and row 1. (19) the report's
review-scoping item is declined here (it changes `gate_kg._GROUPS`) and goes to the backlog.

## Pass 4 — findings: 15

A third independent read-only reviewer (Opus 5.5 subagent). 3 major, 11 minor, 1 wording: four of Pass 3's fixes
were partial, eleven findings are new. All checked against c2583ff; none rejected.

Partial, now complete: N3 (major; decision 4's graph check was still `impacted`-only in a test row, Enforcement, the
CHANGELOG and Risks, and sat inside `tree_verified_problem`: now its own `graphs_current_problem` on both push routes
wherever `knowledge_graph` is on, whatever `verified_tree` is, with mutants for each gate); N8 (a deleted module is a
trigger case, with its mutant); N15 (`--print-selection` is in `main`'s docstring with its output per kind and a
test; labels fixed); N17 (Risks quote the report's 26 %).

New: (1, major) binding an `allow` or compliance entry was unsatisfiable, since the entry holds its own randomly drawn
approval id: `canon(entry)` drops the `approval` field; a deleted declaration has a key. (2) the other callers of the
three functions: `_declaration_change` takes `bind`, its summary keeps text and a list of ids, A5 deletes
`policy_transitions` and `range_transitions`, the existing tests are listed, the `ast` test allows the audit helper.
(3, major) the gate reads the first `## Sign-off`: the new lines are read from the last (`_last_signoff_section`, with a
two-sign-off test). (4) `check_change` carries `digest`; `stop_problems` passes None. (5) the trace graph holds pass
counts, so the per-commit list rebuilds the graphs after the review is written; records are ungated, so the stamp
stands. (6) `export` of a treeish uses `read-tree` + `checkout-index`, not `git archive`; `git add -A --force`. (7)
`always` (K14) and `knowledge_graph` (K15) are held. (8) the command rule applies only once the stamp is on. (9)
ts-react: the template's lock-file list, yarn and bun stopped by name, and the runner asked whether it collects the
scaffold test. (10) `ci_tree.py` and A6's builders import no networkx, with a test. (11) B6: A1b's placement is
labelled the design's, A1b, A5 and A8 have rows, the later `-n auto` change lands in PR-3, "B1, B2, A6 and A7".

## Pass 5 — findings: 12

A fourth independent read-only reviewer (Opus 5.5 subagent). 4 major, 8 minor: four of Pass 4's fixes were partial,
eight findings are new. Also folded in: #117's independent review (Opus 5.5, 2026-11-24, the owner's local
`review-4.1.0-117.md`), whose findings 117-R1 to R3 belong to this design. None rejected.

Partial, now complete: N15 (the per-commit feedback line runs `--co` when nothing is selected, never the whole suite;
`--print-selection`'s test is in the table); Pass 4's 1 (`canon` takes a dict, an `Allowance` passes `model_dump`, a
removed compliance entry is `None` before `canon`); Pass 4's 2 (the audit log's call moves into
`_log_declaration_change`, which joins `summary["approvals"]`); Pass 4's 3 (major: `Mutation-checked:` and
`KG query:` are read from the last sign-off too, one mutant per line).

New: (1, major) a per-commit `Ran on:` digest needed a `ci_tree.py` run per commit, which read as the stamp per
commit: it is named as the per-commit feedback run on that staged tree, separate from the push stamp, and the
tenant's cost is stated. (2, major) the scratch tenants could not push from B3: `build.sh` installs each app's
dependencies (ts-react before `tenant init`) and runs `agentsmith gate tree` before "Push". (3) the `KG query:` hash
was taken before the review was staged: the order is now write, rebuild, stage, hash, paste. (4) `knowledge_graph:
report` prints and allows; an unknown value is a config problem; `tree_verified_problem` takes `graphs_problem`. (5)
K15 newly refuses in existing tenants: listed in B3's row, P16, the CHANGELOG with its claim, and B5's count. (6)
init stops when the runner cannot be run. (7) the networkx test calls `graphs_current`, with its mutant. (8) every
`Change` value is `canon`'d, and a table names the key, before and after for each of the declaration's weakening
sites, held by an `ast` test.

From #117's review: 117-R1 (a merge's weakening skipped by the sweep and by head-only CI) is Invariant 2's new step 5,
with shapes S10 and S11; 117-R2 (an approval cited anywhere in a range) is closed by binding and stated there; 117-R3
(five coercion spellings still read as guards) is Invariant 1's allow-list, already in A3.

## Pass 6 — findings: 12

A fifth independent read-only reviewer (Opus 5.5 subagent). 2 major, 10 minor: four of Pass 5's fixes were partial,
eight findings are new. None rejected.

Partial, now complete: P5-1 (B6's per-commit text now defers to Part A's list; the stamp is per push, with the
hand-typed export standing in for B1–A7); P5-2 (major: each install's place in `build.sh` is named, ts-react before
`tenant init`; `python-uv` gets its own line; the job gains `setup-node` and `setup-go`); P5-6 (the no-`node_modules`
rule is scoped to vitest and jest and has its fixture case); P5-8 (the `ast` test covers the deleted-declaration
`return`; a data class's `before` is `"classified"`; `canon` takes any JSON value and an absent value is `None`).

New: (1, major) Done means 1 judged every merge in a known-base range, against decision 7: it now says merges are
judged one by one only by the sweep and head-only CI. (2) step 7 is labelled a code change, its trigger named, S10
gets assertion 4 and S11 assertion 1, "× 11 shapes", judged merges join the verified store. (3) a merge is judged
with the messages of `m^1..m`, so a sync merge carries its approval; binding keeps that from unlocking anything else.
(4) per-commit runs no longer overwrite the push stamp (`--no-stamp`), and a run without `--impacted` is labelled
`run <n>`. (5) the per-commit line stops when `--print-selection` fails, and deleted test files are not printed. (6)
the claim lines quote each bullet's opening words and carry nothing after the ids. (7) `review_summary` reads the
last `KG query:` too. (8) the collection check runs with COMMAND's interpreter, and pytest's defaults apply without
`testpaths`.

## Pass 7 — findings: 8

A sixth independent read-only reviewer (Opus 5.5 subagent), limited to Pass 6's fixes and defects that would make
the implementer guess or build something wrong. 2 major, 6 minor: three of Pass 6's fixes were partial, five
findings are new. None rejected. No owner decision contradicted.

Partial, now complete: P5-2 (installs are chosen by the app's files, not the matrix stack; the stamp runs after step
5 for every app; the job gains `setup-uv`, and Node 22 and the go app's `go.mod` version are named); Pass 6's 4 (the
portal per-commit line has `--no-stamp`); Pass 6's 8 (how the interpreter is found for a bare `pytest` command).

New: (1, major) assertion 4 could not pass where the merge deletes the config, because the sweep returns early when
the index has no config: the early return now applies only when no candidate's first parent has one either; K9 is
out of S10; the test initialises the store first. (2, major) the `run` label contradicted Done means 1 and left the
stamp's kind undefined: each run's kind and label are stated (`full`, `impacted`, `run <n>`, `collect 0`), only `full`
and `impacted` satisfy a push, and B2's parse accepts exactly those four. (3) the tenant verb forwards `--no-stamp`,
with a test case. (4) S12 (a sync merge of an approved weakening) kills the own-message mutant. (5) merges are listed
by `rev-list --merges`, initialisation records them, and a version-1 store is backfilled without judging old merges.

## Pass 8 — findings: 8

A seventh independent read-only reviewer (Opus 5.5 subagent), limited to Pass 7's fixes. 2 major, 6 minor: five of
Pass 7's fixes were partial. None rejected.

(1, major) `check_commits` refused an approved config removal (K8b) outright: the `config is None` branch now applies
decision 8's rule (the sweep through `transition_errors` with the commit's message; CI leaves it to the range's ends).
(2, major) the narrowed early return fell into code that needs a config: the sweep's order with no config is spelled
out (uninitialised store returns; no configured first parent records and returns; otherwise skip `rearm_hooks` and
`artifacts_report` and judge). (3) S12 applies only to K0, K2, K4, K8b; the test row reads K × {S10, S12}; Done means 2
states the exclusions. (4) merges have their own store file, which pre-A5 code never rewrites, and a 2000 bound. (5)
`Repairs:` does not clear a transition failure, with a case. (6) a stamp whose command equals the configured one is
`full`; node ids and selecting options make a `run`. (7) Done means 1 separates the push stamp's line from each
commit's `Ran on:`. (8) one predicate, `is_pytest_command`, defines a pytest command and its interpreter for all three
uses; any other command skips the Python check and says so.

## Pass 9 — findings: 7

An eighth independent read-only reviewer (Opus 5.5 subagent), limited to Pass 8's fixes. 2 major, 5 minor; none
rejected.

(1, major) a transition failure had no way to be cleared: `check_change` returns transition errors in their own list;
the sweep clears a failing commit when a descendant's `transition_errors(c^1, d, …)` is empty, and records it; the hook
neither asks for nor accepts `Repairs:` for one; a positive case is added. (2, major) CI's "judged by the range" had no
record verdict and contradicted the S9 test: CI records the removal `failed` unless the range cites a bound removal
approval (then `passed` with a note), matching decision 8's paragraph and S9; merges never enter `check_commits`. (3)
the sweep fails a config-less commit on any transition error, as the hook does. (4) the record-and-return step also
requires that no candidate has a config itself. (5) the merge store's cap is `VERIFIED_CAP`, at least 2000. (6)
`ci_tree.py` reads no config; the push gate treats a stamp whose command equals the configured one as `full`. (7) a
bare `pytest`'s interpreter is found through `realpath`, `python` else `python3`, else the check is skipped and says so.

## Pass 10 — findings: 8

A ninth independent read-only reviewer (Opus 5.5 subagent), limited to Pass 9's fixes. 2 major, 6 minor; none
rejected.

(1, major) the configured-command rule made every accepted stamp `full`, so `select` decided nothing: it now applies
to `run` stamps only; an `impacted` stamp keeps its kind. (2, major) assertion 1 could not pass for K8b in CI (the head
has no config, so CI is red by decision 8's own text): K8b is excepted from assertion 1 and its "allow" is proved by
the hook and the sweep, which now kill the trailer-route mutant. (3) CI's approval check calls `transition_errors` with
the range's `befores` and messages, passed into `check_commits`; no second matcher. (4) an approved removal is
`passed_with_notes`, with its note. (5) `check_change` returns `(errors, notes, transitions)`, and `Failures` carry the
transition errors in a fourth field. (6) a transition failure clears only when every branch tip containing it is
clean. (7) the hook's clearing call is stated, with the new message; a commit with both kinds of failure needs both
cleared. (8) the `realpath` rule applies to any first word named `pytest`, path or bare.

## Pass 11 — findings: 5

A tenth independent read-only reviewer (Opus 5.5 subagent), limited to Pass 10's fixes. 2 major, 3 minor; none
rejected.

(1, major) CI matched a phrase `_config_kept`'s error never contains, and the note's id had no source: CI now decides by
the approval itself (`_bound` and `_cited` over the range's messages, per `before`), and names the ids. (2, major) the
trailer-route mutant could not be killed, because the hook oracle runs the same mutated code: the S9 test gains a
second half with typed expected values (an approved removal: hook 0, sweep records it, CI `passed_with_notes`), which
kills it. (3) `commit_verdict` returns `transitions + errors`, code 1 when either is non-empty. (4) the sweep's
config-less failures go in the transition field, never cleared by `Repairs:`. (5) `check_commits`' signature and the
`range_=range_` call are written out.

## Pass 12 — findings: 1

An eleventh independent read-only reviewer (Opus 5.5 subagent), limited to Pass 11's fixes. 0 major, 1 minor; four
of Pass 11's five fixes complete.

(1) the S9 test's second half did not say what history it builds; read as S9 it kept K1, so the hook would refuse and
the test could not pass. It now builds its own history: S9's two commits without K1, the first deleting the config
with a bound, cited approval, the second restoring it.

## Pass 13 — findings: 2

A twelfth independent read-only reviewer (Opus 5.5 subagent), walking the S9 test's second half end to end. 0 major,
2 minor. The walk confirmed each stated expected value follows from the design's rules once the route is fixed.

(1) the restore's route was unstated, and through the hook it would be refused (a 100-line config is over the 20-line
`n/a` limit), so CI could never record the removal: the restore is committed with `--no-verify`, only the removal is
measured, and CI runs with `--json` and the removal's record is read. (2) the sweep's store was never initialised, so
"records the commit" passed whatever the code did: the test initialises the store before the removal.

## Pass 14 — findings: 1

A thirteenth independent read-only reviewer (Opus 5.5 subagent), walking the S9 second half again. Pass 13's two fixes
are in and every expected value follows. 0 major, 1 minor.

(1) step 3 did not say where `base`, `previous` and the transitions call go relative to the early return; read
literally, the lines between them dereference a `None` config on the removal commit. Step 3 now gives the order:
`problems` check, `base`, `previous`, `transitions`, the early return, then the config-dependent lines and
`check_change`. Checked against c2583ff `commit_verdict`.

## Pass 15 — findings: 2

A fourteenth independent read-only reviewer (Opus 5.5 subagent), checking step 3 against c2583ff's `commit_verdict`
line by line. Pass 14's order is fixed; S9's two halves follow. 0 major, 2 minor.

(1) the hook refused a declaration weakening in a repository with no config on either side, where CI says
`before_adoption` and the sweep records it: the early return now returns `(0, [], [])` when the parent has no config
either, as today. (2) the early return skipped the sweep and clearing block, so a config-less commit above an
unrepaired weakening passed the hook while the push refused it: with an adopted parent, the config-less path runs the
same block and returns its errors with `transitions`.

## Pass 16 — findings: 1

A fifteenth independent read-only reviewer (Opus 5.5 subagent), walking step 3's early return. Pass 15's two fixes
are in. 0 major, 1 minor.

(1) the not-adopted return tested only the commit's parent, so a commit above an earlier unapproved config removal
skipped the clearing block while the push refused it. On any config-less index the hook now runs the sweep and
clearing block (a never-adopted repository stops at the sweep's step 1, a retired one at step 2), and adds
`transitions` only when the parent has a config. Not changed, noted: a config-less refusal is not written to the
declaration's change log (`_log_declaration_change` needs the files list); the refusal itself is reported.

## The owner's revision of decision 4 (2026-11-26), recorded between Pass 16 and Pass 17

Not a review pass: the owner revised decision 4 after the test-time research (track C). Recorded in the design:
the push stamp runs the full suite in parallel (`python3 -m pytest -q -n auto`), as CI does; `pytest-xdist` and
`pytest-timeout` join `requirements.lock`, hash-pinned (B7 rows 15 and 16 answered). The selection at push is not
built (Invariant 4, "Not built"): `--impacted`, `verified_tree.select` and its cover rule, `verified_tree.always`, A1b,
K12 and K14. `select_tests` and `--print-selection` stay, for the per-commit feedback run only. Track C's other
recommendations are adopted: per-commit mutations are the hand mutants plus `--changed-since`; CI's curated shards run
`--changed-since <base>` on pull requests and in full on `main` and weekly; reviews scope their reading by the
closure and always cover lever Groups 1, 3 and 6. Pass 17 reviews this together with Pass 16's fix.

## Pass 17 — findings: 4

A sixteenth independent read-only reviewer (Opus 5.5 subagent), checking Pass 16's fix and the owner's revision of
decision 4. Pass 16's fix holds; the revision is faithful to PLAN.md's update and the research report. 0 major, 4 minor.

(1) the sweep's no-config step (2) did not say whether unrecorded merges count, so an unapproved removal made in a merge
escaped after one sweep: step (2) now covers the candidates and the unrecorded merges, and a failing merge stays
unrecorded. (2) "Not built" superseded a whole section that A1 still partly builds: it now names what A1 builds
(`FULL_SUITE_TRIGGERS`, `graphs_current`, `readers`, `select_tests` for `--print-selection`), `--print-selection`
reads the staged graph without `graphs_current`, the stamp's pass rule and `tree_verified_problem(root, config)` are
restated with no selection. (3) the `select` and `always` keys and K12, K14 survived in `Config`, B3's keys block, the
A1 and B6 rows and the modes test: removed; either key in a config is a config problem; the modes test is K11, K13,
K15. (4) rationale that the push selects tests (What changed, the build order, Enforcement, B7 row 1): reworded to the
graphs-current reason; A1b removed.

## Pass 18 — findings: 5

A seventeenth independent read-only reviewer (Opus 5.5 subagent), grepping the whole design for leftover selection
text and re-checking the no-config step. Pass 17's four fixes hold. 0 major, 5 minor.

(1) one `always` survived in `_gate_modes_kept`'s `Change` note: removed. (2) I4 still described a selection at push:
it now states the full test command, the graphs-current rule and collection. (3) a stale "most of ten minutes" cost:
removed. (4) the `-n` check had no place in `main`'s steps and no test: it is step 1b, its spellings are defined, and
`test_a_parallel_command_without_xdist_stops_before_running` holds it. (5) initialisation never said it writes
`verified-merges`, so an S10 merge could be recorded unjudged: initialisation writes both files, the backfill applies
only to a pre-A5 store, and runs before the unrecorded merges are computed. Also, from the reviewer's notes: the
curated shards' install step gains `pytest-timeout`, so the owner's timeout reaches them.

## Pass 19 — findings: 4

An eighteenth independent read-only reviewer (Opus 5.5 subagent), limited to Pass 18's fixes. They hold. 0 major, 4
minor.

(1) the added shard line was wrong: the shards already install `requirements.lock` with `--require-hashes` before the
mutation step (checked at 03175ea `self-test.yml`), so `pytest-timeout` reaches them from the lock; the text now says
so and adds no install. (2) the `-n` test lacked the `--numprocesses 2` spelling: added. (3) the merge backfill had no
test: `test_a_pre_a5_store_backfills_merges_without_judging`, with three mutants. (4) an unreadable `verified-merges` was
undefined: treated as missing, as `load_verified` treats an unreadable `verified`.

## Pass 20 — findings: 3

A nineteenth independent read-only reviewer (Opus 5.5 subagent), limited to Pass 19's fixes; three of four complete.
0 major, 3 minor, all on the backfill test.

(1) the test did not cover the backfill in the no-config step (2): a case with the config deleted at the index is
added, with the mutant "the backfill only in the config path". (2) the mutant "initialisation not writing
`verified-merges`" could not be killed by a test that starts from a pre-A5 store: it moves to the sweep-agrees test,
where S10 × K1 kills it. (3) the setup was underspecified: `verified` as pre-A5 initialisation writes it, the first
merge S4 × K1, the later one S4 × K7 (a value still present), and the test has its own row in Invariant 2's table.

## Pass 21 — findings: 2

A twentieth independent read-only reviewer (Opus 5.5 subagent), walking the backfill test row end to end. The row
holds otherwise. 0 major, 2 minor.

(1) the setup's S4 × K1 merge would be refused by the armed hook, so the test could not be set up: it is an S10 × K1
merge (committed with `--no-verify`), and each case uses a fresh repository. (2) the moved mutant's kill depended on no
sweep running between initialisation and the merge, which the pre-commit hook's own sweep breaks: the kill is now an
assertion right after the initialising sweep that `verified-merges` exists and lists `[]`.

## Pass 22 — findings: 1

A twenty-first independent read-only reviewer (Opus 5.5 subagent), walking the two test rows Pass 21 changed. Both
fixes hold. 0 major, 1 minor.

(1) S12 could become a fast-forward with no merge commit, so the "own message only" mutant would survive: S12's side
branch now has a commit of its own and the merge is made with `--no-ff`, a real two-parent merge.

## Pass 23 — findings: 0

A twenty-second independent read-only reviewer (Opus 5.5 subagent), walking S12 end to end for K0, K2, K4 and K8b
against step 7 and the store rules at `03175ea`. Pass 22's fix holds; each stated outcome follows, and K2 and K8b kill
the "own message only" mutant. Nothing needs a change.

How the passes were scoped: Passes 2–5 read the whole design; Pass 18 searched the whole design for text left over
from the dropped test selection; the other passes from Pass 6 on were limited to what the previous pass's fixes
touched, as the owner chose on 2026-11-24 ("keep running passes"). The reports are in the owner's local notes
(`track-a/a0-design-review-pass<N>.md`).

## Pass 24 — findings: 0

Rebuild on `main` (2026-11-27). #117 merged by rebase as `d2280a9`, whose tree is identical to `03175ea`, the
commit the passes above read. The design and this record were carried over byte for byte (`git cherry-pick
--no-commit`, then compared with the pre-rebuild commit). Only the graphs changed: `knowledge_graph.json` was
rebuilt rather than merged, and `trace_graph.json` (now on `main`) gains the design and this review as nodes. The
staged set gained the trace graph, so the sign-off's KG query is re-read with `agentsmith gate kg impact --staged`.
Nothing in the design needs a change.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one transition function for hook, CI and sweep; one approval matcher (`_bound`, `_cited`); one test-id resolver (`test_id_resolves`, B2); one pytest-command predicate.
Group 2 · Quality / safety — [x] checked — every rule fails closed where it cannot read its input (shallow base, unknown `knowledge_graph` value, unreadable stores re-initialise as today).
Group 3 · Architecture / hygiene — [x] checked — changes stay in the existing gate modules; test selection at push dropped rather than built unused.
Group 4 · Process — [x] checked — design only; every owner decision recorded in B7 with where it is written; row 17 left open for the owner.
Group 5 · Intuitive UI — [x] n/a — no screen; the portal lockout (A8) is timing only.
Group 6 · Signal integrity — [x] checked — a stamp names its tree's digest; collection is proved; "could not run" is a note, never a pass.
Group 7 · Auth & session integrity — [x] checked — approvals are fresh and bound to what they unlock (decisions 5, 8); the lockout audit no longer leaks which names exist (A8).
Group 8 · Security engineering — [x] checked — SEC-CIAGENT-001's evaluator answers only what it models; the caller side reports event text to any reusable workflow (6b).
Group 9 · Regulation & compliance — [x] checked — the compliance declaration's weakenings each need a bound approval; the change log keeps recording them.
Group 10 · Code optimisation — [x] checked — the stamp runs the full suite in parallel (owner, 2026-11-26), measured at 211–220 s here; graphs rebuild in 1–3 s.

Defect kind and siblings checked: the four classes in the design's Problem table; siblings listed per invariant (hook, CI, sweep; Python and portal tests).
Tests added: none in this commit (design only); each build commit names its tests and mutants.
Reproduced before fixing: n/a (design only).
Mutation-checked: no — design only; each build commit lists its hand mutants and runs `mutation_check.py --changed-since`.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json` and `.agent-rfc/fixtures/trace_graph.json` (the new design and this review are nodes), rebuilt on `main` at `d2280a9`.
Performance measured: n/a (design only); the research report's figures are quoted where used.
Security gates: n/a in this commit.
Compliance evidence: n/a.
Manual-only levers: `independent-oracle` and `generated-not-reported`, checked by reading each invariant's oracle and case families.
Gates run: the gate's design check (`active_designs`: no errors); `verify_system.py --check-kg`; the commit hook when committed; `process_gate.py ci --base origin/main --head HEAD` after it.

Levers reviewed: `fix-the-class-not-the-case`, `independent-oracle`, `generated-not-reported`, `judge-the-ends`, `rebuild-dont-add`, `each-entry-mutated`, `collected-and-counted`, `claim-names-its-test`, `grep-for-siblings`, `gate-integrity`, `identity-not-label`, `outage-is-not-a-finding`

KG query: kg:4bdac5512815
