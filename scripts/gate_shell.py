"""
scripts/gate_shell.py — the shell surface (.agent-rfc/designs/
governance-enforcement.md, G2b).

The edit gate watches an IDE's edit tools. The same agent can open a terminal
and type `git commit --no-verify`, and until this nothing said no until the
sweep found it afterwards.

    refusal(command, hooks_path) -> the reason to refuse, or None

It refuses four things: skipping the commit gate, pointing git at other hooks,
writing to what the gate is made of, and recording an approval from a shell.

**Stated limit, because it decides how much this is worth.** It reads the
command an IDE is about to run — not what that command does. `bash -c "$(…)"`,
a script file, a shell alias and a Makefile target all reach git without
passing through here; so do `git config --edit`, a write straight into
`.git/config`, an `export GIT_CONFIG_…` on an earlier line, and a redirect whose
target is a variable (`> $CONFIG`), which names no path to read. That is why
G3's sweep exists and why the commit and CI gates are the ones that cannot be
talked around. This makes the obvious bypass visible and costly, not
impossible.
"""

from __future__ import annotations

import re
import shlex
from typing import Iterator, List, Optional, Sequence, Set, Tuple

SEE = "See AgentSmith's docs/process-gates.md."
# What the gate is made of. Editing one of these is how you would switch it off,
# so a shell write to one is refused the same way the edit gate refuses it.
PROTECTED = (
    ".githooks/",
    ".agenticframework/approvals.jsonl",
    ".agenticframework/process-gates.json",
    ".claude/settings.json",
    ".cursor/hooks.json",
    ".agents/hooks.json",
    ".gemini/settings.json",
    ".codex/hooks.json",
    ".github/hooks/",
)
# Programs that change a file named on their command line. `cat` and `grep` are
# deliberately absent: reading the gate is fine, and a check that refused it
# would be refusing people who are trying to understand the thing.
WRITERS = {"rm", "mv", "cp", "tee", "truncate", "chmod", "chown", "install", "ln", "dd", "shred"}
_IN_PLACE = {"sed", "perl"}  # only with -i


def _segments(command: str) -> Tuple[List[List[str]], bool]:
    """One shell line, split where one command ends and the next begins.

    Tokenised FIRST, so quoting is respected: a bypass written inside quotes —
    a test fixture, an echo, a here-doc handed to an interpreter — is one
    argument to some other program, not a command being run. Splitting the raw
    text refused the repo's own tests for this rule, which is how this came to
    be tokenised.

    An unbalanced quote is not a line this can read; it falls back to the crude
    split rather than pretending it parsed, and says so in the second return
    value — the redirect check reads the tokens when there are tokens, and the
    raw text when there are not.
    """
    separators = {"&&", "||", ";", "|", "&"}
    try:
        # `punctuation_chars` makes the lexer break on `;`, `|` and `&` the way
        # a shell does — `shlex.split` alone leaves `true;` as one token, and
        # the command after it was never looked at.
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return [part.split() for part in re.split(r"&&|\|\||;|\|", command) if part.strip()], False
    segments: List[List[str]] = [[]]
    for token in tokens:
        if token in separators:
            segments.append([])
        else:
            segments[-1].append(token)
    return [segment for segment in segments if segment], True


# Every operator that sends output somewhere: truncate, append, both streams
# (two spellings each), and the noclobber override. `2> f` tokenises the `2` on
# its own, so the operator after it is still a token of its own here.
# `>&2` names a file descriptor, not a path, and no protected path matches it.
_REDIRECTS = {">", ">>", "&>", ">|", ">&", "&>>"}


def _redirect_targets(words: Sequence[str]) -> List[str]:
    """Where this command writes by redirection: the word after each operator.

    Read from the tokens, not the text. `echo 'x > .githooks/commit-msg'` is
    one argument to `echo` and writes nothing, and this rule refused it — and
    refused the tests and the documents that say so — for as long as it matched
    characters.
    `_segments` tokenises the line the way a shell does, which is what makes the
    difference visible: a quoted string is never an operator.
    """
    return [words[index + 1] for index, word in enumerate(words)
            if word in _REDIRECTS and index + 1 < len(words)]


def _redirect_targets_in_text(segment: str) -> List[str]:
    """The old reading, kept for a line that would not tokenise: over-strict on
    purpose, because a redirect there can be glued to a word."""
    return re.findall(r">>?\s*([^\s;|&]+)", segment)


def _protects(path: str) -> bool:
    # `lstrip("./")` would eat the leading dot of `.githooks/…` — every path
    # here starts with one, so that silently matched nothing.
    cleaned = path.strip("'\"")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return any(cleaned == protected or cleaned.startswith(protected) for protected in PROTECTED)


# Options that take the NEXT word as their value — before the subcommand, and
# after `git config`. Without them a value is read as the subcommand, a key or
# a setting: `git -C ../kyc commit --no-verify` had `../kyc` as its subcommand.
_GIT_OPTION_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env", "--super-prefix"}
_CONFIG_OPTION_VALUE = {"--file", "-f", "--blob", "--type", "--default", "--comment", "--value", "--url"}
# `git config` asks or removes. Everything else that names the key with a value
# after it is a write. The bare words are git >= 2.46's subcommand form.
_CONFIG_VERBS = {"get", "list", "set", "unset", "edit", "remove-section", "rename-section"}
_CONFIG_READS = {"--get", "--get-all", "--get-regexp", "--get-urlmatch", "--list", "-l", "get", "list"}
_CONFIG_UNSETS = {"--unset", "--unset-all", "unset"}
_CONFIG_SECTION_REMOVALS = {"--remove-section", "--rename-section", "remove-section", "rename-section"}
_HOOKS_OFF_FOR_ONE_CALL = ("`{}` runs this command with the hooks turned off. The commit gate is not optional; "
                           f"the sweep finds what skips it and the next commit has to repair it. {SEE}")
# Said by both config refusals, so it is written once: the way out of either.
_RE_ARM = "Re-arming it — `git config core.hooksPath {hooks}` — is allowed and is what the sweep asks for."
_POINTS_AWAY = "`git config core.hooksPath {target}` points this repo away from {hooks}, which is where its gates live."
_REMOVAL = ("it removes core.hooksPath, and with none set git runs .git/hooks, which holds none of "
            "this repo's gates — the ones in {hooks} stop running.")
# `NAME=value cmd` and `env cmd` run cmd. Read as the program, one assignment in
# front skipped every check below.
_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")


def _environment_and_command(words: Sequence[str]) -> Tuple[List[str], List[str]]:
    """The `NAME=value` and `env` words in front of a command, and the command."""
    index = 0
    while index < len(words) and (_ASSIGNMENT.match(words[index]) or words[index] == "env"):
        index += 1
    return list(words[:index]), list(words[index:])


def _walk(words: Sequence[str], takes_value: Set[str]) -> Iterator[Tuple[int, str]]:
    """Each word and where it is, past the value of any option that takes one.

    Both parses below are this walk: a file path after `--file`, a directory
    after `-C`, is that option's value and not a word in its own right.
    """
    index = 0
    while index < len(words):
        if words[index] in takes_value:
            index += 2
            continue
        yield index, words[index]
        index += 1


def _git_subcommand(arguments: Sequence[str]) -> Tuple[str, List[str]]:
    """git's subcommand and the words after it: the first word that is neither
    a global option nor the value of one."""
    for index, word in _walk(arguments, _GIT_OPTION_VALUE):
        if not word.startswith("-"):
            return word, list(arguments[index + 1:])
    return "", []


def _config_refusal(arguments: Sequence[str], hooks_path: str) -> Optional[str]:
    """`git config …` — refused when it writes or removes core.hooksPath.

    A read is not a write. "No value after the key" is git asking, and
    `''` after it is git setting the empty value; they were one case here, so
    `git config core.hooksPath` was refused as pointing the repo at `<empty>`.
    """
    flags: Set[str] = set()
    operands: List[str] = []
    for _, word in _walk(arguments, _CONFIG_OPTION_VALUE):
        (flags.add if word.startswith("-") else operands.append)(word)
    if operands and operands[0] in _CONFIG_VERBS:
        flags.add(operands.pop(0))

    typed = " ".join(arguments)
    gone = f"{_REMOVAL} {_RE_ARM} {SEE}".format(hooks=hooks_path)
    # Removals before reads: `--get --unset` is refused by git, and here too.
    if flags & _CONFIG_SECTION_REMOVALS and operands and operands[0].lower() == "core":
        return f"`git config {typed}` removes the whole core section: {gone}"
    key = next((i for i, operand in enumerate(operands) if operand.lower() == "core.hookspath"), None)
    if key is None:
        return None
    if flags & _CONFIG_UNSETS:
        return f"`git config {typed}`: {gone}"
    if flags & _CONFIG_READS or key + 1 >= len(operands):
        return None
    target = operands[key + 1].strip("'\"")
    if target == hooks_path:
        return None
    return f"{_POINTS_AWAY} {_RE_ARM} {SEE}".format(target=target or "<empty>", hooks=hooks_path)


def _git_refusal(words: Sequence[str], hooks_path: str) -> Optional[str]:
    """`git …` — the three ways to run it without the hooks."""
    arguments = list(words[1:])
    # `git -c core.hooksPath=… <anything>`: the hooks are off for that one call.
    # git reads the key case-insensitively, and `--config-env=` is `-c` again.
    for argument in arguments:
        if argument.lower().removeprefix("--config-env=").startswith("core.hookspath="):
            return _HOOKS_OFF_FOR_ONE_CALL.format(" ".join(words))
    subcommand, rest = _git_subcommand(arguments)

    if subcommand == "config":
        return _config_refusal(rest, hooks_path)

    if subcommand in ("commit", "merge", "rebase", "cherry-pick", "revert"):
        if "--no-verify" in rest or "-n" in rest:
            return (f"`git {subcommand} --no-verify` skips the commit gate. Nothing is saved by it: the sweep "
                    "finds the commit on the next hook run and refuses every push until it is repaired. "
                    f"Fix what the gate is refusing instead. {SEE}")
    if subcommand == "push" and "--no-verify" in rest:
        return ("`git push --no-verify` skips the pre-push sweep, which is the layer that catches commits "
                f"that never met a gate. CI checks the same range after the push. {SEE}")
    return None


def refusal(command: str, hooks_path: str = ".githooks") -> Optional[str]:
    """Why this shell command must not run, or None to let it through."""
    segments, tokenised = _segments(command)
    for segment_words in segments:
        segment = " ".join(segment_words)
        environment, words = _environment_and_command(segment_words)
        # GIT_CONFIG_KEY_<n> and GIT_CONFIG_PARAMETERS are `git -c` from the environment.
        for assignment in environment:
            name, _, value = assignment.partition("=")
            if name.startswith("GIT_CONFIG") and "core.hookspath" in value.lower():
                return _HOOKS_OFF_FOR_ONE_CALL.format(assignment)
        if not words:
            continue
        program = words[0].rsplit("/", 1)[-1]

        if program == "git":
            found = _git_refusal(words, hooks_path)
            if found:
                return found

        if program == "agentsmith" and len(words) > 1 and words[1] == "approve":
            return ("`agentsmith approve` records the owner's permission and asks for it at a terminal — "
                    "an agent's shell has none, so this cannot complete here. Ask the owner to run it. " + SEE)

        # Writing to what the gate is made of: by redirection, or by a program
        # that takes the path as an argument.
        targets = _redirect_targets(segment_words) if tokenised else _redirect_targets_in_text(segment)
        for target in targets:
            if _protects(target):
                return (f"writing to {target.strip(chr(39)+chr(34))} changes the gate itself. It is a gated path: "
                        f"it changes under a design and a review like anything else. {SEE}")
        if program in WRITERS or (program in _IN_PLACE and any(a.startswith("-i") for a in words[1:])):
            for argument in words[1:]:
                if not argument.startswith("-") and _protects(argument):
                    return (f"`{program} {argument}` changes the gate itself. It is a gated path: it changes "
                            f"under a design and a review like anything else. {SEE}")
    return None
