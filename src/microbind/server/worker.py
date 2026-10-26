import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from .store import Store


def process_one(store, kind="scan", timeout=1800):
    job = store.claim(kind)
    if not job:
        return False
    output = store.root / "jobs" / job["id"]
    output.mkdir(parents=True, exist_ok=True)
    child = None
    try:
        with (output / "worker.log").open("w") as log:
            child = subprocess.Popen(
                [sys.executable, "-m", "microbind.server.pipeline", str(store.root), job["id"]],
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            start = time.monotonic()
            while child.poll() is None:
                if time.monotonic() - start > timeout:
                    raise TimeoutError("任务超过时间上限")
                store.update(job["id"])
                time.sleep(2)
            if child.returncode:
                raise RuntimeError("分析失败，请检查项目配置和源码；详细错误见服务端 worker.log")
        store.update(job["id"], status="succeeded", stage="完成")
    except (Exception, KeyboardInterrupt) as error:
        store.update(job["id"], status="failed", stage="任务失败", error=str(error)[:300])
        if isinstance(error, KeyboardInterrupt):
            raise
    finally:
        # Includes any Java grandchildren on timeout, failure, or graceful worker shutdown.
        if child:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=["scan", "verify"], default="scan")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    def stop(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    store = Store(Path(os.getenv("MICROBIND_DATA", "out/server")).resolve())
    try:
        while True:
            handled = process_one(store, args.kind, int(os.getenv("MICROBIND_JOB_TIMEOUT", "1800")))
            if args.once:
                return
            if not handled:
                time.sleep(2)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
