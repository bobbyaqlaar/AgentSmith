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

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))


def _load_checker():
    from _shared import load_script

    return load_script("check_bare_except")


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
        "def f():\n    try:\n        risky()\n    except Exception:\n        pass\n"
    )
    violations = checker.find_violations(source, "test.py")
    assert len(violations) == 1
    assert violations[0][1] == 4  # the `except Exception:` line


def test_bare_ellipsis_is_flagged():
    source = "def f():\n    try:\n        risky()\n    except Exception:\n        ...\n"
    assert len(checker.find_violations(source, "test.py")) == 1


def test_fail_open_comment_suppresses_flag():
    source = (
        "def f():\n"
        "    try:\n"
        "        risky()\n"
        "    except Exception:  # fail-open: must never break the caller\n"
        "        pass\n"
    )
    assert checker.find_violations(source, "test.py") == []


def test_fail_open_comment_on_wrapped_header_suppresses_flag():
    """A formatter (e.g. ruff format) can wrap a long except header across
    multiple lines, moving a trailing comment onto the `):` line rather
    than the `except (` line node.lineno points at — the suppression
    marker must still be found anywhere in that header span."""
    source = (
        "def f():\n"
        "    try:\n"
        "        risky()\n"
        "    except (\n"
        "        OSError\n"
        "    ):  # fail-open: read-only filesystem — stdout only\n"
        "        pass\n"
    )
    assert checker.find_violations(source, "test.py") == []


def test_syntax_error_does_not_raise():
    """Not this checker's job to report syntax errors — must not crash the
    pre-commit hook on an unrelated file that fails to parse."""
    assert checker.find_violations("def f(:\n  pass", "test.py") == []


def test_a_reason_on_the_line_above_counts() -> None:
    """A reason worth writing is often longer than fits after `except Exception:`.

    Requiring it inline put twelve handlers in this repo over any sane line
    limit, setting this checker against E501 — two standards that could not both
    be satisfied. That is how a rule gets waived rather than followed.
    """
    src = (
        "try:\n"
        "    pass\n"
        "# fail-open: the exporter is best-effort and must not fail the call\n"
        "except Exception:\n"
        "    pass\n"
    )
    assert checker.find_violations(src, "x.py") == []


def test_a_reason_further_up_does_not_count() -> None:
    """Only an unbroken run of comment lines. A `fail-open:` note separated by
    code is about a different handler, and would silently exempt this one."""
    src = (
        "# fail-open: this comment is about something else entirely\n"
        "x = 1\n"
        "try:\n"
        "    pass\n"
        "except Exception:\n"
        "    pass\n"
    )
    assert checker.find_violations(src, "x.py") != []


def test_an_undocumented_handler_still_fails() -> None:
    """The control: if this ever passes, the two tests above prove nothing."""
    src = "try:\n    pass\nexcept Exception:\n    pass\n"
    assert checker.find_violations(src, "x.py") != []
