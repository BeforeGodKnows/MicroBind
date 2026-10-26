from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import Analyzer
from .frontend import Project
from .repair import apply_repairs, build_repairs
from .report import dump, write_demo_overview, write_reports


def scan(manifest, output, llm=False):
    if llm:
        from .model_config import require_enabled

        require_enabled()
    project = Project(Path(manifest))
    report = Analyzer(project).run()
    contexts = write_reports(project, report, Path(output))
    if llm:
        from .llm import review

        reports = []
        for context in contexts:
            try:
                reports.append(
                    {
                        "finding_id": context["finding_id"],
                        "status": "completed",
                        **review(context, Path(output) / "llm_cache"),
                    }
                )
            except Exception as e:
                reports.append(
                    {"finding_id": context["finding_id"], "status": "failed", "error": str(e)[:300]}
                )
        report["llm"] = {
            "status": "completed"
            if all(x["status"] == "completed" for x in reports)
            else "partial_or_failed",
            "results": reports,
        }
        write_reports(project, report, Path(output))
    return project, report


def main(argv=None):
    parser = argparse.ArgumentParser(prog="microbind", description="Java 微服务授权分析与修复")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("check-config", help="检查项目配置、服务路径和可信身份方法")
    p.add_argument("manifest", type=Path)
    p = sub.add_parser("scan", help="分析服务源码并输出报告")
    p.add_argument("manifest", type=Path)
    p.add_argument("--out", type=Path, default=Path("out/scan"))
    p.add_argument("--llm", action="store_true")
    p.add_argument("--smart", action="store_true", help="启用模型复核，并限制工具调用次数和耗时")
    p.add_argument("--fail-on-findings", action="store_true")
    p = sub.add_parser("repair", help="生成补丁，可应用到新的源码副本")
    p.add_argument("manifest", type=Path)
    p.add_argument("--out", type=Path, default=Path("out/repair"))
    p.add_argument("--apply-to", type=Path)
    for name, help_text in [
        ("verify", "启动内置靶场，验证 HTTP 响应和数据库状态"),
        ("demo", "运行内置项目的分析、修复和验证流程"),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--project", type=Path, default=Path("demo"))
        p.add_argument("--out", type=Path, default=Path("out") / name)
        p.add_argument("--maven", default="mvn")
        p.add_argument("--maven-settings", type=Path)
        if name == "verify":
            p.add_argument("--mode", choices=["vulnerable", "fixed"], default="vulnerable")
            p.add_argument("--skip-build", action="store_true")
        else:
            p.add_argument("--static-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "check-config":
            from .project_config import diagnose

            print(json.dumps(diagnose(args.manifest), ensure_ascii=False, indent=2))
        elif args.command == "scan":
            if args.smart:
                from .model_config import require_enabled

                require_enabled()
            project, report = scan(args.manifest, args.out, args.llm)
            if args.smart:
                from .smart import review_findings

                report["smart"] = review_findings(project, report, args.out / "smart-cache")
                write_reports(project, report, args.out)
                dump(args.out / "smart.json", report["smart"])
            print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
            if args.fail_on_findings and (
                report["summary"].get("suspected", 0)
                or report["summary"].get("needs_review", 0)
                or report["coverage_gaps"]
            ):
                return sys.exit(2)
        elif args.command == "repair":
            project, report = scan(args.manifest, args.out)
            plan = build_repairs(project, report, args.out / "patches")
            if args.apply_to:
                print(
                    json.dumps(
                        apply_repairs(project.root, plan, args.apply_to),
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            else:
                print(f"Generated {len(plan['patches'])} repair records in {args.out / 'patches'}")
        elif args.command == "verify":
            from .lab import verify

            result = verify(
                args.project, args.out, args.mode, args.maven, args.maven_settings, args.skip_build
            )
            print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
            if not result["passed"]:
                return sys.exit(1)
        else:
            from .lab import verify

            args.out.mkdir(parents=True, exist_ok=True)
            if (args.out / "fixed-project").exists():
                raise ValueError("Output already contains fixed-project; use a new --out directory")
            print("[1/5] Analyzing original sources", flush=True)
            project, before = scan(args.project / "project.yml", args.out / "before")
            print("[2/5] Generating evidence-directed patches", flush=True)
            plan = build_repairs(project, before, args.out / "patches")
            applied = apply_repairs(project.root, plan, args.out / "fixed-project")
            print("[3/5] Re-analyzing repaired sources", flush=True)
            _, after = scan(args.out / "fixed-project" / "project.yml", args.out / "after")
            pipeline = {
                "before": before["summary"],
                "after": after["summary"],
                "repair": applied,
                "dynamic_validation": {"status": "not_run"},
                "sample_type": "constructed_lab_not_real_project_benchmark",
            }
            if not args.static_only:
                print("[4/5] Building and exercising original services", flush=True)
                original = verify(
                    args.project,
                    args.out / "runtime-before",
                    "vulnerable",
                    args.maven,
                    args.maven_settings,
                )
                dump(args.out / "pipeline.json", pipeline)
                print("[5/5] Building and exercising repaired services", flush=True)
                fixed = verify(
                    args.out / "fixed-project",
                    args.out / "runtime-after",
                    "fixed",
                    args.maven,
                    args.maven_settings,
                )
                pipeline["dynamic_validation"] = {
                    "status": "passed" if original["passed"] and fixed["passed"] else "failed",
                    "before": original["summary"],
                    "after": fixed["summary"],
                }
                dump(args.out / "verification.json", {"before": original, "after": fixed})
                write_demo_overview(args.out, pipeline, original, fixed)
                for p in plan["patches"]:
                    if p["status"] == "candidate":
                        case = next(
                            (x for x in fixed["cases"] if x["endpoint"] == p["endpoint"]), None
                        )
                        p["verification"] = (
                            "passed_in_lab"
                            if case and case["passed"] and fixed["passed"]
                            else "failed_or_not_covered"
                        )
                dump(args.out / "patches" / "repair_plan.json", plan)
            dump(args.out / "pipeline.json", pipeline)
            print(json.dumps(pipeline, ensure_ascii=False, indent=2))
            if pipeline["dynamic_validation"]["status"] == "failed":
                return sys.exit(1)
    except (ValueError, RuntimeError, OSError) as e:
        print(f"MicroBind: {e}", file=sys.stderr)
        return sys.exit(1)


if __name__ == "__main__":
    main()
