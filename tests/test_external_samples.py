"""Regressions grounded in the shipped upstream sources, with separate scope claims."""

import json
from pathlib import Path

import pytest

from microbind.engine import Analyzer
from microbind.frontend import Project
from microbind.report import write_reports
from microbind.workflows.registry import Context, make_plan, run_skill

ROOT = Path(__file__).resolve().parents[1]


def test_original_neo_request_mapping_and_feign():
    p = Project(ROOT / "samples/neo-http/project.yml")
    assert len(p.edges) == 5
    edge = next(e for e in p.edges if e["route"] == "/accounts/{accountName}")
    assert edge["verb"] == "GET"
    assert edge["parameter_mapping"] == [
        {"sender": "accountName", "receiver": "accountName", "channel": "path"}
    ]
    r = Analyzer(p).run()
    assert r["assessment"]["status"] == "no_operation_evidence"


def test_original_litemall_read_through_map_and_dynamic_gap(tmp_path):
    p = Project(ROOT / "samples/litemall/project.yml")
    r = Analyzer(p).run()
    rows = r["results"]
    assert [x["status"] for x in rows if x["endpoint"] == ["GET", "/wx/brand/detail"]] == [
        "covered"
    ]
    assert all(x["status"] == "needs_review" for x in rows if "/address/" in x["endpoint"][1])
    assert r["summary"]["entries"] == 6 and r["summary"]["operations"] == 8
    assert r["assessment"]["entries_with_gaps"] == 5
    write_reports(p, r, tmp_path)  # Includes SQL with unknown table, formerly crashed.
    assert (tmp_path / "report.html").is_file()
    assert "覆盖缺口" in (tmp_path / "report.md").read_text()


def test_unsupported_cross_language_is_not_clean():
    r = Analyzer(Project(ROOT / "samples/neo-role/project.yml")).run()
    assert any(g.get("kind") == "unsupported_language" for g in r["coverage_gaps"])
    assert any("postForObject" in g.get("detail", "") for g in r["coverage_gaps"])
    assert r["assessment"]["status"] == "no_operation_evidence"


def test_static_sql_include_does_not_certify_dynamic_sql():
    p = Project(ROOT / "samples/litemall/project.yml")
    methods = {m.name: m for m in p.methods.values() if m.cls.endswith("LitemallBrandMapper")}
    assert methods["selectByPrimaryKey"].sql["supported"]
    assert "floor_price" in methods["selectByPrimaryKey"].sql["raw"]
    assert not methods["selectByExample"].sql["supported"]


def test_skill_prerequisite_and_model_free_plan(tmp_path):
    plan = make_plan(smart=False, repair=False)
    assert plan == ["source.analyze", "report.export"]
    c = Context(ROOT / "demo", tmp_path, {"id": "demo", "builtin": True}, lambda _: None)
    with pytest.raises(ValueError, match="prerequisites"):
        run_skill("repair.propose", c)
    assert c.events == []


def test_disabled_model_blocks_request_even_with_config(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from microbind.server.app import create_app
    from microbind.server.config import Settings
    from microbind.smart import review_one

    monkeypatch.setenv("MICROBIND_LLM_ENABLED", "0")
    monkeypatch.setenv("MICROBIND_LLM_BASE_URL", "http://127.0.0.1:1/v1")
    monkeypatch.setenv("MICROBIND_LLM_MODEL", "unused")
    token = "test-disabled-model-token-32-characters"
    client = TestClient(
        create_app(Settings(tmp_path / "data", ROOT / "demo", token)),
        headers={"Authorization": "Bearer " + token},
    )
    assert not client.get("/api/capabilities").json()["smart_configured"]
    assert client.post("/api/jobs", json={"project_id": "demo", "smart": True}).status_code == 400
    with pytest.raises(ValueError, match="模型功能已关闭"):
        review_one(None, None, tmp_path)  # Switch is checked before tools, cache or HTTP.


def test_source_hashes():
    import hashlib

    for p in (ROOT / "samples").glob("*/provenance.json"):
        for f in json.loads(p.read_text())["files"]:
            assert hashlib.sha256((p.parent / f["path"]).read_bytes()).hexdigest() == f["sha256"]


def test_project_config_reports_wrong_field_and_unknown_identity(tmp_path):
    from microbind.project_config import diagnose

    (tmp_path / "src").mkdir()
    p = tmp_path / "project.yml"
    p.write_text('services: [{name: example, path: src, exposed: "true"}]')
    with pytest.raises(ValueError, match="exposed"):
        diagnose(p)
    p.write_text(
        "services: [{name: example, path: src, exposed: true}]\ntrusted_identity: {missing.Auth.userId: user}"
    )
    result = diagnose(p)
    assert result["valid"] and any("missing.Auth.userId" in w for w in result["warnings"])
