# Review — the gate port: a contract a provider satisfies

Design: `.agent-rfc/designs/gate-port.md`, first slice of
`.agent-rfc/designs/governance-providers.md`. Owner, 2026-09-23: "Start the gate port first."

**Built evidence (2026-09-23):**

- **Failing tests first.** `runtime/test/test_conformance.py` (5) and
  `scripts/test/test_gate_contract.py` (3) were written before `runtime/conformance.py`, the
  `neutral` adapter and the two commands; the first run failed on the missing module.
- **The contract is data, not prose.** `contract/gate/v1/` holds the protocol, both schemas
  generated from `gm.GateEvent` and the new `gm.Decision`, the fixture repository and the five
  cases. `test_the_published_schemas_match_the_models_they_describe` fails if either drifts.
- **AgentSmith certifies against it**: `agentsmith conformance --provider "agentsmith gate"`
  passes 5/5, run from the fixture's directory so the provider cannot depend on where it started.
- **Mutation checks:** a new `gate_contract` suite, 4 mutations, all caught — silence meaning
  allow, the neutral profile answering in an IDE's dialect, a reasonless refusal passing, and a
  provider that cannot run being scored as a wrong answer.

## Pass 1 — findings: 2

Both found by running AgentSmith against its own contract, which is the point of having one.

- `ambiguous-signals` — **finding:** the gate says `allow` by staying silent, which the profile
  cannot tell from a provider that crashed before printing. The adapter now says it explicitly;
  the hooks' own behaviour is untouched, so no IDE dialect changed.
- `test-the-contract` — **finding:** the fixture depended on the provider's installation. Its
  design cited a lever from a document the fixture did not carry, so the covered-path case denied
  for a reason that had nothing to do with the rule under test, and would have failed for any
  provider. The fixture now carries its own rules registry and levers document, and the cases
  decide correctly against nothing but the files in it.

## Pass 2 — findings: 0

Every lever over the contract, the runner, the adapter and the docs. Considered and declined:

- Putting `commit-msg`, `sweep` and `ci` in v1. Their arguments are one CLI's, not a protocol's;
  pinning them now would make the contract AgentSmith-shaped, which is the thing this exists to
  undo. Stated in the contract's README under "What is not in version 1".
- Making the fixture's configuration provider-neutral. A gate decision needs *some* policy
  vocabulary, and inventing a second one would mean maintaining a translation nobody uses yet. The
  README says plainly that the fixture speaks AgentSmith's dialect and that the cases pin
  behaviour rather than file format — an honest limit beats a fake abstraction.
- Letting a provider skip `text` on a refusal. A refusal with no reason is not an answer, and the
  suite fails it.

**Stated limits:**

- the contract covers the three hook events only;
- a tenant cannot yet *name* a provider: `providers.yaml` and a launcher that reads it are the
  next slice, so today the only way to use the contract is to call a provider directly;
- the fixture's configuration is AgentSmith's dialect, as the README says.

## Pass 3 — findings: 2

Both from this repository's own gates, refusing the commit that carried them.

- `no-redundant-artifacts` — **finding:** `contract/gate/v1/README.md` is a second readme, and the
  artifact registry allows one per repository. Renamed to `protocol.md`, which says what it is;
  every reference followed.
- `validate-on-the-receiving-side` — **finding:** `Case` was a frozen dataclass built from
  `cases.json` — data this code did not write — which `P7-pydantic` refuses. It is a Pydantic model
  with `extra="forbid"`, so a malformed case is named on the way in rather than at the point it is
  replayed. `Result` and `Report` stay dataclasses: the runner builds them itself.

## Pass 4 — findings: 1

- `no-redundant-artifacts` — **finding:** the renamed `protocol.md` was then neither an artifact
  nor declared reference documentation, which the artifact check reports at `enforce`. It is
  declared in this repository's `extends.artifacts.reference`: the contract is reference material
  a provider reads, not one of the repository's own documents. `agentsmith artifacts` is clean.

## Pass 5 — findings: 0

The rename, the model, the declaration, and the suites over all three.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — the neutral profile is an adapter over the
                                          existing decision path, not a second implementation
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — command-line output; each case's report line was read
Group 6 · Signal integrity            [x] checked — exit 3 and `deny` stay different answers
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      runtime/test/test_conformance.py (5), scripts/test/test_gate_contract.py (3)
Mutation-checked:          yes — gate_contract, 4 mutations, all caught
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:a5cbba1d4adb
Gates run locally:         ruff, mypy in a clean environment, the repo-tree check, the gate/IDE/CLI
                          suites, the full pytest run, and the conformance suite itself
Declared gaps:             (1) v1 covers the three hook events only; (2) no tenant-side provider
                              resolution yet — the next slice; (3) the fixture speaks AgentSmith's
                              configuration dialect
```
