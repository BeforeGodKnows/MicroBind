"""Offline MicroBind checks on hash-pinned, unmodified upstream source subsets.

Passing a compatibility assertion is not a vulnerability detection success rate.
Use --out to retain the full analyses, contexts and a small JSON/Markdown summary.
"""

import argparse
import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from microbind import __version__
from microbind.cli import scan
from microbind.report import dump


def integrity(folder):
    provenance = json.loads((folder / "provenance.json").read_text())
    for file in provenance["files"]:
        actual = hashlib.sha256((folder / file["path"]).read_bytes()).hexdigest()
        if actual != file["sha256"]:
            raise ValueError("Upstream bytes changed: " + file["path"])
    return provenance


def run(output):
    output = Path(output)
    rows = []
    for name in ["neo-http", "neo-role", "litemall"]:
        folder = ROOT / "samples" / name
        provenance = integrity(folder)
        project, report = scan(folder / "project.yml", output / name)
        if name == "neo-http":
            expected = {
                ("account-service", "GET", "/accounts/{accountName}"),
                ("account-service", "POST", "/accounts"),
                ("account-service", "GET", "/accounts"),
                ("payment-service", "POST", "/payments"),
                ("payment-service", "GET", "/payments/{id}"),
            }
            actual = {
                (project.methods[e["target"]].service, e["verb"], e["route"]) for e in project.edges
            }
            checks = {
                "five_expected_feign_edges": actual == expected,
                "wire_bindings_complete": all(
                    x["sender"] is not None for e in project.edges for x in e["parameter_mapping"]
                ),
                "no_false_clean_verdict": report["assessment"]["status"] == "no_operation_evidence",
            }
            outcome = "通信组件通过；样例没有 SQL 授权真值，不能计算漏洞精度。"
        elif name == "neo-role":
            checks = {
                "python_gap_visible": any(
                    g.get("kind") == "unsupported_language" for g in report["coverage_gaps"]
                ),
                "rest_template_gap_visible": any(
                    "postForObject" in g.get("detail", "") for g in report["coverage_gaps"]
                ),
                "no_false_clean_verdict": report["assessment"]["status"] == "no_operation_evidence",
            }
            outcome = "当前不支持完整路径；未检出该跨语言角色修改问题，已明确报告覆盖缺口。"
        else:
            brand = [r for r in report["results"] if r["endpoint"] == ["GET", "/wx/brand/detail"]]
            address = [r for r in report["results"] if r["endpoint"][1].startswith("/wx/address/")]
            checks = {
                "six_original_endpoints": report["summary"]["entries"] == 6,
                "public_brand_detail_covered": len(brand) == 1 and brand[0]["status"] == "covered",
                "address_not_certified": bool(address)
                and all(r["status"] == "needs_review" for r in address),
                "partial_coverage_visible": report["assessment"]["status"] == "partial",
                "html_written_for_unknown_table": (output / name / "report.html").is_file(),
            }
            outcome = "原始源码子集接入成功；1 条公开读取有静态结论，7 条操作待确认。不是 PCFinder 原论文精度复现。"
        rows.append(
            {
                "sample": name,
                "upstream": {
                    k: provenance[k]
                    for k in ["repository", "commit", "scope", "source_modified", "relation"]
                },
                "original_files_verified": len(provenance["files"]),
                "summary": report["summary"],
                "assessment": report["assessment"],
                "gap_count": len(report["coverage_gaps"]),
                "checks": checks,
                "outcome": outcome,
            }
        )
    doc = {
        "schema_version": "1.0",
        "tool_version": __version__,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "llm_enabled": False,
        "target_code_executed": False,
        "paper_accuracy_reproduced": False,
        "assertions_passed": all(all(r["checks"].values()) for r in rows),
        "samples": rows,
    }
    dump(output / "summary.json", doc)
    lines = [
        "# 上游样例实测记录",
        "",
        "本命令不调用大模型，不执行被分析项目。通过的是兼容性与缺口提示断言，不是漏洞检出率。",
        "",
        "| 样例 | 入口 | HTTP 连接 | 数据操作 | 已有覆盖 | 待确认 | 结论 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        s = row["summary"]
        lines.append(
            f"| {row['sample']} | {s['entries']} | {s['rpc_edges']} | {s['operations']} | {s.get('covered', 0)} | {s.get('needs_review', 0)} | {row['outcome']} |"
        )
    lines += [
        "",
        "各目录包含 analysis.json、HTML、Markdown、SARIF 与源码上下文。来源提交和逐文件 SHA256 位于 samples/*/provenance.json。",
        "",
        "NEO 离线原工具演示需另运行 tools/run_neo_offline.py；它使用作者预置的单服务流，不调用 CodeQL 或 LLM。",
    ]
    (output / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return doc


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=ROOT / "out/paper-samples")
    p.add_argument(
        "--export-zips",
        action="store_true",
        help="Create source ZIPs suitable for UI import (NEO Python sample is preinstalled only)",
    )
    a = p.parse_args()
    doc = run(a.out)
    if a.export_zips:
        for name in ["neo-http", "litemall"]:
            with zipfile.ZipFile(a.out / (name + ".zip"), "w", zipfile.ZIP_DEFLATED) as z:
                for f in sorted((ROOT / "samples" / name).rglob("*")):
                    if f.is_file():
                        z.write(f, f.relative_to(ROOT / "samples" / name))
    print(json.dumps(doc, ensure_ascii=False, indent=2))
    return 0 if doc["assertions_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
