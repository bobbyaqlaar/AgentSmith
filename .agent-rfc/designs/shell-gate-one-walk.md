---
status: active
scope:
  - scripts/gate_shell.py
  - scripts/test/test_gate_shell.py
---
# The shell pre-check's parse: one walk, and a quoted path is a quote

## Problem

`scripts/gate_shell.py` grew two command-line parses when the `git config` reads were fixed
(`.agent-rfc/designs/shell-gate-config-reads.md`, shipped in v2.0.0): one to find git's subcommand,
one to read `git config`'s arguments. They are the same walk — take a word, skip the value of an
option that takes one — written twice, 18 lines apart. The owner asked for the code to be as tight
as it can be, and a duplicated parse in a security gate is the kind of duplication that drifts:
`--file` was taught to consume its value in one of them and `-C` in the other.

Two smaller repetitions came with it: the sentence telling the reader how to re-arm the hooks is
written out in both config refusals, and the removal reason is built on **every** `git config` call,
including the reads that return `None`.

**And one thing the duplication was hiding.** `_redirect_targets` — the other half of the same
reading problem — is a regular expression over the **raw** segment text
(`re.findall(r">>?\s*([^\s;|&]+)", segment)`), so a protected path written *about* is refused as if
it were a redirect. Found while reviewing this slice, by the gate refusing this slice's own work
twice: the shell command that ran the differential check below (its corpus held a quoted redirect
string), and then the command writing the paragraph that recorded that. Neither wrote anything.

That is the class of defect the September slice fixed for the other half of this file —
`test_a_bypass_inside_quotes_is_an_argument_not_a_command` pins it for `git commit --no-verify`,
because `_segments` was tokenised for exactly this reason, and the redirect check was left reading
characters. Half the rule still has the bug the other half's test forbids, and a gate that refuses
people documenting it, testing it or grepping for it is a gate they route around through paths it
cannot see at all.

**So the slice is one refactor and one change to what is refused**, kept apart in the evidence: the
refactor must change nothing a caller can distinguish, and the redirect reading must change only
the cases named here. It turned out to cut both ways — reading the operator as a token also closes
two writes the character pattern never caught, `>|` and `>&`, because it excluded `|` and `&` from a
target and so found no path after either. The differential corpus below measures each claim
separately: 10 quoted mentions allowed, 18 operator forms refused, everything else identical.

## Approach

- **`_walk(words, takes_value)`** yields `(index, word)` past the value of any option that takes
  one. Both parses call it with their own option set (`_GIT_OPTION_VALUE`, `_CONFIG_OPTION_VALUE`),
  so the skipping rule exists once and each level keeps its own vocabulary — mixing the two sets
  would let a git-level flag be read as a `git config` action.
- **`_subcommand_at` becomes `_git_subcommand`**, returning the subcommand and the words after it.
  The caller loses an `Optional[int]` and an `at + 1` slice, and the `commit`/`push` flag checks
  read that subcommand's own words instead of every word on the line (`git -c x=y commit -n` is
  unchanged; a flag before the subcommand can no longer be mistaken for one after it).
- **`next(…)` for the key**, where a list comprehension built every match to use the first.
- **`_RE_ARM`, `_POINTS_AWAY`, `_REMOVAL`** are module-level templates, formatted where they are
  returned.

**Read redirects from the tokens, which `_segments` already produces.** `shlex` with
`punctuation_chars=True` yields a redirect operator as its own token and leaves a quoted string
whole — verified on this machine: `echo x > P`, `echo x >P` and `echo x >> P` give `>`/`>>` as a
token with `P` after it, `2> P` tokenises the `2` separately, `&>` and `>|` are single tokens, and
`echo 'x > P'` is two tokens with no operator at all. So the operator is one of a named set —
`>`, `>>`, `&>`, `&>>`, `>|`, `>&` — and the next token is its target, which cannot fire on a quoted
string, because a quoted string is never one of those tokens. `>&2` names a file descriptor rather
than a path, and no protected path matches it.

**Fail closed when the line did not tokenise.** `_segments` falls back to a crude `split()` on
unbalanced quoting, and in that text a redirect can stay glued to a word where the token rule would
miss a real write. `_segments` therefore reports whether it tokenised, and `refusal` keeps the old
raw-text scan for that one case — the stricter reading, used only where nothing can be parsed.

**Not in scope:** a redirect built by expansion (`echo x > $CONFIG`), which names no path this can
read, and a write through a program not in `WRITERS`. Both stay the module's stated limit.

Measured rather than claimed: executable statements are **104 before and after** (`ast`, excluding
docstrings), `_config_refusal` goes 38 → 30 lines and `_subcommand_at`'s 12 become 7 plus the 13
shared ones. Raw file length rises 6 lines, because the shared walk carries the comment that says
why both parses are it. This slice buys one parse instead of two, not a smaller file — recorded in
`## Levers` as what it is.

## Pillars

- P1 applies — this note precedes the edit; the slice it refactors is `.agent-rfc/designs/shell-gate-config-reads.md`, left at `status: done` because a released design is history.
- P2 n/a — no dependency added; `_walk` is a generator from the standard language.
- P3 n/a — `refusal` stays a pure function; the hook that calls it reports through its existing path.
- P4 applies — for the refactor, no new behavioural test: the contract is that `scripts/test/test_gate_shell.py` and the previous slice's 16 hand mutants read the same, plus one test gap a surviving mutant exposed. For the narrowing, failing tests first: each quoted form allowed; `>`, `>>`, `&>`, `>|`, `2>` and the no-space form still refused; an unbalanced-quote line carrying a real redirect still refused.
- P7 applies — `_walk` is typed `Iterator[Tuple[int, str]]`, `_redirect_targets` takes `Sequence[str]`, `_segments` returns its tokenised flag beside the segments, and `flags`/`operands` carry `Set[str]`/`List[str]` annotations; `scripts/` is outside `[tool.mypy] files = ["runtime"]`, so the types are for the reader and ruff, not a gate.
- P8 n/a — no telemetry wiring.
- P9 n/a — no orchestration.
- P10 n/a — no model calls.
- P11 applies — the command line is still text an agent wrote: `_walk` and the redirect scan only classify tokens, never evaluate them; `_protects` compares paths and never globs; and a `target` carrying `{}` is a `.format` **argument**, never a template.
- P12 n/a — no credentials.
- P13 applies — the risk is a silently weaker gate, and narrowing a refusal makes that risk real rather than theoretical, so: every redirect operator form keeps a test that must refuse, the mutants are re-run (21 of 21 caught, five of them for this reading), and the 1,684-command differential corpus must account for **every** difference — 10 quoted mentions now allowed, 18 `>|`/`>&` writes now refused, the rest identical string for string.
- P14 applies — no fixture changes beyond the knowledge graph, regenerated by `verify_system.py --check-kg`.
- P15 applies — `_git_subcommand` returns `("", [])` for a line with no subcommand, the same answer the `Optional[int]` carried, and no caller can read it as a subcommand named empty. "A path in a redirect" and "a path in a string" were one signal in the raw text; the tokens separate them, and a line that cannot be parsed keeps the strict reading rather than guessing.
- P16 applies — `_segments`'s crude fallback for an unbalanced quote is untouched, `_walk` over that output refuses writes exactly as before, and the redirect scan deliberately falls back to the old over-strict text reading for such a line.

## Deviations

none

## Dependencies

None added.

## Levers

- `no-copy-paste` / `parameterize-dont-clone` — one walk with the option set as its parameter, not two loops.
- `single-source-of-truth` — the re-arming sentence and the removal reason are each written once.
- `gate-integrity` — a refactor of a gate is proven by re-running the mutants, not by the tests passing.
- `test-that-cannot-fail` — the surviving mutant showed `not word.startswith("-")` was unasserted; three cases now pin it.
- `docs-match-behaviour` — the CHANGELOG entry separates the part that changed nothing from the one refusal that is narrowed, and `docs/process-gates.md` says what is read from tokens and what is not read at all.
- `validate-on-the-receiving-side` — the redirect check reads the tokens the shell would act on, not the characters.
- `grep-for-siblings` — the September slice tokenised one half of this rule; this is the half it left.
- `ambiguous-signals` — a protected path mentioned and a protected path written were the same signal.
