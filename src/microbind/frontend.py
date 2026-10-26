"""Java 8 syntax AST + Spring/Feign/MyBatis adapters.

This is a small source frontend, not a Joern CPG or a Java type checker. Unsupported
syntax and unresolved dispatch are exported as coverage gaps rather than erased.
"""

from __future__ import annotations

import ast
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import javalang as jl
import sqlglot
import yaml
from sqlglot import exp


def constant(node):
    if (
        isinstance(node, jl.tree.MemberReference)
        and node.qualifier == "RequestMethod"
        and node.member in {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "TRACE"}
    ):
        return node.member
    if isinstance(node, jl.tree.Literal):
        try:
            return ast.literal_eval(node.value)
        except (ValueError, SyntaxError):
            return node.value
    if isinstance(node, jl.tree.MemberReference):
        return node.member
    if isinstance(node, jl.tree.ElementArrayValue):
        return [constant(v) for v in node.values]
    if isinstance(node, jl.tree.BinaryOperation) and node.operator == "+":
        a, b = constant(node.operandl), constant(node.operandr)
        if isinstance(a, str) and isinstance(b, str):
            return a + b
    return None


def annotations(nodes):
    out = {}
    for a in nodes or []:
        if isinstance(a.element, list):
            out[a.name.split(".")[-1]] = {e.name: constant(e.value) for e in a.element}
        else:
            out[a.name.split(".")[-1]] = {"value": constant(a.element)}
    return out


def typename(t):
    return t.name if t else "void"


def first(v, default=""):
    return (v[0] if v else default) if isinstance(v, list) else (v or default)


def route(anns, base=""):
    for key, verb in [
        ("GetMapping", "GET"),
        ("PostMapping", "POST"),
        ("PutMapping", "PUT"),
        ("DeleteMapping", "DELETE"),
        ("PatchMapping", "PATCH"),
        ("RequestMapping", "ANY"),
    ]:
        if key in anns:
            a = anns[key]
            path = first(a.get("value") or a.get("path"))
            return first(a.get("method"), verb), "/" + "/".join(
                x.strip("/") for x in (base, path) if x.strip("/")
            )
    return None


def parameter(p):
    ann = annotations(p.annotations)
    for key, kind in [
        ("PathVariable", "path"),
        ("RequestParam", "query"),
        ("RequestBody", "body"),
        ("RequestHeader", "header"),
        ("Param", "sql"),
    ]:
        if key in ann:
            return {
                "name": p.name,
                "type": typename(p.type),
                "kind": kind,
                "wire": ann[key].get("value") or ann[key].get("name") or p.name,
            }
    return {"name": p.name, "type": typename(p.type), "kind": "argument", "wire": p.name}


@dataclass
class Method:
    id: str
    service: str
    cls: str
    name: str
    file: str
    line: int
    node: object
    params: list
    fields: dict
    annotations: dict
    route: tuple | None = None
    feign: str | None = None
    sql: dict | None = None
    body_offset: int = 0
    end_offset: int = 0

    def location(self):
        return {"file": self.file, "line": self.line, "method": self.id}


class Project:
    def __init__(self, manifest: Path):
        self.manifest = manifest.resolve()
        self.root = self.manifest.parent
        self.config = yaml.safe_load(self.manifest.read_text(encoding="utf-8"))
        self.methods: dict[str, Method] = {}
        self.texts: dict[str, str] = {}
        self.classes = {}
        self.resources = {}
        self.issues = []
        self.edges = []
        self.rpc = {}
        self.method_security = set()
        self.stats = {"java_files": 0, "parsed_java_files": 0, "sql_statements": 0}
        self._load()

    def _load(self):
        for service in self.config["services"]:
            folder = self.root / service["path"]
            if service.get("language", "java") != "java":
                self.issues.append(
                    {
                        "kind": "unsupported_language",
                        "file": service["path"],
                        "detail": service.get("language"),
                        "service": service["name"],
                    }
                )
                continue
            for file in sorted(folder.rglob("*.java")):
                if "target" in file.parts:
                    continue
                rel = file.relative_to(self.root).as_posix()
                text = file.read_text(encoding="utf-8")
                self.texts[rel] = text
                self.stats["java_files"] += 1
                try:
                    tree = jl.parse.parse(text)
                except (jl.parser.JavaSyntaxError, jl.tokenizer.LexerError) as e:
                    self.issues.append(
                        {
                            "kind": "java_parse_error",
                            "file": rel,
                            "detail": str(e) or repr(getattr(e, "at", "")),
                        }
                    )
                    continue
                self.stats["parsed_java_files"] += 1
                tokens = list(jl.tokenizer.tokenize(text))
                offsets = self.line_offsets(text)
                package = tree.package.name + "." if tree.package else ""
                for cls in tree.types:
                    if not isinstance(
                        cls, (jl.tree.ClassDeclaration, jl.tree.InterfaceDeclaration)
                    ):
                        continue
                    if (
                        service.get("include_classes")
                        and package + cls.name not in service["include_classes"]
                    ):
                        continue
                    ca = annotations(cls.annotations)
                    if "EnableMethodSecurity" in ca:
                        self.method_security.add(service["name"])
                    fields = {d.name: typename(f.type) for f in cls.fields for d in f.declarators}
                    self.classes[(service["name"], cls.name)] = fields
                    base_route = route(ca)
                    base = base_route[1] if base_route else ""
                    feign = ca.get("FeignClient", {}).get("name") or ca.get("FeignClient", {}).get(
                        "value"
                    )
                    if feign:
                        base = ca["FeignClient"].get("path") or base
                    for node in cls.methods:
                        ma = annotations(node.annotations)
                        start = offsets[node.position.line - 1] + node.position.column - 1
                        body_offset, end = start, start
                        for ti, tok in enumerate(tokens):
                            pos = offsets[tok.position.line - 1] + tok.position.column - 1
                            if pos < start:
                                continue
                            if tok.value == ";":
                                end = pos + 1
                                break
                            if tok.value == "{":
                                body_offset = pos + 1
                                depth = 1
                                for close in tokens[ti + 1 :]:
                                    depth += (close.value == "{") - (close.value == "}")
                                    if depth == 0:
                                        end = (
                                            offsets[close.position.line - 1] + close.position.column
                                        )
                                        break
                                break
                        mid = f"{service['name']}:{package}{cls.name}.{node.name}/{len(node.parameters)}"
                        m = Method(
                            mid,
                            service["name"],
                            package + cls.name,
                            node.name,
                            rel,
                            node.position.line,
                            node,
                            [parameter(p) for p in node.parameters],
                            fields,
                            ma,
                            route(ma, base),
                            feign,
                            body_offset=body_offset,
                            end_offset=end,
                        )
                        if mid in self.methods:
                            self.issues.append(
                                {"kind": "ambiguous_overload", "file": rel, "detail": mid}
                            )
                            # Never silently choose among same-arity overloads.
                            self.methods[mid].annotations["MicroBindAmbiguous"] = {}
                            continue
                        self.methods[mid] = m
                        for sql_ann in ("Select", "Update", "Delete", "Insert"):
                            if sql_ann in ma:
                                raw = ma[sql_ann].get("value")
                                raw = " ".join(raw) if isinstance(raw, list) else raw
                                m.sql = self.parse_sql(raw or "", rel, node.position.line)
            for ddl in sorted(folder.rglob("*.sql")):
                if "target" not in ddl.parts:
                    self.parse_ddl(ddl)
            for xml in sorted(folder.rglob("*.xml")):
                if "target" in xml.parts or xml.name == "pom.xml":
                    continue
                self.parse_mapper(xml, service["name"])
        self._connect()

    @staticmethod
    def line_offsets(text):
        out, offset = [], 0
        for line in text.splitlines(keepends=True):
            out.append(offset)
            offset += len(line)
        return out or [0]

    def parse_ddl(self, file):
        rel = file.relative_to(self.root).as_posix()
        self.texts[rel] = file.read_text(encoding="utf-8")
        try:
            statements = sqlglot.parse(self.texts[rel], read="mysql")
        except sqlglot.errors.ParseError as e:
            self.issues.append({"kind": "ddl_parse_error", "file": rel, "detail": str(e)[:300]})
            return
        for s in statements:
            if not isinstance(s, exp.Create) or not isinstance(s.this, exp.Schema):
                continue
            table = s.this.this.name
            columns = []
            for c in s.this.expressions:
                if isinstance(c, exp.ColumnDef):
                    name = c.name
                    kind = (
                        "owner"
                        if name in ("owner_id", "user_id")
                        else "tenant"
                        if name == "tenant_id"
                        else "sensitive"
                        if re.search(r"email|phone|address|balance|detail", name)
                        else "state"
                        if name in ("status", "role")
                        else "ordinary"
                    )
                    columns.append({"name": name, "type": c.args["kind"].sql(), "category": kind})
            self.resources[table] = {
                "name": table,
                "columns": columns,
                "evidence": {"file": rel, "line": 1},
            }

    def parse_sql(self, raw, file, line):
        self.stats["sql_statements"] += 1
        normalized = re.sub(r"#\{([\w.]+)(?:,[^}]*)?\}", r":\1", raw)
        result = {
            "raw": raw.strip(),
            "file": file,
            "line": line,
            "table": None,
            "kind": "unknown",
            "equalities": [],
            "parameters": re.findall(r"#\{([\w.]+)", raw),
            "supported": True,
        }
        try:
            tree = sqlglot.parse_one(normalized, read="mysql")
            table = next(tree.find_all(exp.Table), None)
            result["table"] = table.name if table else None
            result["kind"] = (
                "read"
                if isinstance(tree, exp.Select)
                else "write"
                if isinstance(tree, (exp.Update, exp.Delete, exp.Insert))
                else "unknown"
            )
            # Joins/unions/subqueries require additional row binding; do not certify these.
            if (
                len(list(tree.find_all(exp.Table))) != 1
                or list(tree.find_all(exp.Join))
                or isinstance(tree, exp.Union)
            ):
                result["supported"] = False
            where = tree.args.get("where")

            def guaranteed(node):
                if isinstance(node, (exp.Where, exp.Paren)):
                    return guaranteed(node.this)
                if isinstance(node, exp.And):
                    return guaranteed(node.left) + guaranteed(node.right)
                # OR conjuncts are NOT individually guaranteed.
                if isinstance(node, exp.EQ):
                    for left, right in [(node.left, node.right), (node.right, node.left)]:
                        if isinstance(left, exp.Column) and isinstance(right, exp.Placeholder):
                            return [{"column": left.name, "parameter": right.name}]
                        if isinstance(left, exp.Column) and isinstance(
                            right, (exp.Literal, exp.Boolean)
                        ):
                            val = (
                                right.this
                                if isinstance(right, exp.Boolean)
                                else (right.this if right.is_string else int(right.this))
                            )
                            return [{"column": left.name, "literal": val}]
                return []

            result["equalities"] = guaranteed(where) if where else []
        except (sqlglot.errors.ParseError, ValueError, AttributeError) as e:
            result["supported"] = False
            result["error"] = str(e)[:300]
        return result

    def parse_mapper(self, file, service):
        text = file.read_text(encoding="utf-8")
        if "<mapper" not in text:
            return
        rel = file.relative_to(self.root).as_posix()
        self.texts[rel] = text
        try:
            root = ET.fromstring(text)
        except ET.ParseError as e:
            self.issues.append({"kind": "mapper_parse_error", "file": rel, "detail": str(e)})
            return
        ns = root.attrib.get("namespace")
        fragments = {x.attrib.get("id"): x for x in root if x.tag == "sql"}

        def expand_static(element, stack=()):
            parts = [element.text or ""]
            for child in element:
                if child.tag != "include" or len(child):
                    raise ValueError("Dynamic MyBatis element: " + child.tag)
                ref = child.attrib.get("refid", "")
                if ref.startswith((ns or "") + "."):
                    ref = ref[len(ns) + 1 :]
                if ref not in fragments or ref in stack or len(stack) >= 16:
                    raise ValueError("Missing or recursive MyBatis include: " + ref)
                parts.extend([expand_static(fragments[ref], stack + (ref,)), child.tail or ""])
            return " ".join(parts)

        for statement in root:
            if statement.tag not in ("select", "update", "delete", "insert"):
                continue
            sid = statement.attrib.get("id")
            match = re.search(
                r"<(?:select|update|delete|insert)\b[^>]*\bid=[\"\']"
                + re.escape(sid or "")
                + r"[\"\']",
                text,
            )
            line = text[: match.start()].count("\n") + 1 if match else 1
            try:
                expanded, error = expand_static(statement), None
            except ValueError as e:
                expanded, error = " ".join(statement.itertext()), str(e)
            sql = self.parse_sql(expanded, rel, line)
            if error:
                sql["supported"] = False
                sql["error"] = error
            for m in self.methods.values():
                if m.service == service and m.cls == ns and m.name == sid:
                    m.sql = sql

    def _connect(self):
        for m in self.methods.values():
            if not m.feign or not m.route:
                continue
            candidates = []
            for target in self.methods.values():
                if target.feign or target.service != m.feign or not target.route:
                    continue
                if m.route[0] != target.route[0]:
                    continue
                shape = lambda path: re.sub(r"\{[^}]+\}", "{}", path)
                if shape(m.route[1]) == shape(target.route[1]):
                    candidates.append(target)
            if len(candidates) != 1:
                self.issues.append(
                    {
                        "kind": "rpc_resolution",
                        "file": m.file,
                        "detail": f"{m.id}: {len(candidates)} targets",
                    }
                )
                continue
            target = candidates[0]
            mapping = []
            src_path = re.findall(r"\{([^}]+)\}", m.route[1])
            dst_path = re.findall(r"\{([^}]+)\}", target.route[1])
            for p in target.params:
                matches = []
                for i, q in enumerate(m.params):
                    same = p["kind"] == q["kind"] and p["wire"] == q["wire"]
                    if p["kind"] == q["kind"] == "body":
                        same = True
                    if (
                        p["kind"] == q["kind"] == "path"
                        and p["wire"] in dst_path
                        and q["wire"] in src_path
                    ):
                        same = dst_path.index(p["wire"]) == src_path.index(q["wire"])
                    if same:
                        matches.append(i)
                mapping.append(matches[0] if len(matches) == 1 else None)
            self.rpc[m.id] = (target, mapping)
            self.edges.append(
                {
                    "source": m.id,
                    "target": target.id,
                    "kind": "http",
                    "verb": m.route[0],
                    "route": m.route[1],
                    "parameter_mapping": [
                        {
                            "sender": m.params[i]["name"] if i is not None else None,
                            "receiver": p["name"],
                            "channel": p["kind"],
                        }
                        for p, i in zip(target.params, mapping)
                    ],
                }
            )

    def resolve(self, method, qualifier, name, arity, types):
        cls = types.get(qualifier) or method.fields.get(qualifier) or qualifier
        if not qualifier or qualifier == "this":
            cls = method.cls
        out = [
            m
            for m in self.methods.values()
            if m.service == method.service
            and m.name == name
            and len(m.params) == arity
            and (m.cls == cls or m.cls.split(".")[-1] == cls)
        ]
        return out[0] if len(out) == 1 and "MicroBindAmbiguous" not in out[0].annotations else None

    def entries(self):
        exposed = {s["name"] for s in self.config["services"] if s.get("exposed")}
        return [
            m for m in self.methods.values() if m.service in exposed and m.route and not m.feign
        ]

    def inventory(self):
        return [
            {
                "id": m.id,
                **m.location(),
                "service": m.service,
                "parameters": m.params,
                "route": m.route,
                "feign": m.feign,
                "sql": m.sql,
            }
            for m in self.methods.values()
        ]
