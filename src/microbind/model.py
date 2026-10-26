"""Serializable facts, symbolic values and execution states.

Values retain identity, rather than collapsing all request inputs into one taint.
Each state belongs to ONE entry and branch. Facts are never unioned across entries.
"""

from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass, field
from typing import Any


def stable_id(*parts: Any) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:16]


@dataclass(frozen=True)
class Value:
    term: tuple
    reads: frozenset[str] = frozenset()

    def field(self, name: str) -> "Value":
        if self.term[0] == "row":
            return Value(("column", self.term[1], self.term[2], name), self.reads)
        return Value(("field", self.term, name), self.reads)


UNKNOWN = Value(("unknown",))


def literal(value: Any) -> Value:
    return Value(("literal", value))


def term_text(t: tuple) -> str:
    if t[0] == "literal":
        return repr(t[1])
    if t[0] in ("input", "trusted", "unknown"):
        return ":".join(map(str, t))
    if t[0] == "column":
        return f"{t[1]}[{term_text(t[2])}].{t[3]}"
    if t[0] == "row":
        return f"{t[1]}[{term_text(t[2])}]"
    if t[0] == "field":
        return term_text(t[1]) + "." + t[2]
    if t[0] == "not":
        return "!(" + term_text(t[1]) + ")"
    if t[0] == "op":
        return f"({term_text(t[2])} {t[1]} {term_text(t[3])})"
    return str(t)


@dataclass
class State:
    env: dict[str, Value] = field(default_factory=dict)
    # Conservative read dependencies of explicitly allocated java.util maps.
    map_reads: dict[tuple, frozenset[str]] = field(default_factory=dict)
    facts: list[dict] = field(default_factory=list)
    operations: list[dict] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    status: str = "running"
    result: Value = UNKNOWN

    def fork(self) -> "State":
        return copy.deepcopy(self)


def equivalent(a: tuple, b: tuple, facts: list[dict]) -> bool:
    """Equality closure plus congruence for object fields. No taint = equality shortcut."""
    pairs = [(f["left"], f["right"]) for f in facts if f["op"] == "=="]
    parent = {}

    def add(t):
        parent.setdefault(t, t)
        if t[0] == "column":
            add(t[2])
        elif t[0] == "field":
            add(t[1])

    for x in [a, b] + [x for pair in pairs for x in pair]:
        add(x)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        x, y = find(x), find(y)
        if x == y:
            return False
        parent[x] = y
        return True

    for x, y in pairs:
        union(x, y)
    while True:
        changed, signatures = False, {}
        for x in parent:
            if x[0] == "column":
                signature = ("column", x[1], find(x[2]), x[3])
            elif x[0] == "field":
                signature = ("field", find(x[1]), x[2])
            else:
                continue
            if signature in signatures:
                changed = union(x, signatures[signature]) or changed
            else:
                signatures[signature] = x
        if not changed:
            break
    return find(a) == find(b)


def constrain(state: State, value: Value, truth: bool, evidence: dict) -> list[State]:
    """Split boolean formulas and discard direct equality contradictions."""
    t = value.term
    if t[0] == "literal":
        return [state] if bool(t[1]) == truth else []
    if t[0] == "not":
        return constrain(state, Value(t[1]), not truth, evidence)
    if t[0] == "op" and t[1] in ("&&", "||"):
        op, a, b = t[1:]
        if (op == "&&" and truth) or (op == "||" and not truth):
            out = []
            for s in constrain(state, Value(a), truth, evidence):
                out += constrain(s, Value(b), truth, evidence)
            return out
        # Exclusive branch expansion: a OR b = a OR (!a AND b).
        out = constrain(state.fork(), Value(a), truth, evidence)
        for s in constrain(state, Value(a), not truth, evidence):
            out += constrain(s, Value(b), truth, evidence)
        return out
    if t[0] == "op" and t[1] in ("==", "!="):
        op = t[1] if truth else ("!=" if t[1] == "==" else "==")
        a, b = t[2:]
    else:
        op, a, b = "==", t, ("literal", truth)
    if a[0] == b[0] == "literal":
        return [state] if ((a == b) == (op == "==")) else []
    if op == "!=" and equivalent(a, b, state.facts):
        return []
    candidate = {"left": a, "op": op, "right": b, "evidence": evidence}
    trial = state.facts + [candidate]
    if any(f["op"] == "!=" and equivalent(f["left"], f["right"], trial) for f in trial):
        return []
    state.facts.append(candidate)
    return [state]
