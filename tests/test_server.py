import io
import json
import stat
import zipfile
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from fastapi.testclient import TestClient

from microbind.server.app import create_app
from microbind.server.config import Settings
from microbind.server.sources import unpack
from microbind.server.store import Store
from microbind.server.worker import process_one

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "test-only-access-token-32-characters"


@pytest.fixture
def client(tmp_path):
    app = create_app(Settings(tmp_path / "data", ROOT / "demo", TOKEN))
    return TestClient(app, headers={"Authorization": "Bearer " + TOKEN})


def archive(files):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return out.getvalue()


def test_api_auth_and_execution_boundary(client):
    assert client.get("/api/health", headers={"Authorization": ""}).status_code == 200
    assert client.get("/api/health").json()["auth_required"] is True
    assert client.get("/api/projects", headers={"Authorization": ""}).status_code == 401
    assert client.get("/api/jobs", headers={"Authorization": "Bearer invalid"}).status_code == 401
    assert client.get("/api/projects").json()[0]["id"] == "demo"
    assert "path" not in client.get("/api/projects").json()[0]
    assert (
        client.post("/api/jobs", json={"project_id": "demo", "kind": "verify"}).status_code == 400
    )
    assert client.get("/api/jobs/unknown/result").status_code == 404


@pytest.mark.parametrize("value", [None, "1", "", "false"])
def test_authentication_requires_explicit_opt_out(monkeypatch, value):
    monkeypatch.delenv("MICROBIND_TOKEN_FILE", raising=False)
    monkeypatch.delenv("MICROBIND_TOKEN", raising=False)
    if value is None:
        monkeypatch.delenv("MICROBIND_AUTH_REQUIRED", raising=False)
    else:
        monkeypatch.setenv("MICROBIND_AUTH_REQUIRED", value)
    with pytest.raises(ValueError, match="MICROBIND_TOKEN"):
        Settings.env()


def test_anonymous_api_keeps_execution_boundary(monkeypatch, tmp_path):
    monkeypatch.setenv("MICROBIND_AUTH_REQUIRED", "0")
    monkeypatch.setenv("MICROBIND_TOKEN_FILE", str(tmp_path / "absent-token"))
    monkeypatch.setenv("MICROBIND_DATA", str(tmp_path / "data"))
    monkeypatch.setenv("MICROBIND_DEMO", str(ROOT / "demo"))
    monkeypatch.setenv("MICROBIND_VERIFY_ENABLED", "0")
    with TestClient(create_app()) as anonymous:
        assert anonymous.get("/api/health").json()["auth_required"] is False
        assert anonymous.get("/api/projects").status_code == 200
        assert anonymous.get("/api/capabilities").status_code == 200
        assert (
            anonymous.post("/api/jobs", json={"project_id": "demo", "kind": "verify"}).status_code
            == 400
        )
        response = anonymous.post("/api/jobs", json={"project_id": "demo"})
        assert response.status_code == 202
        id = response.json()["id"]
        assert process_one(anonymous.app.state.store, timeout=60)
        assert anonymous.get("/api/jobs/" + id).json()["status"] == "succeeded"
        assert anonymous.get("/api/jobs/" + id + "/download").status_code == 200


def test_api_queue_worker_repair_download(client):
    response = client.post("/api/jobs", json={"project_id": "demo", "repair": True})
    assert response.status_code == 202
    id = response.json()["id"]
    assert client.get("/api/jobs/" + id + "/result").status_code == 409
    assert process_one(client.app.state.store, timeout=60)
    assert client.get("/api/jobs/" + id).json()["status"] == "succeeded"
    result = client.get("/api/jobs/" + id + "/result").json()
    assert result["before"]["summary"]["suspected"] == 8
    assert result["after"]["summary"].get("suspected", 0) == 0
    assert result["repair"]["applied"]["patch_count"] == 8
    assert result["verification"] is None
    assert result["smart"]["status"] == "disabled"
    bundle = client.get("/api/jobs/" + id + "/download")
    with zipfile.ZipFile(io.BytesIO(bundle.content)) as z:
        assert "result.json" in z.namelist()
        assert "fixed-project/project.yml" in z.namelist()
    assert client.delete("/api/jobs/" + id).status_code == 200
    assert not (client.app.state.settings.data / "jobs" / id).exists()


@pytest.mark.parametrize("thinking", [None, True, False])
def test_job_thinking_choice_reaches_model(client, monkeypatch, thinking):
    received = []
    expected = thinking is not False

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            received.append(body)
            assert body["thinking"] == {"type": "enabled" if expected else "disabled"}
            if len(received) == 1:
                finding = json.loads(body["messages"][1]["content"])["finding_id"]
                message = {
                    "role": "assistant",
                    "content": None,
                    "reasoning_content": "stub-thinking-state",
                    "tool_calls": [
                        {
                            "id": "policy",
                            "type": "function",
                            "function": {
                                "name": "get_policy",
                                "arguments": json.dumps({"finding_id": finding}),
                            },
                        }
                    ],
                }
            else:
                if expected:
                    assert body["messages"][2]["reasoning_content"] == "stub-thinking-state"
                message = {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "verdict": "needs_review",
                            "explanation": "queue protocol test only",
                            "required_conditions": [],
                            "evidence_ids": [],
                            "suggested_test": "check policy",
                        }
                    ),
                }
            raw = json.dumps({"choices": [{"message": message}]}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("MICROBIND_LLM_ENABLED", "1")
    monkeypatch.setenv("MICROBIND_LLM_MODEL", "deepseek-flash")
    monkeypatch.setenv("MICROBIND_LLM_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1")
    monkeypatch.setenv("MICROBIND_SMART_MAX_FINDINGS", "1")
    try:
        payload = {"project_id": "demo", "smart": True, "repair": False}
        if thinking is not None:
            payload["thinking"] = thinking
        response = client.post("/api/jobs", json=payload)
        assert response.status_code == 202
        assert response.json()["options"]["thinking"] is expected
        assert client.get("/api/capabilities").json()["thinking_supported"]
        id = response.json()["id"]
        assert process_one(client.app.state.store, timeout=60)
        result = client.get("/api/jobs/" + id + "/result").json()
        assert result["smart"]["results"][0]["status"] == "completed"
        assert result["smart"]["results"][0]["thinking_enabled"] is expected
        assert len(received) == 2
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_upload_and_reject_escape(client, tmp_path):
    bad = archive({"../outside.java": "class A {}", "project.yml": "services: []"})
    assert client.post("/api/projects", files={"file": ("bad.zip", bad)}).status_code == 400
    bad = archive({"project.yml": "services: [{name: bad, path: /etc}]"})
    assert client.post("/api/projects", files={"file": ("bad.zip", bad)}).status_code == 400
    valid = archive(
        {
            "repo/project.yml": "services: [{name: sample, path: src, exposed: true}]",
            "repo/src/A.java": "class A {}",
            "repo/.env": "SECRET=no-export",
        }
    )
    response = client.post("/api/projects", files={"file": ("sample.zip", valid)})
    assert response.status_code == 201
    id = response.json()["id"]
    source = Path(client.app.state.store.project(id)["path"])
    assert not (source / ".env").exists()
    client.app.state.settings.verify_enabled = True
    assert client.post("/api/jobs", json={"project_id": id, "kind": "verify"}).status_code == 400


def test_zip_symlink_is_rejected(tmp_path):
    p = tmp_path / "bad.zip"
    with zipfile.ZipFile(p, "w") as z:
        i = zipfile.ZipInfo("source.java")
        i.create_system = 3
        i.external_attr = (stat.S_IFLNK | 0o777) << 16
        z.writestr(i, "/etc/passwd")
    with pytest.raises(ValueError):
        unpack(p, tmp_path / "project")


def test_claim_atomic_cancel_and_recover(tmp_path):
    s = Store(tmp_path)
    id = s.enqueue("demo", "scan", {})
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: s.claim("scan"), range(2)))
    assert sum(r is not None for r in results) == 1
    with s.db() as db:
        db.execute("UPDATE jobs SET updated=0 WHERE id=?", (id,))
    assert s.claim("scan") is None
    assert s.job(id)["status"] == "failed"
    id2 = s.enqueue("demo", "scan", {})
    assert s.cancel_queued(id2) == 1
    assert s.claim("scan") is None
