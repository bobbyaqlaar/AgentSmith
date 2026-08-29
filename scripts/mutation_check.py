#!/usr/bin/env python3
"""
scripts/mutation_check.py — curated mutation testing.

A MUTATION is a single deliberate edit that breaks one property the code is
meant to hold. If no test fails, that property is unasserted — the suite is
green for a reason other than the one it claims. A mutation that does not
change the file, or that runs against a failing baseline, proves nothing.

This is the hand-picked half of the framework's mutation testing. Every entry
below was written while fixing the defect it names, and each one FAILED at
least one test at the moment it was added; keeping them means a later edit
cannot quietly remove a guard whose tests would then still pass. The
exhaustive half is mutmut (see pyproject.toml [tool.mutmut] and the
non-blocking CI job), which enumerates mutations nobody thought to write.

Usage:
    python3 scripts/mutation_check.py              # every suite
    python3 scripts/mutation_check.py --list       # names only, run nothing
    python3 scripts/mutation_check.py structured_output prompt_guard

Exit codes: 0 all mutations caught · 1 something survived, a target is stale,
or the baseline was already failing.

WHEN A TARGET GOES STALE. "target absent" means the code was refactored and
the mutation no longer applies. That is not a false alarm — the evidence for
that property has expired. Re-point the entry at the new code and confirm it
still fails a test; do not delete it because it stopped matching.
"""

from __future__ import annotations

import argparse
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Mutation:
    """One broken property.

    `before` must appear in `path` exactly `expect` times, and every occurrence
    is replaced. Pinning the count is the point: if it drifts, the code moved
    and the evidence for this property needs re-confirming, which is a
    different thing from the mutation having become wrong.
    """

    name: str
    path: str
    before: str
    after: str
    expect: int = 1


@dataclass(frozen=True)
class Suite:
    """A group of mutations and the tests that must notice them."""

    name: str
    tests: tuple[str, ...]
    mutations: tuple[Mutation, ...]


CATALOGUE: tuple[Suite, ...] = (
    Suite(
        name="pii",
        tests=(
            "runtime/test/test_input_guardrail.py",
            "runtime/test/test_trace_redactor.py",
            "runtime/test/test_luhn_parity.py",
        ),
        mutations=(
            Mutation(
                "digits are not normalised — an Emirates ID in Arabic-Indic "
                "numerals stops being PII",
                "runtime/pii_patterns.py",
                "return text.translate(_DIGIT_TRANSLATION)",
                "return text",
            ),
            Mutation(
                "the redactor forgets the personal identifiers it was taught",
                "runtime/trace_redactor.py",
                "for pattern in (_EMIRATES_ID_HYPHEN, _EMIRATES_ID_DIGITS, _PHONE):",
                "for pattern in ():",
            ),
            Mutation(
                "the fallback tenant goes back to reading TENANT_ID raw",
                "runtime/trace_redactor.py",
                "            self.default_tenant_id = resolve_tenant_id(tenant_id)",
                '            self.default_tenant_id = tenant_id or os.environ.get("TENANT_ID", "unknown")',
            ),
            Mutation(
                "an unresolvable tenant becomes the empty string, not 'unknown'",
                "runtime/trace_redactor.py",
                '            self.default_tenant_id = "unknown"',
                '            self.default_tenant_id = ""',
            ),
        ),
    ),
    Suite(
        name="prompt_guard",
        tests=(
            "runtime/test/test_prompt_guard.py",
            "scripts/test/test_security_prompt_guard_enforcement.py",
        ),
        mutations=(
            Mutation(
                "matching goes back to raw text — every Unicode evasion works again",
                "runtime/prompt_guard.py",
                "probe = _normalise(text)",
                "probe = text",
            ),
            Mutation(
                "separators accept whitespace only — 'ignore-all-previous' passes",
                "runtime/prompt_guard.py",
                r"[\s\-_]+",
                r"\s+",
                # One per pattern in the module; all of them have to go, or the
                # remaining ones still catch the hyphenated form.
                expect=10,
            ),
            Mutation(
                "ZWJ/ZWNJ count as padding — ordinary Persian and emoji trip the guard",
                "runtime/prompt_guard.py",
                '_LEGITIMATE_FORMAT_CHARS = {"\\u200c", "\\u200d"}',
                "_LEGITIMATE_FORMAT_CHARS = set()",
            ),
        ),
    ),
    Suite(
        name="structured_output",
        tests=("runtime/test/test_structured_output.py",),
        mutations=(
            Mutation(
                "an untagged fence outranks an explicit ```json one",
                "runtime/structured_output.py",
                "    out.extend(tagged)\n    out.extend(untagged)\n    out.extend(other)",
                "    out.extend(untagged)\n    out.extend(tagged)\n    out.extend(other)",
            ),
            Mutation(
                "bare spans stop being ordered by opener — `[{...}]` loses its brackets",
                "runtime/structured_output.py",
                "sorted(spans, key=lambda item: item[0])",
                "spans",
            ),
            Mutation(
                "the first candidate wins without being parsed",
                "runtime/structured_output.py",
                "    for label, candidate in candidates:\n"
                "        if _is_json(candidate):\n"
                "            return label, candidate\n"
                "    return candidates[0]",
                "    return candidates[0]",
            ),
            Mutation(
                "_is_json calls everything JSON",
                "runtime/structured_output.py",
                "    except (json.JSONDecodeError, ValueError):\n        return False",
                "    except (json.JSONDecodeError, ValueError):\n        return True",
            ),
            Mutation(
                "every fence tag counts as json — ```python hijacks extraction",
                "runtime/structured_output.py",
                "        if tag in _JSON_TAGS:",
                "        if True:",
            ),
            Mutation(
                "the fence tag stops being captured",
                "runtime/structured_output.py",
                r'r"```([A-Za-z0-9_+.-]*)[ \t]*\r?\n?(.*?)```"',
                r'r"```(?:json|JSON)?()[ \t]*\r?\n?(.*?)```"',
            ),
            Mutation(
                "an empty fence becomes a candidate and gets blamed for the failure",
                "runtime/structured_output.py",
                "        if not body:\n            continue",
                "        if False:\n            continue",
            ),
            Mutation(
                "a parse failure stops naming the block it tried",
                "runtime/structured_output.py",
                'f"invalid JSON in {origin}: {exc}"',
                'f"invalid JSON: {exc}"',
            ),
            Mutation(
                "a schema failure stops naming the block it tried",
                "runtime/structured_output.py",
                'f"schema validation failed for {origin}: {exc}"',
                'f"schema validation failed: {exc}"',
            ),
            Mutation(
                "the error quotes the model's payload into the log",
                "runtime/structured_output.py",
                'f"invalid JSON in {origin}: {exc}"',
                'f"invalid JSON in {candidate}: {exc}"',
            ),
        ),
    ),
    Suite(
        name="circuit_breaker",
        tests=(
            "scripts/test/test_circuit_breaker.py",
            "scripts/test/test_breaker_fail_open.py",
            "scripts/test/test_cost_router.py",
        ),
        mutations=(
            Mutation(
                "the burst limit goes back to a bare int() — an empty var kills the import",
                "scripts/circuit_breaker.py",
                'BURST_TOKEN_LIMIT = env_number("AGENT_BURST_TOKEN_LIMIT", 50_000, cast=int)',
                'BURST_TOKEN_LIMIT = int(os.environ.get("AGENT_BURST_TOKEN_LIMIT", "50000"))',
            ),
            Mutation(
                "the monthly cap goes back to a bare float()",
                "scripts/circuit_breaker.py",
                'MONTHLY_USD_CAP = env_number("AGENT_MONTHLY_USD_CAP", 150.0)',
                'MONTHLY_USD_CAP = float(os.environ.get("AGENT_MONTHLY_USD_CAP", "150.0"))',
            ),
            Mutation(
                "env_number stops treating a declared-but-empty var as unset",
                "scripts/_shared.py",
                '    raw = (os.environ.get(var) or "").strip()\n    if not raw:\n        return default',
                "    raw = os.environ.get(var, str(default))",
            ),
            Mutation(
                "a malformed limit falls back silently",
                "scripts/_shared.py",
                '        print(\n'
                '            f"⚠️  {var}={raw!r} is not a number — using {default}",\n'
                '            file=sys.stderr,\n'
                '        )\n'
                '        return default',
                "        return default",
            ),
            Mutation(
                "the breaker import moves back inside the one try — the fail-open "
                "handler raises UnboundLocalError",
                "scripts/agent_logger.py",
                "        try:\n"
                "            from circuit_breaker import (\n"
                "                CircuitBreakerTripped,\n"
                "                audit_token_velocity_circuit,\n"
                "            )\n"
                "        except Exception as exc:",
                '        try:\n'
                '            from circuit_breaker import (\n'
                '                CircuitBreakerTripped,\n'
                '                audit_token_velocity_circuit,\n'
                '            )\n'
                '            audit_token_velocity_circuit(input_tokens, output_tokens)\n'
                '        except CircuitBreakerTripped as tripped:\n'
                '            print(f"[agent_logger] {tripped}", file=sys.stderr)\n'
                '        except Exception as exc:',
            ),
        ),
    ),
    Suite(
        name="conversation_memory",
        tests=("runtime/test/test_memory_and_vector.py",),
        mutations=(
            Mutation(
                "nothing is protected — eviction deletes the system prompt first",
                "runtime/conversation_memory.py",
                'PROTECTED_ROLES = frozenset({"system"})',
                "PROTECTED_ROLES = frozenset()",
            ),
            Mutation(
                "the guard swallows the budget — nothing is ever evicted",
                "runtime/conversation_memory.py",
                "            if len(evictable) <= 1:\n                break",
                "            if len(evictable) <= 99:\n                break",
            ),
            Mutation(
                "the estimate goes back to chars//4 — Arabic reads 65% low",
                "runtime/conversation_memory.py",
                "    return max(1, int(alnum / 4 + symbols * 0.6 + non_ascii * 1.2))",
                "    return max(1, len(text) // 4)",
            ),
            Mutation(
                "the buffer stops saying it cannot shrink",
                "runtime/conversation_memory.py",
                "        if total > self.token_budget:\n            logger.warning(",
                "        if False:\n            logger.warning(",
            ),
        ),
    ),
    Suite(
        name="degraded_defaults",
        tests=(
            "runtime/test/test_degraded_defaults.py",
            "runtime/test/test_memory_and_vector.py",
            "runtime/test/test_llm_gateway_budget.py",
        ),
        mutations=(
            Mutation(
                "an empty selector stops meaning unset — BUDGET_BACKEND='' crashes again",
                "runtime/environment.py",
                '    raw = os.environ.get(var, "").strip().lower()\n    if not raw:\n        return default',
                "    raw = os.environ.get(var, default).lower()",
            ),
            Mutation(
                "a typo'd backend silently resolves to the default",
                "runtime/environment.py",
                "    if raw not in options:\n        raise ValueError(",
                "    if False:\n        raise ValueError(",
            ),
            Mutation(
                "a degraded default is logged at the same level everywhere",
                "runtime/environment.py",
                '    if environment in {"staging", "production"}:\n'
                '        logger.error("%s [environment=%s]", message, environment)\n'
                '    else:\n'
                '        logger.info("%s [environment=%s]", message, environment)',
                '    logger.info("%s [environment=%s]", message, environment)',
            ),
            Mutation(
                "one degraded default silences the others",
                "runtime/environment.py",
                "    if key in _degraded_warned:\n        return\n    _degraded_warned.add(key)",
                "    if _degraded_warned:\n        return\n    _degraded_warned.add(key)",
            ),
            Mutation(
                "the warning repeats on every call",
                "runtime/environment.py",
                "    if key in _degraded_warned:\n        return\n    _degraded_warned.add(key)",
                "    _degraded_warned.add(key)",
            ),
            Mutation(
                "the per-worker spend cap stops announcing itself",
                "runtime/llm_gateway.py",
                '    warn_degraded_default(\n        "budget-backend-memory",',
                '    _unused = (\n        "budget-backend-memory",',
            ),
            Mutation(
                "the in-process vector index stops announcing itself",
                "runtime/vector_store.py",
                '    warn_degraded_default(\n        "vector-backend-memory",',
                '    _unused = (\n        "vector-backend-memory",',
            ),
            Mutation(
                "VECTOR_BACKEND aliases are narrowed — a tenant on =pgvector breaks",
                "runtime/vector_store.py",
                '_VECTOR_ALIASES = ("memory", "mem", "inmemory", "postgres", "pgvector", "pg")',
                '_VECTOR_ALIASES = ("memory", "postgres")',
            ),
            Mutation(
                "the fake embedder stops announcing itself",
                "runtime/embeddings.py",
                '    warn_degraded_default(\n        "embedder-hash",',
                '    _unused = (\n        "embedder-hash",',
            ),
            Mutation(
                "the embedder identity collapses to its dimension",
                "runtime/embeddings.py",
                '        return f"hash:{self.dim}"',
                '        return f"{self.dim}"',
            ),
            Mutation(
                "the retrieval span stops naming the embedder",
                "runtime/vector_store.py",
                '        if embedder:\n            span.set_attribute("agent.retrieval.embedder", embedder)',
                "        pass",
            ),
            Mutation(
                "_identity_of raises on an embedder that predates `identity`",
                "runtime/vector_store.py",
                "    try:\n        value = embedder.identity\n    except Exception:\n        return None",
                "    value = embedder.identity",
            ),
        ),
    ),
)


def _dirty_catalogue_files(suites: tuple[Suite, ...]) -> list[str]:
    """Catalogue files with uncommitted changes.

    This harness REWRITES the files it mutates. Running it over uncommitted work
    risks losing that work, and a run killed before its restore (a timeout, a
    SIGKILL) leaves the mutation in place — which is how a stray edit reaches a
    commit. Refusing to start on a dirty file covers both: it protects work in
    progress, and it is what surfaces the residue of a previous crashed run.
    """
    paths = sorted({m.path for suite in suites for m in suite.mutations})
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--", *paths],
            cwd=REPO, capture_output=True, text=True, check=True,
        )
    except Exception:
        return []  # not a git checkout, or no git — nothing to assert
    return [line[3:] for line in result.stdout.splitlines() if line.strip()]


def _install_restore_handlers(target: Path, original: str) -> None:
    """Put the file back if this run is interrupted.

    Covers Ctrl-C and SIGTERM. A SIGKILL cannot be caught, which is why the
    dirty-file check above exists as the backstop.
    """

    def _restore(signum, frame):  # pragma: no cover - signal path
        target.write_text(original, encoding="utf-8")
        print(f"\n  interrupted — restored {target.relative_to(REPO)}", file=sys.stderr)
        raise SystemExit(130)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _restore)
        except (ValueError, OSError):  # pragma: no cover - non-main thread
            pass


def _pytest(tests: tuple[str, ...]) -> subprocess.CompletedProcess:
    args = [sys.executable, "-m", "pytest", *tests, "-q", "-p", "no:cacheprovider"]
    if _has_timeout_plugin():
        # A mutation can turn a loop into an infinite one. Without a per-test
        # timeout that hangs the whole run rather than reporting a survivor.
        args.append("--timeout=120")
    # check=False deliberately: a NON-ZERO exit is the good outcome here. It
    # means the suite noticed the mutation, which is the entire point.
    return subprocess.run(args, cwd=REPO, capture_output=True, text=True, check=False)


def _has_timeout_plugin() -> bool:
    try:
        import pytest_timeout  # noqa: F401
    except Exception:
        return False
    return True


def _last_line(proc: subprocess.CompletedProcess) -> str:
    lines = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()]
    return lines[-1] if lines else "(no output)"


def run_suite(suite: Suite) -> list[str]:
    """Run one suite. Returns a list of problems; empty means every mutation died."""
    problems: list[str] = []

    # A dirty baseline makes every result below meaningless — this has happened.
    baseline = _pytest(suite.tests)
    if baseline.returncode != 0:
        return [
            f"{suite.name}: BASELINE ALREADY FAILING — {_last_line(baseline)}. "
            f"Nothing below this line can be trusted; fix the suite first."
        ]

    for mutation in suite.mutations:
        target = REPO / mutation.path
        original = target.read_text(encoding="utf-8")

        occurrences = original.count(mutation.before)
        if occurrences != mutation.expect:
            problems.append(
                f"{suite.name}: STALE TARGET ({occurrences} matches, expected "
                f"{mutation.expect}) — {mutation.name}"
                f"\n      in {mutation.path}; re-point it at the new code, do not delete it."
            )
            continue

        previous_handlers = (
            signal.getsignal(signal.SIGINT),
            signal.getsignal(signal.SIGTERM),
        )
        _install_restore_handlers(target, original)
        try:
            target.write_text(original.replace(mutation.before, mutation.after),
                              encoding="utf-8")
            if target.read_text(encoding="utf-8") == original:
                problems.append(f"{suite.name}: MUTATION DID NOT APPLY — {mutation.name}")
                continue
            result = _pytest(suite.tests)
        finally:
            target.write_text(original, encoding="utf-8")
            for sig, handler in zip(
                (signal.SIGINT, signal.SIGTERM), previous_handlers, strict=True
            ):
                try:
                    signal.signal(sig, handler)
                except (ValueError, OSError):  # pragma: no cover
                    pass

        if result.returncode == 0:
            problems.append(
                f"{suite.name}: SURVIVED — {mutation.name}"
                f"\n      the tests pass with this broken; the property is unasserted."
            )
        else:
            print(f"  caught   {mutation.name[:88]}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("suites", nargs="*", help="suite names (default: all)")
    parser.add_argument("--list", action="store_true", help="list suites and exit")
    args = parser.parse_args()

    if args.list:
        for suite in CATALOGUE:
            print(f"{suite.name:22} {len(suite.mutations):2} mutations  "
                  f"{len(suite.tests)} test file(s)")
        return 0

    selected = CATALOGUE
    if args.suites:
        known = {s.name for s in CATALOGUE}
        unknown = set(args.suites) - known
        if unknown:
            print(f"unknown suite(s): {', '.join(sorted(unknown))}", file=sys.stderr)
            print(f"known: {', '.join(sorted(known))}", file=sys.stderr)
            return 1
        selected = tuple(s for s in CATALOGUE if s.name in set(args.suites))

    dirty = _dirty_catalogue_files(selected)
    if dirty:
        print(
            "🛑  refusing to run: these files have uncommitted changes and this "
            "harness rewrites them.\n",
            file=sys.stderr,
        )
        for path in dirty:
            print(f"      {path}", file=sys.stderr)
        print(
            "\n    Commit or stash them first. If you did not edit these, a previous "
            "run\n    was killed before it could restore one — check the diff before "
            "discarding it.",
            file=sys.stderr,
        )
        return 1

    problems: list[str] = []
    total = 0
    for suite in selected:
        print(f"\n── {suite.name} ({len(suite.mutations)} mutations)")
        total += len(suite.mutations)
        problems.extend(run_suite(suite))

    print()
    if problems:
        print(f"🛑  {len(problems)} problem(s) across {total} mutation(s):\n")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print(f"✅  {total} mutations, all caught")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
