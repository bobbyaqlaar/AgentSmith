"""GitHub expressions, evaluated in three values (.agent-rfc/designs/pass3-root-causes.md)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from security import gha_expression as gx

ROLE = ("github", "event", "comment", "author_association")


def value(condition: str, role: str = "NONE"):
    return gx._eval(gx.parse(condition), {ROLE: role})


@pytest.mark.parametrize("condition, expected", [
    ("github.event.comment.author_association == 'owner'", False),       # strings compare without case
    ("github.event['comment'].author_association == 'NONE'", True),      # index and dot are one path
    ("1 == '1'", True), ("true == 1", True), ("null == 0", True), ("'' == false", True),  # GitHub's coercions
    ("'abc' == 1", False),                                               # NaN equals nothing
    ("!false && 2 > 1", True), ("1 < 2 == true", True),                  # precedence: ! < > before == before &&
    ("contains(fromJSON('[\"A\",\"B\"]'), 'b')", True), ("contains('ABC', 'bc')", True),
    ("startsWith('Contributor', 'contrib')", True), ("format('{0}-{1}', 'a', 'b') == 'a-b'", True),
    ("success() && always()", True),
])
def test_values(condition, expected):
    assert value(condition) == expected


@pytest.mark.parametrize("condition", [
    "github.event.issue.number > 0", "failure()", "hashFiles('x') != ''", "github.event.comment.body == 'x'",
    "github.event.comment.user.login == github.event.comment.author_association",
])
def test_anything_not_bound_is_unknown(condition):
    assert value(condition) is gx.UNKNOWN


def test_unknown_does_not_decide_a_conjunction_or_a_disjunction_it_cannot_decide():
    assert gx.may_be_true(["github.event.comment.author_association == 'OWNER' && x"], {ROLE: "NONE"}) is False
    assert gx.may_be_true(["x || github.event.comment.author_association == 'OWNER'"], {ROLE: "NONE"}) is True
    assert gx.may_be_true(["(x && github.event.comment.author_association == 'OWNER') == false"], {ROLE: "NONE"})


@pytest.mark.parametrize("condition", ["a ===", "(a", "a b", "'open", "f(,)"])
def test_what_cannot_be_parsed_may_be_true(condition):
    assert gx.may_be_true([condition], {}) is True


def test_text_around_an_expression_is_a_string_and_so_true():
    assert gx.may_be_true(["false ${{ false }}"], {}) is True
    assert gx.may_be_true(["${{ false }}"], {}) is False


# Unknown must survive every operator. Read as true or false anywhere, a `!` above it turns
# "this guard may let an outsider in" into "this guard keeps outsiders out".
@pytest.mark.parametrize("condition", [
    "!github.event.issue.pull_request",                                   # ! of unknown
    "!(github.event.issue.pull_request && true)",                         # && of unknown and true
    "!(github.event.issue.pull_request && 'x')",
    "!(false || github.event.issue.pull_request)",                        # || of false and unknown
    "(github.event.issue.pull_request && true) == false",
    "!(github.event.issue.pull_request == 'x')",                          # comparison of unknown
])
def test_unknown_stays_unknown_under_negation(condition):
    assert value(condition) is gx.UNKNOWN
    assert gx.may_be_true([condition], {ROLE: "NONE"}), f"{condition} was read as definitely false"


@pytest.mark.parametrize("condition, expected", [
    ("github.event.issue.pull_request && false", False),                  # unknown && false is false
    ("github.event.issue.pull_request || true", True),                    # unknown || true is true
    ("!(github.event.issue.pull_request && false)", True),
])
def test_unknown_resolves_when_the_other_side_decides(condition, expected):
    assert gx._truthy(value(condition)) is expected


@pytest.mark.parametrize("condition, expected", [
    ("0x1F == 31", True),                                                 # hex literals
    ("startsWith(null, 'N')", False), ("contains(true, 'true')", True),  # GitHub's string coercion
    ("format('{0}', 1) == '1'", True),
])
def test_literals_and_coercion_as_github_reads_them(condition, expected):
    assert gx._truthy(value(condition)) is expected
