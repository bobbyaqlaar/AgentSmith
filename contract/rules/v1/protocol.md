# The rules contract, version 1

A **rules provider** renders the files every IDE's agent reads before it starts — `CLAUDE.md`,
`AGENTS.md`, `GEMINI.md`, `.cursorrules`, `.github/copilot-instructions.md`, skill files — and checks
that a repository still holds them. AgentSmith is one provider. This directory is what another
platform implements instead, and the suite that proves it did.

## The protocol

```
<rules-command> <verb>          verb ∈ render | check
```

- **cwd** is the repository, or the request's `cwd` names it.
- **stdin** is one request, `request.schema.json`: an object; unknown keys are ignored.
- **stdout** is one answer — `rendered.schema.json` for `render`, `check.schema.json` for `check` —
  and nothing else.
- **exit 3** this provider cannot run here. An answer is JSON on stdout; anything else, whatever
  the exit code, is no answer.

## What a render reads

The repository's **committed declarations and content**, and the provider's own version — nothing
else: not the environment, not machine configuration, not the git remote. Two machines render the
same bytes from the same commit, so a check fails only on a change somebody made.

- `.agenticframework/tenant.yaml` — `tenant.name`, `tenant.owner`, `framework.version`;
- `.agenticframework/process-gates.json` `extends` — the tenant's own rules (`extends.schema.json`):
  `rules_extra`, its notes; `test_command`; `otel_endpoint`;
- the files it commits, which decide the stack, and a lock file the default test command.

## `render`

`{"files": [{"path", "text", "placement", "kind"}]}` — each file once.

| Field | Means |
|---|---|
| `placement: whole` | the file is the provider's: placing it replaces it |
| `placement: block` | the provider owns the region between the markers; the rest of the file is the tenant's |
| `kind: instructions` | an IDE's standing rules file: it must carry every one of the tenant's `rules_extra` notes |
| `kind: supporting` | anything else (a skill file) |

**The markers** each stand on a line of their own:

```
<!-- agentsmith:rules:begin …free text to the end of the line…
…the provider's text…
<!-- agentsmith:rules:end -->
```

Placing a `block` replaces the first marked region, or appends one to a file that has none. A
provider returns `whole` for a file that already exists **only** when it recognises the file as its
own — how is its own business — so a tenant's hand-written file is never overwritten.

**Paths** are relative and normalised — no empty, `.` or `..` segment, no backslash, no control
character — and outside `.git/`, `.githooks/`, `.agenticframework/`, `.github/workflows/` and
`.github/actions/`, in any letter case: a rules provider writes what agents read, never a
repository's hooks, declarations or CI. The pattern in `rendered.schema.json` is the rule. **The
caller enforces it**, and refuses the whole render on the first path that breaks it: it writes
nothing rather than half.

## `check`

`{"decision": "allow" | "deny", "text", "report", "files": [{"path", "state"}]}`

| `state` | Means |
|---|---|
| `current` | a `whole` file is byte-equal to its render; a `block` file's region equals its text |
| `drifted` | anything else — including a `block` file with no markers. Text outside a block is never compared |
| `absent` | the repository does not have the file. **Not drift**: a repository may choose not to commit its rule files |

`deny` when any file drifted, with `text` naming each one and the command that repairs it; `report`
is for a person — a diff of each drifted file.

## Who asks

- **A repository's CI**, through a step that resolves the declared provider. Failure is **closed**:
  drift, a bad path or no answer fails the step. Nothing runs per IDE session; the files already
  placed stand.
- **The provider's own tooling** that writes files into a repository (AgentSmith: `agentsmith sync`
  and `tenant adopt`), which places a render by the rules above.

## The declaration

`.agenticframework/providers.json` names the provider (`providers.schema.json`):

```json
{"providers": {"rules": {"command": "agentsmith rules", "version": "^2", "contract": 1}}}
```

The command is split on whitespace, with no quoting, and run with the verb appended.
`"rules": "none"` — the repository declares no rules provider, and a check says so instead of
checking. Removing or changing the entry is a change to an always-governed file.

## Conformance

```bash
agentsmith conformance --port rules --provider "<command>"
```

Builds `fixture.json`'s repository — a tenant's declarations with two notes of its own, and a
`CLAUDE.md` it wrote by hand with no markers — fresh for each case of `cases.json`: a render that
validates, that does not change with the environment, that carries every note in every
instructions file and does not take the hand-written file whole; then, with the render placed, a
check that allows, that denies a change inside a block or a whole file and names it, that ignores
the tenant's text outside a block, that reports a deleted file absent, and that denies once a note
changes; and no answer to an unknown verb.

## What is not in version 1

The registry — the pillar catalogue a design is checked against — is the gate provider's policy,
not something a tenant holds; a tenant adds to it through `extends.pillars`. The IDE hook configs
wire the gate and belong to it.
