"""An explicit skill catalog. Uploaded source never registers executable skills."""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class Skill:
    id: str
    title: str
    requires: tuple[str, ...]
    produces: tuple[str, ...]
    permissions: tuple[str, ...]
    handler: Callable
    version: str = "1.0"


@dataclass
class Context:
    source: Path
    output: Path
    project_info: dict
    progress: Callable[[str], None]
    values: dict = field(default_factory=dict)
    events: list = field(default_factory=list)


def registry():
    from .steps import analyze, export, repair, review, verify

    return {
        s.id: s
        for s in [
            Skill(
                "source.analyze",
                "源码授权分析",
                (),
                ("project", "result"),
                ("read_source", "write_report"),
                analyze,
            ),
            Skill(
                "model.review",
                "模型证据复核",
                ("project", "result"),
                ("smart_done",),
                ("read_source", "model_network"),
                review,
            ),
            Skill(
                "repair.propose",
                "补丁生成与副本复查",
                ("project", "result"),
                ("fixed_source",),
                ("write_project_copy",),
                repair,
            ),
            Skill(
                "lab.verify",
                "自建靶场运行验证",
                ("result", "fixed_source"),
                ("runtime_done",),
                ("execute_trusted_lab",),
                verify,
            ),
            Skill(
                "report.export",
                "报告与证据打包",
                ("result",),
                ("bundle",),
                ("write_report",),
                export,
            ),
        ]
    }


def catalog():
    return [
        {
            "id": s.id,
            "title": s.title,
            "version": s.version,
            "requires": list(s.requires),
            "produces": list(s.produces),
            "permissions": list(s.permissions),
            "implementation": "registered_builtin",
        }
        for s in registry().values()
    ]


def run_skill(id, ctx):
    skill = registry()[id]
    missing = set(skill.requires) - ctx.values.keys()
    if missing:
        raise ValueError("Skill prerequisites missing: " + ", ".join(sorted(missing)))
    event = {"skill_id": id, "version": skill.version, "title": skill.title, "status": "running"}
    ctx.events.append(event)
    start = time.monotonic()
    ctx.progress(skill.title)
    try:
        skill.handler(ctx)
        if set(skill.produces) - ctx.values.keys():
            raise RuntimeError("Skill did not produce its declared artifacts: " + id)
        event["status"] = "succeeded"
    except Exception as error:
        event.update(status="failed", error=type(error).__name__)
        raise
    finally:
        event["elapsed_seconds"] = round(time.monotonic() - start, 4)
        from ..report import dump

        dump(ctx.output / "skill-events.json", ctx.events)


def make_plan(*, smart=False, repair=True, verify=False):
    return (
        ["source.analyze"]
        + (["model.review"] if smart else [])
        + (["repair.propose"] if repair or verify else [])
        + (["lab.verify"] if verify else [])
        + ["report.export"]
    )
