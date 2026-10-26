"""Build and execute the actual Spring/Feign/MyBatis lab over localhost HTTP."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zipfile import ZipFile

from .report import dump

KEY = "local-demo-internal-key"


def request(url, method="GET", body=None, headers=None):
    req = Request(
        url,
        method=method,
        data=json.dumps(body).encode() if body is not None else (b"" if method == "POST" else None),
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urlopen(req, timeout=10) as r:
            status, raw = r.status, r.read().decode()
    except HTTPError as e:
        status, raw = e.code, e.read().decode()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = raw
    return status, value


def build(root, log_dir, maven="mvn", settings=None):
    log_dir.mkdir(parents=True, exist_ok=True)
    command = [maven]
    if settings:
        command += ["-s", str(settings)]
    command += ["-B", "-q", "-f", str(root / "pom.xml"), "clean", "package", "-DskipTests"]
    start = time.perf_counter()
    with (log_dir / "build.log").open("w", encoding="utf-8") as log:
        p = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=900)
    if p.returncode:
        raise RuntimeError(f"Maven build failed; see {log_dir / 'build.log'}")
    for name in ("data", "orders", "gateway"):
        jar = root / name / "target" / (name + "-0.1.0.jar")
        with ZipFile(jar) as z:
            if b"Main-Class:" not in z.read("META-INF/MANIFEST.MF"):
                raise RuntimeError(f"Build did not produce an executable Spring Boot jar: {jar}")
    return {
        "status": "passed",
        "elapsed_seconds": round(time.perf_counter() - start, 2),
        "log": "build.log",
    }


def free_ports(count):
    sockets = []
    try:
        for _ in range(count):
            s = socket.socket()
            s.bind(("127.0.0.1", 0))
            sockets.append(s)
        return [s.getsockname()[1] for s in sockets]
    finally:
        for s in sockets:
            s.close()


@contextmanager
def running_lab(root, logs):
    names = ["data", "orders", "gateway"]
    ports = dict(zip(names, free_ports(3)))
    urls = {k: f"http://127.0.0.1:{v}" for k, v in ports.items()}
    processes = []
    handles = []
    snapshot = tempfile.TemporaryDirectory(prefix="microbind-jars-")
    logs.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "LAB_INTERNAL_KEY": KEY,
        "BIND_ADDRESS": "127.0.0.1",
        "DATA_URL": urls["data"],
        "ORDERS_URL": urls["orders"],
    }
    try:
        # Run immutable snapshots of this build: another build of the same source
        # directory must not rewrite an archive while a JVM is starting from it.
        archives = {}
        for name in names:
            source = root / name / "target" / (name + "-0.1.0.jar")
            if not source.exists():
                raise RuntimeError(f"Build missing: {source}")
            frozen = Path(snapshot.name) / (name + ".jar")
            shutil.copyfile(source, frozen)
            with ZipFile(frozen) as z:
                if z.testzip() is not None:
                    raise RuntimeError(f"Corrupt build archive: {source}")
                if b"Main-Class:" not in z.read("META-INF/MANIFEST.MF"):
                    raise RuntimeError(f"Non-executable archive: {source}")
            archives[name] = {
                "sha256": hashlib.sha256(frozen.read_bytes()).hexdigest(),
                "size_bytes": frozen.stat().st_size,
            }
        dump(logs / "executed-artifacts.json", archives)
        for name in names:
            jar = Path(snapshot.name) / (name + ".jar")
            log = (logs / (name + ".log")).open("w", encoding="utf-8")
            handles.append(log)
            p = subprocess.Popen(
                [
                    "java",
                    "-Xmx192m",
                    "-XX:ActiveProcessorCount=2",
                    "-jar",
                    str(jar),
                    "--server.port=" + str(ports[name]),
                ],
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            processes.append(p)
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if p.poll() is not None:
                    raise RuntimeError(f"{name} exited; see {logs / (name + '.log')}")
                try:
                    if request(urls[name] + "/health")[0] == 200:
                        break
                except (URLError, TimeoutError, ConnectionError):
                    pass
                time.sleep(0.2)
            else:
                raise RuntimeError(f"{name} did not become ready; see {logs}")
        yield urls
    finally:
        for p in reversed(processes):
            if p.poll() is None:
                p.terminate()
        for p in reversed(processes):
            try:
                p.wait(timeout=8)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
        for h in handles:
            h.close()
        snapshot.cleanup()


def verify(
    root: Path, outdir: Path, mode="vulnerable", maven="mvn", settings=None, skip_build=False
):
    root = root.resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    result = {
        "mode": mode,
        "runtime": "real Spring Boot + Feign + MyBatis + H2; localhost HTTP",
        "build": {"status": "skipped"} if skip_build else build(root, outdir, maven, settings),
        "cases": [],
        "boundary_checks": [],
    }
    cases = json.loads((root / "expected.json").read_text(encoding="utf-8"))
    with running_lab(root, outdir) as urls:
        internal = {"X-Internal-Key": KEY}

        def reset():
            status, _ = request(urls["data"] + "/internal/test/reset", "POST", headers=internal)
            if status != 200:
                raise RuntimeError("Lab reset failed")

        def order(oid):
            return request(urls["data"] + f"/internal/test/orders/{oid}", headers=internal)[1]

        def user(uid):
            return request(urls["data"] + f"/internal/test/users/{uid}", headers=internal)[1]

        def perform(case, attack):
            reset()
            route = case["route"]
            target = 102 if attack else 101
            role = "/admin/" in route
            if role:
                target = 2
            path = route.replace("{id}", str(target))
            body = None
            if case["name"] in ("mismatch", "aligned"):
                path = route.replace("{id}", "101")
                body = {"orderId": target}
            if case["name"] == "spoof":
                path += "?userId=" + ("2" if attack else "1")
            if case["name"] == "branch":
                path += "?check=false"
            token = "admin-demo" if role and not attack else "alice-demo"
            status, response = request(
                urls["gateway"] + "/api" + path,
                case["method"],
                body,
                {"Authorization": "Bearer " + token},
            )
            db = user(2) if role else order(target)
            if case["method"] == "POST":
                changed = db.get("role") == "ADMIN" if role else db.get("status") == "CANCELLED"
                effect = changed if attack else changed and 200 <= status < 300
                # Aligned request intentionally chooses the path object, even with a different body.
                if case["name"] == "aligned" and attack:
                    effect = order(102)["status"] == "CANCELLED"
            elif case["name"] in ("tenantAll", "tenantSafe"):
                if attack:
                    effect = isinstance(response, list) and any(
                        x["tenantId"] != 10 for x in response
                    )
                else:
                    # Availability and unauthorized disclosure are separate assertions.
                    effect = (
                        status == 200
                        and isinstance(response, list)
                        and {101, 103} <= {x["id"] for x in response}
                    )
            elif case["name"] == "publicCatalog":
                effect = (
                    False
                    if attack
                    else status == 200 and isinstance(response, list) and bool(response)
                )
            else:
                effect = (
                    isinstance(response, dict)
                    and response.get("id") == target
                    and "address" in response
                )
                if not attack:
                    effect = effect and status == 200
            return {
                "request": {"method": case["method"], "path": path, "actor": token, "body": body},
                "http_status": status,
                "response": response,
                "observed_database_row": db,
                "effect": effect,
            }

        for case in cases:
            attack = perform(case, True)
            legitimate = perform(case, False)
            expected = case["status"] == "suspected" and mode == "vulnerable"
            result["cases"].append(
                {
                    "endpoint": [case["method"], case["route"]],
                    "scenario": case["reason"],
                    "expected_unauthorized_effect": expected,
                    "attack": attack,
                    "legitimate": legitimate,
                    "passed": attack["effect"] == expected and legitimate["effect"],
                }
            )
        checks = [
            ("gateway_rejects_no_token", urls["gateway"] + "/api/safe/101", {}, 401),
            ("orders_rejects_direct_call", urls["orders"] + "/safe/101", {}, 403),
            ("data_rejects_direct_call", urls["data"] + "/internal/orders/101", {}, 403),
            (
                "gateway_discards_forged_identity",
                urls["gateway"] + "/api/safe/102",
                {
                    "Authorization": "Bearer alice-demo",
                    "X-User-Id": "2",
                    "X-Tenant-Id": "20",
                    "X-Role": "ADMIN",
                },
                403,
            ),
        ]
        for name, url, headers, expected in checks:
            status, _ = request(url, headers=headers)
            result["boundary_checks"].append(
                {"name": name, "status": status, "expected": expected, "passed": status == expected}
            )
    result["summary"] = {
        "scenarios": len(result["cases"]),
        "passed_scenarios": sum(x["passed"] for x in result["cases"]),
        "unauthorized_effects_observed": sum(x["attack"]["effect"] for x in result["cases"]),
        "legitimate_requests_passed": sum(x["legitimate"]["effect"] for x in result["cases"]),
        "boundary_checks_passed": sum(x["passed"] for x in result["boundary_checks"]),
    }
    result["passed"] = all(x["passed"] for x in result["cases"] + result["boundary_checks"])
    dump(outdir / "verification.json", result)
    return result
