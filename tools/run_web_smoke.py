"""Start actual API, worker and frontend processes; run Chromium against them."""

import os
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    children = []
    evidence = ROOT / "out/validation"
    evidence.mkdir(parents=True, exist_ok=True)
    with (evidence / "sample-preparation.log").open("w") as log:
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools/run_paper_samples.py"),
                "--out",
                str(evidence / "paper-samples"),
                "--export-zips",
            ],
            cwd=ROOT,
            stdout=log,
            stderr=log,
            check=True,
        )
    with tempfile.TemporaryDirectory(prefix="microbind-web-") as work:
        env = {
            **os.environ,
            "MICROBIND_DATA": work,
            "MICROBIND_DEMO": str(ROOT / "demo"),
            "MICROBIND_TOKEN": "web-smoke-test-token-not-for-deployment",
            "MICROBIND_VERIFY_ENABLED": ("1" if os.getenv("MICROBIND_E2E_VERIFY") == "1" else "0"),
            "MICROBIND_LLM_ENABLED": "0",
            "MICROBIND_SAMPLES": str(ROOT / "samples"),
        }
        logs = []
        (ROOT / "out/validation").mkdir(parents=True, exist_ok=True)
        try:
            commands = [
                (
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "microbind.server.app:create_app",
                        "--factory",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        "8000",
                    ],
                    ROOT,
                ),
                ([sys.executable, "-m", "microbind.server.worker"], ROOT),
                (["npm", "run", "dev", "--", "--port", "4173", "--strictPort"], ROOT / "frontend"),
            ]
            if os.getenv("MICROBIND_E2E_VERIFY") == "1":
                commands.append(
                    ([sys.executable, "-m", "microbind.server.worker", "--kind", "verify"], ROOT)
                )
            for i, (command, cwd) in enumerate(commands):
                log = open(ROOT / "out/validation" / f"web-service-{i}.log", "w")
                logs.append(log)
                children.append(
                    subprocess.Popen(
                        command, cwd=cwd, env=env, stdout=log, stderr=log, start_new_session=True
                    )
                )
            for url in ["http://127.0.0.1:8000/api/health", "http://127.0.0.1:4173"]:
                for attempt in range(100):
                    if any(c.poll() is not None for c in children):
                        raise RuntimeError("A web service exited; see logs")
                    try:
                        with urllib.request.urlopen(url, timeout=1) as r:
                            if r.status == 200:
                                break
                    except OSError:
                        time.sleep(0.2)
                else:
                    raise RuntimeError("Web service failed to become ready")
            test = subprocess.run(["npx", "playwright", "test"], cwd=ROOT / "frontend", env=env)
            return test.returncode
        finally:
            for child in children:
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            for child in children:
                try:
                    child.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait()
            for log in logs:
                log.close()


if __name__ == "__main__":
    sys.exit(main())
