# The gate contract, version 3

**Contract 2, plus `commit`, `push` and the knowledge graph.** Everything [version 2](../v2/protocol.md)
says holds here unchanged — and through it, [version 1](../v1/protocol.md) — so a provider that
satisfies version 3 satisfies both. Versions 1 and 2 stay published and served: a repository moves
between them by changing one number in its declaration.

Version 2 put a tenant's CI behind the contract; its local commit and push still ran AgentSmith's own
script. Version 3 adds those two questions — **may this commit be made**, and **may this history leave
the machine** — and two verbs for the knowledge graph a review is scoped by, so a third-party provider
can govern a repository end to end.

## The protocol

```
<provider-command> <event>          event ∈ session-start | pre-edit | stop | ci | commit | push
<provider-command> kg build
<provider-command> kg impact [--staged | --base <ref>]
```

- **cwd** is the repository being asked about. Paths in the event are relative to it, or absolute.
- **stdin** is one event, `event.schema.json`.
- **stdout** is one decision, `decision.schema.json`, and nothing else.
- **exit 0** a decision was made — the answer is on stdout, including `allow`.
- **exit 3** this provider cannot run here (not installed, no interpreter, wrong repository). It is
  **not** a refusal: a provider that means "no" says `deny` and exits 0.

**An answer is a decision on stdout.** A caller that gets no decision treats the provider as not
having answered, whatever the exit code, and may try the next one. That covers exit 3, a command
that is not there (127) or not executable (126), and — the case that matters in practice — a
provider installed but too old to know the event, which exits with a usage error. A provider is
never wrong to print a decision and exit 0.

### The `ci` event

The event is a **range**: `{"kind": "range", "base": "<ref>", "head": "<ref>"}`. Any ref git resolves
is a valid `base` or `head`. A `base` of all zeros (`0000…`, what a push to a new branch reports) means
the branch has no history on the remote: the provider judges the **head commit alone**, and may say
so in its report.

The answer is one decision, `allow` (the range passes) or `deny` (it does not, with `text`). Two
optional fields are for the person reading CI, never for a machine:

- `report` — markdown: what was checked and what failed;
- `annotations` — one line per problem, in the CI system's own annotation syntax where it has one.

A provider with nothing to say beyond the verdict leaves both empty. An event that is not a range is
answered `deny`, with the reason — never `allow`.

**`ci` never falls back.** Version 1 lets a caller that gets no decision "try the next one". For `ci`
there is no next one: a caller that gets no decision — the provider is not installed, is not
executable, exits 3, or is too old to know the event — **fails the check**, and says which of those
happened. A check that cannot run is not a check that passed, and falling back to a framework's own
files would put back the coupling this event exists to remove. The three version-1 events keep
version 1's fall-through.

### The `commit` event

`{"kind": "commit", "message": "<the whole message>", "amend": false}` — may the change **staged** in
`cwd` be committed with this message? `amend` says the commit replaces the current head. The answer is
one decision: `allow`, or `deny` with the reason. What a provider checks is its own policy — AgentSmith
checks the subject line's form, the Design and Review trailers, and any commit that skipped the gate
and is not repaired by this one. The caller is the repository's `commit-msg` hook, which holds no
policy of its own at version 3: it asks.

### The `push` event

`{"kind": "push"}` — may this repository's history leave this machine? `allow`, or `deny` with the
reason. AgentSmith answers with its bypass sweep: a commit made without meeting a gate is refused until
it is repaired. The refs git passes to its `pre-push` hook stay with the hook.

### Nothing falls back from `ci`, `commit` or `push`

A caller that gets no decision for any of the three — the provider is not installed, is not
executable, exits 3, or is too old to know the event — **refuses**: the check fails, the commit or the
push is blocked, and the caller says which of those happened. Falling back to a framework's own files
would put back the coupling these events exist to remove. The three version-1 events keep version 1's
fall-through.

### The knowledge graph

A review is scoped by the change and what depends on it, and the scope is named by a hash the
review's sign-off carries (`KG query: kg:<12 hex>`). The graph lives in the repository, at
`.agent-rfc/fixtures/knowledge_graph.json`, in the shape `knowledge_graph.schema.json` publishes — the
repository's own data, not a provider's artefact. A provider whose `commit` or `ci` answers check a
review's scope offers two verbs:

- **`kg build`** writes the graph for the repository in `cwd`;
- **`kg impact`** prints, as JSON (`kg_impact.schema.json`), the files a review must read, the lever
  groups, the changed files the graph does not know yet, and the hash. With `--staged` — the default —
  it scopes the commit being made, from the index, which is what a provider's `commit` answer checks a
  review against; with `--base <ref>` it diffs the working tree against that ref.

They are verbs, not events: no decision, and stdout is the result itself.

### What a provider must govern

The declaration — `.agenticframework/providers.json` — decides who governs the repository, and from
version 2 on whether its CI, its commits and its pushes are checked at all: `"gate": "none"` turns
every check off. A provider therefore
governs the declaration **whatever its configuration lists**: an edit to it, like any governed edit,
needs what the provider asks of a governed change. Without that, one unreviewed commit could switch
every other rule off. A conformance case pins it.

What a provider does around the verdict — sending a record of it somewhere, say — is the provider's
business, configured by its own environment; it never changes the decision's meaning, and never
enters stdout.

## Resolution

A repository declares its provider in `.agenticframework/providers.json`
(`providers.schema.json`, this directory). A caller asks, in order:

1. `$GOVERNANCE_PROVIDER` — an operator escape for trying a provider without editing the
   repository. It is an operator's variable, never something fetched content sets;
2. the `gate` command in the declaration;
3. whatever the caller falls back to — for AgentSmith's own launcher, its own script.

`"gate": "none"` declares the repository ungoverned: the hooks do nothing, and there is no
fall-back, because "declared ungoverned" and "no provider could run" are different answers.

### The four decisions

| Decision | Means | `text` |
|---|---|---|
| `allow` | the edit, the turn, the range, the commit or the push may proceed | optional |
| `deny` | it may not | **required** — the reason a person acts on |
| `block` | the turn is refused (a `stop` event's refusal, which IDEs spell apart from `deny`) | **required** |
| `context` | not a refusal: what the session should start knowing | the context itself |

Silence is not an answer. A provider that allows says so, because a caller cannot tell an empty
answer from a provider that crashed before printing one.

### The event

`kind` is `edit`, `shell`, `other`, `range`, `commit` or `push`; `paths` are what an edit would
touch; `command` is the shell command for a `shell` event; `cwd` names the repository when it is not
the working directory; `stop_active` says a turn is already ending; `base` and `head` bound a
`range`; `message` and `amend` describe a `commit`. One event shape for all six questions — which is
how each was added without breaking a provider that ignores the fields it does not know.

**IDE dialects are not in this contract.** Six IDEs send six payload shapes for the same three
questions; translating them is the provider's adapter (AgentSmith's is `scripts/gate_ides.py`). A
provider implements one protocol here, not six dialects.

### Which contract a repository speaks

`providers.json` carries a top-level `contract`, and the `gate` entry may carry its own, which wins.
At **3** `commit`, `push` and `ci` go to the declared command; at **2**, `ci` only; at **1** — and with
no declaration — a caller keeps doing what it did before version 2. The gate entry may also name
`setup`: the provider's own CI setup step, pinned (for AgentSmith,
`bobbyaqlaar/AgentSmith/.github/actions/setup-agentsmith@<release>`). It is read by whatever writes the
repository's CI workflow, and never executed from the declaration.

## Conformance

```bash
agentsmith conformance --provider "<command>" --contract 3
```

`fixture.json` describes a repository — its files, its first commit, and a short tagged history —
which the runner builds fresh. A gate decision is about a repository, so the contract carries the
repository too; everything the decisions depend on is inside it, including its own rules registry
and levers document, so a run needs nothing from any provider's installation.

`cases.json` holds what must be answered, each pinning a different rule:

1. an edit to a path no gate governs — `allow`;
2. an edit to a governed path that no design covers — `deny`;
3. an edit to a governed path an active design covers — `allow`;
4. a turn ending with governed changes and no review — `block`;
5. a session starting — `context`.

`text` is never matched: a provider words its own answers. Only `deny` and `block` must carry text,
because a refusal with no reason is not an answer.

The fixture's `.agenticframework/` files are written in AgentSmith's configuration vocabulary — a
governed-paths list, a rules registry, a design with a scope. A provider with its own vocabulary
maps them; what the cases pin is the *behaviour*, not the file format.

Version 3 carries version 2's ten cases word for word — those five, then:

6. an edit to the declaration, which the fixture's configuration does not list — `deny`;
7. a range whose commits touch nothing governed — `allow`;
8. a range with a governed commit that names no design — `deny`;
9. a new branch, judged by its head commit alone — `allow`;
10. a `ci` event that is not a range — `deny`;

and adds:

11. the review scope of a staged change — `kg impact` names it;
12. a commit that stages nothing governed — `allow`;
13. a commit that stages a governed change and names no design — `deny`;
14. a push of a history that held to the gate — `allow`;
15. a push of a history holding a commit that skipped the gate — `deny`.

Before case 11 the fixture drops the tags that point at the commit the `ci` cases needed — the one
that skipped the gate — so from there on every provider reads the same history, whether it sweeps
everything reachable or only what it has not seen. Case 15 then makes a commit without any gate, which
is what a `push` must stop. A subject line's form is **not** a case: it is policy, and providers differ.

## What is not in version 3

The record a provider may send about a CI run is its own wire contract (C3 of
`.agent-rfc/designs/governance-contracts.md`); the rules a provider renders into the repository are the
rules contract (C4).
