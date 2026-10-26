"""Run the original author's offline example at the reviewed revision (no model)."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

COMMIT = "65ec4e35a1db67159a9d89a59e3e28d30f665690"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--out", type=Path, default=Path("out/neo-original"))
    a = p.parse_args()
    repo = a.repo.resolve()
    a.out.mkdir(parents=True, exist_ok=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    if head != COMMIT:
        raise ValueError("Expected NEO commit " + COMMIT)
    if subprocess.check_output(
        ["git", "diff", "HEAD", "--", "examples", "src"], cwd=repo, text=True
    ).strip():
        raise ValueError("NEO tracked source differs from the expected revision")
    result = subprocess.run(
        [sys.executable, "examples/run_demo.py"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=120,
    )
    (a.out / "stdout.txt").write_text(result.stdout + result.stderr)
    result.check_returncode()
    source = repo / "global_work/role-switch-demo/GlobalFlowSourceSink.json"
    doc = json.loads(source.read_text())
    (a.out / "flows.json").write_text(json.dumps(doc, indent=2))
    flows = [f for group in doc["grouped_flows"].values() for f in group]
    assert len(flows) == 1 and flows[0]["services"] == ["user-profile", "user-mgmt"]
    summary = {
        "commit": COMMIT,
        "flow_count": len(flows),
        "services": flows[0]["services"],
        "codeql_run": False,
        "llm_run": False,
        "seeded_service_flows": True,
        "full_paper_reproduction": False,
        "passed": True,
    }
    (a.out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
