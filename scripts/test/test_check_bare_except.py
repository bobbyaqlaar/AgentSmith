"""
scripts/test/test_check_bare_except.py — regression coverage for
scripts/check_bare_except.py, the AST-based replacement for hooks/
pre-commit's old regex check that matched the HEADER line of almost any
multi-line `except` clause (since the colon always ends the line) rather
than verifying the body was actually empty.

The case that exposed the bug: hooks/pre-commit flagged
runtime/provider_dispatch.py's `except KeyError: raise ValueError(...) from
None` — a correctly-written, non-empty, re-raising handler — as a "bare
except clause with no handler body."
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_bare_except", SCRIPTS_DIR / "check_bare_except.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = _load_checker()


def test_multiline_reraise_is_not_flagged():
    """The exact pattern that triggered the original false positive — a
    multi-line `except X: raise ... from None` re-raising handler."""
    source = (
        "def get_cloud_adapter(provider):\n"
        "    try:\n"
        "        return _CLOUD_ADAPTERS[provider]\n"
        "    except KeyError:\n"
        "        raise ValueError(\n"
        "            f'Unknown cloud provider {provider!r}'\n"
        "        ) from None\n"
    )
    assert checker.find_violations(source, "test.py") == []


def test_multiline_log_and_continue_is_not_flagged():
    source = (
        "def f():\n"
        "    try:\n"
        "        risky()\n"
        "    except Exception as exc:\n"
        "        logger.warning('failed: %s', exc)\n"
    )
    assert checker.find_violations(source, "test.py") == []


def test_bare_pass_is_flagged():
    source = (
        "def f():\n"
        "    try:\n"
        "        risky()\n"
        "    except Exception:\n"
        "        pass\n"
    )
    violations = checker.find_violations(source, "test.py")
    assert len(violations) == 1
    assert violations[0][1] == 4  # the `except Exception:` line


def test_bare_ellipsis_is_flagged():
    source = (
        "def f():\n"
        "    try:\n"
        "        risky()\n"
        "    except Exception:\n"
        "        ...\n"
    )
    assert len(checker.find_violations(source, "test.py")) == 1


def test_noqa_comment_suppresses_flag():
    source = (
        "def f():\n"
        "    try:\n"
        "        risky()\n"
        "    except Exception:  # noqa: bare-except — must never break the caller\n"
        "        pass\n"
    )
    assert checker.find_violations(source, "test.py") == []


def test_syntax_error_does_not_raise():
    """Not this checker's job to report syntax errors — must not crash the
    pre-commit hook on an unrelated file that fails to parse."""
    assert checker.find_violations("def f(:\n  pass", "test.py") == []
