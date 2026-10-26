"""Human-readable evidence reports plus machine-readable/SARIF exports."""

from __future__ import annotations

import html
import json

from . import __version__
from .model import term_text

LABELS = {"suspected": "疑似缺陷", "covered": "已满足授权要求", "needs_review": "待确认"}
REASONS = {
    "missing_owner": "缺少对目标对象的归属约束",
    "object_mismatch": "检查对象与实际操作对象不一致",
    "untrusted_subject": "用于授权的身份由请求方提供",
    "missing_tenant": "缺少可信租户范围约束",
    "missing_role": "缺少所需角色检查",
    "unknown_policy": "授权策略需要确认",
}


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_demo_overview(output, pipeline, original, fixed):
    """One standalone report combines source evidence with observed runtime effects."""
    source = (output / "before" / "report.html").read_text(encoding="utf-8")
    rows = []
    by_route = {tuple(x["endpoint"]): x for x in fixed["cases"]}
    for before in original["cases"]:
        after = by_route[tuple(before["endpoint"])]
        rows.append(
            "<tr><td>"
            + html.escape(" ".join(before["endpoint"]))
            + "</td><td>"
            + ("观察到" if before["attack"]["effect"] else "未观察到")
            + "</td><td>"
            + ("仍发生" if after["attack"]["effect"] else "未发生")
            + "</td><td>"
            + ("通过" if after["legitimate"]["effect"] else "失败")
            + "</td></tr>"
        )
    panel = '<section style="background:#fff;padding:22px;border:1px solid #dbe2e8;margin:24px 0"><h2>靶场运行验证 · 修复前后</h2><p>本次在内置订单靶场运行 18 个场景，请求经过网关、Feign、MyBatis 和 H2，并检查 HTTP 响应及数据库状态。</p>'
    panel += f"<p><b>越权请求生效数：{original['summary']['unauthorized_effects_observed']} → {fixed['summary']['unauthorized_effects_observed']}；修复后正常请求：{fixed['summary']['legitimate_requests_passed']}/18；边界检查：{fixed['summary']['boundary_checks_passed']}/4。</b></p>"
    panel += (
        '<p class="muted">下方展示修复前的源码证据，运行记录和补丁保存在输出目录中。</p><details><summary>展开逐场景验证结果</summary><div style="overflow-x:auto"><table style="width:100%;text-align:left;border-collapse:collapse"><thead><tr><th>入口</th><th>修复前越权请求</th><th>修复后越权请求</th><th>正常请求</th></tr></thead><tbody>'
        + "".join(rows)
        + "</tbody></table></div></details></section>"
    )
    source = source.replace("<nav>", panel + "<nav>", 1)
    (output / "demo-report.html").write_text(source, encoding="utf-8")


def context_for(project, result):
    mids = {x.get("method") for x in result["operation"]["trace"]}
    mids |= {x["evidence"].get("method") for x in result["facts"]}
    mids.add(result["entry"])
    snippets = []
    for mid in sorted(x for x in mids if x in project.methods):
        m = project.methods[mid]
        text = project.texts[m.file]
        begin = project.line_offsets(text)[m.line - 1]
        snippets.append(
            {"evidence_id": mid, "file": m.file, "line": m.line, "code": text[begin : m.end_offset]}
        )
    sql = result["operation"]["sql"]
    snippets.append(
        {
            "evidence_id": "sql:" + result["operation"]["method"],
            "file": sql["file"],
            "line": sql["line"],
            "code": sql["raw"],
        }
    )
    return {
        "finding_id": result["id"],
        "endpoint": result["endpoint"],
        "resource": result["operation"]["table"],
        "operation": result["operation"]["kind"],
        "object": term_text(result["operation"]["object"]),
        "required": result["required"],
        "policy_basis": result["policy_basis"],
        "trusted_identity_configuration": project.config.get("trusted_identity", {}),
        "deployment_assumptions": project.config.get("trust_boundary", {}),
        "facts": [
            {
                "predicate": term_text(f["left"]) + " " + f["op"] + " " + term_text(f["right"]),
                "evidence": f["evidence"],
            }
            for f in result["facts"] + result["operation"]["sql_constraints"]
        ],
        "parameter_mappings": [x for x in result["operation"]["trace"] if x["kind"] == "rpc"],
        "static_verdict": result["status"],
        "missing": result["missing"],
        "snippets": snippets,
    }


def write_reports(project, report, output):
    output.mkdir(parents=True, exist_ok=True)
    dump(output / "analysis.json", report)
    for key in ("resources", "service_edges", "access_paths"):
        dump(output / (key + ".json"), report[key])
    dump(output / "operations.json", [m for m in report["methods"] if m["sql"]])
    contexts = [context_for(project, r) for r in report["results"]]
    for c in contexts:
        dump(output / "contexts" / (c["finding_id"] + ".json"), c)
    s = report["summary"]
    lines = [
        "# MicroBind 授权分析报告",
        "",
        f"源码解析器：`{report['frontend']}`。模型复核状态：`{report['llm']['status']}`。",
        "",
        report.get("assessment", {}).get("message", ""),
        "",
        f"Java 文件 {s['parsed_java_files']}/{s['java_files']}；HTTP 连接 {s['rpc_edges']}；数据操作 {s['operations']}。",
        f"疑似缺陷 {s.get('suspected', 0)}；已满足授权要求 {s.get('covered', 0)}；待确认 {s.get('needs_review', 0)}。",
        "",
        "本报告记录静态分析结果，依据项目配置中的授权规则、可信身份和对外接口进行判断。无法解析的语法和调用见覆盖缺口；运行验证的结果单独记录。",
        "",
        "| 入口 | 判定 | 说明 |",
        "| --- | --- | --- |",
    ]
    for r in report["results"]:
        reasons = (
            "；".join(REASONS.get(m["kind"], m["kind"]) for m in r["missing"])
            or "已满足配置中的授权要求"
        )
        lines.append(f"| {' '.join(r['endpoint'])} | {LABELS[r['status']]} | {reasons} |")
    for r, c in zip(report["results"], contexts):
        op = r["operation"]
        lines += [
            "",
            f"## {' '.join(r['endpoint'])}",
            "",
            f"结论：{LABELS[r['status']]}。操作：{op['kind']} `{op['table']}`。",
            "",
            f"操作对象：`{term_text(op['object'])}`。授权要求：`{json.dumps(r['required'], ensure_ascii=False)}`。",
            "",
            f"代码位置：`{op['location']['file']}:{op['location']['line']}`。",
        ]
        for x in c["parameter_mappings"]:
            lines += [
                "",
                f"跨服务：`{x['method']}` → `{x['target']}`；参数：`{json.dumps(x['bindings'], ensure_ascii=False)}`。",
            ]
        if c["facts"]:
            lines += ["", "相关条件：", ""] + [
                f"- `{f['predicate']}`，来源 `{f['evidence']['file']}:{f['evidence']['line']}`。"
                for f in c["facts"]
            ]
        lines += ["", "```sql", op["sql"]["raw"], "```"]
    if report["coverage_gaps"]:
        lines += [
            "",
            "## 分析覆盖缺口",
            "",
            "```json",
            json.dumps(report["coverage_gaps"], ensure_ascii=False, indent=2),
            "```",
        ]
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    rules = sorted({m["kind"] for r in report["results"] for m in r["missing"]})
    sarif = {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "MicroBind",
                        "version": __version__,
                        "rules": [
                            {"id": x, "shortDescription": {"text": REASONS.get(x, x)}}
                            for x in rules
                        ],
                    }
                },
                "results": [
                    {
                        "ruleId": missing["kind"],
                        "level": "warning" if r["status"] == "suspected" else "note",
                        "message": {
                            "text": " ".join(r["endpoint"])
                            + ": "
                            + REASONS.get(missing["kind"], missing["kind"])
                        },
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": r["operation"]["location"]["file"]},
                                    "region": {"startLine": r["operation"]["location"]["line"]},
                                }
                            }
                        ],
                        "partialFingerprints": {"microbind/v1": r["id"]},
                    }
                    for r in report["results"]
                    if r["status"] != "covered"
                    for missing in r["missing"]
                ],
            }
        ],
    }
    dump(output / "report.sarif", sarif)
    cards = []
    for r, c in zip(report["results"], contexts):
        e = lambda value: html.escape("未知" if value is None else str(value))
        reasons = (
            "；".join(REASONS.get(x["kind"], x["kind"]) for x in r["missing"])
            or "当前操作满足配置中的授权要求"
        )
        facts = "\n".join(x["predicate"] for x in c["facts"]) or "未提取到适用的授权条件"
        trace = "".join(
            f"<li><b>{e(t['kind'])}</b> {e(t.get('method', ''))}<small>{e(json.dumps(t.get('bindings') or t.get('arguments') or {}, ensure_ascii=False))}</small></li>"
            for t in r["operation"]["trace"]
            if t["kind"] in ("call", "rpc")
        )
        snippets = "".join(
            f"<details><summary>{e(x['file'])}:{x['line']}</summary><pre>{e(x['code'])}</pre></details>"
            for x in c["snippets"]
        )
        cards.append(
            f'<article data-status="{r["status"]}"><h2><span class="badge {r["status"]}">{LABELS[r["status"]]}</span>{e(" ".join(r["endpoint"]))}</h2><p>{e(reasons)}</p><p class="muted">{e(c["resource"])} · {e(c["operation"])} · {e(c["object"])}</p><details><summary>查看调用、参数与代码证据</summary><ol>{trace}</ol><h3>已成立的条件</h3><pre>{e(facts)}</pre>{snippets}</details></article>'
        )
    page = """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MicroBind · 授权分析报告</title>
<style>body{margin:0;background:#f1f4f7;color:#182b40;font:15px/1.65 system-ui,"Microsoft YaHei",sans-serif}main{max-width:1120px;margin:auto;padding:40px 24px}h1{font-size:34px;margin:5px 0}h2{font-size:17px;margin:0}h3{font-size:15px}.kicker{color:#44746a;letter-spacing:2px}header{margin-bottom:28px}.muted{color:#596b7d;font-size:13px;overflow-wrap:anywhere}.stats{display:flex;gap:14px;flex-wrap:wrap}.stats div{flex:1;background:#fff;border:1px solid #dbe2e8;padding:16px;min-width:120px}.stats b{font-size:26px;display:block}nav{display:flex;gap:12px;margin:22px 0}input,select{padding:10px;border:1px solid #b9c9d5;border-radius:4px;font:inherit}input{flex:1}article{background:#fff;border:1px solid #dbe2e8;border-radius:6px;padding:20px;margin:12px 0}.badge{display:inline-block;font-size:12px;margin-right:12px;padding:3px 8px;border-radius:4px}.suspected{color:#9f3418;background:#fce9df}.covered{color:#236247;background:#e0f3e9}.needs_review{color:#6d5412;background:#fff1c9}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#edf2f6;border-radius:4px;padding:14px;font:13px/1.6 ui-monospace,monospace}summary{cursor:pointer;color:#235777;padding:8px 0}small{display:block;color:#586777;overflow-wrap:anywhere}li{margin-bottom:10px;overflow-wrap:anywhere}footer{margin-top:30px;color:#596b7d}</style>
<main><header><div class="kicker">MICROBIND / RESEARCH DEMO</div><h1>跨服务授权分析</h1><p>沿调用链核对授权检查与数据库操作是否使用同一对象。</p><p class="muted">查看调用路径、SQL 条件和源码位置。</p></header>"""
    page += "<p>" + html.escape(report.get("assessment", {}).get("message", "")) + "</p>"
    page += (
        '<section class="stats">'
        + "".join(
            f"<div>{label}<b>{number}</b></div>"
            for label, number in [
                ("数据操作", s["operations"]),
                ("疑似缺陷", s.get("suspected", 0)),
                ("已满足授权要求", s.get("covered", 0)),
                ("待确认", s.get("needs_review", 0)),
            ]
        )
        + "</section>"
    )
    page += (
        '<nav><input id="q" placeholder="筛选接口、资源或证据"><select id="status"><option value="">全部判定</option value="suspected">疑似缺陷</option><option value="covered">已满足授权要求</option><option value="needs_review">待确认</option></select></nav><section id="cards">'
        + "".join(cards)
        + "</section>"
    )
    page += f"<footer>覆盖缺口：{len(report['coverage_gaps'])}。完整静态记录见 analysis.json。生成补丁时附 patches/；执行运行验证后附相应验证记录。授权规则和可信身份来自项目配置。</footer></main>"
    page += """<script>function filter(){const q=document.getElementById('q').value.toLowerCase(),s=document.getElementById('status').value;document.querySelectorAll('article').forEach(a=>a.hidden=!(a.textContent.toLowerCase().includes(q)&&(!s||a.dataset.status===s)))}document.getElementById('q').oninput=filter;document.getElementById('status').onchange=filter;</script></html>"""
    (output / "report.html").write_text(page, encoding="utf-8")
    return contexts
