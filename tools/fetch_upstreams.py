"""Download the inspected upstream revisions without executing their code."""

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--name", action="append")
    p.add_argument("--out", type=Path, default=Path("out/upstreams"))
    a = p.parse_args()
    records = json.loads((ROOT / "docs/upstreams.json").read_text(encoding="utf-8"))
    for record in records:
        if a.name and record["name"] not in a.name:
            continue
        folder = a.out / record["name"]
        if folder.exists():
            raise SystemExit(f"Destination exists: {folder}; use a different --out")
        folder.mkdir(parents=True)

        def git(*args):
            subprocess.run(["git", "-C", str(folder), *args], check=True)

        git("init", "-q")
        git("remote", "add", "origin", record["url"] + ".git")
        git("fetch", "--depth=1", "--filter=blob:none", "origin", record["commit"])
        git("sparse-checkout", "init", "--cone")
        if record["sparse_paths"]:
            git("sparse-checkout", "set", *record["sparse_paths"])
        git("checkout", "--detach", "FETCH_HEAD")
        print(record["name"], record["commit"])


if __name__ == "__main__":
    main()
