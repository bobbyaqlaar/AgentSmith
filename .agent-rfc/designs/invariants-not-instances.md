---
status: active
scope:
  - scripts/security/gha_expression.py
  - scripts/security/runners/agent_workflow.py
  - scripts/test/test_gha_expression.py
  - scripts/test/test_gha_expression_oracle.py
  - scripts/test/gha_oracle/**
  - scripts/test/test_agent_workflow_injection.py
  - contract/security/v1/cases.json
  - scripts/test/test_security_contract.py
  - scripts/process_gate.py
  - scripts/gate_pillars.py
  - scripts/gate_history.py
  - scripts/test/test_range_verdict.py
  - scripts/test/test_declaration_ratchet.py
  - scripts/test/test_process_gate.py
  - scripts/map_codebase.py
  - scripts/local_knowledge_graph.py
  - scripts/gate_kg.py
  - scripts/verify_system.py
  - scripts/test/test_kg_rebuild.py
  - scripts/test/test_knowledge_graph.py
  - scripts/test/test_kg_drift_gate.py
  - scripts/test/test_gate_kg.py
  - scripts/test/test_trace_graph.py
  - .agent-rfc/fixtures/knowledge_graph.json
  - .agent-rfc/fixtures/trace_graph.json
  - scripts/ci_tree.py
  - scripts/test/test_ci_tree.py
  - scripts/test/test_collection.py
  - scripts/mutation_check.py
  - scripts/test/test_mutation_check_lists.py
  - scripts/test/test_claims.py
  - portal/test/scripts.test.ts
  - portal/proxy.ts
  - portal/lib/signInPolicy.ts
  - portal/test/signInPolicy.test.ts
  - portal/test/proxy.test.ts
  - .github/workflows/self-test.yml
  - .agenticframework/process-gates.json
  - CHANGELOG.md
  - THIRD_PARTY_LICENSES.md
  - docs/process-gates.md
  - docs/validation-checklist.md
  - docs/UserManual.md
  - docs/PRODUCT_BACKLOG.md
  - templates/agent-rules.yaml
  - templates/governance.json
  - scripts/gate_models.py
  - scripts/collection_check.py
  - scripts/test/**
  - agentsmith/machine/governance.py
  - agentsmith/architectures.py
  - agentsmith/cli.py
  - agentsmith/adopt.py
  - agentsmith/sync.py
  - agentsmith/test/**
  - docs/review-levers.md
  - docs/review-lever-notes.md
  - docs/design-review-checklist.md
  - docs/scratch-tenants.md
  - .github/scratch-tenants/**
  - .github/workflows/scratch-tenants.yml
  - contract/gate/v3/protocol.md
---
# Five invariants, each with an oracle and a gate, so a fix cannot be a fix of the instance

From the fourth review pass on release 4.1.0 (the owner's local `review-4.1.0-pass4.md`, findings named P4-R1 to
P4-R13 below), at the owner's request (2026-11-14). Written against PR #117 at c7da273; the 2026-11-23 additions were read at `main` `cdf04e1` and #117's head `c2583ff`. Every file, function and
helper named here was read at that commit; the package named in `## Dependencies` was installed and run. The owner
answered the pending decisions on 2026-11-23 and 2026-11-26, but one (B7 row 17); they are recorded in "B7 — Owner decisions" and in the sections they
change, and "What changed on 2026-11-23" below lists every change they made to this document.

**How to read this document if you are the implementer.** Do the commits in "Order of work" in order. For each one,
make exactly the code changes its section lists, add exactly the tests it names, run the commands it lists, and stop.
Where this document makes a decision, do not make a different one. Where you believe it is wrong, stop and ask the
owner; do not improvise. A section is done when its "Done means" list is true, not when the example from the review
passes.

## What changed on 2026-11-23

The owner's answers (B7) and two facts about the tree since c7da273. Each commit's implementer reads this first.

- **The tree moved.** #117 gained `2aee5f3`, now `c2583ff` after #117 was rebuilt on `cdf04e1` (`.agent-rfc/designs/pass4-majors.md`): `success()` is unknown, `ci`
  compares the merge base with the head, and the graph rebuilds import edges each run. Those are instance fixes of
  P4-R1, P4-R4 and P4-R8. A3, A5 and A6 replace them with the general forms written here; each of those commits
  starts by reading `c2583ff`'s diff and lists, in its review record, which of its lines it keeps, replaces or
  deletes. #117 was then rebuilt on `main` after #119 (`143ac82`, `cdf04e1`). `143ac82` added review lever Groups
  8–10 (security engineering, regulation and compliance, code optimisation), 50 levers, and Groups 8–10 in the
  sign-off block of `docs/validation-checklist.md`. So this design's lever and sign-off group is **Group 11**, not 8.
- **Order (the plan).** The push refuses committed graphs that are not builds from nothing (A6), and "complete"
  means A7's `RUNS` edges, so the graph must be right first: **A6 and A7 come before A1.** The build order is B1, B2, A6, A7, A1, A2, A3, A4, the
  `approval-binding` design's commit, A5, A8, B3, B4 ("B6 — Order of
  work"). The commits keep their names.
- **ruff's S rules land first** (decision 24). `feat/ruff-s-rules` lands before PR-2, so PR-2 to PR-4 are built on
  `main` after it, and each new subprocess call (`scripts/ci_tree.py`, `scripts/collection_check.py`, the git calls
  of `select_tests` and `graphs_current`) carries the repository's `# noqa: S603, S607` form with its reason.
- **The stamp (decision 4, revised by the owner on 2026-11-26).** The full suite, in parallel (`-n auto`), at push
  and in CI; no test selection at push, and no A1b (Invariant 4, "Not built"). `pytest-xdist` and `pytest-timeout`
  join `requirements.lock`. Wherever the knowledge graph is on, the committed knowledge
  graph and trace graph must be builds from nothing of the pushed tree, or the push is refused (Invariant 4).
- **Approvals are fresh and bound (decisions 5 and 8).** An approval counts only when it is new in the commit or
  range **and** bound to what it unlocks. Binding changes `agentsmith approve` and is its own design,
  `.agent-rfc/designs/approval-binding.md`, built before A5. Removing the gate config takes such an approval, cited
  by an `Approval:` trailer (Invariant 2).
- **The caller side (decision 6b).** A job that passes an untrusted `github.event.*` field through `with:` to any
  reusable workflow is reported, local or in another repository (A4).
- **Collection for TypeScript too (decision 13).** Python and TypeScript are checked in 4.1.0; Go gets the lever.
- **Groups 8–10 are checked (decision 15)** by the same mechanism and key as Group 11 (B2).
- **Tenants (decisions 9, 10, 12).** `tenant init` declares `CHANGELOG.md` and writes a starter; `tenant adopt`
  writes `report`; every stack's scaffold ships a passing test (B3).
- **Release (decision 3).** All of Part A and Part B, in 4.1.0.

## Problem

Four passes found the same defect classes. Each fix and its test were shaped by the example in the report, so the
next spelling, route or case got through:

| Class | Pass 1–2 | Pass 3 | Pass 4, still open | Why the last fix missed it |
|---|---|---|---|---|
| A guard an outsider passes is judged restrictive | R9, P2-R5 | P3-R1 | P4-R1 `!success()`, P4-R2 six coercions, P4-R3 reusable workflows | the evaluator returns a definite value for operations it does not model exactly; its tests are the reported spellings |
| CI does not judge what the hook judges | P2-R12 | P3-R3 | P4-R4 merge commits, P4-R5 config removed | CI's verdict is built from commits, so a change no listed commit carries is never seen; the test is the reported route |
| The graph says what the code does not, and its check agrees | — | P3-R17 | P4-R8 94 stale edges, P4-R11 file times | edges are added and never replaced; the check compares the graph with the same incremental path |
| A local green that CI does not reproduce | R23 | — | P4-R10 a test needing a tag | tests ran in a full local clone, on files not yet tracked, or after `process.exit` |
| A claim nothing proves | — | — | P4-R13 three CHANGELOG statements; "the untrusted roles" mutation-checked when one of six was | the gate checks that a record exists, not that a claim in it names a test |

The previous implementer was given rules ("fix the cause") and still fixed instances. Rules that depend on the
implementer's judgment do not hold. This design replaces each rule with (1) an invariant a test can check, (2) an
oracle that is independent of the fix, with its cases generated, and (3) a gate that fails when the invariant is
skipped.

## Approach

Five invariants. Each has its own section below with code shapes, the oracle, named tests, enforcement and done-means.

1. **Unknown unless certain.** The expression evaluator gives a definite value only for operations in a closed table;
   the `else` branch of every dispatch returns `UNKNOWN`. Oracle: GitHub's own evaluator, `@actions/expressions`, run
   over generated expressions.
2. **Judge the whole range.** Every before-and-after rule is one function of (state before, state after, approvals
   recorded between them, messages). The hook calls it with (parent, index); CI calls it with (merge base, head).
   Oracle: the real hook on the squashed change, over generated commit shapes.
3. **Rebuild, don't add.** The graph is assembled from nothing on every build; only a file's parse is cached. Oracle:
   an independent extraction, over generated edit sequences.
4. **Verify where it will run.** A tool runs the tests in a one-commit, tagless copy of the staged tree (the
   suite, in parallel, with the graphs proved current) and the push hook requires its stamp for the tree being pushed; CI runs the full suite. Tests prove every
   test is collected, in Python and TypeScript.
5. **Claims cite their test.** Each CHANGELOG bullet a commit adds needs a line in the review record naming a test
   the gate resolves; each closed list is mutated one entry at a time by the harness.

The minors: P4-R6 (timing) and P4-R7 (document the lockout) are separate small items; P4-R11 falls under
invariant 3; P4-R12 under invariants 1, 3 and 5; P4-R13 under invariant 5; P4-R9 under invariant 3.

## Invariants

- I1 — a definite answer from the guard evaluator is GitHub's answer for every completion of what is unbound
  - oracle: `@actions/expressions`, GitHub's own evaluator in another language; it shares no code with `scripts/security/gha_expression.py`
  - cases: generated families F1 to F6 (literals, contexts, operators, calls, guard shapes, spelling), each with every completion
  - enforcement: the required check that runs `scripts/test/`, where the oracle test fails rather than skips
- I2 — CI's verdict on a before-and-after rule depends only on the state before, the state after and the messages between
  - oracle: the real commit hook on the squashed change, a different entry point on a different history
  - cases: generated table of content changes K0–K11, K13 and K15, with lettered cases (K2b, K8b–d) by commit shapes S1 to S12
  - enforcement: the same required check, and an `ast` test that keeps transition rules out of `check_change`
- I3 — the knowledge graph after any edit sequence equals a build from nothing
  - oracle: an extraction written in the test, and a build in a fresh copy with no graph and no cache
  - cases: generated edit sequences from steps E1 to E12 over ten seeds
  - enforcement: the `--check-kg` step, comparing committed bytes with a cache-less build
- I4 — the full test command passed on a one-commit, tagless copy of the tree being pushed; the committed graphs are builds from nothing of that tree; and every test is collected
  - oracle: git's export of the index; an `ast` scan set against pytest's collector, and the TypeScript runner's own file list; for the per-commit feedback selection, a reachability walk written in the test over generated edges
  - cases: generated repositories with staged, unstaged and untracked files, duplicate names, files outside the test paths, import chains of length 1 to 4, and one case per full-suite trigger
  - enforcement: the push hook's graphs-current and stamp rules on both push routes, the collection test in a required check, and CI's full suite
- I5 — every changelog bullet a commit adds names a test that exists, and every closed list has one mutant per entry
  - oracle: the commit's own diff and file tree for claims; the list's own literal for mutants
  - cases: generated from each commit's added lines and from each list's entries at run time
  - enforcement: the claims rule on hook, CI and sweep, and the required curated-mutations check

## Pillars

- P1 applies — the fourth pass's findings and the owner's five invariants are the requirement; `.agent-rfc/designs/pass3-root-causes.md` is the design this one corrects.
- P2 applies — changes in place in `scripts/security/gha_expression.py`, `scripts/process_gate.py` and `scripts/map_codebase.py`; one test-only package, listed under Dependencies.
- P3 applies — the range verdict is decided inside the existing `agent.gate` spans of `scripts/process_gate.py`; no new span name.
- P4 applies — differential, shape and edit-sequence tests beside `scripts/test/test_gha_expression.py`, `scripts/test/test_declaration_ratchet.py` and `scripts/test/test_knowledge_graph.py`; per-entry mutants in `scripts/mutation_check.py`.
- P7 applies — the oracle harness is an ES module run by Node 22, as `portal/package.json` already requires; Python stays on Pydantic models in `scripts/gate_models.py`.
- P8 n/a — no telemetry wire changes.
- P9 n/a — no orchestration.
- P10 n/a — no model routing.
- P11 applies — `scripts/security/runners/agent_workflow.py`: a guard counts only when it is certainly false for every outsider; a reusable workflow's string inputs are untrusted text.
- P12 applies — `portal/proxy.ts`: the audit write no longer delays the answer, so timing does not say which names have accounts.
- P13 applies — `scripts/process_gate.py`: one transition function for the hook and CI; a removed gate config is refused; no gate is turned down.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is rebuilt from nothing, loses its clock values, and is compared with a from-nothing build.
- P15 applies — `scripts/security/gha_expression.py`: unknown is the default of every dispatch, never a listed case.
- P16 applies — `CHANGELOG.md` says what newly fails and how to recover: guards that used `format`, `toJSON` or `success()` no longer count; an old approval, or one recorded for another change, no longer unlocks a weakening; removing the gate config, or turning `knowledge_graph` or another held key down, needs a bound approval; a weakening inside a merge commit is judged too; event text passed to any reusable workflow is reported; a push with a stale graph is refused where the graph is on; a TypeScript test file its runner skips stops the run.

## Deviations

none

## Dependencies

- `.agent-rfc/designs/approval-binding.md` (owner, 2026-11-23, decision 5): A5 and `gate-modes-kept` call its
  `approval_unlocks`; the gate-config removal route (decision 8) uses it. It is built in PR-3 before A5.

Part B adds no package. Part A adds one package, test-only, never installed in a tenant, the portal image or the Python environment:

- `@actions/expressions` 0.3.61 — MIT — published by GitHub from `actions/languageservices`. Transitive packages:
  none (`npm ls --all` in a fresh install lists this package alone; its `package.json` has no `dependencies`).
  Needs Node 20 or later; the portal's CI job already uses Node 22.

It is declared in a new `scripts/test/gha_oracle/package.json` with its own `package-lock.json`, not in
`portal/package.json`: the portal's lock file is what its production image installs, and a test oracle for a Python
security control is not a portal dependency. No Python package is added. `THIRD_PARTY_LICENSES.md` gains one line for it
(name, version, MIT, "test-only: the SEC-CIAGENT-001 oracle").

## Levers

- `guards-must-be-able-to-fail` — invariant 1: a guard counts only where the evaluator is certain; the differential test fails for any definite answer GitHub's evaluator contradicts.
- `consistent-auth-gates` — invariant 2: the hook and CI call one transition function, so no route has its own rule.
- `one-verdict` — invariant 2: the verdict on a range is computed once from its two ends, never re-derived per commit.
- `gate-integrity` — invariant 3: the graph check compares with a from-nothing build, so it can fail; invariant 5: the claims check resolves each test it is given.
- `fixture-truth` — invariant 3: the committed graph holds no clock value, so two correct builds are byte-equal.
- `environment-parity` — invariant 4: the tests run in a one-commit, tagless copy of the staged tree before the push, as CI's behaviour job checks out.
- `run-the-gates-ci-lists` — invariant 4: the stamp the push hook requires is of the tree being pushed, not of the working tree.
- `test-that-cannot-fail` — invariants 4 and 5: every test function is proved collected; every closed list is mutated entry by entry.
- `docs-match-behaviour` — invariant 5: a CHANGELOG bullet names its test; the three wrong statements are corrected.
- `grep-for-siblings` — each invariant names every sibling route it found (sweep, hook, CI; hook and `kg check`; Python and portal tests).
- `minimal-host-dependency` — the oracle needs Node only in the test job; the control itself gains no dependency.

## Anti-patterns: what a fix must NOT do

Each line is something a previous pass did. If your change matches one, it is wrong, whatever the tests say.

1. **Do not add a spelling to a list of refused spellings.** (R9 refused `||` and `!`; P2-R5 matched one term; P4-R1
   would be "make `success()` unknown".) Remove the reason the spelling worked: here, delete every branch that
   returns a definite value for something not in the allow-list table.
2. **Do not write a deny-list.** Never `if name in (things that are unknown): return UNKNOWN`. Write
   `handler = TABLE.get(name); if handler is None: return UNKNOWN`.
3. **Do not fix one route.** (P2-R12 fixed `check_change`; CI reached it another way. P3-R3 fixed ungated commits;
   merges were still skipped.) Before changing a rule, list every caller with `grep -n "<function>(" scripts/*.py` and
   write the list in the review record.
4. **Do not build the test from the reported example.** A test that contains the string from the review proves that
   string. Each invariant below names a generator; the reported example must be produced by the generator, not typed
   in. Reported examples may be added as a regression table only after the generated test exists and catches them.
5. **Do not derive a test's expected values from the code under test.** (A role test parametrised over
   `_UNTRUSTED_ROLES` loses the case when the role is deleted.) Expected values come from the oracle or from a list
   written in the test file.
6. **Do not compare a result with the path that produced it.** (`--check-kg` compared the graph with what the same
   builder adds.)
7. **Do not make CI fetch more so a test passes** (tags, depth). The test builds what it needs.
8. **Do not claim without a test.** No CHANGELOG bullet, review line or count ("23 mutants", "1,287 edges") without
   the test or command that produced it, run on the staged tree.
9. **Do not say a list was checked unless each entry was.** "The untrusted roles" means six mutants, one per role.
10. **Do not append to a test file below its exit.** A portal test after `process.exit` never runs.
11. **Do not run tests before `git add`.** An untracked test file passes locally and does not exist in CI.

## Invariant 1 — Unknown unless certain

### The invariant

For every expression `E` and every partial binding `B` of context paths: if `gha_expression` evaluates `E` under `B`
to a definite truth value `v`, then for **every** completion of the unbound contexts and **every** value of the
status functions, GitHub's evaluator gives truth value `v` and raises no error. Whenever that cannot be shown, the
result is `UNKNOWN`. `UNKNOWN` is what the code returns when nothing matched: it is the fall-through, never a case.

Second half, so the evaluator cannot satisfy the first by always answering `UNKNOWN`: every guard in the
`MUST_DECIDE` table (below) evaluates to definitely false for an outsider.

### Defects it closes

P4-R1, P4-R2 (all six, and the `1_0` direction), P4-R3, and P4-R12's survivors on this file: the three role
mutants, the computed index, `fromJSON` of bad text.

### Code changes — `scripts/security/gha_expression.py`

Keep the tokenizer, `_Parser`, `_truthy`, the three-valued `&&`, `||`, `!` in `_eval`, `_path`, and `may_be_true`.
Replace `_number`, `_equal`, `_compare`, `_text`, `_call` and the literal handling as follows. Delete `_number` and
`_text` entirely: no caller may remain (`grep -n "_number\|_text" scripts/security/gha_expression.py` prints
nothing).

**Value domain.** A definite value is exactly one of: `str`, `bool`, `None`, a finite `float`, or `Array` (below).
Nothing else.

```python
class Array(tuple):
    """A flat array of primitives from fromJSON. Usable only as contains()'s first argument."""

def _primitive(value: Any) -> bool:
    return value is None or isinstance(value, (str, bool)) or (isinstance(value, float) and math.isfinite(value))
```

**Literals** (`_Parser.postfix`). A number token gives a definite value only if it matches
`^-?\d+(?:\.\d+)?$`. A hex literal or one with an exponent becomes the node `("unknown",)`, which `_eval` returns
`UNKNOWN` for. Strings, `true`, `false`, `null` are unchanged.

**The `if:` text** (`parse`). Decide on the text exactly as given, before any `strip()`:

```python
def parse(condition: str) -> tuple:
    if "${{" not in condition:
        return _Parser(condition).parse()            # GitHub wraps a bare `if:` itself
    if condition.startswith("${{") and condition.endswith("}}") and condition.count("${{") == 1:
        return _Parser(condition[3:-2]).parse()
    return ("unknown",)                              # text or whitespace around ${{ }}: not modelled
```

This changes one current behaviour on purpose: text around an expression used to be the literal `True`; it is now
`UNKNOWN`. `may_be_true` treats `UNKNOWN` as "may be true", so the control's verdict for such an `if:` is unchanged
(the field is reported). A trailing newline or space is "around" (decision: not modelled, so unknown).

**Equality and comparison.** The only shapes that give a definite value:

```python
def _equal(a: Any, b: Any) -> Any:
    if not (_primitive(a) and _primitive(b)):
        return UNKNOWN                                # UNKNOWN itself, Array, anything else
    if isinstance(a, str) and isinstance(b, str):
        return a.lower() == b.lower()
    if type(a) is type(b):                            # bool/bool, float/float, None/None
        return a == b
    return UNKNOWN                                    # mixed types: GitHub coerces; not modelled

def _compare(op: str, a: Any, b: Any) -> Any:
    if type(a) is float and type(b) is float and math.isfinite(a) and math.isfinite(b):
        return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]
    return UNKNOWN
```

Decision: **all** mixed-type comparisons are `UNKNOWN`, including `'1' == 1` and `null == 0`. There is no
string-to-number coercion anywhere in this file; do not add one.

**Calls.** One table. Each handler checks its operand types first and returns `UNKNOWN` for any shape it does not
list. Names are already lower-cased by the parser.

```python
def _always(args: list) -> Any:
    return True if not args else UNKNOWN

def _contains(args: list) -> Any:
    if len(args) != 2:
        return UNKNOWN
    haystack, needle = args
    if isinstance(haystack, str) and isinstance(needle, str):
        return needle.lower() in haystack.lower()
    if isinstance(haystack, Array) and _primitive(needle):
        results = [_equal(item, needle) for item in haystack]
        if any(r is True for r in results):
            return True
        return UNKNOWN if any(r is UNKNOWN for r in results) else False
    return UNKNOWN

def _starts(args: list) -> Any:        # _ends is the same with endswith
    if len(args) == 2 and isinstance(args[0], str) and isinstance(args[1], str):
        return args[0].lower().startswith(args[1].lower())
    return UNKNOWN

def _fromjson(args: list) -> Any:
    if len(args) != 1 or not isinstance(args[0], str):
        return UNKNOWN
    try:
        value = json.loads(args[0], parse_constant=_reject)     # NaN, Infinity raise ValueError
    except ValueError:
        return UNKNOWN                                          # GitHub raises; nothing is certain
    return _from_json_value(value)

def _from_json_value(value: Any) -> Any:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else UNKNOWN
    if isinstance(value, list):
        items = [_from_json_value(item) for item in value]
        return Array(items) if all(_primitive(item) for item in items) else UNKNOWN
    return UNKNOWN                                              # objects, nested arrays

_EXACT_CALLS: dict[str, Callable[[list], Any]] = {
    "always": _always,
    "contains": _contains,
    "startswith": _starts,
    "endswith": _ends,
    "fromjson": _fromjson,
}

def _call(name: str, args: list) -> Any:
    handler = _EXACT_CALLS.get(name)
    if handler is None or any(arg is UNKNOWN for arg in args):
        return UNKNOWN
    return handler(args)
```

`success`, `failure`, `cancelled`, `hashFiles`, `format`, `toJSON`, `join`, `case` and any name GitHub adds later
are not in the table and so are `UNKNOWN`. Do not add a line for any of them. `format` and `toJSON` are removed on
purpose: their exact rules (brace escapes, number formatting) are what P4-R2 found wrong, no legitimate guard in
`MUST_DECIDE` needs them, and a guard that uses them is now reported (stated in the CHANGELOG as newly failing).

**`_eval`.** Three changes only:
- add `if kind == "unknown": return UNKNOWN` as the first branch;
- `_truthy` returns `UNKNOWN` for an `Array` (decision: an array's truth is not modelled) and otherwise, for a
  primitive, `value not in (False, 0.0, "", None)`; delete its NaN branch (a NaN can no longer be a value);
- the last line of `_eval` (comparison) calls the new `_compare`, and `==`/`!=` the new `_equal`.

The existing dispatch on `kind` ends in the comparison branch. Change the end to be explicit and closed:

```python
    if kind in ("<", "<=", ">", ">="):
        return _compare(kind, _eval(node[1], bindings), _eval(node[2], bindings))
    return UNKNOWN                                    # any node kind not listed above
```

### Code changes — `scripts/security/runners/agent_workflow.py` (P4-R3)

Decision: in a workflow whose `on:` contains `workflow_call`, an input declared with `type: string`, or with no
`type`, is untrusted text. Inputs of `type: number` or `type: boolean` are not. `workflow_dispatch` inputs are not
(only someone with write access can start one). It is reported as `inputs.<name>`; `_guarded` already returns
`False` for it (it is not an authored field), so no `if:` excuses it.

```python
_INPUT = re.compile(r"(?<![\w.])inputs\.([\w-]+)", re.I)

def _call_inputs(workflow: dict) -> set[str]:
    """Lower-cased names of string inputs of a `workflow_call` workflow."""
    on = workflow.get("on", workflow.get(True))       # YAML reads the key `on` as True
    call = on.get("workflow_call") if isinstance(on, dict) else None
    declared = call.get("inputs") if isinstance(call, dict) else None
    if not isinstance(declared, dict):
        return set()
    return {str(name).lower() for name, spec in declared.items()
            if not isinstance(spec, dict) or str(spec.get("type", "string")).lower() == "string"}
```

- `_untrusted_fields(text, inputs: frozenset[str] = frozenset())` also returns `inputs.<name>` for each `_INPUT`
  match in `_normalised(expression)` whose lower-cased name is in `inputs`.
- `_tainted`, `_step_problems` and `_workflow_problems` pass the workflow's `_call_inputs(workflow)` down. Check
  `grep -n "_untrusted_fields(" scripts/security/runners/agent_workflow.py`: every call passes it.
- The module docstring's limit list gains: "a reusable workflow in another repository is not read; event text passed
  to any reusable workflow is reported at the caller". `_workflow_problems` gains the caller-side check below (a
  `uses:` job has no steps, so today it is skipped); otherwise the callee's own file reports its inputs.

`_UNTRUSTED_ROLES` is unchanged.

**String inputs: report all, no trusted marker** (owner, 2026-11-23, decision 6). There is no way to mark an input
trusted. The runner's failure message (`scripts/security/runners/agent_workflow.py`, `run`, today "Pass an issue or
pull-request number and let the agent fetch it as data, or restrict the author") becomes: "untrusted event text
reaches a coding agent. Pass a number and let the callee read what it needs, decide in the caller and pass a
boolean or a closed choice, or give the agent no event text. An agent that fetches the text itself still reads it:
limit what it may do (read-only token, no write tools, no secrets). Or restrict the author: " + the problems. `docs/UserManual.md`, in the SEC-CIAGENT-001 section, gains the remedies, as three refactors: pass a number
(the pull request or issue number) and let the callee read what it needs; decide in the caller and pass a `boolean`
or a value from a closed `choice` list; or give the agent no event text at all and let it fetch the text with its own
tools. And one warning, word for word: "Letting the agent fetch the pull request's text does not make the text
trusted: it moves the injection to where this check cannot see it. What limits the damage then is what the agent may
do: a read-only token, no write tools, no secrets in its environment."

**The caller side** (owner, 2026-11-23, decision 6b). A callee in another repository is not read, so the place to
catch event text sent to one is the caller. In `_workflow_problems`, a job with a `uses:` key (a reusable workflow:
`./.github/workflows/<file>.yml` or `<owner>/<repo>/.github/workflows/<file>.yml@<ref>`) is checked whether or not
the callee is read: each value under its `with:` whose `_untrusted_fields(value, _call_inputs(workflow))` is not
empty (so a `workflow_call` workflow that forwards its own string input, `with: t: ${{ inputs.title }}`, is caught:
the shared-workflow chain 6b closes), is reported as "`<file>`: job `<id>` passes untrusted event text to a reusable workflow (`<uses>`): `with.<name>` ←
`<field>`", prefixed with the workflow file as every other problem is. It is reported for every callee, local or
remote: whether the callee hands it to an agent cannot be known from here. No `if:` excuses it: the owner's words
are "any `uses:` workflow". Whether a job guard that is certainly false for every outsider should excuse it, as it
does for a step, is asked in B7 (row 17); until the owner answers, it does not. Steps' `uses:` (actions, not workflows) are unchanged: their `with:`
is already read when the action is an agent. Tests, in `scripts/test/test_agent_workflow_injection.py`:
`test_a_caller_passing_event_text_to_any_reusable_workflow_is_reported`, generated over every field family (and the forwarded `inputs.*` family)
`_untrusted_fields` names (written as a list in the test) × a local and a remote `uses:` × with and without a job `if:` (reported in both),
expected values from that list, never from the function (mutants: `uses:` jobs skipped; remote
`uses:` skipped; a job `if:` read as excusing it; `inputs` not passed on the caller side); and two contract cases in `contract/security/v1/cases.json` (a remote callee
given `github.event.pull_request.title`: fail; given `github.event.pull_request.number`: pass).

### The independent oracle

**What it is.** `@actions/expressions` 0.3.61, GitHub's TypeScript implementation of the expression language, called
from Python through one Node subprocess.

New files:
- `scripts/test/gha_oracle/package.json`: `{"name": "agentsmith-gha-oracle", "private": true, "type": "module",
  "dependencies": {"@actions/expressions": "0.3.61"}}` (exact version, no caret).
- `scripts/test/gha_oracle/package-lock.json`: written by `npm install --ignore-scripts` there; commit it.
- `scripts/test/gha_oracle/evaluate.mjs`: reads JSON lines on stdin, writes one JSON line per input. Input
  `{"expression": str, "context": object, "functions": {"success": bool, …}}`. Output
  `{"ok": true, "truthy": bool}` or `{"ok": false, "error": str}`. Input `{"list_functions": true}` answers
  `{"functions": [names of wellKnownFunctions]}`. Shape (this was run on 2026-11-14 and works):

```js
import { Parser, Lexer, Evaluator, data, wellKnownFunctions } from "@actions/expressions";
import { truthy } from "@actions/expressions/result";
// toData(v): null→new data.Null(), boolean→BooleanData, number→NumberData, string→StringData,
//            array→new data.Array() + add(), object→new data.Dictionary() + add(key, value)
// per line: fns = Map(name → {name, minArgs: 0, maxArgs: 255, call: () => new data.BooleanData(value)})
//           lr = new Lexer(expression).lex()
//           expr = new Parser(lr.tokens, Object.keys(context), [...fns.values()]).parse()
//           result = new Evaluator(expr, toData(context), fns).evaluate()
//           print {ok: true, truthy: truthy(result)}; on any throw print {ok: false, error}
```

- `scripts/test/test_gha_expression_oracle.py`: starts `node evaluate.mjs` once (`subprocess.Popen`, cwd the oracle
  directory), sends every case, reads every answer.

**When Node or `node_modules` is missing:** if the environment variable `CI` is set, the test **fails** with "run
`npm ci --ignore-scripts` in scripts/test/gha_oracle"; otherwise it is skipped with that sentence as the reason.
Never skipped in CI.

**The generator** (in the test file; `random.Random(seed)` for seeds `0..19`, so runs repeat). Families:

- **F1 literals.** Strings: `''`, `'OWNER'`, `'owner'`, `'NONE'`, `'0'`, `'1'`, `'1.0'`, `'0x10'`, `'1_0'`, `' 1 '`,
  `'1e3'`, `'true'`, `'false'`, `'null'`, `'Object'`, `'Array'`, `'{0}'`, `'{{0}}'`, `'Infinity'`, `'NaN'`. Numbers:
  `0`, `1`, `-1`, `1.5`, `16`, `0x10`, `1e3`. Keywords: `true`, `false`, `null`.
- **F2 contexts.** `github.event.comment.author_association` (the bound path), the same path written
  `github['event']['comment']['author_association']`, `github.event_name`, `github.actor`, `inputs.x`, `env.X`,
  `github.event.nope.deep` (missing), `github.event[github.event_name]` (computed index), `github.event.*.x` (filter).
- **F3 operators.** `!a`, and `a op b` for each of `==`, `!=`, `<`, `<=`, `>`, `>=`, `&&`, `||`, with and without
  brackets. **Exhaustive at depth 1**: every ordered pair of atoms from F1 ∪ F2 with every operator. Then, per seed,
  200 random trees of depth 2–3.
- **F4 calls.** Every name the oracle lists (`list_functions`), plus `success`, `failure`, `cancelled`, `always`,
  `hashFiles`, and the invented `nosuch`; arguments from F1, F2 and `fromJSON('<text>')` for each text in `[1]`,
  `["OWNER","MEMBER"]`, `{"a":1}`, `"OWNER"`, `1`, `true`, `null`, `nope`, `[[1]]`, `[]`, `{}`, `1e400`, `NaN`.
  Arities 0, 1, 2, 3. Because the names come from the oracle, a function GitHub adds is tested the day the version is
  raised.
- **F5 guard shapes.** With `G` each of the four owner tests in `MUST_DECIDE` and `X` any expression from F1–F4:
  `G || X`, `X || G`, `G && X`, `!(X) || G`, `(G && X) == false`, `(G || X) != true`. This family is the shape of
  every bypass in all four passes; P4-R1 and each P4-R2 example must be among its outputs (the test asserts that
  `!success() || G` and `fromJSON('[1]') != fromJSON('[1]') || G` were generated, by string membership in the
  generated set, so the generator cannot be narrowed without failing).
- **F6 spelling.** Each F4 name in three cases (`fromJSON`, `FROMJSON`, `fromjson`); each expression with and without
  spaces around operators.

**Completions.** For each expression: the partial binding is `{author_association: role}` for each role in
`ROLES_UNDER_TEST` (the six untrusted roles, written in the test file). Every other context path that appears in the
expression takes each value in `''`, `'OWNER'`, `'NONE'`, `'x'`, `0`, `1`, `true`, `false`, `null`, `{"a": 1}`,
`["OWNER"]`; each status function takes `true` and `false`. All combinations when there are at most 64, otherwise 64
drawn with the seed.

**The assertion.** For each (expression, role): `ours = _truthy(_eval(parse(E), binding))`, wrapped as
`may_be_true` wraps it. If `ours` is `True` or `False`, then every completion's oracle answer is `ok` with the same
`truthy`. An oracle error or a different answer on any completion is a failure whose message prints the expression,
the completion and both values. If `ours` is `UNKNOWN`, nothing is asserted.

**Why it does not share the fix's blind spot.** The oracle is a different implementation in a different language by
the language's owner; the cases come from the grammar and not from any report; and the assertion is the invariant
itself ("definite implies certain"), checked against all completions, so a value that varies (`success()`) is caught
without anyone listing it.

**Its limits, stated.** (a) The package's README says it is one of several implementations; it is not the Actions
runner. Measured: it answers `false` for `contains(fromJSON('{"a":1}'), 'Object')` where pass 4 expected `true` from
the runner. Wherever the two could differ (objects, arrays, coercions), this design returns `UNKNOWN`, so neither
is trusted. (b) Status functions and `hashFiles` are not in the package; the harness supplies them as functions
returning each boolean, which is all the assertion needs. (c) How an `if:` string is wrapped is workflow syntax, not
expression syntax, so the oracle cannot test it; `parse` returns `UNKNOWN` for every form except the two exact ones.

### Named tests

In `scripts/test/test_gha_expression_oracle.py`:

| Test | Asserts | Mutant it must kill |
|---|---|---|
| `test_a_definite_answer_is_githubs_answer_for_every_completion` | the assertion above over F1–F6 | `"success": _always` added to `_EXACT_CALLS`; `_equal` returning `a == b` for two `Array`s; mixed-type `_equal` returning `False` |
| `test_the_generator_produces_the_reported_bypasses` | the generated set contains the P4-R1 and six P4-R2 expressions | F5 or the `fromJSON` texts removed from the generator |
| `test_the_oracle_itself_can_disagree` | a deliberately wrong evaluator (a stub that answers `False` for everything) fails the assertion | the assertion loop skipped or emptied (`test-that-cannot-fail`) |
| `test_the_oracle_runs_in_ci` | with `CI` set and no `node_modules`, the fixture raises, not skips | the CI branch changed to skip |

In `scripts/test/test_gha_expression.py` (pure Python, no Node; these are what the mutation job runs):

| Test | Asserts | Mutant it must kill |
|---|---|---|
| `test_a_function_outside_the_allow_list_is_unknown` — parametrised over `success`, `failure`, `cancelled`, `hashfiles`, `format`, `tojson`, `join`, `case`, `nosuch`, each with 0, 1 and 2 literal arguments | `_eval` gives `UNKNOWN` | `_call`'s `return UNKNOWN` changed to `return False` or `True`; any name added to `_EXACT_CALLS` |
| `test_the_allow_list_is_exactly_these_five` | `set(_EXACT_CALLS) == {"always","contains","startswith","endswith","fromjson"}` | a sixth entry added without changing this design |
| `test_a_computed_index_is_unknown` | `github.event[github.event_name].author_association == 'OWNER'` is `UNKNOWN` with the association bound to `NONE`, and `_guarded` is `False` for it | `_path` returning the base path when the index is not a literal |
| `test_fromjson_of_bad_text_is_unknown` — texts `nope`, `{`, `NaN`, `[[1]]`, `{"a":1}` | `UNKNOWN` | the `except ValueError` branch returning `None`; `_from_json_value` returning a `dict` |
| `test_mixed_types_and_arrays_are_unknown` — `'0x10' == 16`, `'1' == 1`, `true == 1`, `null == 0`, `fromJSON('[1]') != fromJSON('[1]')`, `'a' < 'b'` | `UNKNOWN` | the mixed-type branch of `_equal` returning `False`; `_compare` accepting strings |
| `test_text_or_space_around_an_expression_is_unknown` — `"${{ false }} "`, `"x ${{ false }}"`, `"${{ false }}\n"` | `may_be_true` is `True` | `parse` stripping before it decides |
| `test_every_guard_in_must_decide_is_definitely_false_for_an_outsider` — `MUST_DECIDE` × six roles | `may_be_true` is `False` | `_contains`' array branch returning `UNKNOWN`; `"contains"` dropped from the table |

`MUST_DECIDE` (written in the test file, with `A` standing for `github.event.comment.author_association`):
`A == 'OWNER'`; `A == 'OWNER' || A == 'MEMBER' || A == 'COLLABORATOR'`;
`contains(fromJSON('["OWNER","MEMBER","COLLABORATOR"]'), A)`;
`A == 'OWNER' && github.event_name == 'issue_comment'`; `startsWith(A, 'OWNER')`. These five and no others.

Existing tests in that file that assert a definite value for `format`, `toJSON`, hex, or mixed-type comparison
(`test_literals_and_coercion_as_github_reads_them`, `test_values`) are changed to expect `UNKNOWN` for those rows,
and `test_text_around_an_expression_is_a_string_and_so_true` is replaced by
`test_text_or_space_around_an_expression_is_unknown`. Do not delete a row; change its expected value.

In `scripts/test/test_agent_workflow_injection.py`:

| Test | Asserts | Mutant it must kill |
|---|---|---|
| `test_a_deny_list_that_omits_one_untrusted_role_is_not_a_guard` — parametrised over `GITHUB_UNTRUSTED = ("CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER", "MANNEQUIN", "NONE")` **written in the test file** | the guard `A != r1 && A != r2 …` over the other four is reported | that role removed from `_UNTRUSTED_ROLES` (five mutants) |
| `test_a_deny_list_of_every_role_github_defines_is_not_a_guard` | `!=` over all five is reported | `A_ROLE_GITHUB_HAS_NOT_DEFINED` removed |
| `test_the_role_list_is_githubs_untrusted_roles_and_one_more` | `set(_UNTRUSTED_ROLES) == set(GITHUB_UNTRUSTED) \| {"A_ROLE_GITHUB_HAS_NOT_DEFINED"}` | a role renamed |
| `test_a_guard_that_depends_on_the_run_so_far_is_not_a_guard` — `!success() \|\| G`, `success() == false \|\| G`, `!cancelled() \|\| G`, `!failure() \|\| G` | each is reported | `success` treated as constant |
| `test_a_string_input_of_a_reusable_workflow_reaching_an_agent_fails` — callee with `on: workflow_call`, input `prompt` (string; and untyped), prompt `${{ inputs.prompt }}`, also through `env:` | reported as `inputs.prompt` | `_call_inputs` returning an empty set; the `inputs` argument not passed to `_tainted` |
| `test_a_number_input_and_a_dispatch_input_pass` | `type: number` under `workflow_call`, and a `workflow_dispatch` string input, are not reported | `_call_inputs` ignoring `type`; reading `workflow_dispatch` |
| `test_an_author_guard_counts_for_each_authored_object` — parametrised over `("issue", "pull_request", "discussion", "comment", "review", "review_comment")` **written in the test file**, each with its own `author_association` path and a body or title field | the guarded field is not reported | that entry removed from `_AUTHORED` (six mutants) |

`contract/security/v1/cases.json` gains three cases (a `!success()` guard fails; a reusable-workflow string input
fails; a number input passes) and `scripts/test/test_security_contract.py`'s pinned count goes from 43 to 46.

### Enforcement

- **Mechanical.** `.github/workflows/self-test.yml`, job `python-behaviour`: add `actions/setup-node@v4` with
  `node-version: "22"` and a step `npm ci --ignore-scripts` with `working-directory: scripts/test/gha_oracle`, both
  before the step that runs `pytest scripts/test/ -v`. With `CI` set the oracle test fails if it cannot run, so the
  required check `Python runtime behaviour tests (Postgres-backed)` is red whenever the evaluator gives a definite
  answer the oracle contradicts.
- **Mechanical.** `test_the_allow_list_is_exactly_these_five` makes widening the table a visible test edit.
- **Mechanical.** The per-entry mutants of invariant 5 cover `_EXACT_CALLS` and `_UNTRUSTED_ROLES`.
- **Judgment that remains.** Whether a new handler added to the table later is exact. The oracle test checks it;
  a reviewer need only confirm the oracle test ran (its count is printed).

### Done means

1. `grep -n "success\|failure\|cancelled\|format\|tojson\|_number\|_text" scripts/security/gha_expression.py` prints
   no line of code (docstring mentions are allowed).
2. Every named test above exists and passes; each named mutant, applied by hand, fails the named test.
3. The oracle test prints how many expressions and completions it compared; the number is in the review record.

## Invariant 2 — Judge the whole range

### The invariant

`process_gate.py ci --base B --head H` reaches a verdict on the before-and-after rules that is a function of exactly
three things: the tree at `before` (defined below from `B` and `H`), the tree at `H`, and the commit messages in
`before..H`. Two ranges with the same three things get the same verdict, however their commits are shaped. And that
verdict equals the commit hook's verdict on the one commit that takes `before` to `H` with those messages joined.

The before-and-after rules are the entries of `RANGE_RULES` (below). Rules about one commit's own records (the
`Design:` and `Review:` trailers, the review's freshness, the knowledge-graph scope, cross-references, the
mechanical pillar checks) stay per commit: they are about a commit by nature.

### Defects it closes

P4-R4 (merge commits; the head-only case for a new branch), P4-R5 (config removed), and P3-R4 in part: an approval
recorded before the range no longer unlocks a change in it. What P3-R4 leaves open is under "Out of scope".

### Decisions

- **`before`.** If `B` names a commit in the repository: `before = git merge-base B H`. (Not `B` itself: a pull
  request's base is the tip of the base branch, and if that branch strengthened the declaration after the fork,
  comparing with its tip would read the branch as weakening it.) If `git merge-base --all B H` prints more than one
  commit, the rules run against each and the problems are joined.
- **Unknown, empty or all-zero `B`.** Try `git merge-base origin/<default> H`, where `<default>` is the new option
  `--default-branch` (the workflow passes `${{ github.event.repository.default_branch }}`), or, without the option,
  the target of `refs/remotes/origin/HEAD`. If that gives a commit other than `H`, it is `before`. If the repository
  is shallow (`git rev-parse --is-shallow-repository` prints `true`) and no base can be read, **fail closed**: exit 1,
  "the base of this range cannot be read in a shallow clone; check out with fetch-depth: 0". Otherwise (a first push
  of the default branch, or no remote) `before` is nothing: every declaration is a seed, and the report keeps the
  caveat line. In every one of these cases the **per-commit** list stays the head commit alone, as today: gate
  contracts 2 and 3 publish that case. Only `befores` changes. Without the option, the default branch is read from
  `repository.default_branch` in the file `$GITHUB_EVENT_PATH` names, then from `refs/remotes/origin/HEAD` (Part B, B5).
- **An approval counts when it is new and bound** (owner, 2026-11-23, decision 5). An approval unlocks a weakening
  only if its id is in `.agenticframework/approvals.jsonl` at the after-state and **not** at the before-state, **and**
  it is bound to what it unlocks: its subject, recorded by `agentsmith approve`, names this weakening (the key, the
  file, or the deviation, and the value it moves from and to). What a subject holds, how `agentsmith approve`
  records it and how the gate matches it are `.agent-rfc/designs/approval-binding.md` (built before A5); this design
  calls its one function, `approval_unlocks(approval, change) -> bool`, and adds no rule of its own. The hook uses the
  same rule with (parent, index), so the approval line and the weakening are committed together, or in CI's case
  inside one range.
- **Weaken, then restore, inside one range passes CI** (owner, 2026-11-23, decision 7: accepted). The two ends are
  equal. The hook still refuses the weakening commit when it is made. This follows from the invariant and is stated
  in `docs/process-gates.md`, in the section on ranges, in these words: "CI judges a range by its two ends. A
  weakening that a later commit in the same range undoes is not seen by CI; the commit hook refused it when it was
  made, and only `--no-verify` gets it into the range, which the sweep reports."
- **A removed gate config.** A commit whose first parent carries `.agenticframework/process-gates.json` and which
  does not is refused by the hook and listed as failed by CI and the sweep: "removes the gate config", unless the
  commit (hook) or a commit in the range (CI) carries an `Approval: <id>` trailer naming an approval that is fresh and
  bound to removing `.agenticframework/process-gates.json` (owner, 2026-11-23, decision 8; the file is gone, so the
  trailer carries the id). It is "before adoption" only when its parent has none either. CI (which runs the gate, so
  the repository adopted it) stays red until the workflow step is removed too: that is the existing behaviour of
  `ci_verdict` for a head without a config, and the owner removes the step in the same change.

### Code changes — `scripts/process_gate.py`

Callers found with `grep -n "check_change(\|check_commits(\|_declaration_change(" scripts/process_gate.py`:
`commit_verdict` (the hook and contract 3's `commit`), `check_commits` (twice), `ci_verdict`, `sweep`. All five are
handled below; if the grep shows another, stop and ask.

**1. One transition function.**

```python
Nothing: Reader = lambda path: None

@dataclass(frozen=True)
class Change:
    """What one rule would unlock: the record `approval_unlocks` matches an approval's subject against
    (`.agent-rfc/designs/approval-binding.md` implements the match; this design fixes the shape)."""
    rule: str                  # the RANGE_RULES name, e.g. "gate-config-kept"
    target: str                # the file, or the file and key: ".agenticframework/process-gates.json#pillars.mode"
    before: Optional[str]      # the value given up, as text; for a whole file, "present"; None if it did not exist
    after: Optional[str]       # the value it becomes, as text; None when the target is removed

def _fresh_approvals(before: Reader, after: Reader) -> List["gm.Approval"]:
    """Approvals recorded between the two states."""
    old = {a.id for a in load_approvals(before)[0]}
    return [a for a in load_approvals(after)[0] if a.id not in old]

def _bound(approvals, change: Change) -> List["gm.Approval"]:
    """The fresh approvals bound to this change (decision 5). Every rule passes only these on."""
    return [a for a in approvals if approval_binding.approval_unlocks(a, change)]

def _cited(messages: str) -> set[str]:
    return set(gp._APPROVAL_TRAILER.findall(messages))   # one `Approval: A-xxxxxxxx` per line, as for the declaration

def _config_kept(before, after, bind, messages) -> List[str]:
    if before(CONFIG) is not None and after(CONFIG) is None:
        change = Change("gate-config-kept", CONFIG, "present", None)
        if any(a.id in _cited(messages) for a in bind(change)):   # decision 8
            return []
        return [f"{CONFIG} is removed — the gates are not retired by a change they would check, unless an "
                "`Approval:` trailer cites a fresh approval of this removal (`agentsmith approve`)"]
    return []

def _declaration_kept(before, after, bind, messages) -> List[str]:
    if before(gp.DECLARATION_FILE) == after(gp.DECLARATION_FILE):
        return []
    return gp.declaration_transition(before(gp.DECLARATION_FILE), after(gp.DECLARATION_FILE), bind, messages)[0]

def _pillar_policy_kept(before, after, bind, messages) -> List[str]:
    old, new = parse_config(before(CONFIG))[0], parse_config(after(CONFIG))[0]
    if old is None or new is None or not old.pillars_declared:
        return []
    return gp.transition_problems(old.pillar_policy, new.pillar_policy, bind)

def _compliance_profile_kept(before, after, bind, messages) -> List[str]:
    old, new = parse_config(before(CONFIG))[0], parse_config(after(CONFIG))[0]
    if new is None:
        return []
    return gp.compliance_transition_problems(old.compliance if old else None, new.compliance, bind)

RANGE_RULES: Tuple[Tuple[str, Callable[..., List[str]]], ...] = (
    ("gate-config-kept", _config_kept),
    ("declaration-kept", _declaration_kept),
    ("pillar-policy-kept", _pillar_policy_kept),
    ("compliance-profile-kept", _compliance_profile_kept),
)

def transition_errors(before: Reader, after: Reader, messages: str) -> List[str]:
    """Every before-and-after rule, once, on two states. The only caller of the four rules."""
    fresh = _fresh_approvals(before, after)
    bind = lambda change: _bound(fresh, change)      # each rule sees only the approvals bound to its own change
    return [problem for _name, rule in RANGE_RULES for problem in rule(before, after, bind, messages)]
```

`gp.declaration_transition`, `gp.transition_problems` and `gp.compliance_transition_problems` in
`scripts/gate_pillars.py` take `bind: Callable[[Change], List[Approval]]` in place of their `approvals` list (read
at c2583ff: each took the list), and keep the rest of their logic. How each builds its `Change`:

- `declaration_weakenings` returns records, `Weakening(key, before, after, text)`, in place of strings (`text` is
  today's string, kept for messages). Each is `Change("declaration-kept", f"{DECLARATION_FILE}#{key}", before,
  after)`. **Every** weakening needs a cited approval bound to it: one approval per weakening, or one approval whose
  subject lists several (`approval-binding` decides the subject's form; `approval_unlocks` is true when any listed
  change matches). Today one cited approval covers them all; that is the gap K2b closes.
- `transition_problems`: a `mode` weakening keeps having no approval route (refused, as at c2583ff; K7). A new
  `allow` entry cites its approval in its JSON field `approval`, as today; its change is `Change("pillar-policy-kept",
  f"{CONFIG}#pillars.allow[{check}:{path}]", None, canon(entry.model_dump(exclude={"approval"})))`, and the cited id must be in `bind(change)`.
- `compliance_transition_problems`: the new entry's `approval` field, as today; its change is
  `Change("compliance-profile-kept", f"{CONFIG}#compliance", canon(old), None if new is None else canon(new))`.
- `canon(value) = json.dumps(<any JSON value; for a dict, without its "approval" key>, sort_keys=True,
  separators=(",", ":"))`: an entry **without** its own `approval` field (an `Allowance`, a Pydantic model, is
  passed as `model_dump(exclude={"approval"})`). The id is drawn at random when
  `agentsmith approve` records the approval (`governance.py`, `secrets.token_hex`), so a subject recorded before
  the entry is written cannot contain it; `approval-binding` matches subjects against this form.
- A deleted declaration is `Weakening("*", "present", None, "the declaration is deleted")`, target
  `f"{DECLARATION_FILE}#*"`.
- `_gate_modes_kept` (A5): `Change("gate-modes-kept", f"{CONFIG}#{key}", canon(old), canon(new))` per weakened key
  (a mode is a string; the command is `shlex.split` of the effective command, a list).
- Every value a `Change` carries is `canon` of the value, so `agentsmith approve` and the gate serialise alike. The
  declaration's weakenings, one row per append site in `declaration_weakenings` (c2583ff `gate_pillars.py:100–158`):

  | Site | `key` | `before` | `after` |
  |---|---|---|---|
  | profile changed | `profile` | old profile | new profile |
  | app owner changed | `app_owner` | old | new |
  | a data class no longer classified | `data_classes.<class>` | `"classified"` | `None` |
  | `boundary.hosts` widened | `boundary.hosts` | old list | new list |
  | a sink loosened | `boundary.sinks.<sink>` | old entry | new entry or `None` |
  | a number loosened (`looser`) | `<section>.<key>` | old number | new value |
  | backup host changed | `continuity.backup_host` | old | new |
  | a language removed | `languages` | the removed language | `None` (one row per language; K1 is `languages`, `"ar"`, `None`) |
  | an agent removed | `agents.<name>` | the agent's entry | `None` |
  | an agent's owner changed | `agents.<name>.accountable_owner` | old | new |
  | user calls loosened | `user_calls_per_minute` | old | new |
  | the declaration deleted | `*` | `"present"` | `None` |

  A site this table does not name is a test failure (`test_every_weakening_site_has_a_key`, which parses
  `declaration_weakenings` with `ast` and requires each `found.append`, and the deleted-declaration `return`, to build
  a `Weakening` with a key from this table; mutant: a site appending a bare string). An absent value (`profile`
  removed, a number set to something else) is Python `None`, never `canon(None)`; numbers and strings pass through
  `canon` like any JSON value. `approval-binding` serialises the same way.

Every other caller changes with them (read at c2583ff):

- `_declaration_change` (`process_gate.py`, the audit log's helper) takes `bind`; `commit_verdict` builds it from
  `_fresh_approvals(previous, read)`. Its `summary` keeps `weakened = [w.text for w in weakenings]` (so
  `_log_declaration_change`'s `'; '.join` still works) and `approvals`, a list of every bound id cited (several may
  be needed now), in place of the single `approval`.
- `policy_transitions` and `range_transitions` (the per-commit and range wrappers `2aee5f3` added) are deleted in
  A5: `transition_errors` replaces both, and `_range_problems` calls it.
- Tests that call the old forms are updated in A5, with no assertion weakened: `scripts/test/test_declaration_ratchet.py`
  (its string comparisons become `.text` comparisons; its list arguments become a `bind` built from the list) and
  `scripts/test/test_compliance_port.py` (its `[]` becomes `lambda change: []`). Their names are listed in A5's
  review.
`approval_binding.approval_unlocks` comes from the `approval-binding` design's commit, built before A5; until then
the rule cannot be built, which is why A5 follows it.

**2. `check_change` loses the rules.** Delete from `check_change`: the `declaration = _declaration_change(...)` line
and its three uses, and the block from `previous_config = …` through the two `errors.extend(gp.…transition…)` calls.
Add a parameter `transitions: List[str]` (required, no default), returned beside the other lists: `check_change`
returns `(errors, notes, transitions)`. `check_commits`' `Failures` entries gain a fourth field, the commit's
transition errors, printed after its `errors`; a commit fails when either list is non-empty. `check_change` no longer decides any before-and-after rule; it reports the ones it is
handed. The `previous` parameter stays (the mechanical pillar checks and `arming` read it).

**3. The hook.** In `commit_verdict`, in this order (at c2583ff `base` and `previous` are computed below the early
return, and the lines between them need a config): right after the `problems` check, compute `base` (with its amend
and root-commit cases, unchanged), `previous = _reader_at(root, base[0])` and `transitions =
transition_errors(previous, read, message)`. Then the early return, moved here. When the index has no config, run the same sweep and clearing
block that follows `check_change` (it needs no config: `sweep` follows its no-config order, and `Repairs:` and the
clearing call read only git and the message). A never-adopted repository stops at the sweep's step (1) (an
uninitialised store: one file read) and a repository retired by an approved removal at step (2), so neither is
refused. Return that block's errors, plus `transitions` only when `previous(CONFIG)` is not None (a repository with
no config on either side is not judged on the declaration, as CI's `before_adoption` and the sweep say), code 1 when
the result is non-empty, else `(0, [], [])`. So a commit above an earlier unapproved removal is refused by the hook
as by the push. Then `files`, `lines`, `added`, `evidence`
and `check_change`, as now, all of which need a config. With a config, `commit_verdict` returns
`transitions + errors` as its errors (`check_change`'s third list joined to its first), with code 1 when either is
non-empty. The audit log's call moves into
`_log_declaration_change`, which then takes `(root, files, message, read, previous, bind)` and calls
`_declaration_change` itself (at c2583ff `commit_verdict` made that call, `process_gate.py:1240`); `commit_verdict`
passes a `bind` built from `_fresh_approvals(previous, read)`. Its log line joins `summary["approvals"]` (`approved by
{', '.join(summary['approvals'])}`) in place of `summary['approval']`.

**4. CI.** `check_commits` gains a parameter `transitions: bool`. With `True` (the sweep), each commit's
`check_change` receives `transition_errors(parent reader or Nothing, read, message)`. With `False` (CI), it receives
`[]`. In `check_commits`, the `if config is None:` branch becomes: if the first parent's reader has a config, the
commit is judged by decision 8's rule, not refused outright. With `transitions=True` (the sweep), it fails when
`transition_errors(parent, read, <its message>)` is non-empty; those errors go in the `Failures` entry's fourth field
(transition errors), with `errors` empty, so only the clearing rule below clears them, never `Repairs:`. It reports
every error it returns, as the hook does (a
removal with a bound approval that also weakens the declaration still fails). With `transitions=False` (CI), `check_commits` receives
`range_` (its `befores` and `messages`, the latter including merges' messages): the removal commit is judged by
the approval, not by an error's wording. For each `B` (each `before` that has a config, else the commit's parent):
`ids = [a.id for a in _bound(_fresh_approvals(B, <the commit's reader>), Change("gate-config-kept", CONFIG,
"present", None)) if a.id in _cited(range_.messages)]`. The commit is `failed` ("removes the gate config") when `ids`
is empty for any `B`, otherwise `passed_with_notes` with "removes the gate config; approved by <ids>". This uses the
same `_bound` and `_cited` as `_config_kept`; no second matcher is written. Only when the parent has no config either is it
`unadopted` (`before_adoption`). Merges never enter `check_commits`; they are judged only by step 7's call.

`ci_verdict` replaces `_range_commits` with:

```python
class Range(NamedTuple):
    befores: List[str]          # merge bases; empty when the range starts from nothing
    commits: List[str]          # rev-list --reverse --no-merges, for the per-commit rules
    messages: str               # every message in the range, merges included, joined by "\n"
    caveat: Optional[str]
    unreadable: Optional[str]   # set when a shallow clone hides the base: the run fails

def _range(root: Path, base: str, head: str, default_branch: Optional[str]) -> Range: ...
```

and, after `check_commits(root, range_.commits, records, transitions=False, range_=range_)`
(signature: `check_commits(root, commits, records=None, *, transitions: bool, range_: Optional[Range] = None)`,
with `range_` required when `transitions` is false; the sweep passes none):

```python
    range_errors: List[str] = []
    after = _reader_at(root, head)
    for before in (range_.befores or [None]):
        range_errors += transition_errors(_reader_at(root, before) if before else Nothing, after, range_.messages)
```

`range_errors` (deduplicated, order kept) are reported as `- ❌ range: <problem>`, annotated
`::error title=Process gate (range)::…`, and make the exit code 1. `messages` comes from
`git log --format=%B <before>..<head>` **without** `--no-merges`. `cmd_ci` and `cmd_ci_decision` gain
`--default-branch`; the `ci` parser gets `ci.add_argument("--default-branch", default=None)`.

**5. The sweep** calls `check_commits(root, candidates, transitions=True)`: it judges commits one at a time on a
developer's machine, as the hook would have.

**6. The workflow.** `.github/workflows/self-test.yml`, step "Every gated commit has a design and a clean review":
add `--default-branch "${{ github.event.repository.default_branch }}"` through an `env:` variable, as `BASE` is
passed. Change the comment above `BASE` (it says the script checks the head commit only).

### The independent oracle

**The hook on the squash.** For a generated history from `before` to `H`, build a second repository holding one
commit that takes the tree at `before` to the tree at `H`, with every message of the range joined, made by
`git commit` **through the real hooks** (no `--no-verify`). CI's exit code on the first repository's range must equal
the hook's exit code on that one commit, for the before-and-after rules. Both repositories are built with the
existing `_make_repo(tmp_path, name, files, monkeypatch)` and `GATE_FILES`/`HOOK_FILES` of
`scripts/test/test_process_gate.py`, and CI is run with its `_ci(repo, base)`.

To keep the trailer rules out of the comparison, every generated change touches only
`.agenticframework/compliance.json`, `.agenticframework/approvals.jsonl`, `.agenticframework/process-gates.json` and
an ungated `notes.txt`; where the config is gated the squash commit carries `Design: n/a: range test` and
`Review: n/a: range test` (allowed for at most 20 gated lines, `SMALL_CHANGE_LINES`), and so do the shaped commits.

**7. Merges are judged too** (a code change, numbered after step 6 above; from #117's independent review, 117-R1
and R2, 2026-11-24). The per-commit lists
skip merges (`--no-merges`), so three judges still decided by history shape: the sweep, which is also the pre-push
decision (`local_commits`); CI with no known base, whose merge head `check_commits` lists with `diff-tree` and no
`-m`, so no files; and, in a range, a merge that weakens and a later commit that restores. The first two are closed
here, and only those two: for every merge commit `m` (more than one parent) that the sweep's `local_commits` leaves
out, and for a merge head in head-only CI, the sweep and `ci` run `transition_errors(_reader_at(root, f"{m}^1"),
_reader_at(root, m), <the messages of m^1..m>)` (`git log --format=%B m^1..m`: the merge and the commits it brings in,
so a sync merge of an owner-approved weakening carries that approval's citation; binding keeps a wider message set
from unlocking anything else). Merges are listed with `git rev-list --reverse --merges --branches HEAD`, beside
`local_commits`' non-merge list. A judged merge joins the sweep's verified store (`save_verified`) as other commits
do. Merges have their own store file, `.git/agentsmith/verified-merges`, which pre-A5 code never writes (it would
rewrite `verified` as version 1). Initialisation (no `verified` yet) writes `verified-merges` together with `verified`,
recording every merge it lists (an empty list when there are none). When `verified` exists and `verified-merges` does
not, which only a store written by pre-A5 code has, every merge already reachable is recorded without being judged,
so an upgrade never judges history nobody changed. That backfill runs before the unrecorded merges are computed
(including in the no-config order's step (2)). An unreadable `verified-merges` is treated as missing, as
`load_verified` treats an unreadable `verified` (so the backfill rule above applies; `verified` is untouched). Test:
`test_a_pre_a5_store_backfills_merges_without_judging`, in the named-tests table below. Merges are listed with
`--max-count=2000`, as `local_commits` is, and the merge file is capped at `VERIFIED_CAP` (5000), which must stay
at least the listing's 2000.

**The sweep when the index has no config**, in this order: (1) if the store is uninitialised, return as today (an
unadopted repository is never written to); (2) otherwise compute the candidates and the unrecorded merges (step 7's list); if no
candidate and no unrecorded merge, nor the first parent of any, has a config, record them all as verified and
return (a merge that fails at step (3) stays unrecorded, so every later sweep takes step (3) again, as a failing
non-merge commit does); (3) otherwise skip `rearm_hooks` and `artifacts_report` (both
need a config) and judge the candidates, so a head commit or merge that removes the config is judged by decision 8's
rule at push, and judge the unrecorded merges by step 7's call. An approved removal (K8b) passes step (3) once and
is recorded; later sweeps return at step (2).

**How a transition failure is cleared.** `check_change` keeps the transition errors in their own list (`transitions`
is returned beside `errors`, not prepended), so the sweep and `commit_verdict` can tell the two kinds apart. A
per-commit failure is cleared by `Repairs:` as today. A transition failure is not: a failing commit `c` is cleared
when every local branch tip and `HEAD` that contains `c` gives an empty `transition_errors(_reader_at(c^1),
_reader_at(tip), git log --format=%B c^1..tip)` (the value restored, or a fresh, bound approval cited since); `c` is
then recorded. A stale branch still at the weakening keeps `c` failing until that branch is moved or deleted. The
hook neither asks for nor accepts `Repairs:` for a transition failure: it allows a commit when
`transition_errors(_reader_at(c^1), read, <git log --format=%B c^1..HEAD> + "\n" + message)` is empty for each
failing `c` below it. A commit with both kinds of failure is recorded only when `Repairs:` clears its per-commit
errors and the rule above clears its transition errors.
Cases: S10 × K1 followed by an empty commit with `Repairs: <the merge>`: the sweep still refuses; S10 × K1 followed by
a commit that restores `ar`: the sweep exits 0 and records both.
In a range with a known base nothing changes: CI judges the merge base and the head (decision 7). The third is decision 7's accepted case (the ends are equal), now for a merge as
for an ordinary commit; the hook refuses the merge when it is made, and the sweep refuses it at push (S10). An
approval for a merge's weakening is cited in the merge's own message; with binding (decision 5) an approval cited
elsewhere in the range unlocks only the change it is bound to (117-R2).

**The generator** (`scripts/test/test_range_verdict.py`). A case is (content change, shape). Content changes:

| Id | Before → after | Expected (from the hook on the squash, not typed in) |
|---|---|---|
| K0 | nothing changes in the three files | allow |
| K1 | `languages` loses `ar` | refuse |
| K2 | K1, plus a new approval line and `Approval: A-…` in a message | allow |
| K3 | K1, citing an approval already present at `before` | refuse |
| K4 | `session.idle_minutes` 15 → 10 (stronger) | allow |
| K5 | the declaration is deleted | refuse |
| K6 | the declaration is renamed to another path | refuse |
| K7 | `pillars.mode` `enforce` → `report` in the config | refuse |
| K8 | the config is deleted | refuse |
| K9 | `ar` removed, then restored: the two ends are equal | allow |
| K10 | the config's `compliance` entry (`dubai-gov`, `enforce`) is removed | refuse |
| K2b | K1, plus a new approval bound to another change (K7's key) and cited | refuse (decision 5) |
| K8b | K8, with a new approval bound to removing the config, cited by `Approval:` | allow (decision 8) |
| K8c | K8, with a new approval bound to another change, cited by `Approval:` | refuse |
| K8d | K8, with a bound approval already present at `before`, cited | refuse |

The base repository's config declares `pillars` with mode `enforce` and `compliance` with mode `enforce`, and its
declaration has real values (no `REPLACE_ME`), so K1, K7 and K10 have something to weaken.

Shapes, each applied to each content change (K9 only where a shape has two steps):

| Id | Shape |
|---|---|
| S1 | one ordinary commit, `--no-verify` |
| S2 | two commits: half the change each (for K2: approval first, weakening second; and the reverse) |
| S3 | the change made on a side branch, merged with `--no-ff` |
| S4 | a clean side branch merged with `git merge --no-commit --no-ff`, the change made in the merge commit itself (P4-R4) |
| S5 | both branches touch the declaration, conflict; the resolution is the change |
| S6 | the change, then `git commit --amend --no-verify` adding an unrelated line |
| S7 | the change one commit below the head of a **new branch**, CI run with an all-zero base and `--default-branch main` |
| S8 | S1 pushed to a clone made with `--depth 1`, CI run with the real base sha: expected exit 1 and the shallow message for every content change |
| S9 | the config deleted in one commit and restored in the next, with K1 in the first (P4-R5) |
| S10 | S4's merge made with `--no-verify`, then pushed: assertion 4 |
| S11 | S4's merge as the head of a new branch, CI run with an all-zero base: assertion 1 |
| S12 | a side branch is cut from `main` and gets one commit of its own; the change is then committed on `main` through the hook with its approval and `Approval:` trailer; then `main` is merged into the side branch with `--no-ff --no-verify` and git's default merge message (a real two-parent merge, never a fast-forward), then pushed: assertion 4 |

**The assertions.**
1. *Agreement:* for every (K, S) except S8, `_ci(...).returncode != 0` equals "the hook refused the squash", except
   K8b, which CI refuses in every shape because the head has no config (`ci_verdict` stays red until the workflow
   step is removed too, decision 8 above). K8b's "allow" is proved through the hook and the sweep (assertion 4).
2. *Shape-invariance:* for each K, every S1–S7 gives the same exit code.
3. *The oracle is live:* at least one K is refused and at least one allowed (so an oracle that always allows, or a
   generator that produces nothing, fails).
4. *The sweep agrees:* for every K under S10, and for K0, K2, K4 and K8b under S12 (S12 commits the change on
   `main` through the hook, so only a K the hook allows on one commit can be built), `process_gate.py sweep`'s exit is
   non-zero exactly when the hook refused the squash (under S10, K0, K2, K4 and K8b are allowed; K9 has no S10 case,
   S10 being one step; under S12 all four are allowed). The test initialises the sweep's store before the shaped commits (a first sweep records and
   checks nothing). Mutants: merges skipped by the sweep (S10); a merge judged with its own message only (S12).

**Why it does not share the fix's blind spot.** The expected value is produced by a different entry point (`git
commit` through `.githooks/commit-msg`) on a different history (one commit), and the shapes are a table, not the
reported merge. A shape nobody listed is still covered by assertion 2 in the sense that adding it is one table row;
a route that reads commits instead of ends fails for S4, S5 and S7 at once.

### Named tests — `scripts/test/test_range_verdict.py`

| Test | Asserts | Mutant it must kill |
|---|---|---|
| `test_ci_agrees_with_the_hook_on_the_squash` — parametrised K × S | assertion 1 | `range_errors` not added to the exit code; `--no-merges` added to the messages log; `_fresh_approvals` returning every approval (kills K3, K8d); `_bound` returning every fresh approval (kills K2b, K8c) |
| `test_the_verdict_does_not_depend_on_the_shape` | assertion 2 | `check_commits(..., transitions=True)` in `ci_verdict` (K9 then fails in S2 only) |
| `test_the_oracle_refuses_some_and_allows_some` | assertion 3 | the hook fixture made with `--no-verify` |
| `test_the_sweep_agrees_with_the_hook_on_the_squash` — K × {S10, S12} | assertion 4 | merges skipped by the sweep; a merge judged with its own message only (a sync merge of an approved weakening then refused); initialisation not writing `verified-merges` (killed by an assertion made right after the test's initialising sweep: `.git/agentsmith/verified-merges` exists and lists `[]`) |
| `test_a_pre_a5_store_backfills_merges_without_judging` | setup: `verified` written as pre-A5 initialisation writes it (`save_verified(root, local_commits(root))`: every non-merge commit reachable), no `verified-merges`, and history holding an S10 × K1 merge (S4's merge, `ar` removed in it, committed with `--no-verify`), each case in a fresh repository. The sweep records the merge and exits 0; then an S4 × K7 merge (`pillars.mode` turned down) made with `--no-verify` is judged and refused; the same with an unreadable `verified-merges`; and the same first half with the config deleted at the index (no-config step (2)): the sweep exits 0 and `verified-merges` lists the merge | the backfill judges; the backfill skipped; the backfill only in the config path |
| `test_before_is_the_merge_base_not_the_base_tip` | main strengthens after the fork; the branch does not touch the declaration; CI with `--base <main tip>` passes | `before = base` |
| `test_an_unreadable_base_in_a_shallow_clone_fails_closed` | S8 | the shallow branch falling through to "head only" |
| `test_a_commit_that_drops_the_config_is_refused_by_hook_ci_and_sweep` | S9: hook exit 1; CI lists it failed, not "before adoption"; `process_gate.py sweep` lists it. Second half, its own history, with expected values typed in the test (not from the hook): S9's two commits **without** K1. The test first initialises the sweep's store (`process_gate.py sweep` once); the first commit only deletes the config, carrying a fresh approval bound to the removal, cited by `Approval:`, through the hook; the second restores it with `--no-verify` (only the removal is measured: the restore's own result and the exit codes of the sweep and CI are not asserted); CI is run with `--json` and the removal commit's record is read: the hook exits 0, the sweep records the commit, CI records it `passed_with_notes` naming the id | the parent check removed from the `config is None` branch; the trailer route ignored in `_config_kept` |
| `test_every_before_and_after_rule_is_a_range_rule` | reads `scripts/process_gate.py` with `ast`: inside `check_change`, no call to any name in `{declaration_transition, transition_problems, compliance_transition_problems, _declaration_change}`; and each of those names is called only inside a function listed in `RANGE_RULES`, inside `_declaration_change` (the audit log's helper), or inside `_log_declaration_change` | a transition rule put back in `check_change` |

`scripts/test/test_declaration_ratchet.py`: `test_a_commit_that_weakens_the_declaration_is_refused_then_allowed_with_approval_and_logged`
is changed so the approval line is added in the same commit as the weakening (the new rule), and gains a second half:
the same approval committed first, then the weakening, is refused by the hook. `test_ci_refuses_a_weakening_that_skipped_the_hook`
stays and must still pass unchanged.

### Enforcement

- **Mechanical.** `test_every_before_and_after_rule_is_a_range_rule` fails when a before-and-after rule is called
  outside `RANGE_RULES`. A new rule of this kind has one place to go.
- **Mechanical.** The K × S test runs in the required check `Python runtime behaviour tests (Postgres-backed)`.
- **Mechanical.** Per-entry mutants (invariant 5) over `RANGE_RULES`: dropping any entry must fail a test.
- **Judgment that remains.** Whether a rule added later is "before-and-after". The test above catches the four known
  functions by name; a new comparison function must be added to its name set by whoever writes it. Stated in
  `docs/process-gates.md`.

### Done means

1. `grep -n "no-merges" scripts/process_gate.py` shows it only in `_range`'s per-commit list and `local_commits`;
   merges are judged one by one only by the sweep and by head-only CI (step 7). In a range with a known base, the
   merge base and the head are judged (decision 7).
2. The K × S table has (K0–K10 and K2b, K8b–d at A5's predecessor commit; K11, K13, K15 from A5) × 12 shapes, minus the stated exclusions (S12 only for K0, K2, K4, K8b; S8 and K9 as stated) and the
   stated exclusions; the count that ran is in the review record.
3. P4-R4's scenario and P4-R5's are cells S4 × K1 and S9, not separate tests.

## Invariant 3 — Rebuild, don't add

### The invariant

For any sequence of edits to a repository, `build_graph(root)` after the last edit returns the same graph whether or
not a graph, or a parse cache, existed before. The committed `.agent-rfc/fixtures/knowledge_graph.json` is
byte-for-byte `serialise(build_graph(root))` restricted to tracked paths. No value in it depends on a clock or on the
order of a directory walk.

### Defects it closes

P4-R8, P4-R11 (the knowledge-graph part: file times, a check that rewrites), P4-R12's two import survivors, and
P4-R9 in part (scripts named by path; the rest documented).

### Decisions

- **Edges depend on the whole tree.** Adding `b.py` makes `import b` in an unchanged `a.py` resolve. So no edge is
  ever kept from a previous build. Only a file's **parse** (its symbols and raw import strings), which depends on
  that file's bytes alone, may be cached.
- **The cache** is `<git dir>/agentsmith/kg-parse-cache.json`, never tracked: `{parser_version, files: {path:
  {sha256, language, symbols, imports}}}`. Outside a git checkout there is no cache. A cache that cannot be read is
  ignored, not an error.
- **Clock values leave the graph.** `last_modified` (file nodes) and `created_at` (guardrail nodes) are no longer
  written. `created_at` has the same fault and nothing reads it but the test that says the shape ignores it.
- **Order.** Nodes sorted by `id`; edges by (`source`, `target`, `edge_type`); each node's `symbols` in source order
  as now; `json.dumps(..., indent=2, sort_keys=True)` plus a final newline.
- **Nodes the walk does not own** (`ProductionIncident`, and edges that are not `IMPORTS` or `RUNS`) are carried
  over from the existing file unchanged, as `test_a_production_incident_survives_the_walk` requires. The committed
  fixture has none.
- **`kg check` keeps its contract** (`contract/gate/v3/protocol.md`: exit 1 when stale, regenerating in place). With
  a deterministic build, regenerating a current graph changes no byte, so a check no longer dirties the tree.
- **`--force` stays as an accepted flag that does nothing**: `agentsmith/cli.py` passes it and is not in this
  design's scope. `PARSER_VERSION` now only invalidates the cache.
- **P4-R9.** A Python string constant that names a tracked `.py` file becomes a `RUNS` edge (rule below), and
  `gate_kg._dependents` counts `RUNS` as it counts `IMPORTS`. Hooks, workflows and YAML that run scripts, dynamic
  imports, parent `__init__.py` files and data files are **not** covered; they are listed as limits where `kg impact`
  is documented.

### Code changes

`scripts/map_codebase.py`:

```python
def build_graph(root: Path, cache: Optional[dict] = None) -> dict:
    """The graph of this tree, from nothing. Reads no existing graph. `cache` maps a path to a
    parse made from the same bytes; a miss parses. Returns node-link data, sorted."""

def _parse(path: Path, lang: str, cache: Optional[dict]) -> tuple[list[str], list[str], list[str]]:
    """(symbols, raw imports, script names) for one file, from the cache when its sha256 matches."""

def _script_edges(source_rel: str, names: list[str], tracked_py: set[str]) -> list[str]:
    """`RUNS` targets: for each string constant in a Python file that ends in `.py`: the constant itself if it is a
    tracked path; else `scripts/<constant>` if the constant has no `/` and that is a tracked path; else nothing."""

def run_map(verbose: bool = False, force: bool = False) -> dict:
    """Build from nothing, carry over the nodes the walk does not own, write the file, save the cache."""
```

`run_map`'s body becomes: load the cache; `graph = build_graph(root, cache)`; read the existing fixture only to copy
nodes whose `node_type` is not `CodebaseFile` or `Guardrail` and edges whose `edge_type` is not `IMPORTS` or `RUNS`
(and whose two ends still exist); write with `serialise`; save the cache; return the same `stats` keys as now
(`upserted` = files parsed, `unchanged` = cache hits, `edges`, `guardrails`, `purged` = 0). The incremental-skip
block, the two purge loops and every `kg.add_import`/`kg.upsert_file` call in `run_map` are deleted: there is
nothing to purge in a graph built from nothing. `_parse_python` additionally returns every `ast.Constant` string
ending in `.py`. `serialise(graph: dict) -> str` lives beside `build_graph`.

`scripts/local_knowledge_graph.py`: `upsert_file` drops the `last_modified` parameter and attribute;
`upsert_guardrail` drops `created_at`; `save()` writes through `map_codebase.serialise` (import inside the method, as
`run_map` imports this module). Callers: `grep -rn "last_modified=\|created_at" scripts agentsmith --include=*.py`
must print only lines in `scripts/mutation_check.py` and unrelated runtime modules (`agentsmith/compliance.py`,
`agentsmith/ops_contract.py`, `agentsmith/trace_redactor.py`, `agentsmith/dead_letter.py`, which use the words for
other things and are not touched).

`scripts/gate_kg.py`: `_dependents` yields the source of an edge whose `edge_type` is `IMPORTS` **or** `RUNS`.

`scripts/verify_system.py`: the staleness comparison in `check_kg_fresh` and in `check_kg` (the rest of `check_kg`,
its non-empty and known-node checks, stays) becomes: read the committed file's text;
`fresh = serialise(tracked_only(build_graph(root)))` with **no cache**; compare with
`serialise(tracked_only(json.loads(committed)))`; if they differ, print the first five differing nodes or edges, call
`run_map()` (the contract's "regenerating in place"), and fail. `tracked_only` is today's filter in `_kg_shape`
(tracked file nodes, guardrails whose `source_file` is tracked, edges whose two ends are tracked), returning
node-link data. `_kg_shape` is deleted; its long comment about tracked nodes moves to `tracked_only`.

Fixtures: delete `.agent-rfc/fixtures/knowledge_graph.json`, run `PYTHONPATH=. python3 -m agentsmith.cli gate kg
build`, commit the result and the rebuilt `.agent-rfc/fixtures/trace_graph.json`. Every `KG query:` hash changes once
(`RUNS` edges add dependents).

Documentation: `docs/process-gates.md`, section "The scope a review covered", gains a paragraph "What the graph does
not see" listing the four limits above with the pass-4 counts; the section "Limits, stated" gains one line pointing
at it by name.

### The independent oracle

**Two of them, for two halves.**

*Edges are right* — an extraction written in the test file that shares no code with `map_codebase`: for Python,
`ast.walk` over each file collecting `Import`/`ImportFrom`, resolved by trying, in order, `<root>/<a/b/c>.py`,
`<root>/<a/b/c>/__init__.py`, the same under the importing file's directory, the same under `<root>/scripts`; for
relative imports, from the importing file's package. For TypeScript, the generator below writes only
`import … from "./x"`, `export … from "./x"` and `await import("./x")` with explicit relative paths, which the test
resolves by path arithmetic.

*Incremental equals from nothing* — the same function called on a fresh copy: after each step, copy the tree to an
empty directory (no fixture, no cache), call `build_graph` there, and compare with the result of `run_map()` in the
original (which has the previous graph and the cache).

**The generator** (`scripts/test/test_kg_rebuild.py`; seeds `0..9`; each seed makes a repository of six Python files
and four TypeScript files in two directories plus `scripts/`, then applies 12 steps drawn from this list):

| Step | What it does |
|---|---|
| E1 | add an import of an existing file to an existing file |
| E2 | remove one import line (P4-R8) |
| E3 | rename a file, leaving its importers unchanged (their edges must go) |
| E4 | delete a file |
| E5 | add a new file that an existing, **unchanged** file already imports by name (its edge must appear) |
| E6 | replace `import x` with `from pkg import x` reaching the same file |
| E7 | change a file's bytes without changing its imports |
| E8 | TypeScript: swap `export … from "./a"` for `await import("./a")`, and the reverse |
| E9 | move a file from the root into `scripts/` while a file **outside** `scripts/` imports it by bare name |
| E10 | add and remove a string constant `"scripts/<name>.py"` (a `RUNS` edge) |
| E11 | corrupt the committed graph by adding an edge no file has, without touching any file |
| E12 | rewrite a file with the same bytes at a different time (`os.utime`), and with different bytes at the same time |

After **every** step: (a) `run_map()`'s file equals `serialise(build_graph(fresh copy))`; (b) the `IMPORTS` edge set
equals the independent extraction's; (c) running `run_map()` a second time changes no byte of the file.

**Why it does not share the fix's blind spot.** (a) compares against a tree with no history, so anything remembered
is visible; (b) compares against code that shares nothing with the builder; E5, E9, E11 and E12 are the cases an
"edges per changed file" fix gets wrong and a "clear the file's out-edges" fix (the review's suggestion) also gets
wrong for E5.

### Named tests

`scripts/test/test_kg_rebuild.py`:

| Test | Asserts | Mutant it must kill |
|---|---|---|
| `test_any_edit_sequence_builds_what_a_fresh_tree_builds` | (a), (b), (c) over the seeds | `run_map` starting from the existing graph's edges; the cache keyed by mtime instead of sha256 (E12); the cache also storing resolved edges (E5) |
| `test_the_generator_makes_every_step` | across the seeds each of E1–E12 ran at least once | a step removed from the list |
| `test_a_scripts_import_from_outside_scripts_resolves` | E9's edge, with the importer in another directory | the `scripts/` root dropped from resolution (P4-R12) |
| `test_export_from_and_dynamic_import_each_make_an_edge` | two files, one form each, separate targets | either form no longer read (P4-R12) |
| `test_the_graph_holds_no_clock_value` | no node of a built graph has `last_modified` or `created_at`; two builds a second apart are byte-equal | either attribute written again |
| `test_a_script_named_by_path_is_a_dependent` | `kg impact` on `scripts/tool.py` lists a file holding `"scripts/tool.py"` and one holding `scripts / "tool.py"` | `RUNS` not counted in `_dependents` |

`scripts/test/test_kg_drift_gate.py`: the `_kg_shape` tests are rewritten against `tracked_only` + `serialise`; add
`test_the_check_fails_on_an_edge_no_file_has` (the committed graph plus one invented edge between two tracked files
fails `check_kg_fresh`; mutant: the check building through `run_map` on the existing file) and
`test_a_check_on_a_current_graph_changes_no_file` (in a repository built by the test: `git status --short` is empty
after `check_kg_fresh`; mutant: any clock value). `test_shape_ignores_mtime` and
`test_shape_ignores_guardrail_created_at` are deleted with the attributes they describe; say so in the review record.

`scripts/test/test_knowledge_graph.py`: `test_walker_incremental_skip_and_purge` and
`test_a_graph_built_by_another_parser_is_parsed_again_whole` are replaced by the generated test (they assert the
mechanism being removed); `test_the_committed_graph_knows_who_imports_the_compliance_runtime` stays.

### Enforcement

- **Mechanical.** `.github/workflows/self-test.yml` already runs `python3 scripts/verify_system.py --check-kg` in the
  required job `Python scripts/runtime/examples`; with this change that step compares the committed bytes with a
  from-nothing, cache-less build, so a stale or hand-edited graph fails it. A tenant's CI gets the same through
  `.githooks/process-gate kg check`.
- **Mechanical.** The commit gate's `knowledge_graph: enforce` already recomputes each review's `KG query:` from the
  committed graph.
- **Judgment that remains.** None for the invariant. P4-R9's remaining limits (after A7: hooks, workflows and YAML
  that run scripts; dynamic imports; data files) are written where `kg impact` is documented. Whether they are
  acceptable needs no answer now: the owner chose the full suite at push (2026-11-26, B7 row 15), so they bear only on
  the per-commit feedback run and on review scoping, where CI's full run still catches a miss.

### Done means

1. `grep -n "add_import\|last_modified\|created_at\|has_node" scripts/map_codebase.py` prints nothing.
2. `grep -c "last_modified\|created_at" .agent-rfc/fixtures/knowledge_graph.json` prints 0, and the committed graph has
   no edge from `portal/proxy.ts` to `portal/lib/constantTime.ts` (the stale edge pass 4 named).
3. In a fresh clone, `python3 scripts/verify_system.py --check-kg && git status --short` passes and lists no file.
4. The edge count in the CHANGELOG is the number `--check-kg` prints, and the bullet names
   `test_any_edit_sequence_builds_what_a_fresh_tree_builds`.

## Invariant 4 — Verify where it will run

### The invariant

(a) A branch is pushed only after the test command (the full suite) passed in a copy of **the tree being pushed** (made from the
index before the commit) that is a git repository with one commit, no tags and no other history. (b) Every test function that exists in a
tracked test file is collected and run by the commands CI runs. (c) No test passes only because of this repository's
own history.

### Defects it closes

P4-R10's class (a test that needs a tag CI does not have), the portal test appended after `process.exit`, the suite
run before new files were tracked, and review records that quote a local count.

### Decisions

- The copy is made from the index with `git checkout-index`, not by cloning: it then contains exactly what the
  commit will contain, and it is stricter than CI's depth-1 checkout (one commit, authored at the epoch, subject
  `ci-tree`), so a test that reads this repository's subjects, tags or commit count fails there.
- CI's own run stays the authority. The stamp is a local pre-flight that stops a red push; `--no-verify` skips it and
  CI still runs the suite.
- **The stamp is required at push, not at every commit** (owner, 2026-11-23, decision 4). Measured on 2026-11-14:
  the full suite (`python3 -m pytest -q`) in a `--depth 1 --no-tags` clone of c7da273 had not finished after ten
  minutes on the owner's machine. A rule that costs ten minutes per commit would be bypassed; once per push is what
  the defect needs (each defect seen was a red CI run after a push).
- **At push, the full suite, in parallel; in CI, the full suite** (decision 4 as the owner revised it on
  2026-11-26). The stamp runs the configured command, `python3 -m pytest -q -n auto`, in the one-commit tree. The
  owner's test-time research (track C, local `test-time-research.md`) measured that KG-selected tests would have
  missed a needed test in 30 of 30 replayed commits (26 % of needed test files, while still running 67 % of the
  suite's time); the full suite in parallel took 211–220 s here, with no failures in three runs and a peak of 1.4 GB.
  The stamp is a pre-flight; CI's full run is the authority.
- **Not built (owner, 2026-11-26).** The test selection at push is dropped: there is no `--impacted` flag, no
  `verified_tree.select` or `verified_tree.always` key (either in a config is a config problem, "`<key>` is not a
  `verified_tree` key"), no cover rule, no commit A1b, and no K12 or K14 (those numbers stay unused). What A1 still builds from "Code changes"
  below: `FULL_SUITE_TRIGGERS`, `graphs_current`, `readers` and `select_tests`, for the per-commit feedback run
  (`--print-selection`) only, never for the stamp.
- **The stamp's command and CI** (owner, 2026-11-26). A1 adds `pytest-xdist` and `pytest-timeout` to
  `requirements.lock`, hash-pinned, writes AgentSmith's `verified_tree.command` as `python3 -m pytest -q -n auto`,
  and adds `-n auto` to CI's `python-behaviour` job. The lock line alone does not install xdist in the interpreter
  the stamp runs: when COMMAND holds `-n` and `xdist` is not importable by COMMAND's interpreter, `ci_tree.py` exits 2
  with "`-n` needs pytest-xdist in <interpreter>; install `requirements.lock` there, or drop `-n`". "Before every
  push" carries the report's condition: unload local models (`ollama stop`) before the stamp.
- **Mutations and reviews** (owner, 2026-11-26, adopting track C). Per commit: the hand mutants the review names,
  plus `mutation_check.py --allow-dirty --changed-since HEAD`. In CI: a pull request's curated-mutation shards run
  `--changed-since <base>`; the full curated run stays on pushes to `main` and the weekly schedule; the shards already install
  `requirements.lock` with `--require-hashes` (`self-test.yml`, before the mutation step), so `pytest-timeout` reaches
  them from the lock and `mutation_check.py`'s existing `--timeout=120` applies there. Reviews: the files to read come
  from the graph's closure of the change; lever Groups 1, 3 and 6 are always reviewed, and every group when the
  change touches `scripts/process_gate.py`, `agentsmith/cli.py` or a hook. B1 writes this into
  `docs/validation-checklist.md` Step 1; it changes no gate code.
- **The graphs are current before every push** (decision 4), wherever the repository's `knowledge_graph` mode is not
  `off`, whether or not `verified_tree` is on (its own function on the push routes, below). A push cannot change its commits, so "rebuilt before every push" is enforced as "the
  committed graphs are builds from nothing of the tree being pushed, or the push is refused"; "complete" means A7's
  `RUNS` edges and the limits written in Invariant 3. A tenant made by `tenant init` or `tenant adopt` has
  `knowledge_graph: off`, so its first push is not refused for a graph it has not built. The trace graph is checked
  only where the repository tracks `.agent-rfc/fixtures/trace_graph.json` (a tenant has none: `trace_graph.py` reads
  AgentSmith's own files). This needs A6 (a build from nothing that holds no clock value); A6 comes before A1.
- The rule is switched on per repository by a new config key, off by default, so tenants are unaffected.

### Code changes

**`scripts/ci_tree.py`** (new; standard library only, and so is what it imports for `graphs_current`: A6's
`build_graph`, `tracked_only` and `serialise` work on plain dicts and import no `networkx`, which the pre-push
process does not have; `test_graphs_current_runs_without_networkx` calls `graphs_current(root, "HEAD")` on a small
`tmp_path` repository with `networkx` made unimportable, and it returns without `ImportError`; mutant: `build_graph`
through `AgentKnowledgeGraph`):

```python
def untracked_tests(root: Path) -> list[str]:
    """`git ls-files --others --exclude-standard` filtered to basenames matching test_*.py, *_test.py, *.test.ts."""

def gated_digest(root: Path, is_gated: Callable[[str], bool], treeish: Optional[str] = None) -> str:
    """sha256 over the sorted lines "<mode> <blob> <path>" of the gated files in the index (`git ls-files -s`),
    or, with `treeish`, in that commit (`git ls-tree -r <treeish>`). The two sources give the same lines for the
    same content, so a stamp made before `git commit` matches the commit it became."""

def export(root: Path, target: Path, links: Sequence[str], treeish: Optional[str] = None) -> None:
    """treeish None: git checkout-index --all --prefix=<target>/ (the index); a treeish: the same command with
    GIT_INDEX_FILE=<a temporary file> after `git read-tree <treeish>` into it (not `git archive`, which honours
    `export-ignore` and `export-subst`). Then: git init -q -b main ; git add -A --force (a tracked file matching
    .gitignore stays);
    git -c user.name=ci-tree -c user.email=ci-tree@example.invalid commit -q --date=1970-01-01T00:00:00Z -m ci-tree ;
    then symlink each existing <root>/<link> to <target>/<link>."""

def main(argv) -> int:
    """ci_tree.py [--link PATH]... [--no-stamp] -- COMMAND...  |  ci_tree.py --print-selection
    --print-selection: print, one per line, the pytest files of `select_tests` for the index (kind impacted), or,
    when the kind is full, only the changed pytest files that exist in the index (a deleted test file is not printed), with "full: <reason>" on stderr; it exits non-zero when `select_tests` fails, and the per-commit line then stops; nothing runs and no stamp
    is written. It is per-commit feedback, never a gate (`test_print_selection_prints_changed_files_when_full`).
    1. untracked_tests(root) non-empty -> print them, exit 2 ("stage them or delete them: CI will not see them").
    1b. when is_pytest_command(COMMAND) and COMMAND holds `-n` (an argv word equal to `-n` or `--numprocesses`, or
       starting with `-n` or `--numprocesses=`) and `xdist` is not importable by COMMAND's interpreter: exit 2, naming
       the interpreter, before the export; nothing runs.
    2. export to a temporary directory; run COMMAND there with CI unset and AGENTSMITH_CI_TREE=1.
    3. unless `--no-stamp` (the per-commit feedback runs), write <git dir>/agentsmith/ci-tree.json: {digest,
       command, selection, ran, exit, at}, so a per-commit run never replaces the push stamp (fields under
       "The per-commit selection"); the last line printed, with or without `--no-stamp`, is `ci-tree <first 12 of
       digest> <kind> <n or all> exit <code>`, the one format B2's `Ran on:` reads. What a run writes (as
       `selection.kind` and as the label): `collect 0` when it holds `--co` or `--collect-only`; else `run <n>` when it names test paths (a tracked
       file, or a node id `<tracked file>::<name>`) or carries a selecting option (`-k`, `-m`, `--lf`, `--ff`,
       `--deselect`), `<n>` being the paths named or `all`; otherwise `full all`. `ci_tree.py` reads no config. The
       push gate, which compares the stamp's `command` with the effective configured command anyway, treats a
       stamp of kind `run` whose command equals it as `full` (so a configured command that names files can satisfy
       a push). Otherwise only a `full` stamp can; `run` and `collect` lines serve `Ran on:`.

**A pytest command** (one predicate, `is_pytest_command(argv)`, used by `--print-selection`, the Python collection check and
the `-n` check): the first word's basename is `pytest`, or is `python`, `python3` or `python3.<N>` followed by
`-m pytest`. Its interpreter is that first word when it is a Python; when the first word's basename is `pytest` (bare, or a path
such as `.venv/bin/pytest`): resolve it with `realpath` (looked up on PATH only when it contains no `/`) and take
`python`, else `python3`, from that directory (not its shebang, which pip writes as `/bin/sh` for
long paths); if neither exists, the Python check is skipped and `ci_tree.py` prints why. Any other command (`uv run
pytest`, `npm test`) is not one: the Python collection check is skipped and `ci_tree.py` prints that it was.
    4. exit with COMMAND's code."""
```

**The per-commit selection** (built in A1 for `--print-selection` only; the stamp runs the configured command
whole). The selection is filtered to pytest files: only `test_*.py` and `*_test.py` under `pytest.ini`'s `testpaths`
(TypeScript files are never printed; a TypeScript suite runs whole).

```python
FULL_SUITE_TRIGGERS = ("conftest.py", "pytest.ini", "pyproject.toml", "setup.cfg", "requirements*.txt",
                       "requirements.lock", "package.json", "package-lock.json", ".github/workflows/*")

def graphs_current(root: Path, treeish: Optional[str]) -> Optional[str]:
    """None, or the sentence naming the stale graph. Exports `treeish` (None: the index) with `export`, builds the
    knowledge graph there from nothing and, where the tree tracks `.agent-rfc/fixtures/trace_graph.json`, the trace
    graph (`trace_graph.py --check` run in the export). The knowledge-graph comparison is A6's `check_kg_fresh`
    comparison (both sides `tracked_only`, serialised the same way, the nodes the walk does not own carried over from
    the committed graph) without its `run_map()` repair. Writes nothing in `root`."""

def readers(root: Path, treeish: Optional[str], path: str) -> list[str]:
    """Tracked `.py` files of the tree whose text contains `path`, or a parent directory of it written as a string
    ending in "/" or as a quoted directory name (`".agent-rfc/reviews"`), excluding the file itself."""

def select_tests(root: Path, graph: dict, base: Optional[str], treeish: Optional[str] = None,
                 graphs_problem: Optional[str] = None) -> Selection:
    """Selection(kind="impacted"|"full", tests=[...], reason=...), for the index (treeish None) or a commit.
    changed = files that differ between `base` and the tree (`git diff --name-only --no-renames base [treeish]`),
    deleted files included. kind="full", naming the reason, when: `base` is None (no upstream and no default branch
    to measure from); a changed path matches FULL_SUITE_TRIGGERS (by basename or by glob); a changed path is deleted
    (its importers are no longer its dependents in the new graph); `graphs_problem` (the caller's one
    `graphs_current` result) is not None; or a changed path is not a `CodebaseFile` node and `readers` finds none
    ("no file names <path>").
    Otherwise kind="impacted" and tests = every pytest file (above) in the transitive closure of
    `gate_kg._dependents` (the one hop rule A7 widens to `RUNS`, applied until nothing is added) from the changed
    files that are nodes and from the readers of those that are not, plus every changed pytest file. An empty list
    is kind="impacted", tests=[]: `--print-selection` prints nothing (the per-commit line then runs `--co`)."""
```

The rule for paths the graph has no node for is closed: a record, a document or a data file selects the tests that
reach a file naming it; a path nothing names selects everything. In AgentSmith this is honest about its cost:
every gated commit adds a review record and a CHANGELOG bullet, `scripts/process_gate.py` names both, and most of the
suite depends on `process_gate.py`, so a gated commit's feedback run covers most of the suite.

`base` is `git merge-base @{upstream} HEAD`, else `git merge-base origin/<default> HEAD` (the default branch found
as in Invariant 2), else None. **Which graph:** `--print-selection` reads the index's copy
(`gate_kg.staged_graph`) and does not call `graphs_current` (a per-commit feedback run is not worth an export and a
build; the push checks the graphs). The stamp records `{digest, command, selection: {kind}, ran, exit, at}`, where
`command` is `shlex.join(COMMAND)` as `ci_tree.py` received it (it reads no config), and `ran` is what was executed.
The gate compares `shlex.split(stamp.command)` with `shlex.split(<the effective configured command>)`. A stamp passes
for `HEAD` when its digest is `HEAD`'s, `exit == 0`, its command is the effective configured command, and its kind
is `full` (or `run` with that command, above).

Default links: `node_modules` beside every tracked `package.json` that has one in the working tree (in AgentSmith:
`portal/node_modules`, `scripts/test/gha_oracle/node_modules`; in a ts-react tenant: `node_modules`). The stamp is read and written through
two new functions in `scripts/gate_history.py`, `record_ci_tree(root, digest, command, selection, ran, code)` and
`last_ci_tree(root)`, beside `record_gates_run`/`last_gates_run`, which they copy in shape.

**`scripts/process_gate.py`**: `Config` reads `"verified_tree": {"mode": "off"|"report"|"enforce", "command":
"<text>"}` (default mode `off`; any other shape, `select` and `always` included, is a config problem). `command` defaults to `extends.test_command`; the **effective command**
is the one after that default, and it is what the stamp and `gate-modes-kept` compare. The
collection check runs before COMMAND: the Python check when COMMAND is a pytest command, the TypeScript check whenever
the tree tracks a `package.json`. A new function:

```python
def tree_verified_problem(root: Path, config: Config) -> Optional[str]:
    """None when the rule is off, or when the last ci_tree run passed, with the effective configured command, on
    the gated files HEAD holds. Otherwise the sentence to print."""
```

The graph check is not inside it: a separate function, `graphs_current_problem(root, config) -> Optional[str]`,
runs on the same two push routes before it, wherever `knowledge_graph` is not `off`, whatever `verified_tree` is. It
calls `ci_tree.graphs_current(root, "HEAD")` once and returns its sentence with "— run `agentsmith gate kg build`
and commit it". Under `knowledge_graph: enforce` the push is refused; under `report` the sentence is printed and the
push allowed, as every other `report` mode does. An unknown `knowledge_graph` value becomes a config problem in
`Config.problems` (today `kg_mode` takes any string). `tree_verified_problem` then
computes `ci_tree.gated_digest(root,
config.is_gated, "HEAD")` and requires `gate_history.last_ci_tree(root)` to exist with that digest, `exit == 0`, the
same command (`shlex.split`, above) and a `full` kind (above);
otherwise it returns "the test command has not passed on the tree being pushed — run `python3 scripts/ci_tree.py
-- <command>`". In `report` mode the sentence is
printed and the push is allowed. `import ci_tree`
goes inside the function, after the mode check, so a repository with the rule off never loads it. It has exactly two
callers, the two routes a push takes: `cmd_sweep` when `report_only` is false (what `.githooks/pre-push` runs), and
`cmd_push_decision` (gate contract 3's `push`). In both, a non-`None` answer is printed and makes the push refused.
It is **not** called from `sweep()` itself, which also runs at session start and at stop.
Records and `.md` files are not gated, so writing the review after the run does not invalidate the stamp; any change
to a gated file after the run does.

**`.agenticframework/process-gates.json`**: add `"verified_tree": {"mode": "enforce", "command": "python3 -m pytest -q -n auto"}`.

**`.github/workflows/self-test.yml`**: no checkout change. (The job `python-behaviour` already checks out a pull
request's merge ref at depth 1 without tags; pass 4 reproduced P4-R10 exactly there.)

**`portal/test/scripts.test.ts`** gains one test (below).

### The independent oracles

- For (a): the export is made by git from the index, not by the code under test; the test for it stages one file,
  leaves another unstaged, and asserts which exists in the export.
- For (b), Python: the test file's own `ast` scan of test files against pytest's collector, two unrelated readers of
  the same files. Portal: the source text against the script list, as `portal/test/scripts.test.ts` already does.
- For (c): no static list of git commands (that would be a spelling list). The oracle is behaviour: the suite must
  pass in the one-commit tree, and a pinned test keeps CI's job from being given more history.

### Named tests

`scripts/test/test_ci_tree.py` (each builds its own repository with `tmp_path`):

| Test | Asserts | Mutant it must kill |
|---|---|---|
| `test_the_export_is_the_index_not_the_working_tree` | a staged file is present, an unstaged edit is absent, an untracked file is absent | export by copying the working tree |
| `test_the_export_has_one_commit_and_no_tags` | in a repository with three commits and a tag: `git rev-list --count HEAD` is 1 and `git tag` is empty in the export | export by `git clone` |
| `test_an_untracked_test_file_stops_the_run` | exit 2, the file is named, the command did not run | `untracked_tests` returning `[]` |
| `test_the_stamp_names_the_gated_files_it_ran_on` | the digest changes when a gated staged file changes and does not when a `.md` file does | the digest over all files; over none |
| `test_a_push_requires_a_passing_stamp_for_this_tree` — with `_make_repo`, a bare repository as its remote, and the real `.githooks/pre-push` | `git push` is refused with no stamp, with a failing stamp, with another tree's stamp, with another command's stamp; allowed with the right one; and a stamp made before `git commit` still matches after it | each of the four comparisons removed (four mutants); the digest computed differently for the index and for `HEAD` |
| `test_both_push_routes_apply_the_rule` | `process_gate.py sweep` (exit 1) and the contract-3 `push` decision (`deny`) both refuse without a stamp; `sweep --report` does not | the call removed from either route |
| `test_a_test_that_reads_this_repositorys_history_fails_in_the_tree` | a sample test running `git describe --tags` in its repository root fails under `ci_tree.py` | export keeping tags |
| `test_the_selection_follows_dependents_to_any_depth` — generated repositories: import chains of length 1 to 4 from a test file to the changed module, one `RUNS` edge (A7), and an unrelated test, over five seeds | the selected list equals the reachable set computed by a breadth-first walk written in the test over the generated edges (not `lkg`), plus changed test files | one hop only; `RUNS` edges ignored; changed test files left out |
| `test_each_trigger_selects_the_full_suite` — one case per entry of `FULL_SUITE_TRIGGERS`, written as a list in the test, plus a changed path nothing names, a deleted module, a stale graph and no base | `kind == "full"` and the reason names the case | one mutant per entry (each removed in turn), the readers check removed, deletions not a trigger, the staleness check removed |
| `test_a_path_the_graph_has_no_node_for_selects_its_readers` — a changed `docs/x.md` named by one test file and a changed `.agent-rfc/reviews/y.md` whose directory is named by one module | the test naming the file, and the tests depending on the module, are selected; nothing else | `readers` returning `[]` (everything goes full); parent directories not matched |
| `test_only_pytest_files_are_printed` — a change under `portal/lib` reached by a `.test.ts` and a `test_*.py` | `--print-selection` prints the `.py` file only | the pytest filter removed |
| `test_print_selection_prints_changed_files_when_full` | `--print-selection` prints the selected files for kind impacted, only the changed pytest files that still exist for kind full (a deleted one is left out), nothing for an empty selection (the per-commit line then runs `--co`), and exits non-zero when `select_tests` fails | the full case printing every file; an empty selection printing a placeholder |
| `test_a_parallel_command_without_xdist_stops_before_running` | for each spelling (`-n auto`, `-n4`, `--numprocesses 2`, `--numprocesses=2`), an interpreter without xdist gives exit 2 naming it, and the command does not run; with xdist it runs | the check removed; one spelling not recognised |
| `test_graphs_are_compared_in_the_export_not_the_working_tree` — an unstaged edit that would change the graph | `graphs_current(root, "HEAD")` is None and no file in `root` changes | built from the working tree; the fixture rewritten |
| `test_a_stale_graph_refuses_the_push` — with the real `.githooks/pre-push`, `knowledge_graph: enforce`, with `verified_tree` `enforce` and with it off | a push whose committed knowledge graph, or trace graph, differs from a fresh build is refused, naming the file, in both; with `knowledge_graph: report` it is allowed with the sentence printed; with `knowledge_graph: off` the same push is not refused for it; `knowledge_graph: "on"` is a config problem | either comparison removed; the check gated on `verified_tree`; the check run with `knowledge_graph` off |
| `test_only_the_configured_full_run_satisfies_a_push` | a passing stamp of kind `collect`, or `run` with another command, is refused; `run` with the configured command and `full` are allowed | the kind not checked; `run` accepted whatever its command |

`scripts/test/test_collection.py`:

| Test | Asserts | Mutant it must kill |
|---|---|---|
| `test_every_test_function_is_collected` | run `python3 -m pytest --collect-only -q` once; for every tracked file under `pytest.ini`'s `testpaths` whose name matches `test_*.py`, every module-level `def test_*` and every `test_*` method of a `Test*` class found by `ast` appears in the collected ids. A name defined twice in one file is a failure of its own ("the second definition replaces the first") | a duplicated test name; a file renamed so pytest does not match it |
| `test_no_test_file_lives_where_pytest_does_not_look` | `git ls-files` has no `test_*.py` or `*_test.py` outside `testpaths`, except the paths in `OUTSIDE = {…}` written in the test with a reason each (fill it from the first run; scaffold templates are expected) | a test file added under another directory |
| `test_the_behaviour_job_checks_out_as_a_pull_request_does` | in `.github/workflows/self-test.yml`, job `python-behaviour`'s `actions/checkout` step has no `fetch-depth` and no `fetch-tags` | `fetch-depth: 0` added to suit a test |

`portal/test/scripts.test.ts`:

| Test | Asserts | Mutant it must kill |
|---|---|---|
| `no test file has code after its exit` | for each `*.test.ts`: take the last line matching `^(if \(.*\) )?process\.exit\(` (column 0); every later line is blank or starts with `//` | a `test(...)` appended below `process.exit` (verify by appending one to a copy) |

The existing test there, "no test file is left out of npm test and npm run test:db", already covers the script list.

**TypeScript (owner, 2026-11-23, decision 13).** `scripts/collection_check.py`, written in **A1** with the Python
check, checks TypeScript as well. `ci_tree.py` runs it before COMMAND whenever the tree has a tracked `package.json`
(not only for a pytest command), and runs the Python check when COMMAND is a pytest command. The unit is the file: a TypeScript test's names are strings, which a parser in another language
would read by spelling. For a `package.json` whose `devDependencies` or `dependencies` name `vitest`, the collected
files are `npx --no-install vitest list --filesOnly --json`; for `jest`, `npx --no-install jest --listTests --json`
(never a fetch from the registry: sovereign-first, and the template's own form); and every tracked
`*.test.ts`, `*.test.tsx`, `*.spec.ts` or `*.spec.tsx` outside `node_modules` must be in that list. Any other runner,
or none, is a note: "TypeScript collection not checked: no runner it can ask (vitest or jest)", never a pass
(`outage-is-not-a-finding`). The exit rule above applies to every such file in a tenant as in the portal. Go gets the
lever only: `go test` compiles every `_test.go` file in a package, so a file it does not see fails the build.
Tests, in `scripts/test/test_ci_tree.py`: `test_a_typescript_test_file_the_runner_skips_stops_the_run` (a generated
vitest project with an `include` pattern that misses one of three test files: exit 2, that file named; mutant: TS
not checked) and `test_an_unknown_typescript_runner_is_a_note_not_a_pass` (mutant: the note dropped).

### Enforcement

- **Mechanical.** The push hook refuses a push whose `HEAD` has no passing stamp for its gated files
  (`verified_tree: enforce`), on both push routes. Wherever `knowledge_graph` is not `off`, whatever
  `verified_tree` is, both routes also refuse a push whose
  committed graphs are not builds from nothing of `HEAD`.
- **Mechanical.** `test_every_test_function_is_collected` and the portal rule run in required checks.
- **Mechanical.** CI's `python-behaviour` job is the depth-1, tagless run; a pinned test keeps it so.
- **Judgment that remains.** A test that needs only one commit of this repository passes in the tree. The reviewer
  checks new tests that call `git` use a repository made under `tmp_path`. This is the one eyeball rule here.

### Done means

1. The push stamp, `python3 scripts/ci_tree.py -- <the configured command>`, passes on the pushed head, and its
   last line is `ci-tree <12 hex> full all exit 0`. Each gated commit's `Ran on:` quotes that commit's own per-commit
   line (any of the three kinds) with its own tree's digest.
2. `git push` is refused without it (try it once against a scratch remote, record the refusal text).

## Invariant 5 — Claims cite their test

### The invariant

Every bullet a commit adds to `CHANGELOG.md` has a line in that commit's review record that quotes the bullet's
opening words and names either a test that exists in the commit, or a stated reason there is none. Every closed list
the code decides by (roles, allowed calls, range rules, authored objects, agent actions) is mutated one entry at a
time by the curated harness, generated from the list itself.

### Defects it closes

P4-R13 (three wrong statements), the review record's "the untrusted roles" (one of six), and P4-R12's method gap.

### Code changes

**The claims rule — `scripts/process_gate.py`.** `Config` reads `"claims": "off"|"report"|"enforce"` (default
`off`), parsed exactly as `knowledge_graph` is. A new function, called from `check_change` **before** the
`if not gated:` shortcut, because `CHANGELOG.md` is not a gated path and a commit that only adds bullets must be
judged too. It runs when `added` is not `None`. Its review text is what the commit's `Review:` trailer resolves to
through `record_text`, or the empty string when there is no trailer or it does not resolve (then every added bullet
is unclaimed, and the problem says "add a `Review:` trailer naming the record that holds `## Claims`"). Its problems
join both returns of `check_change`: `enforce` → errors, `report` → notes prefixed `claims (report):`.

```python
_CLAIM = re.compile(r'^- "(?P<quote>[^"]{12,})" — (?:test: (?P<tests>`[^`]+`(?:, `[^`]+`)*)|no test: (?P<why>\S.*))$', re.M)

def claim_problems(added: List[Tuple[str, str]], review_text: str, read: Reader, changelog: str) -> List[str]:
    """Each bullet this commit adds to the changelog is claimed in the review's `## Claims` section."""
```

- A bullet is an added line of the changelog file that starts with `- `. Its text is the line without `- `, with
  `*` and backticks removed and runs of spaces collapsed.
- The `## Claims` section of the review (read with `_section(review_text, "Claims")`) holds lines of the form
  `- "<quote>" — test: ` + one or more backticked ids, or `- "<quote>" — no test: <reason>`.
- A bullet is covered when some claim's quote, normalised the same way, is a prefix of the bullet's text.
- A test id is `<path>::<name>`. It resolves by `gm.test_id_resolves(test_id, read)`, written in B2 (one
  resolver, used by claims and by the sign-off's `Oracle:` line): when `read(path)` is not `None` and the file
  contains `def <name>(` (a `.py` path) or the string `"<name>"` (any other path). An id that does not resolve is a
  problem naming it.
- Problems: a bullet with no claim ("names no test: add a line under `## Claims`"); an unresolved id; a claim line
  whose quote matches no added bullet (a stale claim).
- `no test:` claims are returned as notes in every mode, so CI lists them as it lists `n/a` escapes.

`.agenticframework/process-gates.json`: add `"claims": "enforce"`.

**A trap, for commits 1 and 2.** `scripts/test/test_process_gate.py` builds `FIXTURE_CONFIG` from this repository's
real config and turns `knowledge_graph` off for its fixture repositories. Add, on the next lines,
`FIXTURE_CONFIG["verified_tree"] = {"mode": "off"}` (commit 1) and `FIXTURE_CONFIG["claims"] = "off"` (commit 2), or
every test that commits in a fixture repository starts failing for a reason it is not about. The tests of the two
new rules set the mode they need.

**The mutation sign-off — same function family.** When `claims` is `enforce`, the sign-off's `Mutation-checked:`
line must be `no — <reason>` or `yes — ` followed by suite names, each of which appears as `name="<suite>"` in
`scripts/mutation_check.py` as the commit carries it. A name that is not a suite is a problem. (Free text such as
"yes, the untrusted roles" no longer parses.)

**Per-entry mutants — `scripts/mutation_check.py`.**

```python
@dataclass(frozen=True)
class ClosedList:
    """A list the code decides by. One mutant per entry, made from the file's current text."""
    name: str            # suite name, e.g. "list_untrusted_roles"
    path: str            # file holding the list
    start: str           # the text that opens the literal, e.g. "_UNTRUSTED_ROLES = ("; found exactly once
    entries: str         # regex with one group matching each entry inside the literal
    tests: tuple[str, ...]

def list_suites(lists: tuple[ClosedList, ...]) -> tuple[Suite, ...]:
    """For each list: find `start`, read to the bracket that closes it, find every entry; for each entry build
    Mutation(name=f"{list.name}: without {entry}", before=<the literal's text>, after=<the same text with that one
    entry's line or item removed>, expect=1). A list whose literal is not found, or that yields no entry, raises."""

CLOSED_LISTS = (
    ClosedList("list_untrusted_roles", "scripts/security/runners/agent_workflow.py", "_UNTRUSTED_ROLES = (",
               r'"([A-Z_]+)"', ("scripts/test/test_agent_workflow_injection.py",)),
    ClosedList("list_authored_objects", "scripts/security/runners/agent_workflow.py", "_AUTHORED = (",
               r'"([a-z_]+)"', ("scripts/test/test_agent_workflow_injection.py",)),
    ClosedList("list_agent_actions", "scripts/security/runners/agent_workflow.py", "_AGENT_ACTIONS = (",
               r'"([^"]+)"', ("scripts/test/test_agent_workflow_injection.py",)),
    ClosedList("list_exact_calls", "scripts/security/gha_expression.py",
               "_EXACT_CALLS: dict[str, Callable[[list], Any]] = {", r'"([a-z]+)":',
               ("scripts/test/test_gha_expression.py",)),
    ClosedList("list_range_rules", "scripts/process_gate.py",
               "RANGE_RULES: Tuple[Tuple[str, Callable[..., List[str]]], ...] = (", r'\("([a-z-]+)",',
               ("scripts/test/test_range_verdict.py",)),
)
```

The generated suites are appended to the catalogue the harness already runs (`--list` shows them; the four CI shards
deal them like any other). `test_the_allow_list_is_exactly_these_five` and
`test_the_role_list_is_githubs_untrusted_roles_and_one_more` would kill every such mutant alone, which proves
nothing about behaviour; so for a generated suite the harness runs its tests with
`-k "not exactly_these and not list_is_"` (one constant, `LIST_PIN_FILTER`, used only by `list_suites`). Each entry
must then be killed by a behavioural test: that is the point.

**Documentation.** `docs/validation-checklist.md` Step 4 gains the `## Claims` form and the `Mutation-checked:` form.
`docs/process-gates.md` gains a section "Claims" after "The scope a review covered", with the mode table.

**The corrections (P4-R13)** in `CHANGELOG.md`, third-pass section: "weakens `.agenticframework/process-gates.json`"
becomes `.agenticframework/compliance.json`; the edge-count sentence is replaced by the count invariant 3 produces;
"CI refuses what the commit hook refuses" is replaced by the range statement of invariant 2. The preview's
known-limits paragraph gains P4-R7 and what remains of P3-R4 and P4-R9, and loses what this design closes.

### The independent oracle

- For the claims rule: `git show` of the commit is the source of the bullets and the file tree is the source of the
  tests; the review record (the thing under test) supplies neither.
- For the lists: the mutants are generated from the file's own literal at run time, so the list of mutants cannot be
  shorter than the list. A test in the harness's own suite compares the number of generated mutants with
  `len()` of the imported object.

### Named tests

`scripts/test/test_claims.py`:

| Test | Asserts | Mutant it must kill |
|---|---|---|
| `test_a_changelog_bullet_without_a_claim_is_refused` — through `check_change` with `claims: enforce` | error names the bullet | the rule not called from `check_change` |
| `test_a_claim_naming_a_test_that_does_not_exist_is_refused` — a missing file; a file without that function; a `.ts` file without that title | error names the id | resolution by path only |
| `test_a_claim_for_no_added_bullet_is_refused` | stale claim reported | the reverse check removed |
| `test_no_test_is_allowed_and_listed` | accepted, and a note is returned | notes dropped |
| `test_each_route_applies_the_rule` — the hook (`git commit` in `_make_repo`), `process_gate.py ci`, and `sweep` | all three refuse the same commit | the rule added to one route only |
| `test_mutation_checked_must_name_suites_that_exist` | `yes — nosuch` refused; `yes — list_untrusted_roles` accepted; `no — docs only` accepted | the suite lookup removed |

`scripts/test/test_mutation_check_lists.py`:

| Test | Asserts | Mutant it must kill |
|---|---|---|
| `test_each_closed_list_yields_one_mutant_per_entry` | for each `ClosedList`, the number of mutants equals `len()` of the object imported from its module; each mutant's `after` lacks exactly one entry | `list_suites` returning the first entry only |
| `test_a_list_that_cannot_be_found_is_an_error_not_an_empty_suite` | a wrong `start` raises | returning `()` (`test-that-cannot-fail`) |
| `test_the_generated_suites_are_in_the_catalogue` | `--list` output includes every `ClosedList.name` | the append removed |

### Enforcement

- **Mechanical.** The commit hook, CI and the sweep refuse a commit that adds a changelog bullet without a resolving
  claim (`claims: enforce`).
- **Mechanical.** The required check `Curated mutations` runs one mutant per list entry; a surviving entry is red.
- **Mechanical.** `Mutation-checked:` names suites the gate looks up.
- **Judgment that remains.** Whether the named test proves the sentence. The gate proves the test exists and is
  named; a reviewer reads the pair. Numbers in a bullet (counts) are covered only by Done-means lines that say which
  command printed them.

### Done means

1. This design's own commits each pass the claims rule from the commit that introduces it onward.
2. `python3 scripts/mutation_check.py list_untrusted_roles list_exact_calls list_range_rules list_authored_objects
   list_agent_actions` reports every mutant caught; the output's last line is in the review record.

## Small items

### P4-R6 — the audit write delays only a real account's fifth failure

`portal/proxy.ts`: change `export async function proxy(request: NextRequest)` to
`proxy(request: NextRequest, event: NextFetchEvent)` (import the type from `next/server`) and replace the
`await appendAuditEvent(...).catch(...)` in the `signIn?.lockedNow` branch with
`event.waitUntil(appendAuditEvent({...}).catch(() => undefined));`. The 401 is then returned without waiting, on
every path. Do not add a delay or a dummy write to other paths.

Test, in `portal/test/proxy.test.ts` (which reads the source, since `proxy.ts` imports Next): between the line
containing `basicSignIn(` and the line containing `"Authentication required."` there is no `await`, and
`event.waitUntil(appendAuditEvent(` appears once. Mutant: the `await` restored. Stated limit in the test's comment:
this is a source check; the timing itself is not measured.

### P4-R7 — the lockout can be used against a known account

No code. `docs/UserManual.md`, the portal sign-in section, and the CHANGELOG's known-limits paragraph say: anyone
who knows an account name can keep it locked with five wrong passwords every fifteen minutes; a locked account is
answered exactly as a wrong password is, with no `Retry-After`; the only signal is one `session_denied` audit event
per window; a portal reachable from the internet should use SSO. Claim line: `no test: documentation of a limit`.

## Out of scope

- **How an approval is bound to what it approves** (the rest of P3-R4) is not designed here. The owner put it in
  4.1.0 (decision 5) as its own design, `.agent-rfc/designs/approval-binding.md`, because it changes what the owner
  types at a terminal. This design depends on it (see "Dependencies"); A5 is built after it.
- **Running workflows on GitHub to confirm the runner's behaviour.** The oracle is GitHub's library, not its runner.
- **Edges from hooks, workflows and YAML to the scripts they run; dynamic imports; parent packages; data files**
  (the rest of P4-R9). Documented as limits. Making non-source files nodes is a separate design.
- **The trace graph** (P4-R11's other half) beyond rebuilding its fixture: the owner decided on 2026-11-14 to keep
  it committed, and c7da273 already made it a function of the tree.
- **`agentsmith/cli.py` in Part A**: its `--force` flag keeps working. (Part B adds one verb and the tenant defaults there.)
- **Other repositories' reusable workflows.** Not read.
- **Mixed-type comparisons, `format` and `toJSON` as exact operations.** They can be added to the table later, one
  at a time, each proved by the oracle test.

## Risks

- **False reds from invariant 1.** A guard written with `format(...)`, `toJSON(...)`, a number compared with a
  string, or `success() && <owner test>` no longer counts and the field is reported. (`success() && G` is still
  certainly false for an outsider, because `G` is: `&&` with a false side is false. Only guards that *rely* on the
  unknown part fail.) Every string input of a `workflow_call` workflow that reaches an agent is reported, including
  ones a tenant considers trusted; the remedies are the three refactors in A4 (a number, a choice made in the caller,
  no event text at all), with the owner's warning that an agent fetching the text itself moves the injection out of
  the check's sight. The runner's own failure message (`agent_workflow.py`, "let the agent fetch it as data") is
  changed in A4 to name the three refactors and that warning.
  An `if:` written as a YAML block (`if: |` or `if: >`) that wraps its condition in `${{ }}` ends in a newline, is
  "text around an expression", and no longer counts as a guard; written without `${{ }}`, or with `|-`, it does.
  The profile is a preview; the CHANGELOG lists these as newly failing.
- **False reds from invariant 2.** (1) An approval committed before the weakening's range is refused: the fix is to
  commit them together. (2) With several merge bases the rules run against each; a criss-cross history can be refused
  where one base would pass. (3) A tenant whose CI checks out shallow now fails closed instead of checking the head
  only; the message names the fix. (4) The hook refuses a commit that removes the config.
- **Cost of invariant 4.** A push runs the full suite with `-n auto` (about 3.5 minutes here, 16 serial); CI runs it
  every time. A push that changes no gated file since
  the last stamp needs no new run.
- **The per-commit feedback run can miss a test** (the owner's research report: 26 % of needed test files after A7 and
  the closure). It is feedback, not a gate: the push stamp and CI run the full suite, so a miss costs nothing but a
  later red stamp.
- **False reds from invariant 5.** Every CHANGELOG bullet needs a claim line from the commit that turns the rule on.
  Older bullets are not checked (added lines only).
- **CI time.** The oracle: one Node process and roughly 50,000 evaluations, expected under 30 seconds, plus
  `npm ci` of one package. The K × S table: about 160 small repositories with real hooks, a few seconds each; mark
  the test so it can be split across the existing job if it passes two minutes. The edit-sequence test: 10 seeds × 12
  steps × two builds of a ten-file tree, seconds. Per-entry mutants: about 20 more mutants across four shards.
- **The dependency.** `@actions/expressions` is pre-1.0 and its README says it is one of several implementations.
  It is pinned exactly with a lock file, installed with `--ignore-scripts`, used only in a test job, and wherever it
  and the runner might differ this design returns `UNKNOWN`. If the package is withdrawn, the test fails loudly in CI
  (it cannot skip there); the fallback is to vendor its test data, a separate decision.
- **Every `KG query:` hash changes once** when the graph is rebuilt with `RUNS` edges.

## Order of work, and done means

One commit per row, one session per commit. Each commit carries `Design: .agent-rfc/designs/invariants-not-instances.md`
and `Review: .agent-rfc/reviews/invariants-not-instances.md` with a new pass and sign-off.

| # | Commit | Contents |
|---|---|---|
| 1 | `feat(gate): tests run on the pushed tree before a push` | invariant 4: `scripts/ci_tree.py`, stamp, push rule, `select_tests`, `readers` and `graphs_current` (`select_tests` for `--print-selection` only), `pytest-xdist` and `pytest-timeout` in the lock, `-n auto` in CI, `scripts/collection_check.py` (Python and TypeScript), portal exit rule, config key, `Ran on:`'s digest comparison |
| 2 | `feat(gate): a changelog bullet names its test` | invariant 5: claims rule, `Mutation-checked` rule, `ClosedList` and the three lists that exist today (`_UNTRUSTED_ROLES`, `_AUTHORED`, `_AGENT_ACTIONS`) **with the tests that kill their mutants** (the three role tests and `test_an_author_guard_counts_for_each_authored_object` from invariant 1's table), docs, P4-R13 corrections |
| 3 | `fix(security): the guard evaluator answers only what it models` | invariant 1: evaluator, oracle package and harness, CI step, tests, `list_exact_calls` |
| 4 | `fix(security): a reusable workflow's text inputs are untrusted` | P4-R3, `test_a_guard_that_depends_on_the_run_so_far_is_not_a_guard`, contract cases |
| 5 | `fix(gate): ci judges a range by its two ends` | invariant 2: `transition_errors`, `_range`, K × S test, `list_range_rules`, workflow option |
| 6 | `fix(kg): the graph is built from nothing` | invariant 3: `build_graph`, cache, check, fixtures rebuilt, tests |
| 7 | `feat(kg): a script named by path is a dependent` | P4-R9: `RUNS` edges, limits documented, fixtures rebuilt |
| 8 | `fix(portal): the lockout audit does not delay the answer` | P4-R6, P4-R7, known-limits paragraph |

**Build order (owner, 2026-11-23):** 6, 7, 1, 2, 3, 4, then `approval-binding`'s commit, then 5, 8. The rows keep
their numbers so that "A6" means the same commit everywhere. A6 and A7 come first because the push (1) refuses
committed graphs that are not builds from nothing (6), and "complete" means the `RUNS` edges (7). Commit 1 then comes before 2–5 so each later commit is verified where it will run;
commit 2 before 3 so every later CHANGELOG bullet is held to its test. Until 1 lands, A6 and A7 are verified with
the hand-typed export below.

**Before every commit, in this order. Each must exit 0. Do not continue past a failure.** (Revised 2026-11-23 from
the owner's test-time research: the full staged-tree suite runs once per push, in the stamp, not per commit; the
per-commit mutation run is the changed suites, not a hand-picked list. `ci_tree.py --print-selection` (A1) prints
`select_tests`' list for the index without running anything. The report's review scoping is adopted (owner,
2026-11-26) as a reading rule in `docs/validation-checklist.md` Step 1, written by B1 (Invariant 4, "Mutations and
reviews"); it changes no gate code.)

```bash
git add -A                                                     # everything the commit will contain; nothing else
git status --short | grep '^??' && echo "STOP: untracked files"   # must print nothing
PYTHONPATH=. python3 -m agentsmith.cli gate kg build           # then `git add .agent-rfc/fixtures`
python3 -m pytest -q <changed test files + the test files `gate kg impact --staged` lists>      # feedback, B1–A7
sel="$(python3 scripts/ci_tree.py --print-selection)" && python3 scripts/ci_tree.py --no-stamp -- python3 -m pytest -q ${sel:---co}   # from A1: the selected tests, or collection only when none; its last line is this commit's `Ran on:`
python3 scripts/ci_tree.py --no-stamp -- sh -c 'cd portal && npm test'   # only when portal/** is staged
python3 scripts/mutation_check.py --allow-dirty --changed-since HEAD   # plus each hand mutant the review names
# write the review's pass and sign-off now, with `KG query:` left blank, then rebuild (the trace graph holds passes)
PYTHONPATH=. python3 -m agentsmith.cli gate kg build && git add .agent-rfc/fixtures .agent-rfc/reviews
PYTHONPATH=. python3 -m agentsmith.cli gate kg impact --staged # paste its hash as `KG query:`, then `git add` the review
git commit                                                     # through the hooks; never --no-verify
python3 scripts/process_gate.py ci --base origin/main --head HEAD
```

**Before every push:** unload local models (`ollama stop <model>`), then `python3 scripts/ci_tree.py -- <the
configured command>` (the stamp; the full suite). Records and graph fixtures are not gated, so the rebuild after the
review does not change the gated digest and does not invalidate a stamp. For B1, B2, A6 and A7, before
`scripts/ci_tree.py` exists, run its equivalent by hand:

```bash
T="$(mktemp -d)" && git checkout-index --all --prefix="$T/" && cd "$T" && git init -q -b main && git add -A \
  && git -c user.name=ci-tree -c user.email=ci-tree@example.invalid commit -q -m ci-tree \
  && python3 -m pytest -q
```

For commit 3 onward, once before the first run: `(cd scripts/test/gha_oracle && npm ci --ignore-scripts)`.

**After pushing**, the pull request's required checks are the last word: `Python runtime behaviour tests
(Postgres-backed)` is the depth-1, tagless run. A commit is done when its section's "Done means" list is true, its
named mutants were each applied by hand and killed (list them in the review record, one line per mutant), and every
required check is green on the pushed head. A local green alone is not done.

# Part B — the framework carries the invariants

Part A fixes release 4.1.0. Part B puts the five invariants and the anti-patterns into the framework, so every
design and build in AgentSmith and in every tenant starts with them. Same reading rule as Part A: do the commits in
order, make the decisions written here, and stop and ask where this document leaves something open. The owner
answered B7 on 2026-11-23, and rows 15–16 on 2026-11-26; row 17 is open, and it blocks only a possible guard
exemption in A4.

Everything named below was read at c7da273: `templates/agent-rules.yaml` (pillars, `records`, `skills`),
`templates/governance.json`, `scripts/gate_models.py` (`Registry`, `Records`, `Signoff`, `check_pillars`,
`check_signoff`), `scripts/process_gate.py` (`Config`, `check_design`, `check_review`, `cmd_session_start`),
`scripts/gate_pillars.py` (`parse_policy`, `transition_problems`), `agentsmith/machine/governance.py` (`design_new`),
`agentsmith/architectures.py` (the scaffold design), `agentsmith/cli.py` (`_process_gates_config`, `GATE_HOOKS`,
`install_gate_hooks`, `_gate_kg`), `agentsmith/adopt.py`, `agentsmith/sync.py` (`plan_sync`, `describe`),
`scripts/generate-ide-config.py`, `scripts/test/test_context_budget.py`, `workflow-templates/`,
`.github/scratch-tenants/` and `contract/gate/v3/`.

## B1 — Design time, every repository

### Pillar placement: strengthen P4, P13, P14 and P15; add no pillar

Why not a seventeenth pillar. A repository's registry is the provider's file (`"registry": "provider"`), read from
the installed framework and **not** at the commit being checked (`Config.doc_text`). `check_pillars` refuses a design
that does not answer every pillar whose `check` holds `design`. So the day a tenant's machine or CI installs a
framework with P17, every active design it has becomes "INCOMPLETE, unlocks nothing", every edit in those scopes is
denied, and every commit citing such a design fails, without the tenant having chosen anything. The only switch the
gate has for "this repository predates a requirement" is all-or-nothing: `registry` declared or not
(`PRE_REGISTRY_SECTIONS`, `config.registry_declared`). The `pillars` policy (`parse_policy`, `transition_problems`)
governs the mechanical checks and the evidence rule, not which pillars exist. There is no per-pillar "since".

Why strengthening is safe. A design answers a pillar by its number. Changing a pillar's `design_question` and `rule`
changes what new designs are asked and what every rule file says; it changes no parsing, so no existing answer stops
resolving. The four pillars already own these subjects: P4 the tests, P13 the gates, P14 derived files, P15 unknown
values.

What then makes the invariants **required** is not the pillar text but the `## Invariants` section below, switched on
per repository by a key in its own config, which is read at the commit.

### The text, word for word (`templates/agent-rules.yaml`)

Replace each `design_question` with the one given. **Append** each sentence to the end of the pillar's existing
`rule`; do not rewrite what is there. Set `meta.version` to `"1.1.0"`.

- **P4 Testing Guardrails**
  - `design_question`: "Which tests fail before and pass after; which independent oracle and generated cases check each invariant; and which lists get one mutant per entry?"
  - appended to `rule`: "Test the property, not the reported example: expected values come from an oracle that shares no code with the fix, over generated cases. A list is mutation-checked one entry at a time. Tests run on the tree that will be pushed, and every claim names its test."
- **P13 Gate Integrity**
  - `design_question`: "Does any check, threshold, exemption or allowlist get weaker; is every unprovable control split into proven half plus declared gap; and does every route to each verdict call one rule on the whole before-and-after state?"
  - appended to `rule`: "Every route to a verdict calls one rule, judged on the state before and the state after, never step by step. A check never compares a result with the path that produced it."
- **P14 Fixture and Baseline Drift**
  - `design_question`: "Which baselines, goldens or fixtures does the change make stale, which projection does each pin, and is each derived file rebuilt from nothing and compared with a from-nothing build?"
  - appended to `rule`: "A derived file is rebuilt from nothing, never added to, holds no clock value, and is checked against a from-nothing build."
- **P15 Ambiguous Signals**
  - `design_question`: "What does each new result read as when the check did not run, and which closed list of cases gives a definite answer, with everything else unknown?"
  - appended to `rule`: "Answer definitely only from a closed list of cases modelled exactly; everything else is unknown by default, never by a list of exceptions."

Size: the five additions (these four and the `design_start` line below) are about 900 characters, about 225
estimated tokens. Measured at c7da273 with `render_files`: the largest rule file is `GEMINI.md` at 2,607 of the 3,000
tokens `scripts/test/test_context_budget.py` allows, so 393 remain. If that test fails after the change, shorten
these sentences; do not raise `RULE_FILE_TOKENS`.

### A new design section, `## Invariants`

Decision: yes, a section, and it is **not** added to `records.design_sections` in the registry (that list is the
provider's and would hit every tenant at once, exactly as a new pillar would). It is required by a new key in
`.agenticframework/process-gates.json`:

    "invariants": "off" | "report" | "enforce"        (default "off"; parsed as `knowledge_graph` is)

The form (the gate parses this; the skeleton writes it):

    ## Invariants

    - I1 — <a property a test can check, in one sentence>
      - oracle: <what the test compares with, and why it shares no code with the change>
      - cases: <the generator's case families; never "the reported example">
      - enforcement: <the hook, gate check or CI step that fails when this is skipped>

or, for a change that alters no behaviour, the single line `none — <why>`.

`scripts/gate_models.py`, beside `check_signoff`:

```python
_INVARIANT = re.compile(r"^- I(\d+) — (\S.*)$")
_INVARIANT_PART = re.compile(r"^  - (oracle|cases|enforcement): (\S.*)$")
_NO_INVARIANTS = re.compile(r"^none — (\S.*)$")

def check_invariants(section: str | None) -> tuple[list[str], list[str]]:
    """-> (errors, notes). The '## Invariants' section of a design."""
```

Rules, each one an error with the item's label:
1. the section is missing;
2. it has neither an `I<n>` item nor the `none — <why>` line, or it has both;
3. items are not numbered 1, 2, 3 in order;
4. an item lacks one of the three parts, or has one twice;
5. a `cases:` part whose text, lower-cased, is exactly one of `the reported example`, `the example`, `n/a`, `none`,
   `todo`; an `oracle:` or `enforcement:` part that is `n/a`, `none` or `todo`;
6. any line in the section that starts with `- ` or `  - ` and matches none of the patterns (so a mistyped item is
   named, not dropped, as `check_pillars` does for pillar lines).

`none — <why>` is accepted and returned as a note, so CI lists it as it lists `n/a` escapes.

`scripts/process_gate.py`: `Config` reads the key into `self.invariants_mode`. `check_design` gains a parameter
`invariants: str = "off"`; when it is `report` or `enforce` it calls `gm.check_invariants(_section(body,
"Invariants"))`. In `enforce` the errors join the design's errors. In `report` they are returned to the caller as
notes prefixed `invariants (report):`. Every caller of `check_design` passes `config.invariants_mode`; find them with
`grep -n "check_design(" scripts/*.py agentsmith/*.py agentsmith/machine/*.py` and list them in the review record
(at c7da273: `check_change`, `active_designs`, `design_summary`).

**Older designs.** The mode is read from the config at the commit, so history is judged by the rule of its day. A
design with `status: done` is only checked when a commit cites it. In a repository that turns the key on, a design
still `active` needs the section before its next commit; `report` mode lists each such design at session start
(below), which is the repository's list of what to fix before it moves to `enforce`.

**The mode only strengthens.** A fifth entry in Part A's `RANGE_RULES`, added in commit A5:
`("gate-modes-kept", _gate_modes_kept)`. For each key in `("invariants", "claims")`, and for `verified_tree`'s
`mode`, with the order `off < report < enforce` (`gp._STRENGTH`): a value at the after-state weaker than at the
before-state is "`<key>` would weaken from 'enforce' to 'report'", unless an `Approval:` trailer cites a fresh
approval bound to that change (`_bound`, with `Change("gate-modes-kept", CONFIG + "#<key>", <before>, <after>)`), as
for the declaration. More weakenings are held the same way: `knowledge_graph` moving down
(`enforce` → `report` → `off`; K15), since decision 4's graph check at push stops where it is off; and a change of
the effective command (`verified_tree.command`, or `extends.test_command` where `command` is absent; a narrower command makes the stamp trivial, and
whether a new command is narrower cannot be told from its text, so every change needs the owner). The command rule
applies only when `verified_tree.mode` at the before-state is not `off` and the before-command is not None: turning
the stamp on with a command for the first time, or editing `extends.test_command` while the stamp is off, is not a
weakening of anything held. An absent key is
`off`. Part A's table gains K11 (`invariants` `enforce` → `report`: refuse), K13 (`command` changed: refuse; with a
bound approval: allow; the stamp turned on with a command for the first time: allow) and K15 (`knowledge_graph`
`enforce` → `off`: refuse; with a bound approval: allow); `test_the_allow_list…`-style pin tests are untouched. (The
numbers K12 and K14 are left unused: they named the selection keys, which are not built.)

### What writes and says it

- `agentsmith/machine/governance.py`, `design_new`: after the `## Approach` block and before `## Pillars`, write

      ## Invariants

      - I1 — TODO: a property a test can check
        - oracle: TODO
        - cases: TODO
        - enforcement: TODO

      <!-- One item per invariant. An oracle shares no code with the change; cases are generated, not the
           reported example; enforcement is a hook, gate check or CI step. Or the one line: none — <why>. -->

  `TODO` is refused by rule 5, so the skeleton is rejected until someone answers it. Written in every repository,
  whatever its mode.
- `agentsmith/architectures.py`, the tool-written scaffold and adoption design: add, before `## Pillars`,
  `## Invariants` with the line `none — a generated scaffold changes no behaviour; every file is checked against
  .agenticframework/scaffold.json`. Without it a new tenant's arming commit is refused by its own gate.
- `scripts/process_gate.py`, `cmd_session_start`: in line 1, when `config.invariants_mode != "off"`, the section list
  becomes `## Problem / ## Approach / ## Invariants / ## Pillars / ## Deviations / ## Dependencies / ## Levers`, and
  one sentence is added after "Answer every pillar.": "State each invariant with its oracle, generated cases and
  enforcement." In `report` mode the "Active designs" line marks a design that fails `check_invariants` as
  `<path> — invariants (report): <first error>`. `test_the_session_start_message_stays_within_its_budget` (1,200
  tokens) is the size check.
- `templates/agent-rules.yaml`, `records.design_start`: insert as the third line (after "Answer EVERY pillar…"):
  "State the change's invariants in `## Invariants`: each a property a test can check, its independent oracle over
  generated cases, and the gate that enforces it. Fixing the reported example is not done."

### Named tests — `scripts/test/test_invariants_section.py` (new)

| Test | Asserts | Mutant it must kill |
|---|---|---|
| `test_a_complete_section_passes_and_each_fault_is_named` — one good section, and one section per rule 1–6 made by a table of edits written in the test | no error; the error for that rule | each rule's branch removed (six mutants) |
| `test_the_skeleton_is_refused_until_answered` | `design_new` output fails `check_invariants`; replacing every TODO passes | `todo` dropped from rule 5 |
| `test_the_scaffold_design_passes_under_enforce` | the design `architectures.py` writes passes `check_design(..., invariants="enforce")` | the `none —` line removed from the scaffold |
| `test_each_mode_on_each_route` — `off`, `report`, `enforce` × hook (`git commit` in `_make_repo`), `process_gate.py ci`, `sweep`, and the pre-edit check | off: silent; report: allowed with the note; enforce: refused | the parameter not passed by one caller |
| `test_a_repository_without_the_key_is_judged_as_before` | a config with no `invariants` key and a design with no section: allowed, no note | the default changed from `off` |

## B2 — Review and sign-off time

### A new lever group — `docs/review-levers.md`

Heading: `## 11 · Invariants, not instances **(+ new group, 2026-11-15, from the 4.1.0 review)**`. Eight levers.
(Group 11: `143ac82` on `main` added Groups 8, 9 and 10; owner, 2026-11-23, decision 15.)
Each is marked `**(2026-11-15)**`; none is `(unevidenced)`: each caught a pass-4 finding, named in its note.

- `allow-list-not-deny-list` — A definite answer comes only from a closed list of cases modelled exactly; everything else falls through to unknown or refused. A list of exceptions is the next bypass.
- `independent-oracle` — What a test or check compares with shares no code and no path with the thing checked.
- `generated-not-reported` — Cases come from a generator that names its families; the reported example must be one of its outputs, never the test.
- `judge-the-ends` — A before-and-after rule reads the state before and the state after; no step in between changes the verdict.
- `rebuild-dont-add` — A derived file is rebuilt from nothing and compared with a from-nothing build; it holds no clock value.
- `each-entry-mutated` — "The list was checked" means one mutant per entry, each killed by a behavioural test.
- `collected-and-counted` — Every test function written is collected and run by the command CI runs; nothing sits after an exit, under a duplicate name, or untracked.
- `claim-names-its-test` — Every sentence about behaviour in a changelog or record names the test that proves it; a count names the command that printed it.

Overlap, checked against the 105 slugs on `main` at `cdf04e1` (55 at c7da273, and the 50 `143ac82` added), and
what is **reused instead of added**:

| Anti-pattern (Part A) | Lever |
|---|---|
| 1, 2 spelling lists, deny-lists | new `allow-list-not-deny-list` (`guards-must-be-able-to-fail` asks whether a guard can fail, not how it defaults) |
| 3 one route fixed | existing `grep-for-siblings`, `one-verdict`, `implemented-not-invoked`; no new lever |
| 4 test built from the example | new `generated-not-reported` (`test-that-pins-a-defect` is about pinning wrong behaviour) |
| 5, 6 expected values from the code; compared with its own path | new `independent-oracle` (`gate-integrity` asks whether a check can fail; `test-the-contract` asks what is asserted on) |
| 7, 11 fetch more history; run before `git add` | existing `environment-parity`, `run-the-gates-ci-lists`; no new lever |
| 8 claims without tests | new `claim-names-its-test` (`docs-match-behaviour` says docs must match; this says how it is shown) |
| 9 a list said to be checked | new `each-entry-mutated` |
| 10 tests after the exit | new `collected-and-counted` (`test-that-cannot-fail` covers a test that runs and cannot fail; this one never runs) |
| invariant 2 | new `judge-the-ends` |
| invariant 3 | new `rebuild-dont-add` (`fixture-truth` is about fixtures proving "not mock") |
| `143ac82`'s `fix-the-class-not-the-case` | reused, no new lever: it names the kind and lists the other routes; `generated-not-reported` and `allow-list-not-deny-list` say how the kind is then tested and coded, which it does not |
| `143ac82`'s `prove-it-fails-first` | reused for "fails before, passes after"; it does not ask for an oracle independent of the fix (`independent-oracle`) |
| `143ac82`'s `outage-is-not-a-finding` | reused for a check that could not run (the TypeScript note, the stamp's fall-back reason); `allow-list-not-deny-list` is about a case not modelled, a different unknown |
| `143ac82`'s `identity-not-label` | reused for `Ran on:` (a digest of the tree, not a branch name) and for approval binding |

In the same commit, because tests require it: a section per new slug in `docs/review-lever-notes.md` under
`## Group 11 · Invariants, not instances` (`scripts/test/test_lever_notes.py`: every non-legacy lever has notes), each
note naming the finding that evidenced it (P4-R1 and R2; P4-R8; P4-R12; P4-R4; P4-R8 and R11; the role mutants; the
portal test after its exit; P4-R13); and a counterpart per slug in `docs/design-review-checklist.md`
(`scripts/test/test_design_and_validation_docs.py::test_every_lever_has_a_design_phase_counterpart`).

### `docs/design-review-checklist.md` — new section `## Group 11 · Invariants, not instances — before you call it a fix`

It goes after the Group 10 section and before the section on keeping the file in step with `review-levers.md`.

One bullet per slug, in that file's build-time voice. The text:

- **`allow-list-not-deny-list`** — Write the table of cases you model exactly first; make "not in the table" the last line of the function.
- **`independent-oracle`** — Before the code, name what the test will compare with. If it is your own function, a copy of it, or a value you computed by reading your code, find another.
- **`generated-not-reported`** — Write the generator's families in the design. Add the reported example to a regression table only after the generator produces it.
- **`judge-the-ends`** — For each rule that compares before and after, write its two inputs. If one of them is "a commit", "a step" or "an event", it is the wrong input.
- **`rebuild-dont-add`** — For each file you derive, write the function that builds it from nothing; a cache may hold only what depends on one input's bytes.
- **`each-entry-mutated`** — For each list the code decides by, plan one mutant per entry and the behavioural test that kills it.
- **`collected-and-counted`** — New tests go where the CI command looks; stage them before you run; nothing goes below a file's exit.
- **`claim-names-its-test`** — Draft the changelog bullet with its test beside it. No test, no bullet, or say `no test:` and why.

### `docs/validation-checklist.md`

Step 2 gains items 5–8: "5. **Each invariant has an oracle test over generated cases** (`independent-oracle`,
`generated-not-reported`). 6. **Each list the code decides by has one mutant per entry** (`each-entry-mutated`).
7. **The suite ran on the tree being pushed** — `agentsmith gate tree -- <test command>`; quote its last line
(`collected-and-counted`, `run-the-gates-ci-lists`). 8. **Each changelog bullet has its `## Claims` line**
(`claim-names-its-test`)." Step 4's block (which lists Groups 1–10 since `143ac82`) gains, under the Group 10 line,
the three lines below, and the note "Groups 8–11 are checked by the gate where `invariants` is on".

### Sign-off

Decision: `records.signoff` in the registry is **unchanged** (it is the provider's list; a new group there would
refuse every tenant's next review; owner, 2026-11-23, decision 14: in code, behind `invariants`). The additions are a
constant in `scripts/gate_models.py`, required by `check_review` only when the repository's `invariants` mode is
`enforce` (in `report`: notes). `check_review(text, registry, adopted)` (c2583ff) gains three keyword parameters:
`read` (a reader of the commit, for `Oracle:`), `invariants` (the mode) and, in A1, `digest: Optional[str]` (the
commit's `gated_digest`, for `Ran on:`). At c2583ff its callers are `check_change` and `stop_problems`.
`check_change` gains the same `digest` parameter: `commit_verdict` computes it from the index, `check_commits` from
each commit; `stop_problems` (a mid-session check of the working tree) passes `digest=None`. `None` skips the digest
comparison, never the parse. Find every caller with `grep -n "check_review(\|check_change(" scripts/*.py
agentsmith/*.py` and list them in the review record.

**Which sign-off is read.** A record holds one `## Sign-off` per batch of passes (`run-token-limits.md` has three),
and `check_signoff` reads the **first** (`_signoff_section`, `re.search`). Groups 8–11, `Oracle:` and `Ran on:` are
read from the **last** `## Sign-off` section: B2 adds `_last_signoff_section(text)` beside it. So are the two
existing lines that change per commit: `Mutation-checked:` (A2's rule) and `KG query:` (`kg_problems` searches the
last section, not the whole text; so does `review_summary`, which feeds the dev record's `kg_query`, so the record
and the gate report the same hash). Groups 1–7 and the other fields keep today's reading. For a record with one
sign-off nothing changes; a record with several was, until now, judged on its first. Test:
`test_the_last_signoff_is_read_for_the_new_lines` (a record with two sign-offs; for each of `Ran on:`,
`Mutation-checked:` and `KG query:`, the first section stale and the last current: allowed; reversed: refused;
mutants: the first section read, one per line).

```python
GATED_SIGNOFF = (
    ("Security engineering", ()),          # Groups 8-10: 143ac82's groups, checked (owner, decision 15)
    ("Regulation & compliance", ()),
    ("Code optimisation", ()),
    ("Invariants, not instances", ("Oracle", "Ran on")),
)
```

    Group 8 · Security engineering        [x] checked  [ ] n/a  [ ] gap: ____
    Group 9 · Regulation & compliance     [x] checked  [ ] n/a  [ ] gap: ____
    Group 10 · Code optimisation          [x] checked  [ ] n/a  [ ] gap: ____
    Group 11 · Invariants, not instances  [x] checked  [ ] n/a  [ ] gap: ____
    Oracle:                    `<test id>`[, `<test id>`…]   or   n/a — <why>
    Ran on:                    ci-tree <12 hex> <kind> <n or all> exit 0        or   n/a — <why>

- Each group line is checked exactly as groups 1–7 are: by its number (`check_signoff` matches `^\s*Group <n>\b`),
  one box ticked, `gap:` needs its text. The numbers run from `len(registry.records.signoff.groups) + 1`: 8 to 11
  with the provider's seven. The names in `GATED_SIGNOFF` are for the error message only, written as
  `docs/validation-checklist.md` Step 4 writes them.
- `docs/validation-checklist.md`'s sentence "The gate checks only Groups 1–7, …" becomes: "The gate checks Groups
  1–7 everywhere, and Groups 8–11 with the `Oracle:` and `Ran on:` lines where the repository's `invariants` mode is
  on; the fields it checks are `Tests added`, `Mutation-checked`, `Fixtures re-pinned` and `Gates run`." (B2.)
- Every review written after B2 lands carries Groups 8–11 where `invariants` is on, AgentSmith's own included.
- `Oracle:` — each backticked id is `<path>::<name>` and resolves by the same rule as a claim's test (Part A,
  invariant 5). One resolver function, `test_id_resolves(test_id, read)`, written **in B2** in
  `scripts/gate_models.py` (B2 comes before A2, which needs it for claims), and called by A2's claims rule.
- `Ran on:` — B2 parses the line and accepts `ci-tree <12 hex> <kind> <n or all> exit 0`, where `<kind>` is one of
  `full`, `run`, `collect` (Invariant 4, `main` step 3), or `n/a — <why>`.
  **A1** adds the comparison (it needs `gated_digest`, which A1 builds): `scripts/ci_tree.py` prints that line last;
  the gate recomputes `gated_digest(root, config.is_gated, <the commit, or the index in the hook>)[:12]` and requires
  equality and `exit 0`. This is checkable in CI as well as locally. Stated limit: the digest can be computed without
  running anything; the line proves which tree is claimed, and CI's own run proves the tests.
- **Per commit, not the push stamp.** From A1 every gated commit's `Ran on:` names a `ci_tree.py` run on that
  commit's own staged tree. Any command satisfies it; the per-commit list uses its feedback run (the tests
  `--print-selection` names, or `pytest --co`, collection only, when it names none), so a commit costs that run,
  not the full suite. The kind and count in the line describe that run. The push stamp is separate (Invariant 4) and
  is the one that runs the configured command, once per push, as decision 4 put it.
- From A1: `n/a — <why>` on either line is accepted only when the design's section is `none — <why>`; otherwise it
  is an error. (B2 to A7 accept it; see B6.)

Tests, in `scripts/test/test_invariants_section.py`: `test_the_signoff_additions_are_asked_only_where_the_mode_is_on`
(off: a seven-group sign-off passes; enforce: it is refused naming each of Groups 8–11, `Oracle` and `Ran on`;
mutants: the mode check removed, and each of the four groups dropped from `GATED_SIGNOFF` in turn), `test_ran_on_is_parsed` (B2: a malformed line refused, both accepted forms pass; mutant: the
parse skipped), `test_ran_on_must_be_this_trees_digest` (**A1**: another tree's digest refused, in the hook and in
`ci`; mutant: the comparison removed), `test_an_oracle_id_that_does_not_resolve_is_refused` (mutant: resolution by
path only).

## B3 — Mechanical enforcement in tenants

### What reaches a tenant, and how

A tenant carries no copy of the gate (3.0.0): its hooks and CI ask the provider. So Part A's code reaches a tenant
when the provider is upgraded; what is **on** there is decided by the tenant's own config.

| Mechanism | How it reaches a tenant | On by |
|---|---|---|
| Range verdicts (invariant 2) | part of `process_gate.py ci`, the hook and the sweep; no key | the upgrade. It is a fix of the gate, not a mode. Newly refused: an approval older than the range, or recorded for another change; an unreadable base in a shallow clone; a commit that removes the config without a bound approval; turning `knowledge_graph` (or any held key) down without a bound approval (K15); a weakening inside a merge commit, in the sweep and in head-only CI |
| `## Invariants`, sign-off Groups 8–11 | `check_design`, `check_review` | `invariants` |
| Claims | `claim_problems` | `claims`, and only for the file `changelog.file` names |
| Push stamp | `tree_verified_problem` in the two push routes; `.githooks/pre-push` is already one of `GATE_HOOKS`, installed and armed by `install_gate_hooks` from `tenant init`, `tenant adopt` and `sync` (sync adds a missing one and says so) | `verified_tree` |
| `scripts/ci_tree.py` | a new verb, `agentsmith gate tree -- <command>`: `agentsmith/cli.py` adds `"tree"` to the `gate` parser's `event` choices and runs `[sys.executable, str(scripts / "ci_tree.py"), *options, "--", *command]`, where `options` are the `--no-stamp` and `--link` arguments given before `--`, as `_gate_kg` runs its scripts | always available |
| Collection check | `scripts/collection_check.py` (written in A1; see Invariant 4), `uncollected(root, python) -> list[str]`: it runs `<python> -m pytest --collect-only -q` in the export with COMMAND's interpreter (never the framework's `sys.executable`, which lacks a tenant's packages): the interpreter `is_pytest_command` names (Invariant 4); any other command skips the check and says so; without `pytest.ini` `testpaths`, the files are pytest's defaults (`test_*.py` and `*_test.py` under the rootdir) (the `ast`-against-`pytest --collect-only` comparison of Part A, moved here; AgentSmith's `test_collection.py` calls it). `ci_tree.py` runs the Python check when `is_pytest_command(COMMAND)` and the TypeScript check whenever the tree tracks a `package.json` (Invariant 4, `Config`), and exits 2 naming each uncollected function or file | with the push stamp. Python and TypeScript (vitest or jest, by file; owner, 2026-11-23, decision 13; see Invariant 4); Go compiles its tests and gets the lever; stated in `docs/process-gates.md` |
| Per-entry mutation | the lever `each-entry-mutated`, P4's rule, and the sign-off line. `scripts/mutation_check.py` and `CLOSED_LISTS` are AgentSmith's own catalogue and are not a tenant's | — |

`Mutation-checked:` in a repository with no `scripts/mutation_check.py` in the commit: `yes — ` must be followed by
at least one backticked test id that resolves (`test_id_resolves`); `no — <why>` as before. (Part A's suite-name
rule applies where the file exists.)

**AgentSmith-internal, not for tenants:** `scripts/test/gha_oracle/` and `@actions/expressions` (the oracle for
SEC-CIAGENT-001 only); `CLOSED_LISTS`; the K × S and edit-sequence tests; `test_collection.py`'s `OUTSIDE` list. A
tenant gets the principle (`independent-oracle`, the `oracle:` line) and chooses its own oracle.

### The keys, in `.agenticframework/process-gates.json`

    "invariants":    "off" | "report" | "enforce"
    "claims":        "off" | "report" | "enforce"
    "verified_tree": {"mode": "off" | "report" | "enforce", "command": "<text>"}

`verified_tree` gains `report` (Part A had off and enforce): the push is allowed and the sentence is printed as a
warning. `command` defaults to `extends.test_command` when that is declared; with `mode` not `off` and neither
present, the config is a problem ("`verified_tree` needs a `command`"). Unknown keys and values are config
problems. All three keys, `verified_tree`'s effective command, and `knowledge_graph`, are held by `gate-modes-kept`
(K11, K13, K15; B1, "The mode only strengthens").

### Defaults per onboarding path

`agentsmith/cli.py`, `_process_gates_config(stack, session_start=None, gated=None, existing=False)`:

| Path | `invariants` | `claims` | `verified_tree` | Why |
|---|---|---|---|---|
| `tenant init` (a new repository) | `enforce` | `enforce` | `{"mode": "enforce", "command": TEST_COMMAND_BY_STACK[stack]}` | nothing exists to be refused; the owner's aim is on from the first commit |
| `tenant adopt` (`existing=True`, passed by `agentsmith/adopt.py`) | `report` | `report` | `{"mode": "report", "command": …}` | an existing codebase sees what would be refused without being stopped; the same reasoning the function's docstring gives for `artifacts`, `pillars` and `knowledge_graph` (owner, 2026-11-23, decision 10) |
| `agentsmith sync` (an existing tenant) | not written | not written | not written | a sync adds nothing a repository did not ask for (`plan_sync`'s rule); absent means `off` |

**A changelog from day one** (owner, 2026-11-23, decision 9). For `tenant init` only, `_process_gates_config` also
writes `"changelog": {"file": "CHANGELOG.md", "paths": <the stack's GATED_BY_STACK globs>}`, and `tenant init`
writes `CHANGELOG.md` when the repository has none: a title line and `## [Unreleased]`, nothing else. An existing
`CHANGELOG.md` is left as it is. `tenant adopt` and `sync` write neither (an existing repository declares its own).

**A passing test in every scaffold** (owner, 2026-11-23, decision 12: keep `enforce`). `tenant init` writes, when the
path is absent, one test per stack that checks the scaffold it made: every file `.agenticframework/scaffold.json`
lists exists. Each is written inside the stack's gated globs, so the stamp's digest covers it:

- `python-fastapi`: `test/test_scaffold.py` (standard library and pytest only; `test/**` is gated).
- `go`: `internal/scaffold/scaffold_test.go` (package `scaffold`, `encoding/json`, `os`, `path/filepath` only),
  reading `../../.agenticframework/scaffold.json` (the test runs in its package directory). When there is no
  `go.mod`, init writes one: `module <tenant id>` and `go 1.22`, a fixed floor, so init needs no Go installed.
- `ts-react`: the test goes in `lib/` (gated for the stack, and outside a stock Vite `tsconfig.app.json`'s
  `include: ["src"]`, so the template's `tsc -b` does not type-check a file that reads `node:fs`). With a
  `package.json` naming `vitest`: `lib/scaffold.test.ts` importing from `vitest` (vitest strips types; it does not
  type-check). Naming `jest`: `lib/scaffold.test.js`, CommonJS with `require("node:fs")`, which jest runs with no
  TypeScript transform. Naming neither: `lib/scaffold.test.mjs` using `node:test`; when `scripts.test` is absent,
  or is npm's default (`echo "Error: no test specified" && exit 1`), init sets it to `node --test
  lib/scaffold.test.mjs` (a file by name: Node 21 and later do not take a directory); when another `test` script
  exists init leaves it, says the scaffold test runs only under `node --test`, and the first push runs the tenant's
  own command.
- `ts-react` with **no** `package.json`, or with none of the lock files the tenant CI template accepts
  (`package-lock.json`, `npm-shrinkwrap.json`, `pnpm-lock.yaml`): init stops before writing anything, with "a
  ts-react tenant needs its `package.json` and lock file first — create the app, then run `tenant init`". A
  `yarn.lock` or `bun.lockb` stops it by name: "the ts-react CI template does not support yarn or bun yet".
- For a vitest or jest `package.json` (a "neither" project runs `node --test` and needs no `node_modules`): when the
  runner cannot be run (no `node_modules`), init stops: "install the project's dependencies (`npm ci` or
  `pnpm install`), then run `tenant init` again"; it never writes a test it could not check (`outage-is-not-a-finding`).
- After writing a vitest or jest test, init asks the runner whether it collects the file (`npx --no-install vitest
  list --filesOnly --json`, or `npx --no-install jest --listTests --json`). A runner config whose `include`, `roots`
  or `testMatch` leaves `lib/` out stops init: "the scaffold test at <path> is not collected by <runner>; add
  `lib/**` to its includes, then run `tenant init` again", and the test file is removed. The tenant CI template
  (`workflow-templates/ci-ts-react.yml`) requires a lock file and runs `tsc`, so a scaffold without them would pass
  the stamp and turn the tenant's own CI red on day one, which decision 12 exists to prevent.

The files are listed in the scaffold manifest, so `.agenticframework/scaffold.json` holds them. Tests:
`test_each_stacks_scaffold_test_passes_in_the_one_commit_tree` (`agentsmith/test/test_cli.py`; one case per branch
above: `python-fastapi` and `go` in an empty repository, `ts-react` with a vitest, a jest and a neither
`package.json` from fixtures, plus one with npm's default `test` script, one with a `yarn.lock`, and one whose
vitest config includes only `src/**`, and one with a vitest `package.json` and no `node_modules` (each of these
three must stop init with its sentence); each `tenant init` then `scripts/ci_tree.py
-- <TEST_COMMAND_BY_STACK[stack]>` exits 0, and for `ts-react` the template's own type-check step (`npx --no-install
tsc -b --noEmit`, as `workflow-templates/ci-ts-react.yml` runs it) exits 0 too; a stack whose toolchain is not on the runner is a skip locally and must run in the Scratch tenants workflow, B4,
whose tenants' own CI must be green; mutants: the test file not written; written outside the gated globs; written
under `src/`; npm's default script kept), `test_a_new_tenants_first_push_with_a_stamp_is_allowed` (for each stack:
`tenant init`, the arming commit, `scripts/ci_tree.py -- <command>`, then `git push` to a bare remote through the
real `.githooks/pre-push`: allowed, and refused without the stamp; mutant: the graphs-current rule applied with
`knowledge_graph` off), and
`test_a_ts_react_init_without_a_package_json_stops` (mutant: the check removed) and `test_init_writes_a_starter_changelog_and_declares_it` (mutants: the key not written; an
existing `CHANGELOG.md` overwritten).

`TEST_COMMAND_BY_STACK = {"python-fastapi": "python3 -m pytest -q", "go": "go test ./...", "ts-react": "npm test"}`,
beside `GATED_BY_STACK`. Change the docstring of `_process_gates_config`: it says the three older modes are off on
day one; add that the three new ones are on for a new repository and why they differ (they ask for nothing that has
to exist already).

**What a tenant's commit costs with `invariants` on.** Each gated commit's `Ran on:` needs one `agentsmith gate tree --no-stamp
-- <command>` run on its staged tree. The command is the developer's choice (a fast subset is enough; a tenant's graph
is off, so there is no `--print-selection`); the push stamp runs the configured command once per push. Stated in
`docs/process-gates.md` and `docs/UserManual.md` with B3.

**What an existing tenant sees after `sync`.** Its verdicts on designs, reviews and pushes do not change. It sees:
(1) one note from `plan_sync`, added to `plan.notes` when any of the three keys is absent from its config, printed by
`describe`: "new in this framework, off here: `invariants`, `claims`, `verified_tree` — a design states its
invariants and oracle, a changelog bullet names its test, and tests run on the pushed tree. Turn each on in
.agenticframework/process-gates.json: `report` lists what would be refused, `enforce` refuses it; a mode only moves
up (AgentSmith docs/process-gates.md › Invariants)". (2) The refreshed rule files, with the new pillar text and
`design_start` line. (3) The range-verdict fixes, listed in the CHANGELOG as newly refused. When the tenant sets
`report`, session start lists each active design without the section and CI lists notes: that list is its backlog.
Nothing is written to the tenant's backlog file by the tool.

### Workflow templates

Read at c7da273: no `workflow-templates/ci-*.yml` sets `fetch-depth` or `fetch-tags`, so a tenant's test job already
checks out one commit and no tags, as Part A's oracle for "where it will run" requires. Nothing is added to them. One
test pins it: `test_tenant_ci_templates_check_out_one_commit_and_no_tags` (every `actions/checkout` step in
`workflow-templates/ci-*.yml` has neither key; mutant: `fetch-depth: 0` added). `workflow-templates/agentsmith-gates.yml`
keeps `fetch-depth: 0` (the gate needs the range) and is unchanged: the default branch reaches the provider without
a new argument (see B5).

### Named tests

| Test (file) | Asserts | Mutant it must kill |
|---|---|---|
| `test_a_new_tenant_is_born_with_the_three_modes_on` (`agentsmith/test/test_cli.py`) | `_process_gates_config("go")` has the three keys at `enforce` and the stack's command; and its arming commit passes its own gate with the real hooks | a key dropped; the scaffold design without its section |
| `test_an_adopted_tenant_gets_report` (`scripts/test/test_tenant_adopt.py`) | the three keys are `report`; a commit with a design lacking the section is allowed with a note | `existing` not passed |
| `test_sync_changes_no_mode_and_says_what_is_new` (the sync test file that holds `plan_sync` tests) | the config's bytes are unchanged; the note is in `describe`; no note when all three keys are present | sync writing a key; the note unconditional |
| `test_gate_tree_runs_the_command_in_the_export` (`agentsmith/test/test_cli.py`) | `agentsmith gate tree -- <cmd>` exits with the command's code and writes the stamp; with `--no-stamp` it writes none | the verb not wired; `--no-stamp` not forwarded |
| `test_an_uncollected_test_stops_the_run` (`scripts/test/test_ci_tree.py`) | a duplicated test name in a staged file: exit 2, named | `uncollected` not called |
| `test_a_mode_cannot_be_turned_down_without_approval` (`scripts/test/test_range_verdict.py`, K11, K13, K15) | hook and `ci` refuse `enforce` → `report` for each of the three keys; the effective command changed (K13), either through `verified_tree.command` or through `extends.test_command` with `command` absent, refused, and allowed with a bound approval; turning the stamp on with a command for the first time allowed; `knowledge_graph` `enforce` → `off` (K15) refused, and allowed with a bound approval (the base config has `knowledge_graph: enforce` and a current graph) | a key missing from `_gate_modes_kept` (three mutants); `command` not held; the raw key compared instead of the effective command; the command held while the stamp was off; `knowledge_graph` not held |

## B4 — Rendering

- `templates/agent-rules.yaml` is the source. `scripts/generate-ide-config.py` needs **no code change**:
  `_design_start_lines` renders every `records.design_start` line into `.cursorrules`, `CLAUDE.md`, `AGENTS.md`,
  `GEMINI.md`, `.github/copilot-instructions.md` and, through `_render_skill`, the `.agents/skills/*/skill.md` files;
  pillar rules render from `pillars`. Run `python3 scripts/generate-ide-config.py --registry` to rewrite
  `templates/governance.json`, and commit it.
- Drift tests that already exist and must stay green: `scripts/test/test_gate_models.py` (runs `--registry
  --check-only`: the committed registry equals the render); `scripts/test/test_generate_ide_config_governance.py`
  (`test_the_rules_source_states_the_design_start_block`,
  `test_every_ide_rule_file_tells_the_agent_to_ask_before_deviating`,
  `test_write_regenerates_a_tracked_rule_file_and_check_only_sees_the_drift`); the gates workflow's `rules check`
  step in a tenant; `scripts/test/test_design_and_validation_docs.py` and `scripts/test/test_lever_notes.py` for the
  levers.
- New, in `scripts/test/test_generate_ide_config_governance.py`:
  `test_every_ide_rule_file_names_the_invariants_section` — parametrised over the five rule files and the
  `efficiency_stack` skill: the rendered text contains "## Invariants" and "independent oracle" (mutant: the
  `design_start` line removed); and `test_the_four_pillars_carry_the_invariants` — the rendered P4, P13, P14 and P15
  rules each end with their appended sentence, compared with strings **written in the test** (mutant: a sentence
  dropped from the yaml).
- Short enough to read every session: `scripts/test/test_context_budget.py` holds every rule file to 3,000 estimated
  tokens and the session-start message to 1,200. Measured headroom before the change: 393 tokens in the largest file.
  The additions are about 225. Those two tests are the check; their limits are not raised.

## B5 — Contracts and release

- **Rules contract (`contract/rules/v1`).** Unchanged. The rendered text changes; its schemas and fixture do not pin
  the `design_start` wording (searched: no match).
- **Record contract (`contract/record/v1`).** Unchanged: the new errors and notes are strings in fields that exist.
- **Gate contract (`contract/gate/v3`, and v2 through it).** The hook interface and the event and decision schemas
  are unchanged. `push` may now answer `deny` for a missing stamp, which is a provider's policy inside an existing
  answer, as the commit-subject rule is. Two points need care:
  1. Versions 2 and 3 publish the case "a new branch: the head commit alone" (`cases.json`; v2's protocol, case 9).
     **This corrects Part A:** for an all-zero or unreadable base, the per-commit list stays `[head]`, exactly as
     today, so that case is untouched. Only the before-and-after rules use the merge base with the default branch.
  2. No new argument crosses the contract. `--default-branch` exists only on AgentSmith's own command line. Behind the
     contract the provider finds the default branch itself, in this order: the option; `repository.default_branch`
     in the JSON file `$GITHUB_EVENT_PATH` names; the target of `refs/remotes/origin/HEAD`. (`process_gate.py` already
     reads `GITHUB_*` in its `ci` route.)
  `contract/gate/v3/protocol.md` gains one sentence, with no change to cases or schemas and no v4 (owner,
  2026-11-23, decision 11), after the paragraph on the push range: "A provider may judge rules that compare a
  state before and after a change from where the branch left the default branch; rules about a single commit are
  still judged per commit, and for a new branch on the head commit alone." Test: the contract's existing case
  tests stay green unchanged (`scripts/test/test_gate_contract*.py`), which is the claim that nothing else moved.
- **The knowledge-graph shape** (`contract/gate/v3/knowledge_graph.schema.json`) allows any `edge_type` string and
  extra fields, so `RUNS` edges and the removed clock values need no schema change.
- **Semver.** Nothing is switched on in an existing tenant; the new keys and the verb are additive; the gate fixes
  newly refuse what B3's "Range verdicts" row lists (six things), and each is in the CHANGELOG. That is a minor release: 4.1.0, with Part A (owner, 2026-11-23,
  decision 3; 4.1.0 is not yet released).

**The CHANGELOG entry** (under `## [Unreleased]`; each bullet's claim line goes in the review record's `## Claims`):

    ### Added — designs state their invariants
    - A design states its invariants in `## Invariants`: each a testable property, its independent oracle, generated cases and enforcement. On in a new tenant; `report` on adoption; off after a sync until you turn it on (`invariants`).
    - `agentsmith gate tree -- <command>` runs your tests in a one-commit, tagless copy of the staged tree; with `verified_tree` on, a push needs its stamp.
    - A changelog bullet names its test in the review's `## Claims` (`claims`).
    - Review levers gain group 11, "Invariants, not instances", with eight levers; sign-off Groups 8–11 are checked where `invariants` is on.
    ### Changed — may newly refuse
    - CI judges a range's before-and-after rules by its two ends: an approval recorded before the range no longer unlocks a weakening in it; a shallow clone that hides the base fails; a commit that removes the gate config is refused unless an `Approval:` trailer cites a fresh approval of that removal.
    - An approval unlocks only the change it was recorded for: one recorded in the range for another weakening is refused.
    - Turning `knowledge_graph`, `invariants`, `claims` or `verified_tree` down, or changing the test command once the push stamp is on, needs the owner's approval bound to that change.
    - A weakening made inside a merge commit is refused by the sweep (pre-push) and by CI with no known base, as an ordinary commit's is.
    - SEC-CIAGENT-001 reports untrusted event text passed through `with:` to any reusable workflow, in this repository or another.
    - Where `knowledge_graph` is on, a push whose committed knowledge graph or trace graph is not a build from nothing of the pushed tree is refused.
    - A TypeScript test file that the project's runner (vitest or jest) does not collect stops the test run.

    Claims:
    - "A design states its invariants" — test: `scripts/test/test_invariants_section.py::test_each_mode_on_each_route`, `agentsmith/test/test_cli.py::test_a_new_tenant_is_born_with_the_three_modes_on`, `scripts/test/test_tenant_adopt.py::test_an_adopted_tenant_gets_report`
    - "agentsmith gate tree" — test: `agentsmith/test/test_cli.py::test_gate_tree_runs_the_command_in_the_export`, `scripts/test/test_ci_tree.py::test_a_push_requires_a_passing_stamp_for_this_tree`
    - "A changelog bullet names its test" — test: `scripts/test/test_claims.py::test_each_route_applies_the_rule`
    - "Review levers gain group 11" — test: `scripts/test/test_design_and_validation_docs.py::test_every_lever_has_a_design_phase_counterpart`
    - "CI judges a range's before-and-after rules" — test: `scripts/test/test_range_verdict.py::test_ci_agrees_with_the_hook_on_the_squash`
    - "Turning `knowledge_graph`, `invariants`, `claims` or `verified_tree` down" — test: `scripts/test/test_range_verdict.py::test_a_mode_cannot_be_turned_down_without_approval`
    - "A weakening made inside a merge commit is refused" — test: `scripts/test/test_range_verdict.py::test_ci_agrees_with_the_hook_on_the_squash`, `scripts/test/test_range_verdict.py::test_the_sweep_agrees_with_the_hook_on_the_squash`
    - "An approval unlocks only the change it was recorded for" — test: `scripts/test/test_range_verdict.py::test_ci_agrees_with_the_hook_on_the_squash`
    - "SEC-CIAGENT-001 reports untrusted event text passed through `with:`" — test: `scripts/test/test_agent_workflow_injection.py::test_a_caller_passing_event_text_to_any_reusable_workflow_is_reported`
    - "Where `knowledge_graph` is on, a push whose committed knowledge graph" — test: `scripts/test/test_ci_tree.py::test_a_stale_graph_refuses_the_push`
    - "A TypeScript test file that the project's runner (vitest or jest) does not collect" — test: `scripts/test/test_ci_tree.py::test_a_typescript_test_file_the_runner_skips_stops_the_run`

(The sync test's id is added to the first claim once its file is named in commit B3.)

**Scratch tenants prove it end to end** (`.github/workflows/scratch-tenants.yml`, `docs/scratch-tenants.md`):

- Job `build` (a tenant made by `tenant init` from `.github/scratch-tenants/apps/<app>`): `build.sh` gains a step
  for each app, because from B3 the tenant's pre-push hook refuses a push with no stamp. Installs, chosen by the
  app's files (the matrix's `stack` is `python-fastapi` for every Python app): for apps with a `package.json`, `npm ci` or `pnpm install --frozen-lockfile` between the app commit (`build.sh` step 2) and
  `tenant init` (step 3), so init's runner question can run (`node_modules` is in each app's `.gitignore`, so
  nothing leaks into the scaffold commit); for the others, after the scaffold commit (step 5): with a `uv.lock`,
  `uv export --only-group dev --no-hashes | pip install -r /dev/stdin && pip install .` (its tests run with
  `python3 -m pytest` on PATH, not in `.venv`); with a `requirements.txt`, `pip install -r requirements.txt`; with a
  `go.mod`, `go mod download`. Then, for every app (ts-react too: a stamp taken before the scaffold commit has the
  wrong digest), after step 5, `agentsmith gate tree -- <TEST_COMMAND_BY_STACK[stack]>`, failing loudly with the
  app's name if it exits non-zero. The `build` job gains `actions/setup-node` (`node-version: 22`, which vite 8 and
  vitest 5 accept; pnpm through `corepack enable`), `actions/setup-go` (`go-version-file` the go app's `go.mod`) and
  `astral-sh/setup-uv`, each pinned as the workflow's other actions are; it does not rely on the runner image.
  Then a new script
  `.github/scratch-tenants/expect-invariants.sh <tenant dir>`, run after "Build the tenant…" and before "Push", in
  the shape of `expect-ungraded.sh`. It (1) asserts the three keys are `enforce` in the tenant's config; (2) writes
  a design with `agentsmith design new probe --scope '<a gated glob>'`, answers its pillars, deletes its
  `## Invariants` section, makes a one-line gated change and runs `git commit` through the hooks: the commit must
  fail and its output must contain "Invariants"; (3) restores the section with one complete item: the same commit
  must then fail only for its review, not for the design; (4) resets the probe so nothing of it is pushed. Exit 1 on
  any other outcome, printing which step.
- Job `adopted` (`adopt.sh`): after "Adopt the tenant…", assert the three keys are `report`; then the existing "Wait
  for the tenant's own CI and its AgentSmith gates" step must be green: an adopted repository whose designs lack the
  section stays green, and its gates run's summary contains `invariants (report)`.
- A synced tenant: `scripts/check_tenant_upgrade.sh` already runs in Self-Test; the unit test
  `test_sync_changes_no_mode_and_says_what_is_new` is the proof for sync, and `docs/scratch-tenants.md` says so in
  "Three layers of checking".

## B6 — Order of work

Part B's design-time half goes **first**, so Part A's own fixes are designed and reviewed under it; its tenant half
goes last, because it switches on mechanisms Part A builds.

| # | Commit | Contents |
|---|---|---|
| B1 | `docs(rules): four pillars and a lever group carry the invariants` | B1's pillar text and `design_start` line, `governance.json` regenerated, B2's lever group, notes and two checklists, B4's two render tests |
| B2 | `feat(gate): a design states its invariants` | `check_invariants`, the `invariants` key, the skeleton, the scaffold design, session start, the sign-off additions, `test_invariants_section.py`; AgentSmith's config sets `"invariants": "enforce"` |
| A6, A7, A1–A4 | Part A's commits in the owner's order (A6 and A7 first) | each design and review now carries its `## Invariants` and Group 8–11 lines; A1 also adds `report` to `verified_tree`, the last line `ci_tree.py` prints, the graphs-current rule, and `scripts/collection_check.py` (Python and TypeScript); A4 also adds the caller side |
| approval-binding | `.agent-rfc/designs/approval-binding.md`'s commit | `agentsmith approve` records the subject; `approval_unlocks` |
| A5 | Part A's fifth | A5 also adds `gate-modes-kept`, K11, K13, K15, the removal route, the `docs/process-gates.md` paragraph and the contract sentence; deletes `policy_transitions` and `range_transitions` |
| A8 | Part A's last | the portal lockout (P4-R6, P4-R7) |
| B3 | `feat(tenant): new repositories start with the invariants on` | `_process_gates_config`, `TEST_COMMAND_BY_STACK`, the init `changelog` key and starter `CHANGELOG.md`, the scaffold test per stack, adopt's `existing=True`, the sync note, `agentsmith gate tree`, the template pin test, B3's tests, `docs/UserManual.md` and `docs/process-gates.md` |
| B4 | `test(scratch): a new tenant refuses a design without invariants` | `expect-invariants.sh`, the two workflow steps, `docs/scratch-tenants.md`, the CHANGELOG entry above |

Between B2 and A1 the `Ran on:` line cannot be produced (no `ci_tree.py` yet): commits B1, B2, A6 and A7 write
`Ran on: n/a — ci_tree.py arrives in A1` and their design section for the commit is this document's, which is not
`none`; so the digest comparison and the rule "n/a only when the section is none" are introduced in A1, not B2
(B2 only parses the line). Say so in B2's review, and in A6's and A7's.

**Pull requests** (owner, 2026-11-23): PR-1 = this design, B1, B2; PR-2 = A6, A7, A1, A2; PR-3 = A3, A4,
approval-binding, A5, A8; PR-4 = B3, B4. Each gets an independent read-only review before the owner merges, and its
findings are fixed in that PR.

Before every commit: the command list in Part A's "Order of work", as written (from A1, its per-commit feedback run
through `ci_tree.py`). Before every push: the stamp, `python3 scripts/ci_tree.py -- <the configured command>` (inside
AgentSmith), the same thing `agentsmith gate tree` runs in a tenant; for B1, B2,
A6 and A7, the hand-typed export given there replaces it. Add, for B1 and any commit touching
`templates/agent-rules.yaml`:

```bash
python3 scripts/generate-ide-config.py --registry                 # then `git add templates/governance.json`
python3 scripts/generate-ide-config.py --registry --check-only    # must exit 0
python3 -m pytest -q scripts/test/test_context_budget.py scripts/test/test_lever_notes.py \
  scripts/test/test_design_and_validation_docs.py scripts/test/test_generate_ide_config_governance.py
```

and for B3 and B4: `bash scripts/check_tenant_upgrade.sh`. B4 is done only when the `Scratch tenants` workflow is
green on the pushed head for every app and for `adopted`.

## B7 — Owner decisions (answered 2026-11-23 and 2026-11-26, but row 17)

The owner answered every question on 2026-11-23 and 2026-11-26, but row 17. Rows are numbered as the questions were asked here; "Plan #" is
the launch plan's decision number, which is the number the body cites ("decision 5" and so on). Each answer is
written into the section it changes; this table is the index. Row 17 is open (row 14 is folded into 15).

| # | Plan # | Question | Owner's answer | Where it is written | Blocks |
|---|---|---|---|---|---|
| 1 | 4 | The stamp at push or at each commit, and how wide its command is | At push, the **KG-impacted tests** in the clean one-commit tree; CI runs the full suite. **Revised 2026-11-26: the full suite at push, in parallel (row 15).** Before every push the knowledge graph and the trace graph are rebuilt and complete | Invariant 4, Decisions and Code changes; "What changed" | A1 (after A6, A7) |
| 2 | 5 | Approvals: new in the range only, binding later | **Freshness and binding now**: an approval counts only if new in the commit or range and bound to what it unlocks; `agentsmith approve` changes, in its own design | Invariant 2, Decisions; Dependencies; `approval-binding.md` | approval-binding, A5 |
| 3 | 6 | Reusable-workflow string inputs, no trusted marker | Report all, no marker. The manual gives the three refactors and says that letting the agent fetch the text moves the injection out of sight; the real control is the agent's permissions | A4 (P4-R3 code changes) | A4 |
| 3b | 6b | (added by the owner) The caller side | Flag untrusted `github.event.*` fields passed via `with:` to any `uses:` workflow | A4 (P4-R3 code changes) | A4 |
| 4 | 7 | Weaken-then-restore inside one range | Accept; documented in `docs/process-gates.md` | Invariant 2, Decisions | A5 |
| 5 | 8 | Removing the gate config | The approval route: a fresh, bound approval cited by an `Approval:` trailer | Invariant 2, Decisions | A5 |
| 6 | 9 | `tenant init` declares a changelog | Yes, and writes a starter `CHANGELOG.md` | B3, Defaults | B3 |
| 7 | 10 | `tenant adopt`'s mode for the new keys | `report` | B3, Defaults | B3 |
| 8 | 11 | A sentence in the gate contract | One clarifying sentence in `contract/gate/v3/protocol.md`; no v4 | B5 | A5 |
| 9 | 3 | Which release | 4.1.0, with Stage 2 | B5 | B4 |
| 10 | 12 | A new tenant's first push needs a stamp | Keep `enforce`; every stack's scaffold ships a passing test | B3, Defaults | B3 |
| 11 | 13 | Test collection checked for Python only | **Python and TypeScript** in 4.1.0; Go: the lever only | Invariant 4; B3 table | A1, B3 |
| 12 | 14 | Where the new sign-off group lives | In code, behind the `invariants` key | B2, Sign-off | B2 |
| 13 | 15 | (added by the owner) Sign-off Groups 8–10 from `143ac82` | Checked by the gate, same mechanism and key; this design's group is renumbered **Group 11** | B2 | B2 |
| 14 | — | (folded into row 15: the graph's remaining limits after A7 are what the report measured) | — | — | — |
| 15 | 4 (revised) | Keep decision 4 (KG-selected tests at push), given the research report's 26 % miss? | **No** (owner, 2026-11-26): the full suite at push, in parallel (`-n auto`); CI too. A1b and the selection at push are not built | Invariant 4, Decisions ("Not built") | A1 |
| 16 | 4 (revised) | Add `pytest-xdist` to `requirements.lock`? | **Yes**, with `pytest-timeout`, hash-pinned (owner, 2026-11-26); `-n auto` in the stamp and in CI | Invariant 4, Decisions | A1 |
| 17 | — | **Open.** The caller-side check (decision 6b) reports event text passed to any reusable workflow. Should a job `if:` that is certainly false for every outsider excuse it, as it does for a step? Until answered: no exemption | — | A4, the caller side | an exemption in A4 |
