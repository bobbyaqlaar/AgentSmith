# The gate contract, version 1

A **gate provider** answers three questions about a repository: may this edit happen, may this turn
end, and what should a session know before it starts. AgentSmith is one provider. This directory is
what another platform implements instead — and the suite that proves it did.

The contract is versioned apart from any provider that implements it. A provider's own version
moves as often as it likes; a tenant pins **contract 1** and a provider range, so a provider's
major release does not reach the tenant's files.

## The protocol

```
<provider-command> <event>          event ∈ session-start | pre-edit | stop
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

## Resolution

A repository declares its provider in `.agenticframework/providers.json`
(`providers.schema.json`). A caller asks, in order:

1. `$GOVERNANCE_PROVIDER` — an operator escape for trying a provider without editing the
   repository. It is an operator's variable, never something fetched content sets;
2. the `gate` command in the declaration;
3. whatever the caller falls back to — for AgentSmith's own launcher, its own script.

`"gate": "none"` declares the repository ungoverned: the hooks do nothing, and there is no
fall-back, because "declared ungoverned" and "no provider could run" are different answers.

### The four decisions

| Decision | Means | `text` |
|---|---|---|
| `allow` | the edit or the turn may proceed | optional |
| `deny` | it may not | **required** — the reason a person acts on |
| `block` | the turn is refused (a `stop` event's refusal, which IDEs spell apart from `deny`) | **required** |
| `context` | not a refusal: what the session should start knowing | the context itself |

Silence is not an answer. A provider that allows says so, because a caller cannot tell an empty
answer from a provider that crashed before printing one.

### The event

`kind` is `edit`, `shell` or `other`; `paths` are what an edit would touch; `command` is the shell
command for a `shell` event; `cwd` names the repository when it is not the working directory;
`stop_active` says a turn is already ending. One event shape for all three questions, so a fourth
question can be added without breaking a provider that ignores the field it does not know.

**IDE dialects are not in this contract.** Six IDEs send six payload shapes for the same three
questions; translating them is the provider's adapter (AgentSmith's is `scripts/gate_ides.py`). A
provider implements one protocol here, not six dialects.

## Conformance

```bash
agentsmith conformance --provider "<command>"
```

`fixture.json` describes a repository — its files and one commit — which the runner builds fresh.
A gate decision is about a repository, so the contract carries the repository too; everything the
decisions depend on is inside it, including its own rules registry and levers document, so a run
needs nothing from any provider's installation.

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

## What is not in version 1

`commit-msg`, `sweep` and `ci` — the git and CI events — are an exit code and a message, already
stable in practice, but their arguments (a message file, a commit range, a record file) would pin
one CLI rather than a protocol. They stay documented behaviour until a second provider exists to
disagree with a shape. The dev record CI writes is separately versioned (`schema: 1`).
