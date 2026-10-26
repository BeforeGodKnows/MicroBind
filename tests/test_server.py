import io
import stat
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

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
    assert client.get("/api/projects", headers={"Authorization": ""}).status_code == 401
    assert client.get("/api/projects").json()[0]["id"] == "demo"
    assert "path" not in client.get("/api/projects").json()[0]
    assert (
        client.post("/api/jobs", json={"project_id": "demo", "kind": "verify"}).status_code == 400
    )
    assert client.get("/api/jobs/unknown/result").status_code == 404


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
