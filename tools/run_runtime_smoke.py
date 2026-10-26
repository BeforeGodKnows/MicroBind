"""Queue -> registered skills -> real bundled Spring services, with LLM disabled."""

import argparse
import json
import os
import tempfile
from pathlib import Path

from microbind.report import dump
from microbind.server.store import Store
from microbind.server.worker import process_one

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=ROOT / "out/runtime-smoke")
    p.add_argument("--maven", default="mvn")
    p.add_argument("--maven-settings", type=Path)
    a = p.parse_args()
    os.environ["MICROBIND_LLM_ENABLED"] = "0"
    os.environ["MICROBIND_MAVEN"] = str(Path(a.maven).resolve()) if "/" in a.maven else a.maven
    if a.maven_settings:
        os.environ["MICROBIND_MAVEN_SETTINGS"] = str(a.maven_settings.resolve())
    with tempfile.TemporaryDirectory(prefix="microbind-runtime-") as data:
        store = Store(Path(data))
        store.add_project("trusted demo", ROOT / "demo", True, "demo")
        id = store.enqueue("demo", "verify", {"smart": False, "repair": True})
        assert process_one(store, "verify", timeout=1800)
        job = store.job(id)
        resultfile = Path(data) / "jobs" / id / "result.json"
        if job["status"] != "succeeded":
            import shutil

            a.out.mkdir(parents=True, exist_ok=True)
            shutil.copytree(Path(data) / "jobs" / id, a.out / "failed-job", dirs_exist_ok=True)
            raise RuntimeError(job["error"])
        result = json.loads(resultfile.read_text())
        assert result["smart"]["status"] == "disabled"
        assert result["verification"]["passed"]
        assert result["verification"]["after"]["summary"]["unauthorized_effects_observed"] == 0
        dump(
            a.out / "runtime-pipeline.json",
            {
                "job": job,
                "before": result["before"]["summary"],
                "after": result["after"]["summary"],
                "repair": result["repair"]["applied"],
                "verification": result["verification"],
                "skill_events": result["skill_events"],
                "llm_enabled": False,
            },
        )
        dump(a.out / "repair-plan.json", result["repair"]["plan"])
        print(
            json.dumps(
                {
                    "before": result["verification"]["before"]["summary"],
                    "after": result["verification"]["after"]["summary"],
                    "skills": result["skill_events"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
