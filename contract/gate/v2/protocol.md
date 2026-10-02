# The gate contract, version 2

**Contract 1, plus the `ci` event.** Everything [version 1](../v1/protocol.md) says holds here
unchanged — its three events, its four decisions, its exit codes and its resolution — and a provider
that satisfies version 2 satisfies version 1. Version 1 stays published and served: a repository
moves to 2 by changing one number in its declaration, and back the same way.

What version 2 adds is the question a tenant's CI asks: **does this range of commits pass?** Version 1
left it out, so a tenant's CI could only run AgentSmith's own script by path. Here it is a protocol
event, answered by whichever provider the repository declares.

## The protocol

```
<provider-command> <event>          event ∈ session-start | pre-edit | stop | ci
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

### What a provider must govern

The declaration — `.agenticframework/providers.json` — decides who governs the repository, and at
version 2 whether its CI checks anything: `"gate": "none"` turns the check off. A provider therefore
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
| `allow` | the edit, the turn or the range may proceed | optional |
| `deny` | it may not | **required** — the reason a person acts on |
| `block` | the turn is refused (a `stop` event's refusal, which IDEs spell apart from `deny`) | **required** |
| `context` | not a refusal: what the session should start knowing | the context itself |

Silence is not an answer. A provider that allows says so, because a caller cannot tell an empty
answer from a provider that crashed before printing one.

### The event

`kind` is `edit`, `shell`, `other` or `range`; `paths` are what an edit would touch; `command` is
the shell command for a `shell` event; `cwd` names the repository when it is not the working
directory; `stop_active` says a turn is already ending; `base` and `head` bound a `range`. One event
shape for all four questions — which is how `ci` was added without breaking a provider that ignores
the fields it does not know.

**IDE dialects are not in this contract.** Six IDEs send six payload shapes for the same three
questions; translating them is the provider's adapter (AgentSmith's is `scripts/gate_ides.py`). A
provider implements one protocol here, not six dialects.

### Which contract a repository speaks

`providers.json` carries a top-level `contract`, and the `gate` entry may carry its own, which wins.
At **2** the `ci` event goes to the declared command. At **1** — including every declaration written
before version 2 — a caller keeps doing what it did, so no repository's meaning changes because this
version exists. The gate entry may also name `setup`: the provider's own CI setup step, pinned
(for AgentSmith, `bobbyaqlaar/AgentSmith/.github/actions/setup-agentsmith@<release>`). It is read by
whatever writes the repository's CI workflow, and never executed from the declaration.

## Conformance

```bash
agentsmith conformance --provider "<command>" --contract 2
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

Version 2 adds:

6. an edit to the declaration, which the fixture's configuration does not list — `deny`;

and the `ci` cases, which name ranges by the fixture's tags:

7. a range whose commits touch nothing governed — `allow`;
8. a range with a governed commit that names no design — `deny`;
9. a new branch, judged by its head commit alone — `allow`;
10. a `ci` event that is not a range — `deny`.

## What is not in version 2

`commit-msg`, `sweep` and `pre-push` — the local git events — and the knowledge graph a review is
scoped by. They are the next slice of `.agent-rfc/designs/governance-contracts.md` (C2). The dev
record a provider may send is versioned separately (`schema: 1`) and becomes a wire contract of its
own (C3).
