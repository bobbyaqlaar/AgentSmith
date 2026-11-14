"""scripts/security/gha_expression.py — GitHub Actions expressions, parsed and evaluated in
three values (.agent-rfc/designs/pass3-root-causes.md).

SEC-CIAGENT-001 must know whether a job's `if:` keeps an outsider's event text away from a
coding agent. Matching the condition's spelling failed three times (R9, P2-R5, P3-R1): each
rewrite of the same condition was a new bypass. This evaluates the condition instead.

`may_be_true(condition, bindings)` answers: with these context paths fixed and every other
context unknown, can the condition be true? Unknown is a third value, never read as true or
false; a condition that cannot be parsed may be true.

The grammar is GitHub's: literals ('string' with '' escapes, numbers, true, false, null),
contexts (`a.b`, `a['b']`, `a[0]`, `a.*`), function calls, `!`, `<` `<=` `>` `>=`, `==` `!=`,
`&&`, `||` and brackets. Comparison of strings ignores case; values of different types are
compared as numbers, as GitHub does.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Callable, Optional

UNKNOWN = object()
_TOKEN = re.compile(r"\s*(?:(?P<num>0x[0-9a-fA-F]+|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)|(?P<str>'(?:[^']|'')*')"
                    r"|(?P<op>==|!=|<=|>=|&&|\|\||[!<>()\[\],.*])|(?P<name>[A-Za-z_][A-Za-z0-9_-]*))")


class Unparsed(ValueError):
    pass


def _tokens(text: str) -> list[tuple[str, str]]:
    out, pos = [], 0
    text = text.strip()
    while pos < len(text):
        match = _TOKEN.match(text, pos)
        if not match or match.end() == pos:
            raise Unparsed(f"cannot read {text[pos:pos + 20]!r}")
        kind = match.lastgroup or ""
        out.append((kind, match.group(kind)))
        pos = match.end()
        while pos < len(text) and text[pos].isspace():
            pos += 1
    return out


class _Parser:
    """Recursive descent: || < && < == != < comparisons < ! < postfix (., [], call)."""

    def __init__(self, text: str) -> None:
        self.toks, self.i = _tokens(text), 0

    def peek(self, value: Optional[str] = None) -> bool:
        return self.i < len(self.toks) and (value is None or self.toks[self.i][1] == value)

    def take(self, value: Optional[str] = None) -> tuple[str, str]:
        if not self.peek(value):
            raise Unparsed(f"expected {value!r}")
        tok = self.toks[self.i]
        self.i += 1
        return tok

    def parse(self) -> tuple:
        tree = self.or_()
        if self.i != len(self.toks):
            raise Unparsed(f"unexpected {self.toks[self.i][1]!r}")
        return tree

    def binary(self, ops: tuple[str, ...], lower: Callable[[], tuple]) -> tuple:
        left = lower()
        while self.peek() and self.toks[self.i][1] in ops:
            op = self.take()[1]
            left = (op, left, lower())
        return left

    def or_(self) -> tuple:
        return self.binary(("||",), self.and_)

    def and_(self) -> tuple:
        return self.binary(("&&",), self.eq)

    def eq(self) -> tuple:
        return self.binary(("==", "!="), self.cmp)

    def cmp(self) -> tuple:
        return self.binary(("<", "<=", ">", ">="), self.unary)

    def unary(self) -> tuple:
        if self.peek("!"):
            self.take()
            return ("!", self.unary())
        return self.postfix()

    def postfix(self) -> tuple:
        kind, value = self.take()
        if kind == "num":
            node: tuple = ("lit", float(int(value, 16)) if value.lower().startswith("0x") else float(value))
        elif kind == "str":
            node = ("lit", value[1:-1].replace("''", "'"))
        elif value == "(":
            node = self.or_()
            self.take(")")
        elif kind == "name" and value in ("true", "false", "null"):
            node = ("lit", {"true": True, "false": False, "null": None}[value])
        elif kind == "name" and self.peek("("):
            self.take("(")
            args = []
            while not self.peek(")"):
                args.append(self.or_())
                if not self.peek(")"):
                    self.take(",")
            self.take(")")
            node = ("call", value.lower(), args)
        elif kind == "name":
            node = ("ctx", (value.lower(),))
        else:
            raise Unparsed(f"unexpected {value!r}")
        while self.peek(".") or self.peek("["):
            if self.take()[1] == ".":
                part = self.take()[1]
                node = ("get", node, ("lit", "*" if part == "*" else part.lower()))
            else:
                index = ("lit", "*") if self.peek("*") and self.take() else self.or_()
                self.take("]")
                node = ("get", node, index)
        return node


def parse(condition: str) -> tuple:
    text = condition.strip()
    if text.startswith("${{") and text.endswith("}}") and text.count("${{") == 1:
        text = text[3:-2]
    elif "${{" in text:
        # Text around an expression makes the whole `if:` a non-empty string: true.
        return ("lit", True)
    return _Parser(text).parse()


def _truthy(value: Any) -> Any:
    if value is UNKNOWN:
        return UNKNOWN
    if isinstance(value, float) and math.isnan(value):
        return False
    return value not in (False, 0, "", None) or isinstance(value, (list, dict))


def _number(value: Any) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip()) if value.strip() else 0.0
        except ValueError:
            return math.nan
    return math.nan


def _equal(a: Any, b: Any) -> Any:
    if a is UNKNOWN or b is UNKNOWN:
        return UNKNOWN
    if isinstance(a, str) and isinstance(b, str):
        return a.lower() == b.lower()
    if type(a) is type(b) and not isinstance(a, (int, float, str)):
        return a == b
    x, y = _number(a), _number(b)
    return not (math.isnan(x) or math.isnan(y)) and x == y


def _compare(op: str, a: Any, b: Any) -> Any:
    if a is UNKNOWN or b is UNKNOWN:
        return UNKNOWN
    if isinstance(a, str) and isinstance(b, str):
        x, y = a.lower(), b.lower()
    else:
        x, y = _number(a), _number(b)
        if math.isnan(x) or math.isnan(y):
            return False
    return {"<": x < y, "<=": x <= y, ">": x > y, ">=": x >= y}[op]


def _text(value: Any) -> str:
    """GitHub's string coercion: null is '', booleans are 'true'/'false', 1.0 is '1'."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return value if isinstance(value, str) else json.dumps(value)


def _call(name: str, args: list) -> Any:
    if name in ("success", "always"):
        return True
    if any(a is UNKNOWN for a in args):
        return UNKNOWN
    if name == "contains" and len(args) == 2:
        haystack, needle = args
        if isinstance(haystack, list):
            return any(_equal(item, needle) is True for item in haystack)
        return _text(needle).lower() in _text(haystack).lower()
    if name in ("startswith", "endswith") and len(args) == 2:
        a, b = _text(args[0]).lower(), _text(args[1]).lower()
        return a.startswith(b) if name == "startswith" else a.endswith(b)
    if name == "fromjson" and len(args) == 1 and isinstance(args[0], str):
        try:
            return json.loads(args[0])
        except ValueError:
            return UNKNOWN
    if name == "tojson" and len(args) == 1:
        return json.dumps(args[0])
    if name == "format" and args and isinstance(args[0], str):
        out = args[0]
        for index, value in enumerate(args[1:]):
            out = out.replace("{%d}" % index, _text(value))
        return out
    return UNKNOWN  # failure(), cancelled(), hashFiles(), join() and anything else


def _eval(node: tuple, bindings: dict[tuple, Any]) -> Any:
    kind = node[0]
    if kind == "lit":
        return node[1]
    if kind in ("ctx", "get"):
        path = _path(node)
        return bindings.get(path, UNKNOWN) if path else UNKNOWN
    if kind == "call":
        return _call(node[1], [_eval(a, bindings) for a in node[2]])
    if kind == "!":
        value = _truthy(_eval(node[1], bindings))
        return UNKNOWN if value is UNKNOWN else not value
    if kind == "&&":
        left = _eval(node[1], bindings)
        if _truthy(left) is False:
            return left
        right = _eval(node[2], bindings)
        if left is UNKNOWN:
            return False if _truthy(right) is False else UNKNOWN
        return right
    if kind == "||":
        left = _eval(node[1], bindings)
        if _truthy(left) is True:
            return left
        right = _eval(node[2], bindings)
        if left is UNKNOWN:
            return True if _truthy(right) is True else UNKNOWN
        return right
    if kind in ("==", "!="):
        same = _equal(_eval(node[1], bindings), _eval(node[2], bindings))
        return same if same is UNKNOWN or kind == "==" else not same
    return _compare(kind, _eval(node[1], bindings), _eval(node[2], bindings))


def _path(node: tuple) -> Optional[tuple]:
    """A context path as a tuple of lower-case keys, or None when an index is computed."""
    if node[0] == "ctx":
        return node[1]
    if node[0] == "get":
        base = _path(node[1])
        index = node[2]
        if base is None or index[0] != "lit":
            return None
        key = index[1]
        return (*base, str(int(key)) if isinstance(key, float) else str(key).lower())
    return None


def may_be_true(conditions: list[str], bindings: dict[tuple, Any]) -> bool:
    """Can every one of these conditions (a job's and a step's `if:`) be true together,
    with these context paths fixed and the rest unknown? Unparsed means yes."""
    for condition in conditions:
        try:
            value = _truthy(_eval(parse(condition), bindings))
        except (Unparsed, RecursionError):
            return True
        if value is False:
            return False
    return True
