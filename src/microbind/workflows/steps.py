"""Each handler has one responsibility and exchanges artifacts via Context."""

import os
import zipfile
from pathlib import Path

from ..cli import scan
from ..repair import apply_repairs, build_repairs
from ..report import context_for, dump


def analyze(ctx):
    project, before = scan(ctx.source / "project.yml", ctx.output / "before")
    ctx.values["project"] = project
    origin = (
        "constructed_lab"
        if ctx.project_info.get("builtin")
        else "upstream_sample"
        if ctx.project_info["id"].startswith("sample-")
        else "uploaded_source"
    )
    ctx.values["result"] = {
        "before": before,
        "contexts": [context_for(project, f) for f in before["results"]],
        "after": None,
        "repair": None,
        "smart": {"status": "disabled", "results": []},
        "verification": None,
        "sample_type": origin,
        "skill_events": ctx.events,
    }
    provenance = ctx.source / "provenance.json"
    if provenance.is_file():
        import json

        ctx.values["result"]["source_provenance"] = json.loads(provenance.read_text())


def review(ctx):
    from ..smart import review_findings

    result = ctx.values["result"]
    result["smart"] = review_findings(
        ctx.values["project"], result["before"], ctx.output / "smart-cache"
    )
    dump(ctx.output / "smart.json", result["smart"])
    ctx.values["smart_done"] = True


def repair(ctx):
    result = ctx.values["result"]
    plan = build_repairs(ctx.values["project"], result["before"], ctx.output / "patches")
    applied = apply_repairs(ctx.source, plan, ctx.output / "fixed-project")
    _, after = scan(ctx.output / "fixed-project" / "project.yml", ctx.output / "after")
    result.update(after=after, repair={"plan": plan, "applied": applied})
    ctx.values["fixed_source"] = ctx.output / "fixed-project"


def verify(ctx):
    from ..lab import verify as verify_lab

    if not ctx.project_info.get("builtin") or ctx.project_info["id"] != "demo":
        raise ValueError("Only the trusted built-in lab may execute")
    result = ctx.values["result"]
    settings = (
        Path(os.environ["MICROBIND_MAVEN_SETTINGS"])
        if os.getenv("MICROBIND_MAVEN_SETTINGS")
        else None
    )
    ctx.progress("编译并验证原始服务的 HTTP 与数据库效果")
    original = verify_lab(
        ctx.source,
        ctx.output / "runtime-before",
        "vulnerable",
        os.getenv("MICROBIND_MAVEN", "mvn"),
        settings,
    )
    ctx.progress("验证修复后服务与正常业务")
    fixed = verify_lab(
        ctx.values["fixed_source"],
        ctx.output / "runtime-after",
        "fixed",
        os.getenv("MICROBIND_MAVEN", "mvn"),
        settings,
    )
    result["verification"] = {
        "before": original,
        "after": fixed,
        "passed": original["passed"] and fixed["passed"],
    }
    for patch in result["repair"]["plan"]["patches"]:
        if patch["status"] == "candidate":
            case = next((c for c in fixed["cases"] if c["endpoint"] == patch["endpoint"]), None)
            patch["verification"] = (
                "passed_in_lab"
                if case and case["passed"] and fixed["passed"]
                else "failed_or_not_covered"
            )
    dump(ctx.output / "patches" / "repair_plan.json", result["repair"]["plan"])
    dump(ctx.output / "result.json", result)
    if not result["verification"]["passed"]:
        raise RuntimeError("HTTP/数据库回归验证未通过，详见结果")
    ctx.values["runtime_done"] = True


def export(ctx):
    ctx.values["bundle"] = ctx.output / "bundle.zip"
    # The archive is available only if this handler and its write succeed.
    ctx.events[-1]["status"] = "succeeded"
    finalize(ctx)


def finalize(ctx):
    dump(ctx.output / "result.json", ctx.values["result"])
    with zipfile.ZipFile(ctx.values["bundle"], "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(ctx.output.rglob("*")):
            if (
                file.is_file()
                and file.name not in {"bundle.zip", "worker.log"}
                and not any(
                    x in {"target", "smart-cache"} for x in file.relative_to(ctx.output).parts
                )
            ):
                archive.write(file, file.relative_to(ctx.output))
