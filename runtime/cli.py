"""
runtime/cli.py — `agentsmith`, the framework's entry point.

WHY THIS EXISTS

Everything a user does with AgentSmith went through fifteen zsh functions and
~61 lines that `install-ai-stack.sh` appended to `~/.zshrc`. That has four
defects for something meant to be a product:

  drift        the tenant scaffold lived in the installer AND in every user's
               shell profile. Editing the repo left the machine writing the old
               one, which happened twice in a single day.
  OS lock-in   zsh functions exist only in an interactive macOS/Linux shell.
               Windows has none, a Dockerfile `RUN` has none, CI has none.
  untestable   not one of the fifteen was covered by a test, because they only
               exist after an interactive install.
  invasive     appending to a login shell is the most intrusive thing the
               installer does, and why re-running it feels risky.

A console script has none of those. `pip install agentsmith-runtime` and
`agentsmith tenant init` works in PowerShell, in a container, in a CI step —
with no profile to source and nothing to un-edit on uninstall.

MIGRATION, finished. Every function is now a subcommand here; the logic lives
in runtime/machine/ (.agent-rfc/designs/agentsmith-cli.md). The installer no
longer writes a profile block, and removes the old one.

WHAT A CHILD PROCESS CANNOT DO is export into its parent shell, which is how
the functions "set" a mode. Nothing needs to any more: `agentsmith mode` writes
~/.agent-framework/state/mode, which the gateway and the git hooks read — so
the mode reaches IDEs, git GUIs and hooks, which an export never did.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Optional, Sequence

# The scaffold's shape is a product decision, so it lives here as data rather
# than as a heredoc: a test can assert on it, and there is exactly one copy.
STACKS = ("python-fastapi", "ts-react", "go")
ISOLATIONS = ("shared", "dedicated")


# A tenant id has to survive being written into YAML, read back, and spliced
# into an environment variable NAME (HITL_ENCRYPTION_KEY_<TENANT>). This is the
# set that does all three. Deliberately narrow: this runs once, when a tenant is
# created, which is the only moment the id is free to change.
TENANT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def validate_tenant_id(tenant_id: str) -> str:
    """The tenant id, or a ValueError explaining what it has to look like."""
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ValueError("tenant id must be a non-empty string")
    if not TENANT_ID_PATTERN.match(tenant_id):
        raise ValueError(
            f"tenant id {tenant_id!r} must be 1-64 characters of letters, digits, "
            f"dot, underscore or hyphen, starting with a letter or digit. It is "
            f"written into YAML, resolved back by runtime/tenancy.py, and spliced "
            f"into the HITL_ENCRYPTION_KEY_<TENANT> variable name."
        )
    return tenant_id


def _default_framework_version() -> str:
    """The release to declare, without a source-checkout marker.

    framework_version() reports `1.3.0+src` from a checkout, which is the right
    answer for "what is running" and the wrong one to write into a tenant's
    config: the tenant is declaring which RELEASE it targets. The literal that
    used to be here was a second copy of the version number and would have
    drifted from pyproject.toml at the next bump.
    """
    from runtime.version import SOURCE_SUFFIX, framework_version

    version = framework_version()
    return version[: -len(SOURCE_SUFFIX)] if version.endswith(SOURCE_SUFFIX) else version


def tenant_yaml(
    tenant_id: str, *, isolation: str = "shared", framework_version: Optional[str] = None
) -> str:
    """The scaffolded `.agenticframework/tenant.yaml`, as text.

    Every key below is READ by something — that is the entry criterion, learned
    from shipping five that were not. `environments:` with `phoenix_namespace`,
    `eval_fail_below` and `redaction_profile` used to be here and was removed:
    nothing read any of it, and two of the three were actively misleading.

    Modes are QUOTED because YAML 1.1 parses a bare `off` as the boolean false,
    which would silently mean something no mode name matches.

    So is the TENANT ID, for the same reason and for a while it was not: the
    quoting was applied to the values someone had thought about rather than to
    the class of problem. `agentsmith tenant init off` wrote `id: off`, YAML
    read False, and runtime/tenancy.py resolved the tenant to the string
    "False" — which then keyed the spend ledger, the HITL encryption variable
    and every span. `123` became an int the same way.
    """
    validate_tenant_id(tenant_id)
    quoted_id = json.dumps(tenant_id)  # a JSON string is a valid YAML scalar
    return f"""# {tenant_id} — AgentSmith tenant configuration (SPECS.md §23)
#
# Generated by `agentsmith tenant init`. Every key here is read by the runtime;
# each `security.*` line is overridden by the environment variable named beside
# it, and a declaration outranks an ambient export — see runtime/config.py.

tenant:
  id: {quoted_id}
  name: {quoted_id}
  # A MARKER, not a control: no code reads it. It tells an operator which
  # manifests to apply (runtime/k8s/dedicated-tenant/ for `dedicated`).
  isolation: {isolation}
  # owner: you@example.com        # else `git config user.email`

framework:
  version: "{framework_version or _default_framework_version()}"

# Security posture. Quoted on purpose: YAML 1.1 reads a bare `off` as false.
security:
  prompt_guard: "default"           # off|warn|default|strict  (PROMPT_GUARD)
  input_guardrail: "default"        # off|default|custom       (INPUT_GUARDRAIL)
  tool_allowlist_strict: false      # deny-by-default tools    (TOOL_ALLOWLIST_STRICT)
  ip_redaction: false               # scrub IPs from spans     (ENABLE_IP_REDACTION)
  # Tool arguments and results on the span. OFF by default: it is a new
  # egress channel. When on, payloads go on the attribute names
  # trace_redactor already scrubs, so the profile applies.
  trace_tool_payloads: false        #                          (TRACE_TOOL_PAYLOADS)

moderation:
  mode: "optional"                  # off|optional|required    (MODERATION_HOOK)
  # hook: mypackage.moderation:classify_output

budget:
  monthly_usd_cap: 150              # AGENT_MONTHLY_USD_CAP overrides

workflow:
  engine: temporal                  # WORKER_BACKEND overrides
  task_queue: {tenant_id}           # TASK_QUEUE overrides

delivery:
  platform: on-prem                 # see docs/delivery-model.md
  data_access_pattern: api-only

# Environment variables permitted to outrank the declarations above. Empty by
# default: an ambient export must not silently relax a declared posture.
# env_overrides: [AGENT_MONTHLY_USD_CAP]
"""


# ── tenant init ──────────────────────────────────────────────────────────────


def _templates_dir() -> Optional[Path]:
    """Where `agentsmith tenant init` copies CI workflows from.

    The installed location first, then the checkout — so a developer running
    from a clone gets their own templates rather than the machine's stale copy,
    which is the drift this whole file exists to end.
    """
    for candidate in (
        Path.home() / ".agent-framework" / "workflow-templates",
        Path(__file__).resolve().parent.parent / "workflow-templates",
    ):
        if candidate.is_dir():
            return candidate
    return None


class FrameworkRootError(RuntimeError):
    """Refusing to scaffold a tenant into the framework's own checkout."""


# Markers that identify the framework's own repository. `pyproject.toml`
# declaring the package name is the definitive one — that string exists in
# exactly one project. The others are corroborating: a tenant repo has no
# reason to ship the installer or the workflow templates it is a consumer of.
FRAMEWORK_MARKERS = (
    ("pyproject.toml", 'name = "agentsmith-runtime"'),
    ("install-ai-stack.sh", None),
    ("workflow-templates", None),
    ("templates/agent-rules.yaml", None),
)


def looks_like_framework(root: Path) -> Optional[str]:
    """The marker that says this is the framework's checkout, or None.

    Written after scaffolding a tenant into the framework repo by accident:
    `tenant init` defaults --root to the working directory, and running it from
    the wrong terminal is a two-second mistake. Twelve tests went red because
    the stray `tenant.yaml` declared a security posture that then outranked the
    environment those tests set — loud, but only because a precedence change
    two days earlier happened to make it so. It should not depend on that.

    Requires TWO markers, not one. A single check on `install-ai-stack.sh`
    would refuse in a repo that merely vendored the installer, and a guard that
    fires on legitimate work is one people learn to bypass.
    """
    found: list[str] = []
    for name, needle in FRAMEWORK_MARKERS:
        path = root / name
        if not path.exists():
            continue
        if needle is None:
            found.append(name)
        else:
            try:
                if needle in path.read_text(encoding="utf-8"):
                    found.append(f"{name} declares {needle!r}")
            except OSError:
                continue
    return " and ".join(found) if len(found) >= 2 else None


# A callee missing from this list makes GitHub reject the whole workflow as
# invalid, not just the missing job — so they ship together with their caller.
WORKFLOWS = (
    "cd-staging.yml",
    "cd-production.yml",
    "eval-scorecard.yml",
    "eval-fairness.yml",
    "eval-hallucination.yml",
    "eval-ttft-live.yml",
    "eval-security.yml",
)


def init_tenant(
    tenant_id: str,
    root: Path,
    *,
    stack: str = "python-fastapi",
    isolation: str = "shared",
    force: bool = False,
    allow_framework_root: bool = False,
) -> list[str]:
    """Scaffold a tenant. Returns the paths written, relative to `root`.

    Never overwrites without `force`: a tenant.yaml is edited by hand after
    generation, and silently replacing it would discard a declared posture.

    Refuses to write into the framework's own checkout — see
    `looks_like_framework`. `force` does NOT bypass that: it means "replace
    files I already own", which is a different question from "write into the
    wrong repository", and overloading one flag onto both is how a guard gets
    disabled by someone solving an unrelated problem.
    """
    marker = None if allow_framework_root else looks_like_framework(root)
    if marker:
        raise FrameworkRootError(
            f"{root} looks like the AgentSmith framework itself ({marker}).\n"
            f"A tenant scaffolded here would declare a security posture and a "
            f"budget that the framework's own tests then run against.\n"
            f"Run this in the tenant's repository, pass --root, or override "
            f"with --allow-framework-root if you really mean it."
        )
    # Every argument is checked before the first mkdir. The id used to be
    # validated inside tenant_yaml(), which runs after `.agenticframework/`
    # exists — so a rejected id left a directory behind and the next run found
    # a half-scaffolded tenant.
    validate_tenant_id(tenant_id)
    if isolation not in ISOLATIONS:
        raise ValueError(f"isolation must be one of {ISOLATIONS}, got {isolation!r}")
    if stack not in STACKS:
        raise ValueError(f"stack must be one of {STACKS}, got {stack!r}")

    written: list[str] = []
    cfg_dir = root / ".agenticframework"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg = cfg_dir / "tenant.yaml"
    if cfg.exists() and not force:
        print("  = .agenticframework/tenant.yaml exists — left untouched")
    else:
        cfg.write_text(tenant_yaml(tenant_id, isolation=isolation))
        written.append(".agenticframework/tenant.yaml")

    templates = _templates_dir()
    if templates is None:
        print(
            "  ! no workflow-templates found — CI workflows not written. "
            "Re-run install-ai-stack.sh, or use a checkout.",
            file=sys.stderr,
        )
        return written

    wf_dir = root / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    for name in (f"ci-{stack}.yml", *WORKFLOWS):
        src = templates / name
        if not src.is_file():
            print(f"  ! template missing, skipped: {name}", file=sys.stderr)
            continue
        dest = wf_dir / name
        if dest.exists() and not force:
            print(f"  = .github/workflows/{name} exists — left untouched")
            continue
        # Same substitution hooks/post-checkout makes; copied verbatim, the
        # workflows carried a literal `{{TENANT_ID}}`.
        dest.write_text(src.read_text(encoding="utf-8").replace("{{TENANT_ID}}", tenant_id), encoding="utf-8")
        written.append(f".github/workflows/{name}")

    written += _copy_composite_actions(root)
    return written


def _actions_dir() -> Optional[Path]:
    """Composite actions the cd-* workflows call as `./.github/actions/<name>`.

    Installed location first, then the checkout — the same order, for the same
    reason, as `_templates_dir`.
    """
    for candidate in (
        Path.home() / ".agent-framework" / "github-actions",
        Path(__file__).resolve().parent.parent / ".github" / "actions",
    ):
        if candidate.is_dir():
            return candidate
    return None


def _copy_composite_actions(root: Path) -> list[str]:
    """`uses: ./.github/actions/<name>` resolves inside the TENANT's repo, so the
    actions must be copied in beside the workflows that call them.

    hooks/post-checkout always did this; `tenant init` wrote cd-staging.yml and
    cd-production.yml without it, and both fail at their first `uses:` with
    "Can't find 'action.yml'". Per action, never overwriting — a tenant may
    have adjusted one (KYC Sentinel diffs its gcp-auth against the framework's
    in CI precisely because they are copies).
    """
    source = _actions_dir()
    if source is None:
        print(
            "  ! no composite actions found — cd-staging.yml/cd-production.yml will fail "
            "at ./.github/actions/*. Re-run install-ai-stack.sh, or use a checkout.",
            file=sys.stderr,
        )
        return []
    written = []
    for action in sorted(p for p in source.iterdir() if p.is_dir()):
        dest = root / ".github" / "actions" / action.name
        if dest.exists():
            continue
        shutil.copytree(action, dest)
        written.append(f".github/actions/{action.name}")
    return written


# ── commands ─────────────────────────────────────────────────────────────────


def _cmd_tenant_init(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else Path.cwd()
    try:
        written = init_tenant(
            args.tenant_id,
            root,
            stack=args.stack,
            isolation=args.isolation,
            force=args.force,
            allow_framework_root=args.allow_framework_root,
        )
    except FrameworkRootError as exc:
        print(f"agentsmith: refusing to scaffold here.\n{exc}", file=sys.stderr)
        return 3
    except ValueError as exc:
        print(f"agentsmith: {exc}", file=sys.stderr)
        return 2
    for path in written:
        print(f"  + {path}")
    print(f"\nTenant '{args.tenant_id}' scaffolded ({args.stack}, {args.isolation}).")
    if ".agenticframework/tenant.yaml" in written:
        # Declared in OPERATIONS.md, the portal's audit route and its event
        # types since the shell-function days, and written by nothing once the
        # scaffold moved here.
        import os

        from runtime.machine.policy import audit_log_event

        audit_log_event(
            "tenant_created",
            os.environ.get("AGENT_OWNER_ID") or "unknown",
            args.tenant_id,
            {"stack": args.stack, "isolation": args.isolation},
        )
    # The generated workflows run `python3 scripts/*.py` from THIS repo, and
    # those import runtime.* and read fixtures/. Vendoring them is
    # hooks/post-checkout's job — one implementation, not a second copy here
    # to drift — so say plainly that the scaffold is not usable until it runs.
    if not (root / "scripts" / "run-security-checks.py").exists():
        print(
            "\nNot done yet: scripts/, runtime/ and fixtures/ are not vendored, and every "
            "scripts/*.py step in the workflows above fails until they are.\n"
            "Commit, then run `git checkout` (no path — `git checkout .` discards "
            "uncommitted work) to fire the AgentSmith post-checkout hook."
        )
    if args.isolation == "dedicated":
        print("Apply runtime/k8s/dedicated-tenant/ to provision its own worker pool.")
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    """Delegates to verify_system, which already owns every check.

    It used to look beside this file (`<package>/../scripts/`), which exists in a
    checkout and never in an installed package — so `agentsmith doctor` could
    only ever run from a clone.
    """
    import subprocess

    from runtime.machine.state import find_script

    script = find_script("verify_system.py")
    if script is None:
        print("agentsmith: verify_system.py not found in ./scripts/ or ~/.agent-framework/scripts/", file=sys.stderr)
        return 1
    return subprocess.run([sys.executable, str(script), *args.checks], check=False).returncode


# `shellenv` was removed: it printed `export AI_STACK_MODE=…` for a profile to
# eval, and an exported mode outranks the machine's mode file for every process
# that shell starts — the opposite of what `agentsmith mode` is for.


def _cmd_mode(args: argparse.Namespace) -> int:
    from runtime.machine import ops

    return ops.mode(args.mode)


def _cmd_check(args: argparse.Namespace) -> int:
    from runtime.machine import ops

    return ops.check()


def _cmd_status(args: argparse.Namespace) -> int:
    from runtime.machine import ops

    return ops.status()


def _cmd_models(args: argparse.Namespace) -> int:
    from runtime.machine import ops

    return ops.models("judge" if args.judge else "ollama")


def _cmd_dashboard(args: argparse.Namespace) -> int:
    from runtime.machine import ops

    return ops.dashboard_start() if args.action == "start" else ops.dashboard_stop()


def _cmd_evals(args: argparse.Namespace) -> int:
    from runtime.machine import ops

    return ops.evals()


def _cmd_promote(args: argparse.Namespace) -> int:
    from runtime.machine import ops

    return ops.promote(args.case_id, args.query, args.output)


def _cmd_tenant_promote(args: argparse.Namespace) -> int:
    from runtime.machine import ops

    return ops.tenant_promote(args.tenant_id, args.from_env, args.to_env)


def _cmd_tenant_onprem(args: argparse.Namespace) -> int:
    from runtime.machine import ops

    return ops.onprem_scaffold()


def _cmd_upgrade(args: argparse.Namespace) -> int:
    from runtime.machine.upgrade import upgrade

    return upgrade(Path.cwd(), args.to or _default_framework_version())


def _cmd_scrub(args: argparse.Namespace) -> int:
    from runtime.machine import ops

    return ops.scrub(args.directory, args.yes)


def _cmd_uninstall(args: argparse.Namespace) -> int:
    from runtime.machine import ops

    if args.legacy_profile_only:
        return ops.remove_profile_blocks()
    return ops.uninstall(args.yes, args.purge)


def _cmd_hooks_bypass_check(args: argparse.Namespace) -> int:
    """Exit 0 when the hooks may be bypassed. Called by the four git hooks when a
    bypass is requested and an org policy file exists — see runtime/machine/policy.py."""
    from runtime.machine.policy import bypass_decision

    decision = bypass_decision()
    print(f"AgentSmith: {decision.message}", file=sys.stderr)
    return 0 if decision.allowed else 1


def _cmd_purge_idempotency(args: argparse.Namespace) -> int:
    """Delete idempotency rows past their TTL.

    `idempotency_keys.expires_at` is only read in the lookup's WHERE clause, so
    an expired row stops being returned and never stops existing — the table
    grows by one row per gateway call. `IdempotencyStore.purge_expired` has
    existed the whole time with no caller anywhere; this is the caller, so the
    Day-2 task in OPERATIONS.md §9 can name a command instead of raw SQL.
    """
    try:
        from runtime.idempotency import IdempotencyStore

        deleted = IdempotencyStore().purge_expired()
    except Exception as exc:
        print(f"agentsmith: idempotency purge failed: {exc}", file=sys.stderr)
        return 1
    if deleted < 0:
        print("backend expires its own keys — nothing to purge")
    else:
        print(f"purged {deleted} expired idempotency key(s)")
    return 0


def _cmd_version(args: argparse.Namespace) -> int:
    try:
        from importlib.metadata import version

        print(version("agentsmith-runtime"))
    except Exception:
        print("unknown (not installed as a package)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentsmith", description="AgentSmith framework CLI"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    tenant = sub.add_parser("tenant", help="tenant scaffolding").add_subparsers(
        dest="tenant_command", required=True
    )
    init = tenant.add_parser("init", help="scaffold .agenticframework/ and CI workflows")
    init.add_argument("tenant_id")
    init.add_argument("--stack", default="python-fastapi", choices=list(STACKS))
    init.add_argument("--isolation", default="shared", choices=list(ISOLATIONS))
    init.add_argument("--root", default=None, help="target repo (default: cwd)")
    init.add_argument("--force", action="store_true", help="overwrite existing files")
    init.add_argument(
        "--allow-framework-root",
        action="store_true",
        help="scaffold even where the framework's own checkout is detected",
    )
    init.set_defaults(func=_cmd_tenant_init)

    promote_tenant = tenant.add_parser("promote", help="gate on staging evals, then open the develop → main PR")
    promote_tenant.add_argument("tenant_id")
    promote_tenant.add_argument("--from", dest="from_env", required=True)
    promote_tenant.add_argument("--to", dest="to_env", required=True)
    promote_tenant.set_defaults(func=_cmd_tenant_promote)

    onprem = tenant.add_parser("onprem-scaffold", help="copy the on-prem deployment template into ./deploy/onprem/")
    onprem.set_defaults(func=_cmd_tenant_onprem)

    doctor = sub.add_parser("doctor", help="run verify_system checks")
    doctor.add_argument("checks", nargs="*", help="e.g. --check-kg --check-hooks")
    doctor.set_defaults(func=_cmd_doctor)

    mode = sub.add_parser("mode", help="set the machine's mode (no argument: print it)")
    mode.add_argument("mode", nargs="?", choices=["local", "hybrid", "off"])
    mode.set_defaults(func=_cmd_mode)

    sub.add_parser("check", help="health check: Phoenix, Ollama or API keys, unresolved log entries").set_defaults(
        func=_cmd_check
    )
    sub.add_parser("status", help="mode, hooks, Phoenix, judge, owner, network").set_defaults(func=_cmd_status)

    models = sub.add_parser("models", help="the models the merged registry routes to")
    which = models.add_mutually_exclusive_group()
    which.add_argument("--ollama", action="store_true", help="Ollama ids, space-separated (default)")
    which.add_argument("--judge", action="store_true", help="the judge model in effect")
    models.set_defaults(func=_cmd_models)

    dashboard = sub.add_parser("dashboard", help="start or stop Phoenix (the shared Docker stack when present)")
    dashboard.add_argument("action", choices=["start", "stop"])
    dashboard.set_defaults(func=_cmd_dashboard)

    sub.add_parser("evals", help="sync HITL feedback from Phoenix, then run the eval scorecard").set_defaults(
        func=_cmd_evals
    )

    promote = sub.add_parser("promote", help="promote a fix to the golden dataset and re-run evals")
    promote.add_argument("case_id")
    promote.add_argument("query")
    promote.add_argument("output")
    promote.set_defaults(func=_cmd_promote)

    upgrade = sub.add_parser("upgrade", help="refresh this vendored tenant's framework copy and commit it")
    upgrade.add_argument("--to", default=None, help="version to declare (default: the installed release)")
    upgrade.set_defaults(func=_cmd_upgrade)

    scrub = sub.add_parser("scrub", help="delete generated IDE-rule files under a directory, after listing them")
    scrub.add_argument("directory", nargs="?", default=None)
    scrub.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    scrub.set_defaults(func=_cmd_scrub)

    uninstall = sub.add_parser("uninstall", help="restore git config and remove the command from this machine")
    uninstall.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    uninstall.add_argument("--purge", action="store_true", help="also remove ~/.agent-framework and ~/.git_templates")
    uninstall.add_argument(
        "--legacy-profile-only", action="store_true",
        help="only remove the shell-function block older installs appended to a shell profile",
    )
    uninstall.set_defaults(func=_cmd_uninstall)

    hooks = sub.add_parser("hooks", help="internal: called by the git hooks").add_subparsers(
        dest="hooks_command", required=True
    )
    hooks.add_parser("bypass-check", help="exit 0 when the org policy allows a hook bypass").set_defaults(
        func=_cmd_hooks_bypass_check
    )

    purge = sub.add_parser(
        "purge-idempotency", help="delete idempotency rows past their TTL"
    )
    purge.set_defaults(func=_cmd_purge_idempotency)

    ver = sub.add_parser("version", help="installed framework version")
    ver.set_defaults(func=_cmd_version)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    # `doctor` forwards verify_system's own flags (`--check-kg`). argparse will
    # not hand an option-looking token to a positional, so `agentsmith doctor
    # --check-kg` failed with "unrecognized arguments" — for as long as the
    # command existed. Everything else still rejects unknown arguments.
    args, extra = parser.parse_known_args(argv)
    if extra:
        if args.command != "doctor":
            parser.error(f"unrecognized arguments: {' '.join(extra)}")
        args.checks = [*args.checks, *extra]
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
