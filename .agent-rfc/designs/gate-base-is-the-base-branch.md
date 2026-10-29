---
status: active
scope:
  - scripts/gate_steps.py
  - scripts/test/test_gate_steps.py
---
# The local gate's base is the base branch, not the branch's own remote

## Problem

`scripts/gate_steps.py::_merge_base` claims to answer what CI would, and does
not:

```python
def _merge_base(root: Path) -> str:
    """What CI would call the base of this range: where this branch left the
    upstream one. ..."""
    upstream = _git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}") or "origin/main"
    return _git(root, "merge-base", upstream, "HEAD") or _git(root, "rev-parse", "HEAD~1")
```

`@{upstream}` on a feature branch is **that branch's own remote**, not the
branch it will merge into. `.github/workflows/self-test.yml:44` passes
`github.event.pull_request.base.sha`, which is the **base branch**. Measured on
this branch:

| | base it resolves to | commits in range |
|---|---|---|
| `_merge_base` | `merge-base(origin/test/ts-sweep-runs-once, HEAD)` — the branch's own pushed tip | **0** |
| CI | `merge-base(origin/main, HEAD)` | **5** |

So the local gate asks *"what have I not pushed yet?"* while its docstring and
its place in `_EXPRESSIONS` say it asks *"what is in this change?"*. Two
failures, in opposite directions, both observed today:

**A false positive.** `a149142` touched `runtime/cli.py` with no `CHANGELOG.md`
in that commit; the entry was in `f867679`, already pushed. The local gate's
range held only the unpushed commit, so it refused:

```
changed paths that need a CHANGELOG.md entry (runtime/cli.py), and
CHANGELOG.md was not updated in this range
```

CI passed the same tree, because its range includes `f867679`. A gate that
refuses what CI accepts teaches people to push and see.

**A false negative, which is worse.** Once everything is pushed the range is
empty, and the gate reports success over nothing:

```
Checked 0 commit(s), 0 touching gated paths.
- ✅ every gated commit carries a resolving Design and a clean, same-commit Review
gates: 1 passed, 0 failed, 0 skipped
```

That is the shape `docs/review-levers.md` calls `test-that-cannot-fail` — a
sweep matching nothing, reported as a pass. Every "gates run" I have cited in a
review record after pushing was this, and I called one "vacuous" earlier today
without recognising it as a defect in the gate rather than in my usage.

The CHANGELOG rule itself is not the bug: `scripts/process_gate.py:1498`
evaluates it over `range_files`, the union across the range, which is right —
release notes are a property of a change, not of each commit in it.

## Approach

**Resolve the base branch.** `git symbolic-ref refs/remotes/origin/HEAD` names
it (`refs/remotes/origin/main` here); fall back to `origin/main`, then to
`HEAD~1` as now. `merge-base` that with `HEAD`, so a local run covers every
commit the branch adds — exactly CI's range — whether or not they are pushed.

**Say so where it is read.** The docstring states which question it answers and
why `@{upstream}` is the wrong reference, so the next reader does not restore it
as a simplification.

**Known limit, stated rather than hidden:** for a branch opened against another
branch (a stacked PR), CI's `pull_request.base.sha` is that parent branch and
this returns the default branch, so the local range is wider than CI's. Wider is
the safe direction — it checks more commits, not fewer — and a local run cannot
know which base a PR will declare. Recorded in the docstring.

## Pillars

- P1 applies — this note precedes the edit; the function is quoted in `## Problem`, with the measured base and range for each side and both failures it produced.
- P2 applies — no new module; `_merge_base` in `scripts/gate_steps.py` changes which ref it resolves, and `_EXPRESSIONS` keeps mapping both `pull_request.base.sha` forms to it.
- P3 n/a — a local CI-mirror helper, not a traced runtime path.
- P4 applies — failing test first in `scripts/test/test_gate_steps.py`: `test_the_base_is_the_base_branch_not_the_branchs_own_remote` builds a repository with a `main`, a feature branch pushed to its own remote-tracking ref, and a further commit, then asserts `_merge_base` returns the base-branch merge-base rather than the branch's tip. It fails against the current implementation. `test_the_range_is_not_empty_once_everything_is_pushed` pins the false negative directly.
- P7 applies — `git symbolic-ref refs/remotes/origin/HEAD` is not set in every clone (`git clone` sets it; `git init` plus `git remote add` does not), so the fallback chain is `origin/HEAD` → `origin/main` → `HEAD~1`, and `_git` already returns `""` on failure rather than raising, which is what makes the chain work.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no model call.
- P11 applies — the only inputs are `git` refs from the checkout `root` points at; nothing is read from a file or a network, and the result is passed to `git merge-base`, not to a shell.
- P12 n/a — no credentials.
- P13 applies — this slice IS gate integrity: the gate's local verdict was unfalsifiable once a branch was pushed. The fix widens the range, so the risk is the opposite one — a local run that now refuses something CI accepts. `scripts/test/test_gate_steps.py::test_the_checklist_holds_the_generated_table` still pins the generated table, and the whole range of this branch is run through `process_gate.py ci` with the new base to confirm it agrees with CI's verdict on the same commits.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is regenerated and re-pinned, with `agentsmith gate kg check` as the control, which `kg-check-sees-tracked-guardrails` made a control worth having.
- P15 applies — "✅ gates: 1 passed" meant "nothing was checked" and read as "everything checked out". The count beside it is built in `scripts/process_gate.py` (`f"Checked {len(commits)} commit(s)"`), and `scripts/gate_steps.py::_merge_base` decides what `commits` holds; fixing the base makes that number the one CI would check, so the two readings converge instead of differing silently. `scripts/test/test_gate_steps.py::test_the_range_is_not_empty_once_everything_is_pushed` is what holds it.
- P16 applies — if `origin/HEAD` is unset and `origin/main` does not exist, `_merge_base` falls back to `HEAD~1` as it does today, which is the correct range for a one-commit branch and the behaviour its current docstring already promises.

## Deviations

none

## Dependencies

None added.

## Levers

- `test-that-cannot-fail` — a gate reporting a pass over an empty range.
- `environment-parity` — the same gate, the same tree, two verdicts, depending on what had been pushed.
- `ambiguous-signals` — "0 commits checked" and "everything is fine" printed as one result.
