"""Queue adapter: owns workspace isolation, delegates analysis to registered skills."""

import argparse
import shutil
from pathlib import Path

from ..report import dump
from ..workflows.registry import Context, make_plan, run_skill
from .store import Store


def run(data, id):
    store = Store(data)
    job = store.job(id)
    project_info = store.project(job["project_id"])
    output = Path(data) / "jobs" / id
    output.mkdir(parents=True, exist_ok=True)
    source = Path(project_info["path"])
    if job["kind"] == "verify":
        if not project_info["builtin"] or project_info["id"] != "demo":
            raise ValueError("Uploaded projects cannot execute")
        shutil.copytree(
            source, output / "original-project", ignore=shutil.ignore_patterns("target", ".git")
        )
        source = output / "original-project"
    ctx = Context(source, output, project_info, lambda stage: store.update(id, stage=stage))
    plan = make_plan(
        smart=job["options"].get("smart", False),
        repair=job["options"].get("repair", True),
        verify=job["kind"] == "verify",
    )
    for skill in plan:
        run_skill(skill, ctx)
    dump(output / "result.json", ctx.values["result"])
    return ctx.values["result"]


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("data", type=Path)
    p.add_argument("id")
    a = p.parse_args()
    run(a.data, a.id)
