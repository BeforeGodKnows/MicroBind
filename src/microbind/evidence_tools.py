"""Read-only project evidence, shared by the model loop and MCP transport."""

from .report import context_for


class EvidenceTools:
    def __init__(self, project, report):
        self.project, self.report = project, report
        self.findings = {x["id"]: x for x in report["results"]}
        self.snippets = {}
        for finding in report["results"]:
            for snippet in context_for(project, finding)["snippets"]:
                self.snippets[snippet["evidence_id"]] = snippet
        # Other parsed helpers are available for targeted follow-up queries.
        for id, m in project.methods.items():
            text = project.texts[m.file]
            start = project.line_offsets(text)[m.line - 1]
            self.snippets[id] = {
                "evidence_id": id,
                "file": m.file,
                "line": m.line,
                "code": text[start : m.end_offset],
            }

    @staticmethod
    def schemas():
        specs = [
            ("get_method", "读取一个已解析方法的源码和位置", "method_id"),
            ("get_sql", "读取一个 SQL 方法的语句、参数与资源", "method_id"),
            ("get_path", "读取某条发现的实际调用轨迹、RPC 参数绑定和成立条件", "finding_id"),
            ("get_policy", "读取该发现的配置策略和可信身份假设", "finding_id"),
            ("search_methods", "按字面字符串检索方法标识，最多 20 条；不执行正则", "query"),
        ]
        return [
            {
                "name": name,
                "description": description,
                "inputSchema": {
                    "type": "object",
                    "properties": {arg: {"type": "string", "maxLength": 500}},
                    "required": [arg],
                    "additionalProperties": False,
                },
                "annotations": {
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "openWorldHint": False,
                },
            }
            for name, description, arg in specs
        ]

    def call(self, name, arguments):
        spec = next((s for s in self.schemas() if s["name"] == name), None)
        if (
            not spec
            or not isinstance(arguments, dict)
            or set(arguments) != set(spec["inputSchema"]["required"])
        ):
            raise ValueError("Unknown tool or arguments")
        value = next(iter(arguments.values()))
        if not isinstance(value, str) or not 1 <= len(value) <= 500:
            raise ValueError("Invalid query length")
        if name == "search_methods":
            matches = [k for k in self.project.methods if value.lower() in k.lower()]
            return {"matches": matches[:20], "truncated": len(matches) > 20, "evidence_ids": []}
        if name == "get_method":
            s = self.snippets[value]
            return {
                **s,
                "code": s["code"][:16000],
                "truncated": len(s["code"]) > 16000,
                "evidence_ids": [value],
            }
        if name == "get_sql":
            method = self.project.methods[value]
            if not method.sql:
                raise ValueError("This method has no SQL")
            id = "sql:" + value
            self.snippets.setdefault(
                id,
                {
                    "evidence_id": id,
                    "file": method.sql["file"],
                    "line": method.sql["line"],
                    "code": method.sql["raw"],
                },
            )
            return {"sql": method.sql, "evidence_ids": [id]}
        finding = self.findings[value]
        if name == "get_path":
            c = context_for(self.project, finding)
            return {
                "trace": finding["operation"]["trace"],
                "facts": c["facts"],
                "parameter_mappings": c["parameter_mappings"],
                "evidence_ids": [x["evidence_id"] for x in c["snippets"]],
            }
        return {
            "required": finding["required"],
            "policy_basis": finding["policy_basis"],
            "trusted_identity": self.project.config.get("trusted_identity", {}),
            "trust_boundary": self.project.config.get("trust_boundary", {}),
            "evidence_ids": [],
        }
