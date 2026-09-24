# Review — a tenant hooks onto a governance provider, not onto AgentSmith

Design: `.agent-rfc/designs/governance-providers.md`, the architecture the owner asked for on
2026-09-23 and released slice by slice from 2026-09-24. This closes the parent: the five slices it
named are shipped and reviewed on their own, so what is left to judge is the **arc** — whether the
architecture delivered what it claimed, and where it did not.

Slices, each with its own design and review:

| Slice | Design | Review |
|---|---|---|
| The gate contract and its conformance suite | `gate-port.md` | `gate-port.md` |
| A repository names who governs it | `provider-resolution.md` | `provider-resolution.md` |
| One command keeps a tenant current | `framework-sync.md` | `framework-sync.md` |
| A sync refreshes what it owns, never what it does not | `sync-merged-files.md` | `sync-merged-files.md` |
| A tenant is told when it is behind, as a pull request | `sync-pull-request.md` | `sync-pull-request.md` |

## Pass 1 — findings: 3

Read the design's claims back against the code, rather than re-reading the slices.

1. `docs-match-behaviour` — **the design specifies `.agenticframework/providers.yaml`; what ships is
   `providers.json`.** The launcher is `bash` and must resolve a provider before any interpreter is
   known to exist, so it `sed`-parses the declaration; JSON can be parsed that way and YAML cannot.
   The change is right and was made in `provider-resolution.md`, but the parent still named the
   file it does not write. Corrected in the design, with the reason, so the two documents cannot
   disagree about the filename a tenant looks for.
2. `docs-match-behaviour` — **the resolution order shipped shorter than specified.** The design
   lists four steps (`$GOVERNANCE_PROVIDER`, the command on `PATH`, the machine install, a checkout
   named by `$AGENTSMITH_DIR`); `.githooks/process-gate` asks `$GOVERNANCE_PROVIDER`, then the
   command this repository declares, then AgentSmith's own paths. "The command on `PATH`" was not
   dropped — a declared command *is* resolved through `PATH` — and the last two collapsed into the
   framework-path fallback that already existed. Same intent, one fewer concept. Corrected.
3. `declared-vs-enforced` — **`version: "^2"` is written into every declaration and enforced by
   nothing.** `contract/gate/v1/providers.schema.json` already says so in the field's own
   description ("Recorded for a person and for tooling; the launcher does not enforce it"), which
   is the honest half; the parent design presented the range as what makes two version lines work.
   Corrected there too, and carried below as a stated limit rather than quietly left.

## Pass 2 — findings: 1

1. `ambiguous-signals` — **the design's strongest sentence is not true yet, and closing it without
   saying so would be the wrong kind of "done".** "A major AgentSmith release then touches no
   tenant file at all, [...] because there is nothing left to sync" describes the end state of an
   architecture in which a tenant holds only a declaration. A tenant today still holds the gate
   hooks, two workflows, the rule files' managed block and the IDE hook configs. What the arc
   actually achieved is the other half of the same goal, by a different mechanism: everything a
   tenant holds is now **framework-owned, hash-verified and refreshed without a person** —
   `agentsmith sync` writes it, `Review: n/a: framework sync <version>` gets it past the tenant's
   own gates by hash, and `agentsmith-sync.yml` opens the pull request weekly. The cost of a major
   release went from *six manual steps and two design/review cycles* to *merge one pull request*.
   That is worth claiming, and it is not what the design claimed. Both are now in the design, under
   what shipped versus what the end state still requires.

## Pass 3 — findings: 0

Checked the four things a closing review of an architecture should check, and found nothing further:

- **every slice it named is shipped and separately reviewed** — five designs and five reviews, all
  `status: done`, each with its own sign-off and mutation evidence;
- **the item the design listed under "what this does not fix by itself"** — `agentsmith upgrade`
  refusing its own commit in a gated tenant — is fixed, by the hash-verified escape that design
  called for, in `framework-sync.md`;
- **the decisions taken hold.** Vendoring still works and no tenant was forced to migrate; the
  contract lives in `contract/` with its own integer and ships as a release asset; the gate port
  went first and was proven end to end on a scratch tenant; both visibilities are supported, the
  workflow using the token when set;
- **"or another platform" is checkable rather than asserted** — `agentsmith conformance --provider
  "<command>"` runs five golden cases from `contract/gate/v1/cases.json`, and AgentSmith's own
  adapter is scored by the same suite (`test_agentsmith_passes_its_own_conformance_suite`).

## Stated limits

These are what an honest "done" leaves open. None is a defect in what shipped; each is a boundary
the arc did not cross.

- **Contract v1 covers three events** — `session-start`, `pre-edit`, `stop`. The commit, push and CI
  gates are still AgentSmith-shaped, so a third-party provider can govern an editing session and
  not a commit. Extending the contract to them is the next slice if the owner wants it.
- **One of five ports is declared and resolved.** That was decision 3, taken deliberately: rules,
  telemetry, records and security keep working as they do and are documented as contracts in place,
  not published as schemas with resolvers.
- **The declared provider version range is not enforced** by the launcher.
- **A tenant still holds framework files.** `sync` refreshes them and the scheduled workflow
  proposes it, which is the interim answer; "nothing left to sync" needs the remaining four ports.
- **Neither `agentsmith-gates.yml` nor `agentsmith-sync.yml` has ever run on GitHub.** Both are
  tested as data — parsed, asserted — because CI cannot be run from here. Proving them needs a real
  adopted repository; a scratch repo cannot, since an adoption commit there breaks `build.sh`'s
  bot-author check. This is the single largest piece of unproven work in the arc.
- **The scaffold manifest is unsigned**, so rewriting a file *and* its hash defeats the sync escape
  — deliberately and visibly, exactly as for the generated scaffold.
- **`.cursor/hooks.json` is all-or-nothing**: the framework owns the whole file, not a region of it.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — one launcher, one hash check behind both
                                          escapes, one renderer for the rule files
Group 2 · Quality / safety            [x] checked — an unresolvable gate provider blocks; telemetry
                                          fails open
Group 3 · Architecture / hygiene      [x] checked — three claims in this design corrected against
                                          the code in passes 1 and 2
Group 4 · Process                     [x] checked — five slices, five designs, five reviews, each
                                          with its own sign-off
Group 5 · Intuitive UI                [x] n/a — command-line and a pull request body, reviewed in
                                          the slices that added them
Group 6 · Signal integrity            [x] checked — an answer is a decision on stdout, so a provider
                                          too old to answer is not read as having allowed
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      none in this commit — it closes an architecture; the slices carry the
                          tests (gate_contract 8 mutations, framework_sync 10, both green in CI
                          run 36050953902)
Mutation-checked:          inherited from the slices; no code changes here
Fixtures re-pinned:        not required — no code changed
KG query:                 kg:2db71564cb21
Gates run locally:         no code changed; the documentation gates run in the commit
Declared gaps:             the seven stated limits above, of which the unproven workflows are the
                           one to close first
```
