"""Bounded, path-sensitive symbolic interpretation of the supported Java subset."""

from __future__ import annotations

import copy
import re
import time
from collections import Counter

import javalang as jl

from . import __version__
from .frontend import Project, constant, typename
from .model import UNKNOWN, State, Value, constrain, equivalent, literal, stable_id, term_text


class Analyzer:
    def __init__(self, project: Project):
        self.p = project
        self.max_depth = project.config.get("analysis", {}).get("max_depth", 30)
        self.max_states = project.config.get("analysis", {}).get("max_states", 128)
        self.gaps = []
        self.entry = None

    def loc(self, m, node=None):
        pos = getattr(node, "position", None)
        return {"file": m.file, "line": pos.line if pos else m.line, "method": m.id}

    def cap(self, states):
        if len(states) > self.max_states:
            gap = f"Path budget exceeded: {self.max_states}"
            self.gaps.append({"entry": self.entry.id, "detail": gap})
            states = states[: self.max_states]
            for s in states:
                s.unresolved.append(gap)
        return states

    def invoke(self, m, args, s, depth, intercepted=False):
        if depth > self.max_depth:
            s.unresolved.append(f"Call depth exceeded at {m.id}")
            return [(s, UNKNOWN)]
        caller_env = s.env.copy()
        s.env = {p["name"]: a for p, a in zip(m.params, args)}
        types = {p["name"]: p["type"] for p in m.params}
        s.trace.append(
            {
                "kind": "call",
                **m.location(),
                "arguments": {p["name"]: term_text(a.term) for p, a in zip(m.params, args)},
            }
        )
        if m.feign:
            edge = self.p.rpc.get(m.id)
            if edge is None:
                s.unresolved.append(f"Unresolved Feign endpoint: {m.id}")
                outs = [(s, UNKNOWN)]
            else:
                target, mapping = edge
                if None in mapping:
                    s.unresolved.append(f"Unresolved RPC parameter: {m.id}")
                forwarded = [
                    args[i] if i is not None and i < len(args) else UNKNOWN for i in mapping
                ]
                s.trace.append(
                    {
                        "kind": "rpc",
                        **m.location(),
                        "target": target.id,
                        "bindings": {
                            p["name"]: term_text(a.term) for p, a in zip(target.params, forwarded)
                        },
                    }
                )
                outs = self.invoke(target, forwarded, s, depth + 1, intercepted=True)
        elif m.sql:
            outs = [(s, self.sql(m, args, s))]
        elif m.node.body is None:
            s.unresolved.append(f"No implementation: {m.id}")
            outs = [(s, UNKNOWN)]
        else:
            active = [s]
            if intercepted and "PreAuthorize" in m.annotations:
                expression = m.annotations["PreAuthorize"].get("value") or ""
                role = re.fullmatch(r"hasRole\(['\"]([\w]+)['\"]\)", expression)
                if m.service not in self.p.method_security:
                    s.trace.append({"kind": "disabled_method_security", **m.location()})
                elif role:
                    v = Value(("op", "==", ("trusted", "role"), ("literal", role.group(1))))
                    active = constrain(s, v, True, self.loc(m))
                else:
                    s.unresolved.append(f"Unsupported PreAuthorize expression at {m.id}")
            states = self.block(m.node.body, active, m, types, depth)
            outs = []
            for out in states:
                result = out.result if out.status == "returned" else UNKNOWN
                if out.status == "returned":
                    out.status = "running"
                out.result = UNKNOWN
                outs.append((out, result))
        for out, _ in outs:
            out.env = caller_env.copy()
        return outs

    def sql(self, m, args, state):
        sql = m.sql
        params = {p["wire"]: a for p, a in zip(m.params, args)}
        params.update({p["name"]: a for p, a in zip(m.params, args)})
        obj = ("all", sql["table"])
        for eq in sql["equalities"]:
            if eq["column"] == "id" and "parameter" in eq:
                obj = params.get(eq["parameter"], UNKNOWN).term
        constraints = []
        for eq in sql["equalities"]:
            value = (
                params.get(eq["parameter"], UNKNOWN)
                if "parameter" in eq
                else literal(eq.get("literal"))
            )
            constraints.append(
                {
                    "left": ("column", sql["table"], obj, eq["column"]),
                    "op": "==",
                    "right": value.term,
                    "evidence": {
                        "file": sql["file"],
                        "line": sql["line"],
                        "method": m.id,
                        "kind": "sql",
                    },
                }
            )
        if not sql["supported"]:
            state.unresolved.append(f"Unsupported SQL at {sql['file']}:{sql['line']}")
        oid = stable_id(self.entry.id, m.id, obj, len(state.operations))
        operation = {
            "id": oid,
            "method": m.id,
            "table": sql["table"],
            "kind": sql["kind"],
            "object": obj,
            "collection": obj[0] == "all",
            "sql": sql,
            "parameters": {k: term_text(v.term) for k, v in params.items()},
            "facts_at_effect": copy.deepcopy(state.facts),
            "sql_constraints": constraints,
            "trace": copy.deepcopy(state.trace),
            "location": {"file": sql["file"], "line": sql["line"]},
        }
        state.operations.append(operation)
        if sql["kind"] == "read":
            return Value(("row", sql["table"], obj), frozenset([oid]))
        return Value(("affected_rows", oid))

    def block(self, statements, states, m, types, depth):
        for node in statements or []:
            out = []
            for s in states:
                if s.status != "running":
                    out.append(s)
                else:
                    out += self.statement(node, s, m, types.copy(), depth)
            states = self.cap(out)
        return states

    def statement(self, node, s, m, types, depth):
        if isinstance(node, jl.tree.BlockStatement):
            return self.block(node.statements, [s], m, types, depth)
        if isinstance(node, jl.tree.LocalVariableDeclaration):
            current = [s]
            for d in node.declarators:
                next_states = []
                types[d.name] = typename(node.type)
                for a in current:
                    for b, v in self.expr(d.initializer, a, m, types, depth):
                        b.env[d.name] = v
                        next_states.append(b)
                current = next_states
            return current
        if isinstance(node, jl.tree.StatementExpression):
            return [out for out, _ in self.expr(node.expression, s, m, types, depth)]
        if isinstance(node, jl.tree.ReturnStatement):
            out = []
            for st, v in self.expr(node.expression, s, m, types, depth):
                if v.term in st.map_reads:
                    v = Value(v.term, v.reads | st.map_reads[v.term])
                if st.status == "running":
                    st.status, st.result = "returned", v
                out.append(st)
            return out
        if isinstance(node, jl.tree.ThrowStatement):
            s.status = "thrown"
            return [s]
        if isinstance(node, jl.tree.IfStatement):
            out = []
            for st, condition in self.expr(node.condition, s, m, types, depth):
                if st.status != "running":
                    out.append(st)
                    continue
                for truth, body in [(True, node.then_statement), (False, node.else_statement)]:
                    for branch in constrain(st.fork(), condition, truth, self.loc(m, node)):
                        out += (
                            self.statement(body, branch, m, types.copy(), depth)
                            if body
                            else [branch]
                        )
            return out
        # Loops, exceptions, lambdas and synchronization need a fuller CFG frontend.
        s.unresolved.append(
            f"Unsupported statement {type(node).__name__} at {m.file}:{getattr(node, 'position', None)}"
        )
        return [s]

    def expr(self, node, s, m, types, depth):
        if node is None:
            return [(s, literal(None))]
        if s.status != "running":
            return [(s, UNKNOWN)]
        if isinstance(node, jl.tree.Literal):
            val = {"true": True, "false": False, "null": None}.get(node.value, constant(node))
            results = [(s, literal(val))]
        elif isinstance(node, jl.tree.MemberReference):
            if node.qualifier:
                base = s.env.get(node.qualifier, Value(("unknown", node.qualifier)))
                results = [(s, self.field(base, node.member))]
            else:
                results = [(s, s.env.get(node.member, Value(("unknown", node.member))))]
        elif isinstance(node, jl.tree.BinaryOperation):
            results = []
            # Supported conditions are side-effect free; short-circuit effects are flagged.
            if node.operator in ("&&", "||") and list(
                node.operandr.filter(jl.tree.MethodInvocation)
            ):
                s.unresolved.append(f"Short-circuit call effects require CFG at {m.id}")
            for a, left in self.expr(node.operandl, s, m, types, depth):
                for b, right in self.expr(node.operandr, a, m, types, depth):
                    results.append(
                        (
                            b,
                            Value(
                                ("op", node.operator, left.term, right.term),
                                left.reads | right.reads,
                            ),
                        )
                    )
        elif isinstance(node, jl.tree.MethodInvocation):
            results = self.call(node, s, m, types, depth)
        elif isinstance(node, jl.tree.Assignment):
            results = []
            for st, value in self.expr(node.value, s, m, types, depth):
                target = node.expressionl
                if (
                    isinstance(target, jl.tree.MemberReference)
                    and not target.qualifier
                    and node.type == "="
                ):
                    st.env[target.member] = value
                else:
                    st.unresolved.append(f"Unsupported heap/compound assignment at {m.id}")
                results.append((st, value))
        elif isinstance(node, jl.tree.Cast):
            results = self.expr(node.expression, s, m, types, depth)
        elif isinstance(node, jl.tree.ClassCreator):
            # Only a locally allocated standard map is modeled. No arbitrary
            # application method named put is treated as a collection operation.
            text = self.p.texts[m.file]
            map_name = typename(node.type)
            standard_map = (
                map_name in {"HashMap", "LinkedHashMap"}
                and re.search(r"import\s+java\.util\.(?:" + map_name + r"|\*)\s*;", text)
                and (m.service, map_name) not in self.p.classes
            )
            if standard_map and not node.arguments:
                ref = ("map", stable_id(m.id, repr(node.position), len(s.trace), len(s.map_reads)))
                s.map_reads[ref] = frozenset()
                results = [(s, Value(ref))]
            else:
                results = [(s, Value(("new", map_name)))]
        else:
            s.unresolved.append(f"Unsupported expression {type(node).__name__} at {m.id}")
            results = [(s, UNKNOWN)]
        for selector in getattr(node, "selectors", None) or []:
            next_results = []
            for st, v in results:
                if (
                    isinstance(selector, jl.tree.MethodInvocation)
                    and selector.member.startswith("get")
                    and not selector.arguments
                ):
                    next_results.append(
                        (st, self.field(v, selector.member[3:4].lower() + selector.member[4:]))
                    )
                else:
                    st.unresolved.append(f"Unsupported selector at {m.id}")
                    next_results.append((st, UNKNOWN))
            results = next_results
        for prefix in reversed(getattr(node, "prefix_operators", None) or []):
            if prefix == "!":
                results = [(st, Value(("not", v.term), v.reads)) for st, v in results]
            else:
                results = [(st, Value(("unary", prefix, v.term), v.reads)) for st, v in results]
        return results

    def field(self, value, name):
        if value.term[0] == "row":
            name = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
        return value.field(name)

    def call(self, node, s, m, types, depth):
        arg_states = [(s, [])]
        for arg in node.arguments:
            new = []
            for st, values in arg_states:
                for out, v in self.expr(arg, st, m, types, depth):
                    new.append((out, values + [v]))
            arg_states = new
        results = []
        target = self.p.resolve(m, node.qualifier, node.member, len(node.arguments), types)
        trusted = self.p.config.get("trusted_identity", {})
        trust_key = target.cls + "." + target.name if target else ""
        for st, args in arg_states:
            if st.status != "running":
                results.append((st, UNKNOWN))
            elif trust_key in trusted:
                results.append((st, Value(("trusted", trusted[trust_key]))))
            elif (
                node.qualifier in st.env
                and st.env[node.qualifier].term in st.map_reads
                and node.member == "put"
                and len(args) == 2
            ):
                ref = st.env[node.qualifier].term
                reads = frozenset().union(
                    *(a.reads | st.map_reads.get(a.term, frozenset()) for a in args)
                )
                previous = st.map_reads[ref]
                st.map_reads[ref] = previous | reads
                # Returning the previous value conservatively retains all reads.
                results.append((st, Value(("unknown", "map_previous_value"), previous)))
            elif node.qualifier in st.env and node.member.startswith("get") and not args:
                results.append(
                    (
                        st,
                        self.field(
                            st.env[node.qualifier], node.member[3:4].lower() + node.member[4:]
                        ),
                    )
                )
            elif node.qualifier in st.env and node.member == "equals" and len(args) == 1:
                v = st.env[node.qualifier]
                results.append(
                    (st, Value(("op", "==", v.term, args[0].term), v.reads | args[0].reads))
                )
            elif target:
                st.trace.append(
                    {
                        "kind": "callsite",
                        **self.loc(m, node),
                        "callee": target.id,
                        "arguments": [term_text(a.term) for a in args],
                    }
                )
                results += self.invoke(target, args, st, depth + 1)
            else:
                st.unresolved.append(
                    f"Unresolved call {node.qualifier}.{node.member}/{len(args)} at {m.file}:{node.position.line}"
                )
                # A wrapper whose body is unavailable may return its input.
                # Keep read evidence and mark incomplete, instead of losing it.
                results.append(
                    (st, Value(UNKNOWN.term, frozenset().union(*(a.reads for a in args))))
                )
        return results

    def requirement(self, operation):
        table = operation["table"]
        policy = self.p.config.get("policies", {}).get(table)
        basis = "configured_business_policy"
        if not policy:
            cols = {
                x["category"]: x["name"] for x in self.p.resources.get(table, {}).get("columns", [])
            }
            policy = {
                "single": {"owner": cols["owner"]} if "owner" in cols else {},
                "collection": {"tenant": cols["tenant"]} if "tenant" in cols else {},
            }
            basis = "schema_inferred_policy_requires_review"
        key = "collection" if operation["collection"] else "single"
        req = policy.get(operation["kind"]) or policy.get(key) or {}
        return req, basis

    def judge(self, operation, facts):
        req, basis = self.requirement(operation)
        all_facts = facts + operation["sql_constraints"]
        missing = []
        table, obj = operation["table"], operation["object"]
        if req.get("public"):
            return [], req, basis
        for kind, field in req.items():
            if kind == "role":
                left, right = ("trusted", "role"), ("literal", field)
            elif kind in ("owner", "tenant"):
                left = ("column", table, obj, field)
                right = ("trusted", "user" if kind == "owner" else "tenant")
            else:
                missing.append({"kind": "unknown_policy", "detail": kind})
                continue
            if not equivalent(left, right, all_facts):
                problem = "missing_" + kind
                for f in all_facts:
                    if f["op"] != "==":
                        continue
                    for a, b in [(f["left"], f["right"]), (f["right"], f["left"])]:
                        if a[0] == "column" and kind == "owner" and a[1] == table and a[3] == field:
                            if equivalent(a[2], obj, all_facts) and not equivalent(
                                b, right, all_facts
                            ):
                                problem = "untrusted_subject"
                            elif equivalent(b, right, all_facts) and not equivalent(
                                a[2], obj, all_facts
                            ):
                                problem = "object_mismatch"
                missing.append(
                    {"kind": problem, "required": f"{term_text(left)} == {term_text(right)}"}
                )
        if not req:
            missing.append(
                {
                    "kind": "unknown_policy",
                    "detail": "No authorization requirement could be established",
                }
            )
        return missing, req, basis

    def run(self):
        start = time.perf_counter()
        paths, unknown_entries = [], []
        for entry in self.p.entries():
            self.entry = entry
            args = [Value(("input", entry.id, p["kind"], p["wire"])) for p in entry.params]
            for st, result in self.invoke(entry, args, State(), 0, intercepted=True):
                for note in st.unresolved:
                    unknown_entries.append({"entry": entry.id, "detail": note})
                for op in st.operations:
                    # Reads used only to check permissions are not output disclosures.
                    if op["kind"] == "read" and (
                        st.status == "thrown" or op["id"] not in result.reads
                    ):
                        continue
                    facts = op["facts_at_effect"] if op["kind"] == "write" else st.facts
                    missing, req, basis = self.judge(op, facts)
                    uncertain = bool(st.unresolved) or any(
                        x["kind"] == "unknown_policy" for x in missing
                    )
                    status = "needs_review" if uncertain else "suspected" if missing else "covered"
                    paths.append(
                        {
                            "id": stable_id(entry.id, op["id"], str(facts)),
                            "entry": entry.id,
                            "endpoint": list(entry.route),
                            "entry_location": entry.location(),
                            "status": status,
                            "operation": op,
                            "required": req,
                            "policy_basis": basis,
                            "facts": facts,
                            "missing": missing,
                            "unresolved": sorted(set(st.unresolved)),
                            "effect_timing": "before_write"
                            if op["kind"] == "write"
                            else "before_response",
                        }
                    )
        grouped = {}
        for path in paths:
            key = stable_id(path["entry"], path["operation"]["method"], path["operation"]["object"])
            rank = {"covered": 0, "needs_review": 1, "suspected": 2}
            if key not in grouped or rank[path["status"]] > rank[grouped[key]["status"]]:
                grouped[key] = {**path, "id": key}
        gaps = {str(x): x for x in unknown_entries + self.gaps}
        # Coverage gaps on an entry must prevent a partial safe result from looking complete.
        incomplete = {x["entry"] for x in gaps.values()}
        for p in grouped.values():
            if p["entry"] in incomplete and p["status"] == "covered":
                p["status"] = "needs_review"
        results = sorted(grouped.values(), key=lambda x: (x["endpoint"], x["id"]))
        evaluated_entries = {r["entry"] for r in results}
        entry_coverage = [
            {
                "entry": e.id,
                "endpoint": list(e.route),
                "has_operation_result": e.id in evaluated_entries,
                "has_gap": e.id in incomplete,
            }
            for e in self.p.entries()
        ]
        assessment = {
            "status": "no_operation_evidence"
            if not results
            else "partial"
            if self.p.issues or gaps
            else "analyzed",
            "message": "没有形成可判定的数据操作证据，不能据此认定项目安全。"
            if not results
            else "存在未覆盖代码，请结合覆盖缺口审查。"
            if self.p.issues or gaps
            else "已完成所配置范围内的静态判定。",
            "entries_with_operation_result": len(evaluated_entries),
            "entries_without_operation_result": len(entry_coverage) - len(evaluated_entries),
            "entries_with_gaps": len(incomplete),
            "entry_coverage": entry_coverage,
        }
        return {
            "schema_version": "1.1",
            "tool": "MicroBind",
            "version": __version__,
            "assessment": assessment,
            "frontend": "javalang-ast+sqlglot",
            "policy_source": self.p.manifest.name,
            "summary": {
                **self.p.stats,
                "entries": len(self.p.entries()),
                "rpc_edges": len(self.p.edges),
                "paths": len(paths),
                "operations": len(results),
                **dict(Counter(x["status"] for x in results)),
                "elapsed_seconds": round(time.perf_counter() - start, 4),
            },
            "resources": list(self.p.resources.values()),
            "methods": self.p.inventory(),
            "service_edges": self.p.edges,
            "results": results,
            "access_paths": paths,
            "coverage_gaps": self.p.issues + list(gaps.values()),
            "llm": {"status": "not_requested"},
        }
