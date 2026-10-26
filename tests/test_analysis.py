import json
import shutil
from pathlib import Path

import pytest
import yaml

from microbind.engine import Analyzer
from microbind.frontend import Project
from microbind.model import State, Value, constrain, equivalent
from microbind.repair import apply_repairs, build_repairs
from microbind.report import write_reports

ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = "orders/src/main/java/demo/orders/OrderController.java"
MAPPER = "data/src/main/resources/mapper/OrderMapper.xml"


@pytest.fixture
def lab(tmp_path):
    dest = tmp_path / "lab"
    shutil.copytree(ROOT / "demo", dest, ignore=shutil.ignore_patterns("target"))
    return dest


def run(root):
    return Analyzer(Project(root / "project.yml")).run()


def result(report, path):
    return next(x for x in report["results"] if x["endpoint"][1] == path)


def edit(root, file, old, new):
    path = root / file
    text = path.read_text()
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")


def test_all_labeled_scenarios(lab):
    report = run(lab)
    expected = json.loads((lab / "expected.json").read_text())
    assert not report["coverage_gaps"]
    assert len(report["results"]) == len(expected) == 18
    for case in expected:
        assert result(report, case["route"])["status"] == case["status"]


def test_analysis_does_not_read_expected_labels(lab):
    (lab / "expected.json").unlink()
    assert run(lab)["summary"]["suspected"] == 8


def test_different_request_values_remain_different(lab):
    finding = result(run(lab), "/mismatch/{id}")
    assert finding["missing"][0]["kind"] == "object_mismatch"
    hops = [x for x in finding["operation"]["trace"] if x["kind"] == "rpc"]
    assert any("request.orderId" in str(x["bindings"]) for x in hops)
    assert any("recordId" in x["bindings"] for x in hops)


def test_explicit_object_equality_establishes_coverage(lab):
    edit(
        lab,
        CONTROLLER,
        "return data.cancel(request.getOrderId());",
        'if (request.getOrderId() != id) { throw new AccessDeniedException("mismatch"); }\n        return data.cancel(request.getOrderId());',
    )
    assert result(run(lab), "/mismatch/{id}")["status"] == "covered"


def test_disabling_method_security_removes_role_protection(lab):
    edit(
        lab,
        "orders/src/main/java/demo/orders/SecurityConfig.java",
        "@EnableMethodSecurity",
        "// method security is disabled",
    )
    assert result(run(lab), "/admin/safe/{id}")["status"] == "suspected"


def test_sql_or_does_not_guarantee_tenant_constraint(lab):
    edit(
        lab,
        MAPPER,
        "WHERE tenant_id = #{tenantId}",
        "WHERE tenant_id = #{tenantId} OR status = 'OPEN'",
    )
    assert result(run(lab), "/tenant/scoped")["status"] == "suspected"


def test_sql_predicate_must_bind_trusted_subject(lab):
    edit(
        lab,
        CONTROLLER,
        'public Order sqlOwner(@PathVariable("id") long id)',
        'public Order sqlOwner(@PathVariable("id") long id, @RequestParam("actor") long actor)',
    )
    edit(
        lab,
        CONTROLLER,
        "return data.owned(id, AuthContext.userId());",
        "return data.owned(id, actor);",
    )
    assert result(run(lab), "/sql-owner/{id}")["missing"][0]["kind"] == "untrusted_subject"


def test_check_after_write_is_not_retroactive(lab):
    assert result(run(lab), "/late/{id}")["status"] == "suspected"
    edit(
        lab,
        CONTROLLER,
        "int changed = data.cancel(id);\n        auth.requireOwner(id, AuthContext.userId());",
        "auth.requireOwner(id, AuthContext.userId());\n        int changed = data.cancel(id);",
    )
    assert result(run(lab), "/late/{id}")["status"] == "covered"


def test_conditional_guard_cannot_cover_other_branch(lab):
    assert result(run(lab), "/branch/{id}")["status"] == "suspected"


def test_ignored_boolean_is_not_permission(lab):
    assert result(run(lab), "/ignored/{id}")["status"] == "suspected"
    assert result(run(lab), "/enforced/{id}")["status"] == "covered"


def test_returns_before_sensitive_sink(lab):
    edit(
        lab,
        CONTROLLER,
        "if (check) { auth.requireOwner(id, AuthContext.userId()); }",
        "if (!check) { return 0; }\n        auth.requireOwner(id, AuthContext.userId());",
    )
    assert result(run(lab), "/branch/{id}")["status"] == "covered"


def test_unsupported_statement_yields_coverage_gap(lab):
    edit(
        lab,
        CONTROLLER,
        "long selected = id;",
        "for (int i=0;i<1;i++) { id=id+1; }\n        long selected = id;",
    )
    report = run(lab)
    assert result(report, "/alias/{id}")["status"] == "needs_review"
    assert any("Unsupported statement" in x.get("detail", "") for x in report["coverage_gaps"])


def test_dynamic_sql_is_not_certified(lab):
    edit(
        lab,
        MAPPER,
        "WHERE tenant_id = #{tenantId}",
        '<where><if test="tenantId != null">tenant_id = #{tenantId}</if></where>',
    )
    assert result(run(lab), "/tenant/scoped")["status"] == "needs_review"


def test_rpc_method_mismatch_is_not_silently_joined(lab):
    edit(
        lab,
        "data/src/main/java/demo/data/DataController.java",
        '@PostMapping("/orders/{key}/cancel")',
        '@PutMapping("/orders/{key}/cancel")',
    )
    report = run(lab)
    assert any(x["kind"] == "rpc_resolution" for x in report["coverage_gaps"] if "kind" in x)
    assert any("Unresolved Feign" in x.get("detail", "") for x in report["coverage_gaps"])


def test_rpc_maps_query_parameters_by_name_not_order(lab):
    edit(
        lab,
        "data/src/main/java/demo/data/DataController.java",
        'owned(@PathVariable("key") long recordId, @RequestParam("actor") long subject)',
        'owned(@RequestParam("actor") long subject, @PathVariable("key") long recordId)',
    )
    assert result(run(lab), "/sql-owner/{id}")["status"] == "covered"


def test_unknown_policy_is_explicit(lab):
    config = yaml.safe_load((lab / "project.yml").read_text())
    del config["policies"]["products"]
    (lab / "project.yml").write_text(yaml.safe_dump(config))
    assert result(run(lab), "/catalog")["status"] == "needs_review"


def test_trusted_identity_is_configured_by_qualified_method(lab):
    config = yaml.safe_load((lab / "project.yml").read_text())
    del config["trusted_identity"]["demo.orders.AuthContext.userId"]
    (lab / "project.yml").write_text(yaml.safe_dump(config))
    report = run(lab)
    assert result(report, "/safe/{id}")["status"] != "covered"


def test_complete_patch_plan_and_reanalysis(lab, tmp_path):
    p = Project(lab / "project.yml")
    report = Analyzer(p).run()
    plan = build_repairs(p, report, tmp_path / "patches")
    assert len([x for x in plan["patches"] if x["status"] == "candidate"]) == 8
    fixed = tmp_path / "fixed"
    apply_repairs(lab, plan, fixed)
    after = run(fixed)
    assert after["summary"].get("suspected", 0) == 0
    assert after["summary"]["covered"] == 18
    assert run(lab)["summary"]["suspected"] == 8


def test_stale_patch_is_rejected_without_writing(lab, tmp_path):
    p = Project(lab / "project.yml")
    plan = build_repairs(p, Analyzer(p).run(), tmp_path / "patches")
    edit(
        lab,
        CONTROLLER,
        "public class OrderController",
        "// concurrent edit\npublic class OrderController",
    )
    with pytest.raises(ValueError, match="Stale"):
        apply_repairs(lab, plan, tmp_path / "fixed")
    assert not (tmp_path / "fixed").exists()


def test_boolean_disjunction_not_mistaken_for_both_guards():
    a, b, c, d = [("input", x) for x in "abcd"]
    formula = Value(("op", "||", ("op", "==", a, b), ("op", "==", c, d)))
    paths = constrain(State(), formula, True, {})
    assert len(paths) == 2
    assert not all(equivalent(a, b, s.facts) for s in paths)
    assert not all(equivalent(c, d, s.facts) for s in paths)


def test_transitive_equality_and_contradiction():
    a, b, c = [("input", x) for x in "abc"]
    s = State()
    for x, y in [(a, b), (b, c)]:
        s = constrain(s, Value(("op", "==", x, y)), True, {})[0]
    assert equivalent(a, c, s.facts)
    assert not constrain(s, Value(("op", "!=", a, c)), True, {})


def test_exported_evidence_and_html_escape(lab, tmp_path):
    p = Project(lab / "project.yml")
    report = Analyzer(p).run()
    contexts = write_reports(p, report, tmp_path / "reports")
    assert len(contexts) == 18
    assert all(c["snippets"] for c in contexts)
    sarif = json.loads((tmp_path / "reports/report.sarif").read_text())
    assert len(sarif["runs"][0]["results"]) == 8
    for c in contexts:
        for snippet in c["snippets"]:
            assert (lab / snippet["file"]).exists()
            assert snippet["line"] >= 1


def test_rename_entry_does_not_change_detection(lab):
    edit(lab, CONTROLLER, '@GetMapping("/missing/{id}")', '@GetMapping("/renamed/{id}")')
    edit(lab, CONTROLLER, "public Order missing(", "public Order fetchArbitrary(")
    assert result(run(lab), "/renamed/{id}")["status"] == "suspected"
